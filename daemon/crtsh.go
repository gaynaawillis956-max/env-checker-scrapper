package daemon

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

var crtClient = &http.Client{Timeout: 30 * time.Second}

type crtEntry struct {
	NameValue string `json:"name_value"`
}

// QueryCRTSH returns all known subdomains of domain from certificate transparency logs.
// Wildcards (*.x) are silently skipped.
func QueryCRTSH(domain string) ([]string, error) {
	url := fmt.Sprintf("https://crt.sh/?q=%%.%s&output=json", domain)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "env-checker-daemon/1.0")
	resp, err := crtClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("crt.sh: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("crt.sh HTTP %d", resp.StatusCode)
	}

	var entries []crtEntry
	if err := json.Unmarshal(body, &entries); err != nil {
		return nil, fmt.Errorf("crt.sh parse: %w", err)
	}

	seen := make(map[string]bool)
	var result []string
	suffix := "." + domain
	for _, e := range entries {
		for _, name := range strings.Split(e.NameValue, "\n") {
			name = strings.TrimSpace(strings.ToLower(name))
			if name == "" || strings.HasPrefix(name, "*") {
				continue
			}
			if name != domain && !strings.HasSuffix(name, suffix) {
				continue
			}
			if !seen[name] {
				seen[name] = true
				result = append(result, name)
			}
		}
	}
	return result, nil
}
