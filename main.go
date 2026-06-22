package main

import (
	"context"
	"log"
	"os"
	"runtime"

	"env-checker/benchmark"
	"env-checker/cli"
	"env-checker/daemon"
	"env-checker/profiling"
	"env-checker/scanner"
	"env-checker/util"
	"env-checker/webui"
)

func main() {
	cfg := cli.ParseFlags()

	if cfg.ShowVersion {
		cli.PrintVersion()
		return
	}

	if cfg.WebMode {
		if err := webui.Serve(cfg.WebAddr); err != nil {
			log.Fatalf("web server: %v", err)
		}
		return
	}

	if cfg.DaemonMode {
		// Write default config if it doesn't exist yet
		if _, err := os.Stat(cfg.DaemonConfig); os.IsNotExist(err) {
			if err := daemon.WriteDefaultConfig(cfg.DaemonConfig); err != nil {
				log.Fatalf("create daemon config: %v", err)
			}
			log.Printf("Created default config at %s — edit it then re-run with --daemon", cfg.DaemonConfig)
			return
		}
		daemonCfg, err := daemon.LoadConfig(cfg.DaemonConfig)
		if err != nil {
			log.Fatalf("load daemon config %s: %v", cfg.DaemonConfig, err)
		}
		// Start web UI in background so results are visible at http://localhost:8080
		go func() {
			log.Printf("[web] dashboard → http://localhost:8080")
			if err := webui.Serve("0.0.0.0:8080"); err != nil {
				log.Printf("[web] server error: %v", err)
			}
		}()
		if err := daemon.Run(context.Background(), daemonCfg); err != nil {
			log.Fatalf("daemon: %v", err)
		}
		return
	}

	runtime.GOMAXPROCS(cfg.Threads)
	util.ApplyMemoryLimit(cfg.MemoryLimit)

	profiler := profiling.NewManager(cfg.Debug)
	profiler.Start()
	defer profiler.Stop()

	if cfg.BenchmarkFile != "" {
		if err := benchmark.Run(cfg); err != nil {
			log.Fatalf("benchmark failed: %v", err)
		}
		return
	}

	engine, err := scanner.NewEngine(cfg)
	if err != nil {
		log.Fatalf("failed to initialize scanner: %v", err)
	}

	if err := engine.Run(context.Background()); err != nil {
		log.Fatalf("scan failed: %v", err)
	}
}
