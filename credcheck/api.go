package credcheck

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

var httpClient = &http.Client{Timeout: 12 * time.Second}

// APIResult is the generic outcome of an API token check.
type APIResult struct {
	Valid   bool
	Info    string // account name, email, plan, etc.
	Message string
	Error   string
}

func apiGet(url, authHeader string) (int, []byte, error) {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("Authorization", authHeader)
	req.Header.Set("User-Agent", "env-checker-credcheck/1.0")
	resp, err := httpClient.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 64*1024))
	return resp.StatusCode, body, nil
}

// ── SendGrid ──────────────────────────────────────────────────────────────────

func CheckSendGrid(apiKey string) APIResult {
	if apiKey == "" {
		return APIResult{Message: "no SendGrid key"}
	}
	code, body, err := apiGet("https://api.sendgrid.com/v3/user/profile", "Bearer "+apiKey)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var v struct {
			Username string `json:"username"`
			Email    string `json:"email"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("user=%s email=%s", v.Username, v.Email),
			Message: fmt.Sprintf("✓ VALID SendGrid — %s <%s>", v.Username, v.Email),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ SendGrid HTTP %d", code)}
}

// ── Mailgun ───────────────────────────────────────────────────────────────────

func CheckMailgun(apiKey, domain string) APIResult {
	if apiKey == "" {
		return APIResult{Message: "no Mailgun key"}
	}
	// GET /v3/domains — lists all domains for the account
	req, _ := http.NewRequest("GET", "https://api.mailgun.net/v3/domains", nil)
	req.SetBasicAuth("api", apiKey)
	req.Header.Set("User-Agent", "env-checker-credcheck/1.0")
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			TotalCount int `json:"total_count"`
			Items      []struct {
				Name string `json:"name"`
			} `json:"items"`
		}
		_ = json.Unmarshal(body, &v)
		names := make([]string, 0, len(v.Items))
		for _, it := range v.Items {
			names = append(names, it.Name)
		}
		return APIResult{
			Valid:   true,
			Info:    strings.Join(names, ", "),
			Message: fmt.Sprintf("✓ VALID Mailgun — %d domain(s): %s", v.TotalCount, strings.Join(names, ", ")),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Mailgun HTTP %d", resp.StatusCode)}
}

// ── Postmark ──────────────────────────────────────────────────────────────────

func CheckPostmark(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no Postmark token"}
	}
	req, _ := http.NewRequest("GET", "https://api.postmarkapp.com/server", nil)
	req.Header.Set("X-Postmark-Server-Token", token)
	req.Header.Set("Accept", "application/json")
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			Name string `json:"Name"`
			ID   int    `json:"ID"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("server=%s id=%d", v.Name, v.ID),
			Message: fmt.Sprintf("✓ VALID Postmark — server: %s", v.Name),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Postmark HTTP %d", resp.StatusCode)}
}

// ── SparkPost ─────────────────────────────────────────────────────────────────

func CheckSparkPost(apiKey string) APIResult {
	if apiKey == "" {
		return APIResult{Message: "no SparkPost key"}
	}
	code, body, err := apiGet("https://api.sparkpost.com/api/v1/account", "Bearer "+apiKey)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var v struct {
			Results struct {
				CompanyName string `json:"company_name"`
				Email       string `json:"email"`
			} `json:"results"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    v.Results.CompanyName,
			Message: fmt.Sprintf("✓ VALID SparkPost — company=%s email=%s", v.Results.CompanyName, v.Results.Email),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ SparkPost HTTP %d", code)}
}

// ── Stripe ────────────────────────────────────────────────────────────────────

func CheckStripe(key string) APIResult {
	if key == "" {
		return APIResult{Message: "no Stripe key"}
	}
	req, _ := http.NewRequest("GET", "https://api.stripe.com/v1/balance", nil)
	req.SetBasicAuth(key, "")
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			Available []struct {
				Amount   int    `json:"amount"`
				Currency string `json:"currency"`
			} `json:"available"`
		}
		_ = json.Unmarshal(body, &v)
		info := ""
		if len(v.Available) > 0 {
			info = fmt.Sprintf("%s %d", strings.ToUpper(v.Available[0].Currency), v.Available[0].Amount)
		}
		return APIResult{
			Valid:   true,
			Info:    info,
			Message: fmt.Sprintf("✓ VALID Stripe — balance: %s", info),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Stripe HTTP %d", resp.StatusCode)}
}

// ── GitHub ────────────────────────────────────────────────────────────────────

func CheckGitHub(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no GitHub token"}
	}
	code, body, err := apiGet("https://api.github.com/user", "token "+token)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var v struct {
			Login string `json:"login"`
			Name  string `json:"name"`
			Email string `json:"email"`
			Type  string `json:"type"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    v.Login,
			Message: fmt.Sprintf("✓ VALID GitHub — @%s (%s)", v.Login, v.Name),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ GitHub token HTTP %d", code)}
}

// ── Mailchimp ─────────────────────────────────────────────────────────────────

func CheckMailchimp(apiKey string) APIResult {
	if apiKey == "" {
		return APIResult{Message: "no Mailchimp key"}
	}
	// Data center is the suffix after the last dash: abc123-us1 → us1
	parts := strings.Split(apiKey, "-")
	if len(parts) < 2 {
		return APIResult{Valid: false, Message: "✗ Mailchimp key format invalid"}
	}
	dc := parts[len(parts)-1]
	url := fmt.Sprintf("https://%s.api.mailchimp.com/3.0/", dc)
	req, _ := http.NewRequest("GET", url, nil)
	req.SetBasicAuth("anystring", apiKey)
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			AccountName string `json:"account_name"`
			Email       string `json:"email"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    v.AccountName,
			Message: fmt.Sprintf("✓ VALID Mailchimp — account=%s email=%s", v.AccountName, v.Email),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Mailchimp HTTP %d", resp.StatusCode)}
}
