package output

import "sync"

// Deduper tracks persisted content to prevent duplicates.
type Deduper struct {
	mu    sync.Mutex
	items map[string]string
}

// NewDeduper constructs a new Deduper.
func NewDeduper() *Deduper {
	return &Deduper{items: make(map[string]string)}
}

// Add inserts the key/hash combination if unseen.
func (d *Deduper) Add(key, hash string) bool {
	d.mu.Lock()
	defer d.mu.Unlock()
	if prev, ok := d.items[key]; ok {
		if prev == hash {
			return false
		}
	}
	d.items[key] = hash
	return true
}
