package progress

import (
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"time"
)

// Tracker persists scan offsets for resume support.
type Tracker struct {
	filePath string
	mu       sync.Mutex
	current  int
	lastSave time.Time
}

// NewTracker constructs a new tracker for the given input file.
func NewTracker(inputFile string) *Tracker {
	return &Tracker{filePath: inputFile + ".offset"}
}

// Load restores the last saved offset.
func (t *Tracker) Load() (int, error) {
	data, err := os.ReadFile(t.filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, err
	}
	value, err := strconv.Atoi(string(data))
	if err != nil {
		return 0, err
	}
	t.current = value
	return value, nil
}

// Set updates the tracker state and periodically flushes to disk.
func (t *Tracker) Set(value int) error {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.current = value
	if time.Since(t.lastSave) < 10*time.Second {
		return nil
	}
	t.lastSave = time.Now()
	return os.WriteFile(t.filePath, []byte(strconv.Itoa(value)), 0o644)
}

// Flush forces the current offset to be written immediately.
func (t *Tracker) Flush() error {
	t.mu.Lock()
	defer t.mu.Unlock()
	return os.WriteFile(t.filePath, []byte(strconv.Itoa(t.current)), 0o644)
}

// OffsetFile returns the filename used for offset persistence.
func (t *Tracker) OffsetFile() string {
	return filepath.Base(t.filePath)
}
