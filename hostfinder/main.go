package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"time"

	"env-checker/cli"
	"env-checker/hostfinder/runner"
	"env-checker/util"
)

// Config captures CLI arguments for host discovery.
type Config struct {
	Input        string
	Output       string
	CIDR         bool
	Resolvers    string
	Concurrency  int
	Timeout      time.Duration
	MinOpenPorts int
	PortList     []int
	IncludeIPs   bool
	IncludeHosts bool
	RunEnv       bool
	EnvOutputDir string
	SaveUnknown  bool
	JSONOutput   bool
	Threads      int
	Goroutines   int
	PathsLimit   int
}

func parseFlags() *Config {
	var ports string
	cfg := &Config{}

	flag.StringVar(&cfg.Input, "input", "", "Input file of seed hosts or CIDR ranges")
	flag.StringVar(&cfg.Input, "i", "", "Alias for --input")
	flag.StringVar(&cfg.Output, "output", "discovered-hosts.txt", "Output file to write discovered hosts")
	flag.StringVar(&cfg.Output, "o", "discovered-hosts.txt", "Alias for --output")
	flag.BoolVar(&cfg.CIDR, "cidr", false, "Treat inputs as CIDR ranges to expand")
	flag.BoolVar(&cfg.IncludeIPs, "include-ips", true, "Include raw IP addresses when discovered")
	flag.BoolVar(&cfg.IncludeHosts, "include-hosts", true, "Include discovered hostnames from PTR lookups")
	flag.StringVar(&cfg.Resolvers, "resolvers", "", "Optional file containing DNS resolvers")
	flag.IntVar(&cfg.Concurrency, "concurrency", 256, "Concurrent resolution workers")
	flag.DurationVar(&cfg.Timeout, "timeout", 2*time.Second, "Per lookup timeout")
	flag.StringVar(&ports, "ports", "80,443,8080,8443", "Comma-separated ports to probe for liveness")
	flag.IntVar(&cfg.MinOpenPorts, "min-open", 1, "Minimum number of open ports to keep a host")
	flag.BoolVar(&cfg.RunEnv, "run-env-checker", false, "Run env-checker after discovery completes")
	flag.StringVar(&cfg.EnvOutputDir, "env-output-dir", "", "Output directory override for env-checker run")
	flag.BoolVar(&cfg.SaveUnknown, "save-unknown", false, "Forward --save-unknown to env-checker")
	flag.BoolVar(&cfg.JSONOutput, "json", false, "Forward --json to env-checker")
	flag.IntVar(&cfg.Threads, "threads", 0, "Override env-checker threads")
	flag.IntVar(&cfg.Goroutines, "goroutines", 0, "Override env-checker goroutines")
	flag.IntVar(&cfg.PathsLimit, "paths-limit", 0, "Limit number of paths during env-checker run")

	flag.Parse()

	if cfg.Input == "" {
		log.Fatal("--input is required")
	}

	for _, p := range strings.Split(ports, ",") {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		port, err := util.ParsePort(p)
		if err != nil {
			log.Fatalf("invalid port %q: %v", p, err)
		}
		cfg.PortList = append(cfg.PortList, port)
	}

	if cfg.Concurrency <= 0 {
		cfg.Concurrency = 64
	}
	return cfg
}

func main() {
	cfg := parseFlags()

	inputs, err := util.ReadLines(cfg.Input)
	if err != nil {
		log.Fatalf("load input: %v", err)
	}

	seeds := make([]string, 0, len(inputs))
	if cfg.CIDR {
		for _, entry := range inputs {
			expanded, err := util.ExpandCIDR(entry, cfg.IncludeIPs)
			if err != nil {
				log.Printf("warn: expand CIDR %q: %v", entry, err)
				continue
			}
			seeds = append(seeds, expanded...)
		}
	} else {
		seeds = inputs
	}

	resolvers, err := loadResolvers(cfg)
	if err != nil {
		log.Fatalf("load resolvers: %v", err)
	}

	log.Printf("starting hostfinder with %d seeds", len(seeds))

	results := discoverHosts(cfg, seeds, resolvers)
	if len(results) == 0 {
		log.Printf("no hosts discovered")
		return
	}

	if err := util.AtomicWriteLines(cfg.Output, results); err != nil {
		log.Fatalf("write output: %v", err)
	}

	log.Printf("wrote %d unique hosts to %s", len(results), cfg.Output)

	if cfg.RunEnv {
		if err := runEnvChecker(cfg, results); err != nil {
			log.Fatalf("env-checker failed: %v", err)
		}
	}
}

func runEnvChecker(cfg *Config, hosts []string) error {
	log.Printf("launching env-checker against %d hosts", len(hosts))
	tempDir := filepath.Join(os.TempDir(), fmt.Sprintf("hostfinder-%d", time.Now().UnixNano()))
	if err := os.MkdirAll(tempDir, 0o755); err != nil {
		return fmt.Errorf("create temp dir: %w", err)
	}
	tempFile := filepath.Join(tempDir, "hosts.txt")
	if err := util.AtomicWriteLines(tempFile, hosts); err != nil {
		return fmt.Errorf("write hosts: %w", err)
	}

	base := cli.DefaultConfig()
	base.InputFile = tempFile
	if cfg.EnvOutputDir != "" {
		base.OutputDir = cfg.EnvOutputDir
	}
	if cfg.Threads > 0 {
		base.Threads = cfg.Threads
	}
	if cfg.Goroutines > 0 {
		base.Goroutines = cfg.Goroutines
	}
	base.SaveUnknown = cfg.SaveUnknown
	base.JSONOutput = cfg.JSONOutput
	base.PathsLimit = cfg.PathsLimit
	base.InitializeCluster()

	// Resolve an absolute OutputDir so the runner doesn't need to guess CWD.
	outputDir := base.OutputDir
	if outputDir != "" && !filepath.IsAbs(outputDir) {
		if abs, err := filepath.Abs(outputDir); err == nil {
			outputDir = abs
		}
	}

	runCfg := runner.Config{
		HostsFile:   tempFile,
		SaveUnknown: base.SaveUnknown,
		JSONOutput:  base.JSONOutput,
		Threads:     base.Threads,
		Goroutines:  base.Goroutines,
		OutputDir:   outputDir,
		PathsLimit:  base.PathsLimit,
	}

	// Prefer a pre-built binary placed next to this executable.
	if exe, err := os.Executable(); err == nil {
		dir := filepath.Dir(exe)
		binary := "env-checker"
		if runtime.GOOS == "windows" {
			binary = "env-checker.exe"
		}
		candidate := filepath.Join(dir, binary)
		if _, err := os.Stat(candidate); err == nil {
			runCfg.EnvCheckerPath = candidate
			runCfg.UseGoRun = false
			log.Printf("using env-checker binary: %s", candidate)
		}
	}

	// Fall back to go run with the source root one level above this module.
	if runCfg.EnvCheckerPath == "" {
		runCfg.UseGoRun = true
	}

	return runner.Run(runCfg)
}

func loadResolvers(cfg *Config) ([]string, error) {
	if cfg.Resolvers == "" {
		return []string{"1.1.1.1:53", "8.8.8.8:53", "9.9.9.9:53", "208.67.222.222:53"}, nil
	}
	resolvers, err := util.ReadLines(cfg.Resolvers)
	if err != nil {
		return nil, err
	}
	filtered := make([]string, 0, len(resolvers))
	for _, r := range resolvers {
		r = strings.TrimSpace(r)
		if r == "" {
			continue
		}
		if !strings.Contains(r, ":") {
			r += ":53"
		}
		filtered = append(filtered, r)
	}
	if len(filtered) == 0 {
		return nil, fmt.Errorf("no resolvers provided")
	}
	return filtered, nil
}

type hostResult struct {
	Target string
	Score  int
	PTR    string
}

func discoverHosts(cfg *Config, seeds, resolvers []string) []string {
	type job struct {
		host string
	}

	jobs := make(chan job, cfg.Concurrency*2)
	results := make(chan hostResult, cfg.Concurrency*2)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	var wg sync.WaitGroup

	client := &net.Dialer{Timeout: cfg.Timeout}

	worker := func() {
		defer wg.Done()
		resolverIdx := 0
		for {
			select {
			case <-ctx.Done():
				return
			case j, ok := <-jobs:
				if !ok {
					return
				}
				alive := 0
				for _, port := range cfg.PortList {
					addr := fmt.Sprintf("%s:%d", j.host, port)
					conn, err := client.DialContext(ctx, "tcp", addr)
					if err == nil {
						alive++
						conn.Close()
					}
				}
				if alive >= cfg.MinOpenPorts {
					var ptr string
					if cfg.IncludeHosts {
						resolver := resolvers[resolverIdx%len(resolvers)]
						resolverIdx++
						ptr = reverseLookup(ctx, resolver, j.host)
					}
					results <- hostResult{Target: j.host, Score: alive, PTR: ptr}
				}
			}
		}
	}

	wg.Add(cfg.Concurrency)
	for i := 0; i < cfg.Concurrency; i++ {
		go worker()
	}

	go func() {
		for _, seed := range seeds {
			seed = strings.TrimSpace(seed)
			if seed == "" {
				continue
			}
			jobs <- job{host: seed}
		}
		close(jobs)
	}()

	go func() {
		wg.Wait()
		close(results)
	}()

	collector := make(map[string]hostResult, len(seeds))
	for res := range results {
		if !cfg.IncludeIPs {
			if net.ParseIP(res.Target) != nil {
				continue
			}
		}
		collector[res.Target] = res
		if cfg.IncludeHosts && res.PTR != "" {
			collector[res.PTR] = hostResult{Target: res.PTR, Score: res.Score}
		}
	}

	unique := make([]string, 0, len(collector))
	for host := range collector {
		unique = append(unique, host)
	}
	sort.Strings(unique)
	return unique
}

func reverseLookup(ctx context.Context, resolver string, host string) string {
	ctx, cancel := context.WithTimeout(ctx, 1500*time.Millisecond)
	defer cancel()

	dialer := &net.Dialer{}
	var r net.Resolver
	r.Dial = func(ctx context.Context, network, address string) (net.Conn, error) {
		return dialer.DialContext(ctx, "udp", resolver)
	}

	ptr, err := r.LookupAddr(ctx, host)
	if err != nil || len(ptr) == 0 {
		return ""
	}
	return strings.TrimSuffix(ptr[0], ".")
}
