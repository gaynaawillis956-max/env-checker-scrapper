package daemon

import (
	"encoding/json"
	"os"
	"sync"
	"time"
)

// State tracks which hosts have been scanned and which URLs have been found,
// persisted to disk so it survives restarts.
type State struct {
	mu           sync.Mutex
	path         string
	ScannedHosts map[string]time.Time `json:"scanned_hosts"` // host → last scan time
	FoundURLs    map[string]time.Time `json:"found_urls"`    // url → first discovered
}

// LoadState loads state from path, or returns an empty state if not found.
func LoadState(path string) (*State, error) {
	s := &State{
		path:         path,
		ScannedHosts: make(map[string]time.Time),
		FoundURLs:    make(map[string]time.Time),
	}
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return s, nil
		}
		return nil, err
	}
	if err := json.Unmarshal(data, s); err != nil {
		return s, nil // corrupt file — start fresh
	}
	return s, nil
}

// Save persists state to disk atomically.
func (s *State) Save() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	tmp := s.path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, s.path)
}

// HostCooledDown returns true if the host hasn't been scanned within the cooldown window.
func (s *State) HostCooledDown(host string, cooldown time.Duration) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	last, ok := s.ScannedHosts[host]
	return !ok || time.Since(last) >= cooldown
}

// MarkHostScanned records the current time as the last scan time for host.
func (s *State) MarkHostScanned(host string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.ScannedHosts[host] = time.Now()
}

// IsURLNew returns true if this URL has never been reported before.
func (s *State) IsURLNew(url string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	_, seen := s.FoundURLs[url]
	return !seen
}

// MarkURLFound records that we have notified about this URL.
func (s *State) MarkURLFound(url string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.FoundURLs[url] = time.Now()
}

// Prune removes scanned-host entries older than maxAge to keep the file small.
func (s *State) Prune(maxAge time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	cutoff := time.Now().Add(-maxAge)
	for host, t := range s.ScannedHosts {
		if t.Before(cutoff) {
			delete(s.ScannedHosts, host)
		}
	}
}
