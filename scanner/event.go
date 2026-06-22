package scanner

import "env-checker/output"

const (
	EventProgress = "progress"
	EventFound    = "found"
	EventDone     = "done"
)

// Event carries a scan lifecycle notification over the optional event channel.
type Event struct {
	Type string `json:"type"`

	// progress / done
	Hosts    int64   `json:"hosts,omitempty"`
	Found    int64   `json:"found,omitempty"`
	Saved    int64   `json:"saved,omitempty"`
	Requests int64   `json:"requests,omitempty"`
	Elapsed  float64 `json:"elapsed,omitempty"` // seconds

	// found
	Record *output.Record `json:"record,omitempty"`
}
