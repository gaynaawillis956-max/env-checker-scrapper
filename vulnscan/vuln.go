// Package vulnscan performs active vulnerability checks against web targets.
package vulnscan

import (
	"fmt"
	"io"
	"net/http"
	"time"
)

// Severity levels for findings.
const (
	Critical = "critical"
	High     = "high"
	Medium   = "medium"
	Low      = "low"
	Info     = "info"
)

// Finding is a single confirmed vulnerability or misconfiguration.
type Finding struct {
	Host     string `json:"host"`
	URL      string `json:"url"`
	Type     string `json:"type"`     // e.g. "cors", "git-exposed", "open-redirect"
	Title    string `json:"title"`
	Severity string `json:"severity"`
	Evidence string `json:"evidence"` // response snippet proving the finding
	Detail   string `json:"detail"`   // impact + what to report
}

var client = &http.Client{
	Timeout: 12 * time.Second,
	CheckRedirect: func(req *http.Request, via []*http.Request) error {
		return http.ErrUseLastResponse // don't follow redirects — we want to see them
	},
}

func get(url string, headers map[string]string) (int, http.Header, []byte, error) {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return 0, nil, nil, err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; SecurityScanner/1.0)")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := client.Do(req)
	if err != nil {
		return 0, nil, nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 128*1024))
	return resp.StatusCode, resp.Header, body, nil
}

func snippet(body []byte, max int) string {
	s := string(body)
	if len(s) > max {
		return s[:max] + "…"
	}
	return s
}

func f(host, url, typ, title, severity, evidence, detail string) Finding {
	return Finding{
		Host:     host,
		URL:      url,
		Type:     typ,
		Title:    title,
		Severity: severity,
		Evidence: evidence,
		Detail:   detail,
	}
}

func baseURLs(host string) []string {
	return []string{
		fmt.Sprintf("https://%s", host),
		fmt.Sprintf("http://%s", host),
	}
}
