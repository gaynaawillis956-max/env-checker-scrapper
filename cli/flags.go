package cli

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"runtime"
	"strings"

	"env-checker/util"
)

const version = "1.0.0"

// Config encapsulates all CLI configuration options.
type Config struct {
	InputFile      string
	OutputDir      string
	Threads        int
	Goroutines     int
	Timeout        int
	DNSTimeout     int
	Offset         int
	SaveUnknown    bool
	Debug          bool
	MemoryLimit    int
	DNSConcurrency int
	DNSServersFile string
	BenchmarkFile  string
	ShowVersion    bool
	JSONOutput     bool
	ClusterPeers   []string
	CIDRInput      bool
	IPv6           bool
	PathsLimit     int

	// Web UI mode
	WebMode bool
	WebAddr string // host:port for the web server

	// Autonomous daemon mode
	DaemonMode   bool
	DaemonConfig string // path to daemon.json

	cluster *util.ClusterCoordinator
}

// DefaultConfig returns a configuration instance populated with defaults.
func DefaultConfig() *Config {
	return &Config{
		Threads:        runtime.NumCPU(),
		OutputDir:      "envs",
		Goroutines:     900,
		Timeout:        30,
		DNSTimeout:     2,
		DNSConcurrency: 100,
		IPv6:           true,
		PathsLimit:     0,
	}
}

// ParseFlags parses command-line arguments into a Config struct.
func ParseFlags() *Config {
	cfg := DefaultConfig()

	flag.Usage = func() {
		fmt.Fprintf(flag.CommandLine.Output(), "Usage: env-checker [options]\n\n")
		fmt.Fprintln(flag.CommandLine.Output(), "Options:")
		flag.PrintDefaults()
	}

	clusterPeers := flag.String("cluster-peers", "", "Comma-separated peer list for distributed scanning")

	flag.StringVar(&cfg.InputFile, "input", cfg.InputFile, "Input file containing IP addresses/hostnames (required unless --benchmark)")
	flag.StringVar(&cfg.InputFile, "i", cfg.InputFile, "Input file alias")
	flag.StringVar(&cfg.OutputDir, "output-dir", cfg.OutputDir, "Directory to save discovered files")
	flag.StringVar(&cfg.OutputDir, "o", cfg.OutputDir, "Output directory alias")
	flag.IntVar(&cfg.Threads, "threads", cfg.Threads, "Number of OS threads to use")
	flag.IntVar(&cfg.Threads, "t", cfg.Threads, "Threads alias")
	flag.IntVar(&cfg.Goroutines, "goroutines", cfg.Goroutines, "Number of worker goroutines")
	flag.IntVar(&cfg.Goroutines, "g", cfg.Goroutines, "Goroutines alias")
	flag.IntVar(&cfg.Timeout, "timeout", cfg.Timeout, "HTTP request timeout in seconds")
	flag.IntVar(&cfg.Timeout, "T", cfg.Timeout, "Timeout alias")
	flag.IntVar(&cfg.DNSTimeout, "dns-timeout", cfg.DNSTimeout, "DNS lookup timeout in seconds")
	flag.IntVar(&cfg.DNSTimeout, "D", cfg.DNSTimeout, "DNS timeout alias")
	flag.IntVar(&cfg.Offset, "offset", cfg.Offset, "Skip first N entries from input")
	flag.IntVar(&cfg.Offset, "skip", cfg.Offset, "Skip alias")
	flag.IntVar(&cfg.Offset, "s", cfg.Offset, "Skip alias")
	flag.BoolVar(&cfg.SaveUnknown, "save-unknown", cfg.SaveUnknown, "Save responses that do not match known patterns")
	flag.BoolVar(&cfg.SaveUnknown, "su", cfg.SaveUnknown, "Save unknown alias")
	flag.BoolVar(&cfg.Debug, "debug", cfg.Debug, "Enable CPU and memory profiling")
	flag.IntVar(&cfg.MemoryLimit, "memory-limit", cfg.MemoryLimit, "Soft memory limit in MB (0 disables)")
	flag.IntVar(&cfg.MemoryLimit, "m", cfg.MemoryLimit, "Memory limit alias")
	flag.IntVar(&cfg.DNSConcurrency, "dns-concurrency", cfg.DNSConcurrency, "Maximum concurrent DNS lookups")
	flag.IntVar(&cfg.DNSConcurrency, "dc", cfg.DNSConcurrency, "DNS concurrency alias")
	flag.StringVar(&cfg.DNSServersFile, "dns-servers", cfg.DNSServersFile, "Path to DNS servers list (one per line)")
	flag.StringVar(&cfg.BenchmarkFile, "benchmark", cfg.BenchmarkFile, "Path to benchmark configuration file")
	flag.BoolVar(&cfg.ShowVersion, "version", cfg.ShowVersion, "Print version and exit")
	flag.BoolVar(&cfg.JSONOutput, "json", cfg.JSONOutput, "Emit JSON summary results")
	flag.BoolVar(&cfg.CIDRInput, "cidr", cfg.CIDRInput, "Treat input entries as CIDR ranges")
	flag.BoolVar(&cfg.IPv6, "ipv6", cfg.IPv6, "Allow IPv6 targets when present")
	flag.IntVar(&cfg.PathsLimit, "paths-limit", 0, "Limit number of paths scanned per host (0 = all)")
	flag.BoolVar(&cfg.WebMode, "web", false, "Start the web UI instead of a CLI scan")
	flag.StringVar(&cfg.WebAddr, "addr", "127.0.0.1:8080", "Address for the web UI server (host:port)")
	flag.BoolVar(&cfg.DaemonMode, "daemon", false, "Run autonomous 24/7 scanning loop")
	flag.StringVar(&cfg.DaemonConfig, "config", "daemon.json", "Path to daemon config file (used with --daemon)")

	flag.Parse()

	if *clusterPeers != "" {
		cfg.ClusterPeers = util.SplitAndTrim(*clusterPeers)
	}

	if err := validateConfig(cfg); err != nil {
		fmt.Fprintln(os.Stderr, "Configuration error:", err)
		flag.Usage()
		os.Exit(1)
	}

	cfg.InitializeCluster()
	return cfg
}

func validateConfig(cfg *Config) error {
	if cfg.ShowVersion || cfg.WebMode || cfg.DaemonMode {
		return nil
	}
	if cfg.BenchmarkFile == "" && cfg.InputFile == "" {
		return errors.New("--input is required when not running a benchmark")
	}
	if cfg.Threads <= 0 {
		return errors.New("--threads must be positive")
	}
	if cfg.Goroutines <= 0 {
		return errors.New("--goroutines must be positive")
	}
	if cfg.Timeout <= 0 {
		return errors.New("--timeout must be positive")
	}
	if cfg.DNSTimeout <= 0 {
		return errors.New("--dns-timeout must be positive")
	}
	if cfg.DNSConcurrency <= 0 {
		return errors.New("--dns-concurrency must be positive")
	}
	return nil
}

// PrintVersion prints the tool version.
func PrintVersion() {
	fmt.Println("env-checker version", version)
}

// Coordinator returns the cluster coordinator instance.
func (c *Config) Coordinator() *util.ClusterCoordinator {
	return c.cluster
}

// ClusterEnabled reports whether distributed mode is active.
func (c *Config) ClusterEnabled() bool {
	return c.cluster != nil && c.cluster.Enabled()
}

// ShouldProcess determines if the current node should process the host.
func (c *Config) ShouldProcess(host string) bool {
	if c.cluster == nil {
		return true
	}
	return c.cluster.ShouldProcess(host)
}

// PeersString returns the configured peers as CSV.
func (c *Config) PeersString() string {
	if len(c.ClusterPeers) == 0 {
		return ""
	}
	return strings.Join(c.ClusterPeers, ",")
}

// InitializeCluster wires the cluster coordinator if cluster peers are configured.
func (c *Config) InitializeCluster() {
	if c == nil {
		return
	}
	c.cluster = util.NewClusterCoordinator(c.ClusterPeers)
}

// Accessor helpers for other packages.
func (c *Config) GetInput() string          { return c.InputFile }
func (c *Config) GetOutputDir() string      { return c.OutputDir }
func (c *Config) GetGoroutines() int        { return c.Goroutines }
func (c *Config) GetTimeoutSeconds() int    { return c.Timeout }
func (c *Config) GetDNSTimeoutSeconds() int { return c.DNSTimeout }
func (c *Config) GetOffset() int            { return c.Offset }
func (c *Config) SaveUnknownEnabled() bool  { return c.SaveUnknown }
func (c *Config) JSONOutputEnabled() bool   { return c.JSONOutput }
func (c *Config) CIDRMode() bool            { return c.CIDRInput }
func (c *Config) IPv6Enabled() bool         { return c.IPv6 }
func (c *Config) GetPathsLimit() int        { return c.PathsLimit }
