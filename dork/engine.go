// Package dork runs Google-style search queries to discover targets exposing
// sensitive files and credentials. Uses DuckDuckGo (no API key required) with
// optional Bing Web Search API for higher volume.
package dork

import (
	"fmt"
	"io"
	"log"
	"math/rand"
	"net"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"

	_ "embed"
)

//go:embed builtin.txt
var builtinData string

// userAgents rotated to reduce blocking.
var userAgents = []string{
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
	"Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
}

var (
	hrefRe    = regexp.MustCompile(`href="(https?://[^"]+)"`)
	ddgLiteRe = regexp.MustCompile(`href="(//duckduckgo\.com/l/\?[^"]+)"`)
	uddgRe    = regexp.MustCompile(`[?&]uddg=(https?[^&"]+)`)
	domainRe  = regexp.MustCompile(`^(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}$`)
)

var httpClient = &http.Client{
	Timeout: 20 * time.Second,
	Transport: &http.Transport{
		DialContext: (&net.Dialer{Timeout: 10 * time.Second}).DialContext,
	},
}

// Config controls how the dork engine searches.
type Config struct {
	Engine          string  `json:"engine"`            // "duckduckgo" (default) or "bing"
	BingAPIKey      string  `json:"bing_api_key"`      // optional
	CustomFile      string  `json:"custom_file"`       // path to user dorks file
	MaxPerDork      int     `json:"max_per_dork"`      // max URLs per dork (default 10)
	DelaySeconds    float64 `json:"delay_seconds"`     // delay between requests (default 8)
	UseBuiltin      bool    `json:"use_builtin"`       // include built-in dork list (default true)
	Categories      []string `json:"categories"`       // filter categories (empty = all)
}

func (c *Config) delay() time.Duration {
	if c.DelaySeconds <= 0 {
		return 8 * time.Second
	}
	// add jitter ±30%
	base := time.Duration(c.DelaySeconds * float64(time.Second))
	jitter := time.Duration(rand.Int63n(int64(base) * 3 / 10))
	if rand.Intn(2) == 0 {
		return base + jitter
	}
	return base - jitter
}

func (c *Config) maxPerDork() int {
	if c.MaxPerDork <= 0 {
		return 10
	}
	return c.MaxPerDork
}

// Dorks returns the full list of dorks to run based on Config.
func (c *Config) Dorks() []string {
	var all []string

	if c.UseBuiltin || c.Engine == "" {
		all = append(all, BuiltinDorks(c.Categories)...)
	}

	if c.CustomFile != "" {
		custom, err := LoadFile(c.CustomFile)
		if err != nil {
			log.Printf("[dork] load custom file %s: %v", c.CustomFile, err)
		} else {
			log.Printf("[dork] loaded %d custom dorks from %s", len(custom), c.CustomFile)
			all = append(all, custom...)
		}
	}

	// Deduplicate
	seen := make(map[string]bool)
	out := all[:0]
	for _, d := range all {
		if !seen[d] {
			seen[d] = true
			out = append(out, d)
		}
	}
	return out
}

// BuiltinDorks returns the embedded dork list, optionally filtered by category.
func BuiltinDorks(categories []string) []string {
	lines := parseLines(builtinData)
	if len(categories) == 0 {
		return lines
	}
	// Filter by category comment header (lines under matching # heading)
	var out []string
	var currentCat string
	for _, line := range strings.Split(builtinData, "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "# ──") || strings.HasPrefix(trimmed, "# --") {
			currentCat = strings.ToLower(trimmed)
		}
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		for _, cat := range categories {
			if strings.Contains(currentCat, strings.ToLower(cat)) {
				out = append(out, trimmed)
				break
			}
		}
	}
	return out
}

// LoadFile loads dorks from a text file (one per line, # for comments).
func LoadFile(path string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return parseLines(string(data)), nil
}

func parseLines(s string) []string {
	var out []string
	for _, line := range strings.Split(s, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		out = append(out, line)
	}
	return out
}

var errBlocked = fmt.Errorf("search engine block detected")

// Run searches all configured dorks and calls onDomain for each unique domain found.
// Stops early if the search engine blocks consecutive queries.
func Run(cfg *Config, onDomain func(domain string)) error {
	dorks := cfg.Dorks()
	if len(dorks) == 0 {
		return fmt.Errorf("no dorks configured")
	}
	log.Printf("[dork] running %d dorks via %s", len(dorks), cfg.Engine)

	seen := make(map[string]bool)
	consecutiveBlocks := 0

	for i, dork := range dorks {
		log.Printf("[dork] %d/%d: %s", i+1, len(dorks), dork)

		var urls []string
		var err error

		if cfg.BingAPIKey != "" {
			urls, err = searchBing(dork, cfg.BingAPIKey, cfg.maxPerDork())
		} else {
			urls, err = searchDDG(dork, cfg.maxPerDork())
		}

		if err == errBlocked {
			consecutiveBlocks++
			if consecutiveBlocks >= 2 {
				log.Printf("[dork] DDG blocking — stopping dork search for this cycle (will retry next cycle)")
				return nil
			}
			// Single block: wait longer then retry once
			log.Printf("[dork] DDG block detected — waiting 30s before next query")
			time.Sleep(30 * time.Second)
			continue
		}
		if err != nil {
			log.Printf("[dork] search error: %v", err)
		}
		consecutiveBlocks = 0

		for _, u := range urls {
			domain := extractDomain(u)
			if domain == "" || seen[domain] {
				continue
			}
			seen[domain] = true
			onDomain(domain)
		}

		if i < len(dorks)-1 {
			time.Sleep(cfg.delay())
		}
	}
	return nil
}

// ── DuckDuckGo scraper ────────────────────────────────────────────────────────

func searchDDG(query string, maxResults int) ([]string, error) {
	endpoint := "https://lite.duckduckgo.com/lite/?q=" + url.QueryEscape(query)

	req, err := http.NewRequest("GET", endpoint, nil)
	if err != nil {
		return nil, err
	}
	ua := userAgents[rand.Intn(len(userAgents))]
	req.Header.Set("User-Agent", ua)
	req.Header.Set("Accept", "text/html,application/xhtml+xml")
	req.Header.Set("Accept-Language", "en-US,en;q=0.9")
	req.Header.Set("Referer", "https://lite.duckduckgo.com/")

	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 512*1024))

	bs := string(body)
	if isDDGBlocked(bs) {
		log.Printf("[dork/ddg] bot-block detected for query %q", query)
		return nil, errBlocked
	}
	urls := extractURLs(bs, maxResults)
	log.Printf("[dork/ddg] query %q → %d URLs (body=%d bytes)", query, len(urls), len(body))
	return urls, nil
}

// ── Bing API ──────────────────────────────────────────────────────────────────

func searchBing(query, apiKey string, maxResults int) ([]string, error) {
	endpoint := fmt.Sprintf(
		"https://api.bing.microsoft.com/v7.0/search?q=%s&count=%d&responseFilter=Webpages",
		url.QueryEscape(query), maxResults,
	)
	req, err := http.NewRequest("GET", endpoint, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Ocp-Apim-Subscription-Key", apiKey)
	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 512*1024))
	return extractURLs(string(body), maxResults), nil
}

// ── URL / domain extraction ───────────────────────────────────────────────────

func extractURLs(body string, max int) []string {
	seen := make(map[string]bool)
	var out []string

	addURL := func(raw string) {
		// Decode DDG redirect URLs: //duckduckgo.com/l/?uddg=https%3A%2F%2F...
		// Also handles inline uddg= params in absolute URLs
		if strings.Contains(raw, "uddg=") {
			if m := uddgRe.FindStringSubmatch(raw); len(m) > 1 {
				decoded, err := url.QueryUnescape(m[1])
				if err == nil {
					raw = decoded
				}
			}
		}
		// Skip search engine internals and noise
		for _, skip := range []string{
			"duckduckgo.com", "bing.com", "microsoft.com",
			"w3.org", "schema.org", "google.com", "yahoo.com",
		} {
			if strings.Contains(raw, skip) {
				return
			}
		}
		if !strings.HasPrefix(raw, "http") {
			return
		}
		if !seen[raw] && len(out) < max {
			seen[raw] = true
			out = append(out, raw)
		}
	}

	// DDG lite uses protocol-relative links: href="//duckduckgo.com/l/?uddg=..."
	// These must be handled before the absolute-URL regex since they don't start with https://
	for _, m := range ddgLiteRe.FindAllStringSubmatch(body, -1) {
		addURL("https:" + m[1])
	}

	// Absolute https:// / http:// href links (direct results, Bing HTML, etc.)
	for _, m := range hrefRe.FindAllStringSubmatch(body, -1) {
		addURL(m[1])
	}

	// JSON URL fields (Bing API, SearXNG, etc.)
	urlRe := regexp.MustCompile(`"url"\s*:\s*"(https?://[^"]+)"`)
	for _, m := range urlRe.FindAllStringSubmatch(body, -1) {
		addURL(m[1])
	}

	return out
}

// isDDGBlocked returns true if DDG returned a CAPTCHA or bot-block page.
func isDDGBlocked(body string) bool {
	lower := strings.ToLower(body)
	return strings.Contains(lower, "unusual traffic") ||
		strings.Contains(lower, "captcha") ||
		strings.Contains(lower, "robot") ||
		(len(body) < 500 && strings.Contains(lower, "duckduckgo"))
}

func extractDomain(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return ""
	}
	host := u.Hostname()
	// Strip port if present
	host = strings.TrimSuffix(host, ":80")
	host = strings.TrimSuffix(host, ":443")
	host = strings.ToLower(strings.TrimSpace(host))
	if !domainRe.MatchString(host) {
		return ""
	}
	return host
}
