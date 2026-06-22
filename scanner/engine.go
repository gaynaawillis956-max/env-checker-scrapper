package scanner

import (
	"context"
	"fmt"
	"time"

	"env-checker/cli"
	"env-checker/dns"
	"env-checker/output"
	"env-checker/paths"
	"env-checker/progress"
	"env-checker/util"
	"env-checker/validation"
)

// Engine represents the orchestrated scanning engine facade.
type Engine struct {
	core *coreEngine
}

// NewEngine wires together all subsystems required for scanning.
func NewEngine(cfg *cli.Config) (*Engine, error) {
	pathList := paths.Build()
	originalCount := len(pathList)
	if originalCount < 1700 {
		return nil, fmt.Errorf("expected at least 1700 paths, found %d", originalCount)
	}
	if limit := cfg.GetPathsLimit(); limit > 0 && limit < len(pathList) {
		pathList = pathList[:limit]
	}

	patterns, err := validation.BuildPatterns()
	if err != nil {
		return nil, fmt.Errorf("compile patterns: %w", err)
	}
	validator := validation.NewValidator(patterns)

	writer, err := output.NewWriter(cfg.OutputDir, cfg.SaveUnknownEnabled(), cfg.JSONOutputEnabled())
	if err != nil {
		return nil, fmt.Errorf("create writer: %w", err)
	}

	tracker := progress.NewTracker(cfg.InputFile)
	savedOffset, err := tracker.Load()
	if err != nil {
		return nil, fmt.Errorf("load offset: %w", err)
	}
	startOffset := cfg.GetOffset()
	if savedOffset > startOffset {
		startOffset = savedOffset
	}

	servers, err := dns.LoadServers(cfg.DNSServersFile)
	if err != nil {
		return nil, fmt.Errorf("load DNS servers: %w", err)
	}
	dnsMgr := NewDNSManager(servers, time.Duration(cfg.GetDNSTimeoutSeconds())*time.Second, cfg.DNSConcurrency)

	core := newCoreEngine(cfg, pathList, validator, writer, tracker, dnsMgr, time.Duration(cfg.GetTimeoutSeconds())*time.Second)
	core.startOffset = startOffset

	// Count total lines for ETA reporting; non-fatal if it fails.
	if total, err := util.CountLines(cfg.InputFile); err == nil {
		core.stats.totalHosts = total
	}

	return &Engine{core: core}, nil
}

// SetEvents attaches a channel that receives live scan events (web UI mode).
func (e *Engine) SetEvents(ch chan<- Event) {
	e.core.eventCh = ch
}

// Run executes the engine until completion. ctx allows external cancellation.
func (e *Engine) Run(ctx context.Context) error {
	return e.core.Run(ctx)
}
