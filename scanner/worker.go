package scanner

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"env-checker/cli"
	"env-checker/output"
	"env-checker/progress"
	"env-checker/util"
	"env-checker/validation"
)

type stats struct {
	start          time.Time
	hostsProcessed int64
	filesFound     int64
	filesSaved     int64
	requests       int64
	totalHosts     int64 // set once at startup for ETA calculation
}

type coreEngine struct {
	cfg         *cli.Config
	paths       []string
	validator   *validation.Validator
	writer      *output.Writer
	tracker     *progress.Tracker
	dns         *DNSManager
	factory     *HTTPClientFactory
	cluster     *util.ClusterCoordinator
	startOffset int
	stats       *stats
	eventCh     chan<- Event // nil in CLI mode
}

func newCoreEngine(cfg *cli.Config, paths []string, validator *validation.Validator, writer *output.Writer, tracker *progress.Tracker, dns *DNSManager, timeout time.Duration) *coreEngine {
	return &coreEngine{
		cfg:       cfg,
		paths:     paths,
		validator: validator,
		writer:    writer,
		tracker:   tracker,
		dns:       dns,
		factory:   NewHTTPClientFactory(timeout),
		cluster:   cfg.Coordinator(),
		stats:     &stats{start: time.Now()},
	}
}

// Run executes the scanning process. parentCtx allows external cancellation
// (e.g. from the web UI stop button). Signals create a child cancellation on top.
func (e *coreEngine) Run(parentCtx context.Context) error {
	ctx, cancel := context.WithCancel(parentCtx)
	defer cancel()

	sigCh := make(chan os.Signal, 2)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	go func() {
		count := 0
		for sig := range sigCh {
			count++
			if count == 1 {
				log.Printf("received %s, initiating graceful shutdown", sig)
				cancel()
			} else {
				log.Printf("received %s again, exiting immediately", sig)
				os.Exit(1)
			}
		}
	}()
	defer signal.Stop(sigCh)

	jobs := make(chan string, e.cfg.GetGoroutines()*2)
	errCh := make(chan error, 1)

	var wg sync.WaitGroup
	for i := 0; i < e.cfg.GetGoroutines(); i++ {
		wg.Add(1)
		go e.worker(ctx, &wg, jobs, errCh)
	}

	reportDone := e.startReporter(ctx)

	go func() {
		if err := e.feed(ctx, jobs); err != nil {
			select {
			case errCh <- err:
			default:
			}
		}
		close(jobs)
	}()

	var runErr error
	select {
	case runErr = <-errCh:
		cancel()
	case <-ctx.Done():
		runErr = ctx.Err()
	}

	wg.Wait()
	cancel()
	<-reportDone

	if flushErr := e.tracker.Flush(); flushErr != nil && runErr == nil {
		runErr = flushErr
	}
	if jsonErr := e.writer.FlushJSON(); jsonErr != nil && runErr == nil {
		runErr = jsonErr
	}

	if errors.Is(runErr, context.Canceled) {
		return nil
	}
	return runErr
}

func (e *coreEngine) worker(ctx context.Context, wg *sync.WaitGroup, jobs <-chan string, errCh chan<- error) {
	defer wg.Done()
	clientCache := make(map[Mode]*http.Client)

	for {
		select {
		case <-ctx.Done():
			return
		case host, ok := <-jobs:
			if !ok {
				return
			}
			if err := e.scanHost(ctx, host, clientCache); err != nil {
				select {
				case errCh <- err:
				default:
				}
				return
			}
		}
	}
}

func (e *coreEngine) scanHost(ctx context.Context, host string, clientCache map[Mode]*http.Client) error {
	ip := net.ParseIP(host)
	failures := map[Mode]int{}

	for _, mode := range Modes() {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		client := clientCache[mode]
		if client == nil {
			client = e.factory.Client(mode)
			clientCache[mode] = client
		}

		resolved := ""
		if mode == ModeHTTPSDNS {
			if ip == nil {
				resolved = host
			} else {
				name, err := e.dns.ReverseLookup(host)
				if err != nil || name == "" {
					continue // no PTR record — skip HTTPS-DNS for this host
				}
				resolved = name
			}
		}

		for _, path := range e.paths {
			if ctx.Err() != nil {
				return ctx.Err()
			}

			req, err := BuildRequest(ctx, mode, host, path, resolved)
			if err != nil {
				return err
			}

			resp, body, err := Fetch(client, req)
			atomic.AddInt64(&e.stats.requests, 1)
			if err != nil {
				failures[mode]++
				if failures[mode] >= 3 {
					break
				}
				continue
			}

			// 5xx → server-side error; counts toward mode abandonment.
			if resp.StatusCode >= http.StatusInternalServerError {
				failures[mode]++
				if failures[mode] >= 3 {
					break
				}
				continue
			}

			// 403 Forbidden on a sensitive path strongly suggests the file exists
			// but access is restricted — save it as a confirmed finding.
			if resp.StatusCode == http.StatusForbidden {
				failures[mode] = 0
				e.saveForbidden(host, string(mode), path, resolved)
				continue
			}

			// Any other 4xx → path not found, but the mode is clearly alive.
			if resp.StatusCode >= http.StatusBadRequest {
				failures[mode] = 0
				continue
			}

			failures[mode] = 0

			if validation.ShouldDiscardResponse(resp, body) {
				continue
			}

			result := e.validator.Validate(body, resp.Header.Get("Content-Type"))
			if !result.Valid && !e.cfg.SaveUnknownEnabled() {
				continue
			}

			atomic.AddInt64(&e.stats.filesFound, 1)
			record := output.Record{
				Host:       host,
				Mode:       string(mode),
				Path:       path,
				Indicators: result.Indicators,
				Content:    string(body),
				Valid:      result.Valid,
				Metadata: map[string]string{
					"status":       fmt.Sprintf("%d", resp.StatusCode),
					"content-type": result.ContentType,
					"resolved":     resolved,
				},
			}

			if saved, err := e.writer.Store(record); err != nil {
				return err
			} else if saved {
				atomic.AddInt64(&e.stats.filesSaved, 1)
				if e.eventCh != nil {
					r := record
					select {
					case e.eventCh <- Event{Type: EventFound, Record: &r}:
					default:
					}
				}
			}
		}
	}

	atomic.AddInt64(&e.stats.hostsProcessed, 1)
	return nil
}

func (e *coreEngine) saveForbidden(host, mode, path, resolved string) {
	content := fmt.Sprintf("STATUS=403\nFORBIDDEN=true\nPATH=%s\n", path)
	record := output.Record{
		Host:       host,
		Mode:       mode,
		Path:       path,
		Indicators: []string{"forbidden"},
		Content:    content,
		Valid:       true,
		Metadata: map[string]string{
			"status":   "403",
			"resolved": resolved,
		},
	}
	atomic.AddInt64(&e.stats.filesFound, 1)
	if saved, err := e.writer.Store(record); err == nil && saved {
		atomic.AddInt64(&e.stats.filesSaved, 1)
		if e.eventCh != nil {
			r := record
			select {
			case e.eventCh <- Event{Type: EventFound, Record: &r}:
			default:
			}
		}
	}
}

func (e *coreEngine) feed(ctx context.Context, jobs chan<- string) error {
	handler := func(index int, entry string) error {
		if strings.HasPrefix(entry, "#") {
			return nil
		}
		if e.cluster != nil && !e.cluster.ShouldProcess(entry) {
			return nil
		}

		dispatch := func(target string) error {
			if !e.cfg.IPv6Enabled() {
				if ip := net.ParseIP(target); ip != nil && ip.To4() == nil {
					return nil
				}
			}
			select {
			case <-ctx.Done():
				return context.Canceled
			case jobs <- target:
				return nil
			}
		}

		var err error
		if e.cfg.CIDRMode() && strings.Contains(entry, "/") {
			err = util.IterateCIDR(entry, dispatch)
		} else {
			err = dispatch(entry)
		}
		if err != nil {
			return err
		}
		return e.tracker.Set(index)
	}

	if err := util.ReadLinesFromOffset(e.cfg.GetInput(), e.startOffset, handler); err != nil {
		return err
	}
	return nil
}

func (e *coreEngine) startReporter(ctx context.Context) chan struct{} {
	done := make(chan struct{})
	ticker := time.NewTicker(10 * time.Second)
	go func() {
		defer close(done)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				e.printStats(true)
				return
			case <-ticker.C:
				e.printStats(false)
			}
		}
	}()
	return done
}

func (e *coreEngine) printStats(final bool) {
	elapsed := time.Since(e.stats.start)
	hosts := atomic.LoadInt64(&e.stats.hostsProcessed)
	total := atomic.LoadInt64(&e.stats.totalHosts)
	reqs := atomic.LoadInt64(&e.stats.requests)
	found := atomic.LoadInt64(&e.stats.filesFound)
	saved := atomic.LoadInt64(&e.stats.filesSaved)

	elapsedSec := elapsed.Seconds()
	rateHosts := 0.0
	if elapsedSec > 0 {
		rateHosts = float64(hosts) / elapsedSec
	}
	rateReqs := 0.0
	if elapsedSec > 0 {
		rateReqs = float64(reqs) / elapsedSec
	}

	etaStr := "unknown"
	if rateHosts > 0 && total > hosts {
		remainSec := int64(float64(total-hosts) / rateHosts)
		etaStr = fmt.Sprintf("%dh%02dm%02ds", remainSec/3600, (remainSec%3600)/60, remainSec%60)
	} else if total > 0 && hosts >= total {
		etaStr = "done"
	}

	var mem runtime.MemStats
	runtime.ReadMemStats(&mem)
	memMB := mem.Sys / 1024 / 1024

	elapsedStr := elapsed.Round(time.Second).String()

	if final {
		log.Printf("summary: %d/%d hosts, %d/%d saved/found, %s, %d h/s, %d r/s, %dMB",
			hosts, total, saved, found, elapsedStr, int(rateHosts), int(rateReqs), memMB)
	} else {
		log.Printf("%d/%d hosts, %d/%d saved/found, %s, %d h/s, %d r/s, ETA %s, %dMB",
			hosts, total, saved, found, elapsedStr, int(rateHosts), int(rateReqs), etaStr, memMB)
	}

	if e.eventCh != nil {
		ev := Event{
			Type:     EventProgress,
			Hosts:    hosts,
			Found:    found,
			Saved:    saved,
			Requests: reqs,
			Elapsed:  elapsed.Seconds(),
		}
		if final {
			ev.Type = EventDone
		}
		select {
		case e.eventCh <- ev:
		default:
		}
	}
}
