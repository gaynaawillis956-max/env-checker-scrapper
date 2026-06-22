package runner

import (
	"fmt"
	"log"
	"os/exec"
	"runtime"
)

// Config defines how to launch env-checker from hostfinder.
type Config struct {
	// EnvCheckerPath is the absolute path to the env-checker binary.
	// When set and UseGoRun is false, the binary is invoked directly.
	EnvCheckerPath string
	// EnvCheckerRoot is the directory containing the env-checker Go source.
	// Used only when UseGoRun is true (dev-mode fallback via "go run <root>").
	EnvCheckerRoot string
	HostsFile      string
	SaveUnknown    bool
	JSONOutput     bool
	Threads        int
	Goroutines     int
	OutputDir      string
	UseGoRun       bool
	PathsLimit     int
}

func (c *Config) applyDefaults() {
	if c.Threads <= 0 {
		c.Threads = runtime.NumCPU()
	}
	if c.Goroutines <= 0 {
		c.Goroutines = 600
	}
}

func (c *Config) buildArgs() []string {
	args := []string{"--input", c.HostsFile, "--threads", fmt.Sprintf("%d", c.Threads), "--goroutines", fmt.Sprintf("%d", c.Goroutines)}
	if c.OutputDir != "" {
		args = append(args, "--output-dir", c.OutputDir)
	}
	if c.SaveUnknown {
		args = append(args, "--save-unknown")
	}
	if c.JSONOutput {
		args = append(args, "--json")
	}
	if c.PathsLimit > 0 {
		args = append(args, "--paths-limit", fmt.Sprintf("%d", c.PathsLimit))
	}
	return args
}

// Run executes env-checker.
// Priority: EnvCheckerPath binary > go run EnvCheckerRoot.
func Run(cfg Config) error {
	cfg.applyDefaults()
	args := cfg.buildArgs()

	var cmd *exec.Cmd
	if !cfg.UseGoRun && cfg.EnvCheckerPath != "" {
		cmd = exec.Command(cfg.EnvCheckerPath, args...)
	} else {
		root := cfg.EnvCheckerRoot
		if root == "" {
			root = ".."
		}
		cmdArgs := append([]string{"run", root}, args...)
		cmd = exec.Command("go", cmdArgs...)
	}

	cmd.Stdout = log.Writer()
	cmd.Stderr = log.Writer()
	return cmd.Run()
}
