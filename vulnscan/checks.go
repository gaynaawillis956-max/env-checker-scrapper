package vulnscan

import (
	"fmt"
	"net"
	"net/http"
	"regexp"
	"strings"
)

// ── CORS misconfiguration ─────────────────────────────────────────────────────

func checkCORS(host string) []Finding {
	var out []Finding
	for _, base := range baseURLs(host) {
		code, hdrs, _, err := get(base, map[string]string{
			"Origin": "https://evil.com",
		})
		if err != nil || code == 0 {
			continue
		}
		acao := hdrs.Get("Access-Control-Allow-Origin")
		acac := hdrs.Get("Access-Control-Allow-Credentials")
		if acao == "*" {
			out = append(out, f(host, base, "cors-wildcard",
				"CORS: Wildcard Origin (*)",
				Medium,
				fmt.Sprintf("Access-Control-Allow-Origin: %s", acao),
				"Any website can make credentialed cross-origin requests. Report as CORS misconfiguration."))
		} else if strings.Contains(acao, "evil.com") {
			sev := Medium
			detail := "Origin is reflected — CORS allows arbitrary domains."
			if strings.ToLower(acac) == "true" {
				sev = High
				detail = "Origin reflected AND credentials allowed — full CORS bypass, session hijack possible."
			}
			out = append(out, f(host, base, "cors-reflect",
				"CORS: Reflected Origin with Credentials",
				sev,
				fmt.Sprintf("ACAO: %s | ACAC: %s", acao, acac),
				detail))
		}
		break
	}
	return out
}

// ── Exposed .git repository ───────────────────────────────────────────────────

func checkGitExposed(host string) []Finding {
	var out []Finding
	for _, base := range baseURLs(host) {
		url := base + "/.git/config"
		code, _, body, err := get(url, nil)
		if err != nil || code != 200 {
			continue
		}
		bs := string(body)
		if !strings.Contains(bs, "[core]") && !strings.Contains(bs, "[remote") {
			continue
		}
		evidence := snippet(body, 300)
		detail := "Full source code may be downloadable. Credentials in git history are accessible. Run `git clone` against this host. Report as sensitive data exposure."
		// Check if git config contains credentials
		if strings.Contains(bs, "://") && (strings.Contains(bs, "@") || strings.Contains(bs, "token")) {
			out = append(out, f(host, url, "git-credentials",
				"Exposed .git: Credentials in Config",
				Critical, evidence, "Git remote URL contains embedded credentials. Extract with: git clone "+base+"/.git"))
		} else {
			out = append(out, f(host, url, "git-exposed",
				"Exposed .git Repository",
				High, evidence, detail))
		}
		break
	}
	return out
}

// ── Spring Boot Actuator ──────────────────────────────────────────────────────

var actuatorPaths = []string{
	"/actuator/env",
	"/actuator/configprops",
	"/actuator/mappings",
	"/actuator/httptrace",
	"/actuator/heapdump",
	"/env",
	"/metrics",
	"/health",
	"/dump",
	"/trace",
	"/configprops",
}

func checkActuator(host string) []Finding {
	var out []Finding
	for _, base := range baseURLs(host) {
		for _, path := range actuatorPaths {
			url := base + path
			code, _, body, err := get(url, nil)
			if err != nil || code != 200 {
				continue
			}
			bs := string(body)
			// Must look like Spring JSON
			if !strings.Contains(bs, `"status"`) && !strings.Contains(bs, `"propertySources"`) &&
				!strings.Contains(bs, `"beans"`) && !strings.Contains(bs, `"mappings"`) {
				continue
			}
			sev := Medium
			title := "Spring Boot Actuator Exposed: " + path
			detail := "Actuator endpoints leak internal app info. /env can expose passwords, DB URLs, API keys."
			if path == "/actuator/env" || path == "/env" {
				sev = Critical
				detail = "Actuator /env exposes ALL environment variables including passwords, tokens, DB credentials."
			}
			if path == "/actuator/heapdump" || path == "/dump" {
				sev = Critical
				detail = "Heap dump exposes full JVM memory — passwords, sessions, private keys in plaintext."
			}
			out = append(out, f(host, url, "actuator", title, sev, snippet(body, 400), detail))
		}
		break
	}
	return out
}

// ── Admin panel discovery ─────────────────────────────────────────────────────

var adminPaths = []string{
	"/admin", "/administrator", "/admin/login", "/admin.php",
	"/wp-admin", "/wp-admin/", "/wp-login.php",
	"/phpmyadmin", "/phpmyadmin/", "/pma", "/mysql",
	"/adminer", "/adminer.php", "/adminer-4.8.1.php",
	"/cpanel", "/whm", "/webmail",
	"/manager/html", "/manager/status", // Tomcat
	"/console", "/h2-console",          // H2 database
	"/solr", "/solr/admin",
	"/kibana", "/elastic",
	"/jenkins", "/jenkins/login",
	"/gitlab",
	"/portainer",
	"/grafana",
	"/prometheus",
	"/_admin", "/backend", "/panel",
}

func checkAdminPanels(host string) []Finding {
	var out []Finding
	for _, base := range baseURLs(host) {
		for _, path := range adminPaths {
			url := base + path
			code, _, body, err := get(url, nil)
			if err != nil {
				continue
			}
			if code != 200 && code != 401 && code != 403 {
				continue
			}
			bs := strings.ToLower(string(body))
			// confirm it looks like a real admin panel
			keywords := []string{"login", "password", "username", "admin", "dashboard",
				"sign in", "phpmyadmin", "console", "manager", "jenkins", "grafana"}
			matched := false
			for _, kw := range keywords {
				if strings.Contains(bs, kw) {
					matched = true
					break
				}
			}
			if !matched && code == 200 {
				continue
			}
			sev := Medium
			if code == 200 {
				sev = High
			}
			out = append(out, f(host, url, "admin-panel",
				fmt.Sprintf("Admin Panel Exposed: %s (HTTP %d)", path, code),
				sev,
				fmt.Sprintf("HTTP %d — %s", code, snippet(body, 200)),
				"Admin interface is publicly reachable. Test for default credentials. Report as exposed admin panel."))
		}
		break
	}
	return out
}

// ── phpinfo() exposure ────────────────────────────────────────────────────────

var phpinfoPaths = []string{
	"/phpinfo.php", "/info.php", "/php_info.php",
	"/test.php", "/i.php", "/phi.php",
	"/?=phpinfo()", "/index.php?=phpinfo()",
}

func checkPHPInfo(host string) []Finding {
	var out []Finding
	for _, base := range baseURLs(host) {
		for _, path := range phpinfoPaths {
			url := base + path
			code, _, body, err := get(url, nil)
			if err != nil || code != 200 {
				continue
			}
			bs := string(body)
			if strings.Contains(bs, "PHP Version") && strings.Contains(bs, "PHP Credits") {
				out = append(out, f(host, url, "phpinfo",
					"phpinfo() Page Exposed",
					Medium,
					snippet(body, 300),
					"Exposes PHP version, server paths, loaded extensions, environment variables. Report as information disclosure."))
				break
			}
		}
		break
	}
	return out
}

// ── Directory listing ─────────────────────────────────────────────────────────

var dirListingPaths = []string{
	"/", "/images/", "/uploads/", "/files/",
	"/backup/", "/backups/", "/logs/", "/tmp/",
	"/assets/", "/static/", "/public/",
	"/wp-content/uploads/",
}

func checkDirListing(host string) []Finding {
	var out []Finding
	for _, base := range baseURLs(host) {
		for _, path := range dirListingPaths {
			url := base + path
			code, _, body, err := get(url, nil)
			if err != nil || code != 200 {
				continue
			}
			bs := string(body)
			if strings.Contains(bs, "Index of /") || strings.Contains(bs, "Directory listing for") ||
				strings.Contains(bs, "Parent Directory") {
				out = append(out, f(host, url, "dir-listing",
					"Directory Listing Enabled: "+path,
					Medium,
					snippet(body, 400),
					"Web server exposes file listings. Attacker can enumerate and download source code, backups, configs."))
			}
		}
		break
	}
	return out
}

// ── Open redirect ─────────────────────────────────────────────────────────────

var redirectParams = []string{
	"redirect", "url", "next", "return", "returnUrl", "returnTo",
	"goto", "destination", "redir", "r", "u", "link", "target",
}

func checkOpenRedirect(host string) []Finding {
	var out []Finding
	payload := "https://evil.com"
	for _, base := range baseURLs(host) {
		for _, param := range redirectParams {
			url := fmt.Sprintf("%s/?%s=%s", base, param, payload)
			code, hdrs, _, err := get(url, nil)
			if err != nil {
				continue
			}
			if code >= 300 && code < 400 {
				loc := hdrs.Get("Location")
				if strings.Contains(loc, "evil.com") {
					out = append(out, f(host, url, "open-redirect",
						"Open Redirect via ?"+param,
						Medium,
						fmt.Sprintf("HTTP %d Location: %s", code, loc),
						"Redirect parameter reflects attacker-controlled URL. Used for phishing, OAuth token theft. Report as open redirect."))
					return out
				}
			}
		}
		break
	}
	return out
}

// ── GraphQL introspection ─────────────────────────────────────────────────────

var graphqlPaths = []string{"/graphql", "/api/graphql", "/graphql/console", "/v1/graphql"}

var graphqlQuery = `{"query":"{__schema{types{name}}}"}`

func checkGraphQL(host string) []Finding {
	var out []Finding
	for _, base := range baseURLs(host) {
		for _, path := range graphqlPaths {
			url := base + path
			req, err := newPost(url, graphqlQuery)
			if err != nil {
				continue
			}
			resp, err := client.Do(req)
			if err != nil {
				continue
			}
			resp.Body.Close()
			if resp.StatusCode == 200 {
				out = append(out, f(host, url, "graphql-introspection",
					"GraphQL Introspection Enabled",
					Low,
					fmt.Sprintf("POST %s → HTTP 200", url),
					"GraphQL introspection exposes full API schema — all types, queries, mutations. Attackers can map the entire API surface. Disable introspection in production."))
				break
			}
		}
		break
	}
	return out
}

// ── Laravel / Symfony debug ───────────────────────────────────────────────────

var debugPaths = []string{
	"/telescope/requests",   // Laravel Telescope
	"/_ignition/health-check", // Ignition error page
	"/_profiler",            // Symfony profiler
	"/_debugbar",            // PHP Debugbar
	"/horizon/api/stats",    // Laravel Horizon
	"/clockwork/app",        // Clockwork
}

func checkDebugEndpoints(host string) []Finding {
	var out []Finding
	for _, base := range baseURLs(host) {
		for _, path := range debugPaths {
			url := base + path
			code, _, body, err := get(url, nil)
			if err != nil || code != 200 {
				continue
			}
			bs := strings.ToLower(string(body))
			if len(bs) < 50 {
				continue
			}
			keywords := map[string]string{
				"telescope":  "Laravel Telescope",
				"ignition":   "Laravel Ignition",
				"_profiler":  "Symfony Profiler",
				"debugbar":   "PHP Debugbar",
				"horizon":    "Laravel Horizon",
				"clockwork":  "Clockwork Profiler",
			}
			for kw, name := range keywords {
				if strings.Contains(path, kw) || strings.Contains(bs, kw) {
					out = append(out, f(host, url, "debug-panel",
						name+" Exposed",
						High,
						snippet(body, 300),
						name+" exposes all SQL queries, request data, environment variables, and session data. Critical info for attackers."))
					break
				}
			}
		}
		break
	}
	return out
}

// ── Subdomain takeover ────────────────────────────────────────────────────────

// Fingerprints: service name → response body substring indicating unclaimed
var takeoverFingerprints = map[string]string{
	"GitHub Pages":    "There isn't a GitHub Pages site here",
	"Heroku":          "No such app",
	"Fastly":          "Fastly error: unknown domain",
	"Ghost":           "The thing you were looking for is no longer here",
	"Pantheon":        "The gods are wise, but do not know of the site which you seek",
	"Zendesk":         "Help Center Closed",
	"Shopify":         "Sorry, this shop is currently unavailable",
	"Tumblr":          "Whatever you were looking for doesn't currently exist",
	"WP Engine":       "The site you were looking for couldn't be found",
	"Fly.io":          "404 Not Found",
	"Surge.sh":        "project not found",
	"Unbounce":        "The requested URL was not found on this server",
	"Readme.io":       "Project doesnt exist",
	"Cargo":           "If you're moving your domain away from Cargo",
	"Tilda":           "Please renew your subscription",
}

func checkSubdomainTakeover(host string) []Finding {
	var out []Finding

	// Must be a subdomain (at least 3 parts)
	parts := strings.Split(host, ".")
	if len(parts) < 3 {
		return nil
	}

	// Check CNAME chain
	cnames, err := net.LookupCNAME(host)
	if err != nil || cnames == host+"." {
		return nil
	}

	// Probe HTTP response for takeover fingerprints
	for _, base := range baseURLs(host) {
		_, _, body, err := get(base, nil)
		if err != nil {
			continue
		}
		bs := string(body)
		for svc, fp := range takeoverFingerprints {
			if strings.Contains(bs, fp) {
				out = append(out, f(host, base, "subdomain-takeover",
					"Subdomain Takeover via "+svc,
					High,
					fmt.Sprintf("CNAME: %s\nFingerprint: %s", cnames, fp),
					fmt.Sprintf("DNS points to %s but the resource is unclaimed. Register the %s project to take over this subdomain. High-severity bug bounty finding.", svc, svc)))
				return out
			}
		}
		break
	}
	return out
}

// ── JS file API key scanning ──────────────────────────────────────────────────

var keyPatterns = map[string]*regexp.Regexp{
	"AWS Access Key":    regexp.MustCompile(`AKIA[0-9A-Z]{16}`),
	"AWS Secret Key":    regexp.MustCompile(`[0-9a-zA-Z/+]{40}`),
	"Stripe Secret":     regexp.MustCompile(`sk_live_[0-9a-zA-Z]{24}`),
	"Stripe Publishable":regexp.MustCompile(`pk_live_[0-9a-zA-Z]{24}`),
	"SendGrid Key":      regexp.MustCompile(`SG\.[a-zA-Z0-9_\-]{22,}\.[a-zA-Z0-9_\-]{43,}`),
	"GitHub Token":      regexp.MustCompile(`ghp_[A-Za-z0-9]{36}`),
	"GitHub OAuth":      regexp.MustCompile(`gho_[A-Za-z0-9]{36}`),
	"Slack Token":       regexp.MustCompile(`xox[baprs]-[0-9A-Za-z\-]{10,48}`),
	"Twilio SID":        regexp.MustCompile(`AC[0-9a-fA-F]{32}`),
	"OpenAI Key":        regexp.MustCompile(`sk-[A-Za-z0-9]{48}`),
	"Mailchimp Key":     regexp.MustCompile(`[0-9a-f]{32}-us[0-9]{1,2}`),
	"Firebase URL":      regexp.MustCompile(`https://[a-z0-9\-]+\.firebaseio\.com`),
	"Private Key Header":regexp.MustCompile(`-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----`),
}

var jsExtensions = []string{".js", "/bundle.js", "/app.js", "/main.js", "/vendor.js", "/chunk.js"}

func checkJSKeys(host string) []Finding {
	var out []Finding
	jsPaths := []string{
		"/static/js/main.chunk.js", "/static/js/bundle.js",
		"/js/app.js", "/js/main.js", "/js/vendor.js",
		"/assets/application.js", "/assets/app.js",
		"/build/bundle.js", "/dist/bundle.js",
		"/wp-includes/js/jquery/jquery.min.js", // skip known libraries
	}

	_ = jsExtensions // suppress unused warning

	for _, base := range baseURLs(host) {
		for _, path := range jsPaths {
			if strings.Contains(path, "jquery") {
				continue // skip known safe libraries
			}
			url := base + path
			code, hdrs, body, err := get(url, nil)
			if err != nil || code != 200 {
				continue
			}
			ct := hdrs.Get("Content-Type")
			if !strings.Contains(ct, "javascript") && !strings.Contains(ct, "text") {
				continue
			}
			bs := string(body)
			for keyName, re := range keyPatterns {
				match := re.FindString(bs)
				if match == "" {
					continue
				}
				// truncate key for display
				display := match
				if len(display) > 20 {
					display = display[:8] + "..." + display[len(display)-4:]
				}
				out = append(out, f(host, url, "js-api-key",
					"API Key Exposed in JavaScript: "+keyName,
					High,
					fmt.Sprintf("%s: %s", keyName, display),
					"Hardcoded API key found in public JavaScript file. Extract and validate it. Report as sensitive data exposure."))
			}
		}
		break
	}
	return out
}

// ── Backup config files ───────────────────────────────────────────────────────

var backupPaths = []string{
	"/.env.bak", "/.env.backup", "/.env.old", "/.env.save",
	"/.env~", "/.env.1", "/.env.2",
	"/config.php.bak", "/wp-config.php.bak",
	"/database.yml.bak", "/database.php.bak",
	"/settings.py.bak", "/config.js.bak",
	"/web.config.bak",
	"/.htpasswd", "/.htpasswd.bak",
	"/id_rsa", "/id_rsa.pub",
	"/.ssh/id_rsa",
	"/server.key", "/server.crt", "/ssl.key",
}

func checkBackupFiles(host string) []Finding {
	var out []Finding
	for _, base := range baseURLs(host) {
		for _, path := range backupPaths {
			url := base + path
			code, _, body, err := get(url, nil)
			if err != nil || code != 200 || len(body) < 10 {
				continue
			}
			bs := string(body)
			sev := Medium
			detail := "Backup configuration file exposed. May contain credentials, API keys, or database passwords."

			if strings.Contains(path, "id_rsa") || strings.Contains(path, ".key") || strings.Contains(bs, "PRIVATE KEY") {
				sev = Critical
				detail = "Private key exposed. Attacker can decrypt traffic or impersonate the server."
			} else if strings.Contains(path, ".env") {
				sev = High
				detail = "Backup .env file exposed. Contains application secrets, DB credentials, API keys."
			} else if strings.Contains(path, ".htpasswd") {
				sev = High
				detail = "Apache .htpasswd exposed — contains hashed credentials that can be cracked."
			}
			out = append(out, f(host, url, "backup-file",
				"Exposed Backup File: "+path,
				sev, snippet(body, 300), detail))
		}
		break
	}
	return out
}

// ── Server status / info ──────────────────────────────────────────────────────

func checkServerStatus(host string) []Finding {
	var out []Finding
	checks := map[string]string{
		"/server-status":          "Apache Server Status",
		"/server-info":            "Apache Server Info",
		"/nginx_status":           "Nginx Status",
		"/.well-known/security.txt": "", // not a vuln, skip
	}
	for _, base := range baseURLs(host) {
		for path, name := range checks {
			if name == "" {
				continue
			}
			url := base + path
			code, _, body, err := get(url, nil)
			if err != nil || code != 200 {
				continue
			}
			bs := string(body)
			if path == "/server-status" && !strings.Contains(bs, "Apache") && !strings.Contains(bs, "Server") {
				continue
			}
			if path == "/nginx_status" && !strings.Contains(bs, "Active connections") {
				continue
			}
			out = append(out, f(host, url, "server-status",
				name+" Exposed",
				Low,
				snippet(body, 300),
				"Server status page exposes internal info: worker count, request rates, connected IPs, server version."))
		}
		break
	}
	return out
}

// ── helpers ───────────────────────────────────────────────────────────────────

func newPost(url, body string) (*http.Request, error) {
	req, err := http.NewRequest("POST", url, strings.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; SecurityScanner/1.0)")
	return req, nil
}
