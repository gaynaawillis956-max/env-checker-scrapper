package output

import (
	"encoding/json"
	"fmt"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"env-checker/util"
)

// Record represents a persisted discovery.
type Record struct {
	Host       string            `json:"host"`
	Mode       string            `json:"mode"`
	Path       string            `json:"path"`
	Indicators []string          `json:"indicators"`
	Content    string            `json:"content"`
	Valid      bool              `json:"valid"`
	Metadata   map[string]string `json:"metadata"`
	Timestamp  time.Time         `json:"timestamp"`
}

// Writer manages persistence with deduplication.
type Writer struct {
	outDir      string
	saveUnknown bool
	jsonOutput  bool
	deduper     *Deduper
	mu          sync.Mutex
	records     []Record
}

// NewWriter constructs a Writer instance.
func NewWriter(outDir string, saveUnknown, jsonOutput bool) (*Writer, error) {
	if err := util.EnsureDir(outDir); err != nil {
		return nil, err
	}
	return &Writer{
		outDir:      outDir,
		saveUnknown: saveUnknown,
		jsonOutput:  jsonOutput,
		deduper:     NewDeduper(),
		records:     make([]Record, 0, 1024),
	}, nil
}

// Store writes a record to disk honoring deduplication.
func (w *Writer) Store(record Record) (bool, error) {
	if !record.Valid && !w.saveUnknown {
		return false, nil
	}
	record.Timestamp = util.NowUTC()
	hash := util.HashContent([]byte(record.Content))
	key := fmt.Sprintf("%s|%s|%s|%t", record.Host, record.Mode, record.Path, record.Valid)
	if !w.deduper.Add(key, hash) {
		return false, nil
	}

	suffix := "unknown"
	if record.Valid {
		suffix = "valid"
	}

	sanitizedHost := strings.ReplaceAll(strings.ReplaceAll(record.Host, ":", "_"), ".", "_")
	shortPath := record.Path
	if len(shortPath) > 64 {
		shortPath = shortPath[:64]
	}
	replacer := strings.NewReplacer("/", "-", "\\", "-", "%", "pct")
	shortPath = replacer.Replace(shortPath)
	filename := fmt.Sprintf("%s_%s.%s.%s.txt", sanitizedHost, strings.ToLower(record.Mode), shortPath, suffix)
	absPath := filepath.Join(w.outDir, filename)

	if err := util.WriteFileAtomic(absPath, []byte(record.Content)); err != nil {
		return false, err
	}

	if w.jsonOutput {
		w.mu.Lock()
		w.records = append(w.records, record)
		w.mu.Unlock()
	}

	return true, nil
}

// FlushJSON writes the aggregated JSON summary if enabled.
func (w *Writer) FlushJSON() error {
	if !w.jsonOutput {
		return nil
	}
	w.mu.Lock()
	defer w.mu.Unlock()

	data, err := json.MarshalIndent(w.records, "", "  ")
	if err != nil {
		return err
	}
	summaryPath := filepath.Join(w.outDir, "results.json")
	return util.WriteFileAtomic(summaryPath, data)
}
