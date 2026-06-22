package vulnscan

import (
	"log"
	"sync"
)

// Scan runs all vulnerability checks against host and returns all findings.
// Checks run concurrently for speed.
func Scan(host string) []Finding {
	type checkFn struct {
		name string
		fn   func(string) []Finding
	}

	checks := []checkFn{
		{"cors", checkCORS},
		{"git-exposed", checkGitExposed},
		{"actuator", checkActuator},
		{"admin-panels", checkAdminPanels},
		{"phpinfo", checkPHPInfo},
		{"dir-listing", checkDirListing},
		{"open-redirect", checkOpenRedirect},
		{"graphql", checkGraphQL},
		{"debug-endpoints", checkDebugEndpoints},
		{"subdomain-takeover", checkSubdomainTakeover},
		{"js-keys", checkJSKeys},
		{"backup-files", checkBackupFiles},
		{"server-status", checkServerStatus},
	}

	var (
		mu      sync.Mutex
		wg      sync.WaitGroup
		results []Finding
	)

	for _, c := range checks {
		c := c
		wg.Add(1)
		go func() {
			defer wg.Done()
			defer func() {
				if r := recover(); r != nil {
					log.Printf("[vulnscan] panic in %s for %s: %v", c.name, host, r)
				}
			}()
			found := c.fn(host)
			if len(found) > 0 {
				mu.Lock()
				results = append(results, found...)
				mu.Unlock()
			}
		}()
	}

	wg.Wait()
	return results
}

// ScanMany runs Scan across multiple hosts concurrently (max 20 parallel).
func ScanMany(hosts []string, onFinding func(Finding)) {
	sem := make(chan struct{}, 20)
	var wg sync.WaitGroup
	for _, h := range hosts {
		h := h
		sem <- struct{}{}
		wg.Add(1)
		go func() {
			defer wg.Done()
			defer func() { <-sem }()
			for _, finding := range Scan(h) {
				onFinding(finding)
			}
		}()
	}
	wg.Wait()
}
