package dork

import (
	"encoding/json"
	"encoding/xml"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"
)


var fetchClient = &http.Client{Timeout: 30 * time.Second}

// UpdateResult summarises what was added per source.
type UpdateResult struct {
	Source string
	Added  int
	Error  error
}

// AutoUpdate pulls dorks from all sources and appends new ones to customFile.
// Returns one UpdateResult per source so the caller can log progress.
func AutoUpdate(customFile string) []UpdateResult {
	type sourceFn struct {
		name string
		fn   func() ([]string, error)
	}

	sources := []sourceFn{
		{"ExploitDB GHDB", FetchGHDB},
		{"NVD CVE", FetchNVDDorks},
		{"GitHub Advisories", FetchGitHubAdvisories},
		{"PacketStorm", FetchPacketStorm},
	}

	// Load existing dorks (to avoid duplicates)
	existing := make(map[string]bool)
	if lines, err := LoadFile(customFile); err == nil {
		for _, l := range lines {
			existing[strings.ToLower(strings.TrimSpace(l))] = true
		}
	}

	var results []UpdateResult
	var allNew []string

	for _, src := range sources {
		dorks, err := src.fn()
		res := UpdateResult{Source: src.name, Error: err}
		if err != nil {
			log.Printf("[dork/update] %s error: %v", src.name, err)
			results = append(results, res)
			continue
		}
		for _, d := range dorks {
			d = strings.TrimSpace(d)
			key := strings.ToLower(d)
			if d == "" || existing[key] {
				continue
			}
			existing[key] = true
			allNew = append(allNew, d)
			res.Added++
		}
		log.Printf("[dork/update] %s: +%d new dorks", src.name, res.Added)
		results = append(results, res)
	}

	if len(allNew) > 0 {
		if err := appendDorks(customFile, allNew); err != nil {
			log.Printf("[dork/update] write error: %v", err)
		}
	}

	return results
}

// appendDorks appends dorks to file, creating it if necessary.
func appendDorks(path string, dorks []string) error {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()

	ts := time.Now().UTC().Format("2006-01-02")
	fmt.Fprintf(f, "\n# Auto-updated %s\n", ts)
	for _, d := range dorks {
		fmt.Fprintln(f, d)
	}
	return nil
}

// ── ExploitDB Google Hacking Database ─────────────────────────────────────────

// FetchGHDB downloads dorks from the ExploitDB GHDB JSON API.
// Categories fetched: passwords (5), juicy info (8), files (9), login portals (12),
// vulnerable files (6), vulnerable servers (7).
func FetchGHDB() ([]string, error) {
	// Category IDs most relevant for credential/env hunting
	cats := []int{5, 6, 7, 8, 9, 12}
	seen := make(map[string]bool)
	var out []string

	for _, cat := range cats {
		dorks, err := fetchGHDBCategory(cat)
		if err != nil {
			log.Printf("[ghdb] cat %d: %v", cat, err)
			continue
		}
		for _, d := range dorks {
			if !seen[d] {
				seen[d] = true
				out = append(out, d)
			}
		}
		time.Sleep(2 * time.Second) // be polite
	}
	return out, nil
}

// ghdbEntry is permissive — exploit-db uses varying field names across API versions.
type ghdbEntry struct {
	Date     string `json:"date"`
	URLTitle string `json:"url_title"`
	// Some API versions use "ghdb_dork" or nest the query under "dork"
	Dork     string `json:"ghdb_dork"`
	Category string `json:"category_id"`
}

func (e ghdbEntry) query() string {
	if q := strings.TrimSpace(e.URLTitle); q != "" {
		return q
	}
	if q := strings.TrimSpace(e.Dork); q != "" {
		return q
	}
	return ""
}

type ghdbResponse struct {
	Data         []ghdbEntry `json:"data"`
	RecordsTotal int         `json:"recordsTotal"`
}

func fetchGHDBCategory(cat int) ([]string, error) {
	// Full DataTables v1.10 AJAX format required by exploit-db
	endpoint := fmt.Sprintf(
		"https://www.exploit-db.com/ghdb?draw=1"+
			"&columns%%5B0%%5D%%5Bdata%%5D=date&columns%%5B0%%5D%%5Bname%%5D=date"+
			"&columns%%5B0%%5D%%5Bsearchable%%5D=true&columns%%5B0%%5D%%5Borderable%%5D=true"+
			"&columns%%5B1%%5D%%5Bdata%%5D=url_title&columns%%5B1%%5D%%5Bname%%5D=url_title"+
			"&columns%%5B1%%5D%%5Bsearchable%%5D=true&columns%%5B1%%5D%%5Borderable%%5D=false"+
			"&start=0&length=500&type=0&cat=%d",
		cat,
	)
	req, err := http.NewRequest("GET", endpoint, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("Accept", "application/json, text/javascript, */*; q=0.01")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
	req.Header.Set("Referer", "https://www.exploit-db.com/google-hacking-database")
	req.Header.Set("Accept-Language", "en-US,en;q=0.9")

	resp, err := fetchClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 2*1024*1024))

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("GHDB cat=%d: HTTP %d — %.200s", cat, resp.StatusCode, body)
	}

	var result ghdbResponse
	if err := json.Unmarshal(body, &result); err != nil {
		// If exploit-db changed their API format, extract dorks with a regex fallback
		log.Printf("[ghdb] JSON parse failed for cat=%d (%v) — trying regex fallback", cat, err)
		return ghdbRegexFallback(body), nil
	}

	var dorks []string
	for _, entry := range result.Data {
		q := entry.query()
		if q != "" && looksLikeDork(q) {
			dorks = append(dorks, q)
		}
	}
	log.Printf("[ghdb] cat=%d: %d dorks (recordsTotal=%d)", cat, len(dorks), result.RecordsTotal)
	return dorks, nil
}

// ghdbRegexFallback extracts dork strings directly from raw JSON when the struct parse fails.
func ghdbRegexFallback(body []byte) []string {
	re := regexp.MustCompile(`"(?:url_title|ghdb_dork|query)"\s*:\s*"([^"]{10,300})"`)
	seen := make(map[string]bool)
	var out []string
	for _, m := range re.FindAllSubmatch(body, -1) {
		q := strings.TrimSpace(string(m[1]))
		if q != "" && looksLikeDork(q) && !seen[q] {
			seen[q] = true
			out = append(out, q)
		}
	}
	return out
}

func looksLikeDork(s string) bool {
	keywords := []string{"inurl:", "intext:", "intitle:", "filetype:", "ext:", "site:", "\""}
	for _, kw := range keywords {
		if strings.Contains(strings.ToLower(s), kw) {
			return true
		}
	}
	return false
}

// ── NVD CVE API → auto-generate dorks ────────────────────────────────────────

type nvdResponse struct {
	Vulnerabilities []struct {
		CVE struct {
			ID          string `json:"id"`
			Descriptions []struct {
				Lang  string `json:"lang"`
				Value string `json:"value"`
			} `json:"descriptions"`
			Metrics struct {
				CvssMetricV31 []struct {
					CvssData struct {
						BaseScore float64 `json:"baseScore"`
						BaseSeverity string `json:"baseSeverity"`
					} `json:"cvssData"`
				} `json:"cvssMetricV31"`
			} `json:"metrics"`
		} `json:"cve"`
	} `json:"vulnerabilities"`
}

// FetchNVDDorks pulls recent HIGH/CRITICAL CVEs and generates search dorks.
func FetchNVDDorks() ([]string, error) {
	url := "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=100&cvssV3Severity=HIGH"
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("User-Agent", "env-checker-security-tool/1.0")

	resp, err := fetchClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024))

	var result nvdResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("NVD parse: %w", err)
	}

	seen := make(map[string]bool)
	var dorks []string

	addDork := func(d string) {
		d = strings.TrimSpace(d)
		if d != "" && !seen[d] {
			seen[d] = true
			dorks = append(dorks, d)
		}
	}

	for _, item := range result.Vulnerabilities {
		desc := ""
		for _, d := range item.CVE.Descriptions {
			if d.Lang == "en" {
				desc = d.Value
				break
			}
		}
		if desc == "" {
			continue
		}
		for _, d := range cveToDoorks(item.CVE.ID, desc) {
			addDork(d)
		}
	}
	return dorks, nil
}

// cveToDoorks generates search dorks from a CVE description.
func cveToDoorks(id, desc string) []string {
	desc = strings.ToLower(desc)
	var out []string

	// WordPress plugin pattern
	if wpRe := regexp.MustCompile(`wordpress plugin[:\s]+"?([a-z0-9\s\-_]{3,40})"?`); true {
		if m := wpRe.FindStringSubmatch(desc); len(m) > 1 {
			slug := strings.ReplaceAll(strings.TrimSpace(m[1]), " ", "-")
			out = append(out, fmt.Sprintf(`inurl:"/wp-content/plugins/%s"`, slug))
		}
	}

	// Joomla component
	if strings.Contains(desc, "joomla") {
		if m := regexp.MustCompile(`component[:\s]+"?com_([a-z0-9_]{3,30})"?`).FindStringSubmatch(desc); len(m) > 1 {
			out = append(out, fmt.Sprintf(`inurl:"option=com_%s"`, m[1]))
		}
	}

	// File disclosure / path traversal
	if strings.Contains(desc, "path traversal") || strings.Contains(desc, "directory traversal") ||
		strings.Contains(desc, "local file inclusion") {
		// Try to extract the vulnerable path
		if m := regexp.MustCompile(`(/[a-z0-9_/\-\.]+\.php)`).FindString(desc); m != "" {
			out = append(out, fmt.Sprintf(`inurl:"%s"`, m))
		}
	}

	// Unauthenticated access to admin/api
	if strings.Contains(desc, "unauthenticated") || strings.Contains(desc, "without authentication") {
		if m := regexp.MustCompile(`(/api/[a-z0-9_/\-]+)`).FindString(desc); m != "" {
			out = append(out, fmt.Sprintf(`inurl:"%s" "%s"`, m, id))
		}
	}

	// Exposed configuration / info disclosure
	if strings.Contains(desc, "information disclosure") || strings.Contains(desc, "sensitive information") {
		if strings.Contains(desc, ".env") {
			out = append(out, `inurl:"/.env" "`+id+`"`)
		}
		if strings.Contains(desc, "phpinfo") {
			out = append(out, `filetype:php intext:"phpinfo()"`)
		}
	}

	// Default credentials
	if strings.Contains(desc, "default password") || strings.Contains(desc, "default credential") {
		if m := regexp.MustCompile(`(?:in|for)\s+([A-Za-z0-9\s]{3,25})\s+(?:panel|interface|console|dashboard)`).FindStringSubmatch(desc); len(m) > 1 {
			product := strings.TrimSpace(m[1])
			out = append(out, fmt.Sprintf(`intitle:"%s" intext:"login"`, product))
		}
	}

	return out
}

// ── GitHub Security Advisories ────────────────────────────────────────────────

type ghAdvisory struct {
	GHSAID      string   `json:"ghsa_id"`
	Summary     string   `json:"summary"`
	Severity    string   `json:"severity"`
	References  []struct {
		URL string `json:"url"`
	} `json:"references"`
	Vulnerabilities []struct {
		Package struct {
			Ecosystem string `json:"ecosystem"`
			Name      string `json:"name"`
		} `json:"package"`
	} `json:"vulnerabilities"`
}

// FetchGitHubAdvisories fetches recent HIGH/CRITICAL advisories and generates dorks.
func FetchGitHubAdvisories() ([]string, error) {
	url := "https://api.github.com/advisories?type=reviewed&per_page=100&direction=desc&sort=published"
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	req.Header.Set("User-Agent", "env-checker-security-tool/1.0")

	resp, err := fetchClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 2*1024*1024))

	var advisories []ghAdvisory
	if err := json.Unmarshal(body, &advisories); err != nil {
		return nil, fmt.Errorf("GitHub advisories parse: %w", err)
	}

	seen := make(map[string]bool)
	var dorks []string

	for _, adv := range advisories {
		if adv.Severity != "high" && adv.Severity != "critical" {
			continue
		}
		for _, vuln := range adv.Vulnerabilities {
			eco := strings.ToLower(vuln.Package.Ecosystem)
			name := vuln.Package.Name

			switch eco {
			case "composer", "packagist":
				// PHP package — likely has a web path
				parts := strings.SplitN(name, "/", 2)
				if len(parts) == 2 {
					dork := fmt.Sprintf(`inurl:"/vendor/%s/%s"`, parts[0], parts[1])
					if !seen[dork] {
						seen[dork] = true
						dorks = append(dorks, dork)
					}
				}
			case "npm":
				dork := fmt.Sprintf(`inurl:"/node_modules/%s"`, name)
				if !seen[dork] {
					seen[dork] = true
					dorks = append(dorks, dork)
				}
			case "pip", "pypi":
				dork := fmt.Sprintf(`inurl:"requirements.txt" intext:"%s"`, name)
				if !seen[dork] {
					seen[dork] = true
					dorks = append(dorks, dork)
				}
			}

			// Site:github.com search for configs using the package
			if eco != "" && name != "" {
				dork := fmt.Sprintf(`site:github.com filename:.env intext:"%s"`, name)
				if !seen[dork] {
					seen[dork] = true
					dorks = append(dorks, dork)
				}
			}
		}
	}
	return dorks, nil
}

// ── PacketStorm Security RSS ──────────────────────────────────────────────────

type rssChannel struct {
	Items []struct {
		Title       string `xml:"title"`
		Description string `xml:"description"`
		Link        string `xml:"link"`
	} `xml:"channel>item"`
}

// FetchPacketStorm pulls recent PacketStorm advisories and extracts product names
// to generate targeted search dorks.
func FetchPacketStorm() ([]string, error) {
	feeds := []string{
		"https://packetstormsecurity.com/rss.xml",
		"https://packetstormsecurity.com/files/tags/exploit/rss.xml",
	}

	seen := make(map[string]bool)
	var dorks []string

	for _, feedURL := range feeds {
		req, _ := http.NewRequest("GET", feedURL, nil)
		req.Header.Set("User-Agent", "env-checker-security-tool/1.0")
		resp, err := fetchClient.Do(req)
		if err != nil {
			log.Printf("[packetstorm] %s: %v", feedURL, err)
			continue
		}
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1*1024*1024))
		resp.Body.Close()

		var feed rssChannel
		if err := xml.Unmarshal(body, &feed); err != nil {
			log.Printf("[packetstorm] parse %s: %v", feedURL, err)
			continue
		}

		for _, item := range feed.Items {
			for _, d := range packetstormToDorks(item.Title, item.Description) {
				if !seen[d] {
					seen[d] = true
					dorks = append(dorks, d)
				}
			}
		}
		time.Sleep(1 * time.Second)
	}
	return dorks, nil
}

func packetstormToDorks(title, desc string) []string {
	var out []string
	t := strings.ToLower(title)
	d := strings.ToLower(desc)

	// Remote file inclusion / file read
	if strings.Contains(t, "file read") || strings.Contains(d, "arbitrary file read") {
		if m := pathRe.FindString(t + " " + d); m != "" {
			out = append(out, fmt.Sprintf(`inurl:"%s"`, m))
		}
	}

	// SQL injection
	if strings.Contains(t, "sql injection") || strings.Contains(d, "sql injection") {
		if product := extractProduct(t); product != "" {
			out = append(out, fmt.Sprintf(`inurl:"%s" intext:"sql"`, product))
		}
	}

	// Default/exposed admin
	if strings.Contains(t, "default") && strings.Contains(t, "password") {
		if product := extractProduct(t); product != "" {
			out = append(out, fmt.Sprintf(`intitle:"%s" "login"`, product))
		}
	}

	// WordPress specific
	if strings.Contains(t, "wordpress") || strings.Contains(t, "wp-") {
		if m := wpPluginRe.FindStringSubmatch(t); len(m) > 1 {
			slug := strings.ReplaceAll(strings.TrimSpace(m[1]), " ", "-")
			out = append(out, fmt.Sprintf(`inurl:"/wp-content/plugins/%s"`, slug))
		}
	}

	// Configuration / environment exposure
	if strings.Contains(d, ".env") || strings.Contains(t, "env exposure") {
		out = append(out, `inurl:"/.env" intext:"APP_"`)
	}

	return out
}

var (
	pathRe      = regexp.MustCompile(`/[a-z0-9_/\-]{3,40}\.(?:php|asp|aspx|jsp|py|rb)`)
	wpPluginRe  = regexp.MustCompile(`wordpress\s+(?:plugin\s+)?([a-z0-9\s\-_]{3,30})\s`)
	productNameRe = regexp.MustCompile(`^([a-z0-9][a-z0-9\s\-_]{2,20})\s+(?:v[\d.]+\s+)?(?:sql|rce|xss|lfi|rfi|auth|default)`)
)

func extractProduct(title string) string {
	if m := productNameRe.FindStringSubmatch(title); len(m) > 1 {
		return strings.TrimSpace(m[1])
	}
	return ""
}
