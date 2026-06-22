package webui

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "embed"

	"env-checker/cli"
	"env-checker/credcheck"
	"env-checker/daemon"
	"env-checker/dork"
	"env-checker/output"
	"env-checker/scanner"
	"env-checker/util"
	"env-checker/vulnscan"
)

//go:embed static/index.html
var indexHTML []byte

// Serve starts the web UI server on addr (host:port).
func Serve(addr string) error {
	s := newServer(addr)
	log.Printf("[web] env-checker UI → http://%s", addr)
	return http.ListenAndServe(addr, s.mux)
}

// ────────────────────────────────────────────────────────────────────────────

type server struct {
	addr string
	mux  *http.ServeMux

	// scan state
	mu         sync.RWMutex
	state      string // "idle" | "running" | "done" | "error"
	scanCancel context.CancelFunc
	lastStats  scanner.Event
	errMsg     string

	// accumulated results (for /api/results)
	resMu   sync.Mutex
	results []output.Record

	// SSE subscribers (scan events)
	subsMu sync.RWMutex
	subs   map[chan []byte]struct{}

	// daemon state
	daemonMu     sync.Mutex
	daemonState  string // "idle" | "running"
	daemonCancel context.CancelFunc
	daemonLogMu  sync.Mutex
	daemonLogs   []string // ring of recent log lines

	// daemon SSE subscribers
	dSubsMu sync.RWMutex
	dSubs   map[chan []byte]struct{}
}

func newServer(addr string) *server {
	s := &server{
		addr:        addr,
		state:       "idle",
		subs:        make(map[chan []byte]struct{}),
		daemonState: "idle",
		dSubs:       make(map[chan []byte]struct{}),
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/", s.handleIndex)
	mux.HandleFunc("/api/start", s.handleStart)
	mux.HandleFunc("/api/stop", s.handleStop)
	mux.HandleFunc("/api/events", s.handleEvents)
	mux.HandleFunc("/api/status", s.handleStatus)
	mux.HandleFunc("/api/results", s.handleResults)
	mux.HandleFunc("/api/check-creds", s.handleCheckCreds)
	// daemon endpoints
	mux.HandleFunc("/api/daemon/start", s.handleDaemonStart)
	mux.HandleFunc("/api/daemon/stop", s.handleDaemonStop)
	mux.HandleFunc("/api/daemon/status", s.handleDaemonStatus)
	mux.HandleFunc("/api/daemon/logs", s.handleDaemonLogs)
	mux.HandleFunc("/api/daemon/config", s.handleDaemonConfig)
	// target discovery
	mux.HandleFunc("/api/discover", s.handleDiscover)
	// dork management
	mux.HandleFunc("/api/dork/update", s.handleDorkUpdate)
	mux.HandleFunc("/api/dork/list", s.handleDorkList)
	// vulnerability scan
	mux.HandleFunc("/api/vulnscan", s.handleVulnScan)
	s.mux = mux
	return s
}

// ── static ──────────────────────────────────────────────────────────────────

func (s *server) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write(indexHTML)
}

// ── scan control ─────────────────────────────────────────────────────────────

// startRequest mirrors the JSON body sent by the UI.
type startRequest struct {
	Hosts       string `json:"hosts"`
	OutputDir   string `json:"outputDir"`
	Threads     int    `json:"threads"`
	Goroutines  int    `json:"goroutines"`
	Timeout     int    `json:"timeout"`
	DNSTimeout  int    `json:"dnsTimeout"`
	SaveUnknown bool   `json:"saveUnknown"`
	CIDRMode    bool   `json:"cidrMode"`
	PathsLimit  int    `json:"pathsLimit"`
}

func (s *server) handleStart(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}

	s.mu.RLock()
	running := s.state == "running"
	s.mu.RUnlock()
	if running {
		http.Error(w, "scan already running", http.StatusConflict)
		return
	}

	var req startRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid JSON: "+err.Error(), http.StatusBadRequest)
		return
	}

	// Validate hosts
	hosts := strings.TrimSpace(req.Hosts)
	if hosts == "" {
		http.Error(w, "hosts list is empty", http.StatusBadRequest)
		return
	}

	// Apply defaults
	if req.Threads <= 0 {
		req.Threads = runtime.NumCPU()
	}
	if req.Goroutines <= 0 {
		req.Goroutines = 900
	}
	if req.Timeout <= 0 {
		req.Timeout = 30
	}
	if req.DNSTimeout <= 0 {
		req.DNSTimeout = 2
	}
	if req.OutputDir == "" {
		req.OutputDir = "envs"
	}

	// Write hosts to temp file
	tmpDir, err := os.MkdirTemp("", "env-checker-web-*")
	if err != nil {
		http.Error(w, "create temp dir: "+err.Error(), http.StatusInternalServerError)
		return
	}
	hostsFile := filepath.Join(tmpDir, "hosts.txt")
	lines := strings.Split(strings.ReplaceAll(hosts, "\r\n", "\n"), "\n")
	filtered := make([]string, 0, len(lines))
	for _, l := range lines {
		l = strings.TrimSpace(l)
		if l != "" && !strings.HasPrefix(l, "#") {
			filtered = append(filtered, l)
		}
	}
	if err := util.AtomicWriteLines(hostsFile, filtered); err != nil {
		http.Error(w, "write hosts: "+err.Error(), http.StatusInternalServerError)
		return
	}

	cfg := &cli.Config{
		InputFile:      hostsFile,
		OutputDir:      req.OutputDir,
		Threads:        req.Threads,
		Goroutines:     req.Goroutines,
		Timeout:        req.Timeout,
		DNSTimeout:     req.DNSTimeout,
		DNSConcurrency: 50,
		SaveUnknown:    req.SaveUnknown,
		CIDRInput:      req.CIDRMode,
		PathsLimit:     req.PathsLimit,
		IPv6:           true,
	}
	cfg.InitializeCluster()

	runtime.GOMAXPROCS(req.Threads)

	engine, err := scanner.NewEngine(cfg)
	if err != nil {
		http.Error(w, "engine init: "+err.Error(), http.StatusInternalServerError)
		return
	}

	// Reset state
	s.mu.Lock()
	s.state = "running"
	s.errMsg = ""
	s.mu.Unlock()

	s.resMu.Lock()
	s.results = s.results[:0]
	s.resMu.Unlock()

	s.mu.Lock()
	s.lastStats = scanner.Event{}
	s.mu.Unlock()

	// Event channel
	eventCh := make(chan scanner.Event, 512)
	engine.SetEvents(eventCh)

	ctx, cancel := context.WithCancel(context.Background())
	s.mu.Lock()
	s.scanCancel = cancel
	s.mu.Unlock()

	// Fan out events → SSE subscribers + local cache + results
	go s.processEvents(eventCh)

	// Run engine
	go func() {
		defer os.RemoveAll(tmpDir)
		defer cancel()
		runErr := engine.Run(ctx)
		close(eventCh) // unblock processEvents goroutine

		s.mu.Lock()
		switch {
		case runErr != nil && runErr != context.Canceled:
			s.state = "error"
			s.errMsg = runErr.Error()
		case s.state == "running":
			s.state = "done"
		default:
			// was "stopping" → scan was cancelled by user
			s.state = "idle"
		}
		finalState := s.state
		s.mu.Unlock()

		if runErr != nil && runErr != context.Canceled {
			s.broadcastRaw(fmt.Sprintf(`{"type":"error","message":%s}`, jsonStr(runErr.Error())))
		} else if finalState == "idle" {
			s.broadcastRaw(`{"type":"stopped"}`)
		}
	}()

	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{"ok":true}`)
}

func (s *server) handleStop(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	s.mu.Lock()
	cancel := s.scanCancel
	if s.state == "running" {
		s.state = "stopping"
	}
	s.mu.Unlock()

	if cancel != nil {
		cancel()
	}
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{"ok":true}`)
}

// ── SSE ──────────────────────────────────────────────────────────────────────

func (s *server) handleEvents(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "SSE not supported", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Send current state immediately
	s.mu.RLock()
	state := s.state
	stats := s.lastStats
	errMsg := s.errMsg
	s.mu.RUnlock()

	if state != "idle" {
		ev := stats
		ev.Type = scanner.EventProgress
		if state == "done" {
			ev.Type = scanner.EventDone
		} else if state == "error" {
			fmt.Fprintf(w, "data: {\"type\":\"error\",\"message\":%s}\n\n", jsonStr(errMsg))
			flusher.Flush()
		}
		if b, err := json.Marshal(ev); err == nil {
			fmt.Fprintf(w, "data: %s\n\n", b)
			flusher.Flush()
		}
	}

	// Subscribe
	ch := make(chan []byte, 64)
	s.subsMu.Lock()
	s.subs[ch] = struct{}{}
	s.subsMu.Unlock()
	defer func() {
		s.subsMu.Lock()
		delete(s.subs, ch)
		s.subsMu.Unlock()
	}()

	// Heartbeat ticker to keep connection alive
	ticker := time.NewTicker(25 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-r.Context().Done():
			return
		case <-ticker.C:
			fmt.Fprint(w, ": heartbeat\n\n")
			flusher.Flush()
		case msg, ok := <-ch:
			if !ok {
				return
			}
			fmt.Fprintf(w, "data: %s\n\n", msg)
			flusher.Flush()
		}
	}
}

func (s *server) broadcastRaw(msg string) {
	b := []byte(msg)
	s.subsMu.RLock()
	defer s.subsMu.RUnlock()
	for ch := range s.subs {
		select {
		case ch <- b:
		default:
		}
	}
}

func (s *server) broadcast(ev scanner.Event) {
	b, err := json.Marshal(ev)
	if err != nil {
		return
	}
	s.subsMu.RLock()
	defer s.subsMu.RUnlock()
	for ch := range s.subs {
		select {
		case ch <- b:
		default:
		}
	}
}

func (s *server) processEvents(ch <-chan scanner.Event) {
	for ev := range ch {
		switch ev.Type {
		case scanner.EventProgress, scanner.EventDone:
			// Cache latest stats for late-joining SSE clients; state transitions
			// are owned exclusively by the engine goroutine to avoid races.
			s.mu.Lock()
			s.lastStats = ev
			s.mu.Unlock()
			s.broadcast(ev)

		case scanner.EventFound:
			if ev.Record != nil {
				s.resMu.Lock()
				s.results = append(s.results, *ev.Record)
				s.resMu.Unlock()
				s.broadcast(ev)
			}
		}
	}
}

// ── status / results ─────────────────────────────────────────────────────────

func (s *server) handleStatus(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	state := s.state
	stats := s.lastStats
	errMsg := s.errMsg
	s.mu.RUnlock()

	s.resMu.Lock()
	count := len(s.results)
	s.resMu.Unlock()

	type statusResp struct {
		State   string       `json:"state"`
		Stats   scanner.Event `json:"stats"`
		Count   int          `json:"resultCount"`
		ErrMsg  string       `json:"error,omitempty"`
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(statusResp{State: state, Stats: stats, Count: count, ErrMsg: errMsg})
}

func (s *server) handleResults(w http.ResponseWriter, r *http.Request) {
	// optional ?offset=N for pagination
	offset := 0
	if v := r.URL.Query().Get("offset"); v != "" {
		offset, _ = strconv.Atoi(v)
	}
	s.resMu.Lock()
	slice := make([]output.Record, 0)
	if offset < len(s.results) {
		slice = s.results[offset:]
	}
	s.resMu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(slice)
}

// ── vulnerability scan ────────────────────────────────────────────────────────

// handleVulnScan streams vuln findings for a single host via SSE.
// GET /api/vulnscan?host=example.com
func (s *server) handleVulnScan(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "SSE not supported", http.StatusInternalServerError)
		return
	}
	host := strings.TrimSpace(r.URL.Query().Get("host"))
	if host == "" {
		http.Error(w, "host param required", http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	send := func(evType string, data interface{}) {
		b, _ := json.Marshal(map[string]interface{}{"type": evType, "data": data})
		fmt.Fprintf(w, "data: %s\n\n", b)
		flusher.Flush()
	}

	send("status", fmt.Sprintf("Scanning %s for vulnerabilities…", host))

	count := 0
	findings := vulnscan.Scan(host)
	for _, f := range findings {
		send("finding", f)
		count++
	}
	send("done", fmt.Sprintf("Scan complete — %d finding(s)", count))
}

// ── dork management ──────────────────────────────────────────────────────────

func (s *server) handleDorkUpdate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	customFile := r.URL.Query().Get("file")
	if customFile == "" {
		customFile = "dorks.txt"
	}

	// Run in background, stream results via JSON
	w.Header().Set("Content-Type", "application/json")
	flusher, canFlush := w.(http.Flusher)

	go func() {
		results := dork.AutoUpdate(customFile)
		total := 0
		for _, res := range results {
			total += res.Added
		}
		b, _ := json.Marshal(map[string]interface{}{
			"ok":      true,
			"results": results,
			"total":   total,
		})
		w.Write(b)
		if canFlush {
			flusher.Flush()
		}
	}()

	// Send immediate acknowledgement
	fmt.Fprint(w, `{"ok":true,"status":"running"}`)
}

func (s *server) handleDorkList(w http.ResponseWriter, r *http.Request) {
	customFile := r.URL.Query().Get("file")
	if customFile == "" {
		customFile = "dorks.txt"
	}
	lines, _ := dork.LoadFile(customFile)
	builtin := dork.BuiltinDorks(nil)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"custom":  lines,
		"builtin": builtin,
		"total":   len(lines) + len(builtin),
	})
}

// ── target discovery ─────────────────────────────────────────────────────────

// handleDiscover streams discovered live hosts for a domain via SSE.
// GET /api/discover?domain=example.com
func (s *server) handleDiscover(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "SSE not supported", http.StatusInternalServerError)
		return
	}
	domain := strings.TrimSpace(r.URL.Query().Get("domain"))
	if domain == "" {
		http.Error(w, "domain param required", http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	send := func(evType, data string) {
		fmt.Fprintf(w, "data: {\"type\":%s,\"data\":%s}\n\n", jsonStr(evType), jsonStr(data))
		flusher.Flush()
	}

	send("status", fmt.Sprintf("Querying crt.sh for subdomains of %s…", domain))

	subs, err := daemon.QueryCRTSH(domain)
	if err != nil {
		send("status", fmt.Sprintf("crt.sh error: %v — using apex domain only", err))
		subs = []string{}
	}

	// Always include the apex domain itself
	all := make([]string, 0, len(subs)+1)
	seen := make(map[string]bool)
	for _, h := range append([]string{domain}, subs...) {
		if !seen[h] {
			seen[h] = true
			all = append(all, h)
		}
	}

	send("status", fmt.Sprintf("Found %d subdomains — probing for live hosts…", len(all)))

	// Probe liveness concurrently, streaming results as they come in
	ports := []int{80, 443, 8080, 8443, 8000, 3000}
	type probe struct {
		host string
		live bool
	}

	sem := make(chan struct{}, 256)
	results := make(chan probe, len(all))
	for _, h := range all {
		h := h
		sem <- struct{}{}
		go func() {
			defer func() { <-sem }()
			for _, p := range ports {
				addr := fmt.Sprintf("%s:%d", h, p)
				conn, err := (&net.Dialer{Timeout: 2 * time.Second}).DialContext(r.Context(), "tcp", addr)
				if err == nil {
					conn.Close()
					results <- probe{host: h, live: true}
					return
				}
			}
			results <- probe{host: h, live: false}
		}()
	}

	liveCount := 0
	for range all {
		select {
		case <-r.Context().Done():
			return
		case p := <-results:
			if p.live {
				liveCount++
				send("host", p.host)
			}
		}
	}

	send("done", fmt.Sprintf("Discovery complete — %d/%d hosts are live", liveCount, len(all)))
}

// ── credential check ─────────────────────────────────────────────────────────

func (s *server) handleCheckCreds(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		Content string `json:"content"`
		Index   int    `json:"index"` // -1 → use Content field directly
	}
	req.Index = -1
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid JSON: "+err.Error(), http.StatusBadRequest)
		return
	}

	content := req.Content
	if content == "" && req.Index >= 0 {
		s.resMu.Lock()
		if req.Index < len(s.results) {
			content = s.results[req.Index].Content
		}
		s.resMu.Unlock()
	}
	if content == "" {
		http.Error(w, "no content provided", http.StatusBadRequest)
		return
	}

	report := credcheck.Check(content)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(report)
}

// ── daemon control ────────────────────────────────────────────────────────────

const daemonConfigPath = "daemon.json"
const daemonLogRing = 500

func (s *server) daemonLog(line string) {
	s.daemonLogMu.Lock()
	s.daemonLogs = append(s.daemonLogs, line)
	if len(s.daemonLogs) > daemonLogRing {
		s.daemonLogs = s.daemonLogs[len(s.daemonLogs)-daemonLogRing:]
	}
	s.daemonLogMu.Unlock()

	msg, _ := json.Marshal(map[string]string{"type": "log", "line": line})
	s.dSubsMu.RLock()
	defer s.dSubsMu.RUnlock()
	for ch := range s.dSubs {
		select {
		case ch <- msg:
		default:
		}
	}
}

func (s *server) handleDaemonConfig(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		data, err := os.ReadFile(daemonConfigPath)
		if os.IsNotExist(err) {
			// return a default template
			cfg := daemon.Config{
				Targets:           []string{"example.com"},
				ScanIntervalHours: 6,
				CooldownHours:     24,
				Threads:           8,
				Goroutines:        900,
				TimeoutSeconds:    30,
				DNSTimeoutSeconds: 2,
				OutputDir:         "daemon-results",
				StateFile:         "daemon-state.json",
			}
			data, _ = json.MarshalIndent(cfg, "", "  ")
		} else if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write(data)

	case http.MethodPost:
		body, err := io.ReadAll(io.LimitReader(r.Body, 64*1024))
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		// Validate it parses
		var cfg daemon.Config
		if err := json.Unmarshal(body, &cfg); err != nil {
			http.Error(w, "invalid JSON: "+err.Error(), http.StatusBadRequest)
			return
		}
		if err := os.WriteFile(daemonConfigPath, body, 0o644); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"ok":true}`)

	default:
		http.Error(w, "GET or POST only", http.StatusMethodNotAllowed)
	}
}

func (s *server) handleDaemonStart(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	s.daemonMu.Lock()
	defer s.daemonMu.Unlock()
	if s.daemonState == "running" {
		http.Error(w, "daemon already running", http.StatusConflict)
		return
	}

	cfg, err := daemon.LoadConfig(daemonConfigPath)
	if err != nil {
		http.Error(w, "load config: "+err.Error(), http.StatusBadRequest)
		return
	}

	ctx, cancel := context.WithCancel(context.Background())
	s.daemonCancel = cancel
	s.daemonState = "running"

	go func() {
		// Redirect daemon logs through our SSE stream
		log.SetOutput(&daemonLogWriter{s: s})
		if err := daemon.Run(ctx, cfg); err != nil && err != context.Canceled {
			s.daemonLog("[daemon] error: " + err.Error())
		}
		s.daemonMu.Lock()
		s.daemonState = "idle"
		s.daemonMu.Unlock()
		msg, _ := json.Marshal(map[string]string{"type": "stopped"})
		s.dSubsMu.RLock()
		for ch := range s.dSubs {
			select {
			case ch <- msg:
			default:
			}
		}
		s.dSubsMu.RUnlock()
	}()

	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{"ok":true}`)
}

func (s *server) handleDaemonStop(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	s.daemonMu.Lock()
	cancel := s.daemonCancel
	s.daemonMu.Unlock()
	if cancel != nil {
		cancel()
	}
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{"ok":true}`)
}

func (s *server) handleDaemonStatus(w http.ResponseWriter, r *http.Request) {
	s.daemonMu.Lock()
	state := s.daemonState
	s.daemonMu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"state":%s}`, jsonStr(state))
}

func (s *server) handleDaemonLogs(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "SSE not supported", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Send existing log buffer
	s.daemonLogMu.Lock()
	for _, line := range s.daemonLogs {
		b, _ := json.Marshal(map[string]string{"type": "log", "line": line})
		fmt.Fprintf(w, "data: %s\n\n", b)
	}
	s.daemonLogMu.Unlock()
	flusher.Flush()

	ch := make(chan []byte, 128)
	s.dSubsMu.Lock()
	s.dSubs[ch] = struct{}{}
	s.dSubsMu.Unlock()
	defer func() {
		s.dSubsMu.Lock()
		delete(s.dSubs, ch)
		s.dSubsMu.Unlock()
	}()

	ticker := time.NewTicker(25 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case <-ticker.C:
			fmt.Fprint(w, ": heartbeat\n\n")
			flusher.Flush()
		case msg, ok := <-ch:
			if !ok {
				return
			}
			fmt.Fprintf(w, "data: %s\n\n", msg)
			flusher.Flush()
		}
	}
}

// daemonLogWriter bridges log.SetOutput to our SSE log stream.
type daemonLogWriter struct{ s *server }

func (w *daemonLogWriter) Write(p []byte) (int, error) {
	w.s.daemonLog(strings.TrimRight(string(p), "\n"))
	return len(p), nil
}

// ── helpers ──────────────────────────────────────────────────────────────────

func jsonStr(s string) string {
	b, _ := json.Marshal(s)
	return string(b)
}
