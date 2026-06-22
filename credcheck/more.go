package credcheck

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

// ── Twilio ────────────────────────────────────────────────────────────────────

type TwilioResult struct {
	Valid      bool
	AccountSID string
	FriendlyName string
	Message    string
	Error      string
}

func CheckTwilio(sid, token string) TwilioResult {
	if sid == "" || token == "" {
		return TwilioResult{Message: "no Twilio credentials"}
	}
	apiURL := fmt.Sprintf("https://api.twilio.com/2010-04-01/Accounts/%s.json", sid)
	req, _ := http.NewRequest("GET", apiURL, nil)
	req.SetBasicAuth(sid, token)
	resp, err := httpClient.Do(req)
	if err != nil {
		return TwilioResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			FriendlyName string `json:"friendly_name"`
			Status       string `json:"status"`
			Type         string `json:"type"`
		}
		_ = json.Unmarshal(body, &v)
		return TwilioResult{
			Valid:        true,
			AccountSID:   sid,
			FriendlyName: v.FriendlyName,
			Message:      fmt.Sprintf("✓ VALID Twilio — %s (%s)", v.FriendlyName, v.Status),
		}
	}
	return TwilioResult{Valid: false, Message: fmt.Sprintf("✗ Twilio HTTP %d", resp.StatusCode)}
}

// ── Slack ─────────────────────────────────────────────────────────────────────

func CheckSlack(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no Slack token"}
	}
	data := url.Values{"token": {token}}
	resp, err := httpClient.PostForm("https://slack.com/api/auth.test", data)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var v struct {
		OK    bool   `json:"ok"`
		Team  string `json:"team"`
		User  string `json:"user"`
		Error string `json:"error"`
	}
	_ = json.Unmarshal(body, &v)
	if v.OK {
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("team=%s user=%s", v.Team, v.User),
			Message: fmt.Sprintf("✓ VALID Slack — team=%s user=%s", v.Team, v.User),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Slack: %s", v.Error)}
}

// ── OpenAI ────────────────────────────────────────────────────────────────────

func CheckOpenAI(key string) APIResult {
	if key == "" {
		return APIResult{Message: "no OpenAI key"}
	}
	code, body, err := apiGet("https://api.openai.com/v1/models", "Bearer "+key)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var v struct {
			Data []struct{ ID string `json:"id"` } `json:"data"`
		}
		_ = json.Unmarshal(body, &v)
		count := len(v.Data)
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("%d models available", count),
			Message: fmt.Sprintf("✓ VALID OpenAI — %d models accessible", count),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ OpenAI HTTP %d", code)}
}

// ── Cloudflare ────────────────────────────────────────────────────────────────

func CheckCloudflare(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no Cloudflare token"}
	}
	code, body, err := apiGet("https://api.cloudflare.com/client/v4/user", "Bearer "+token)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var v struct {
			Result struct {
				Email    string `json:"email"`
				Username string `json:"username"`
				ID       string `json:"id"`
			} `json:"result"`
			Success bool `json:"success"`
		}
		_ = json.Unmarshal(body, &v)
		if v.Success {
			return APIResult{
				Valid:   true,
				Info:    v.Result.Email,
				Message: fmt.Sprintf("✓ VALID Cloudflare — %s (%s)", v.Result.Email, v.Result.Username),
			}
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Cloudflare HTTP %d", code)}
}

// ── DigitalOcean ──────────────────────────────────────────────────────────────

func CheckDigitalOcean(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no DigitalOcean token"}
	}
	code, body, err := apiGet("https://api.digitalocean.com/v2/account", "Bearer "+token)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var v struct {
			Account struct {
				Email     string `json:"email"`
				DropletLimit int `json:"droplet_limit"`
				Status    string `json:"status"`
			} `json:"account"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    v.Account.Email,
			Message: fmt.Sprintf("✓ VALID DigitalOcean — %s (droplets: %d)", v.Account.Email, v.Account.DropletLimit),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ DigitalOcean HTTP %d", code)}
}

// ── Discord ───────────────────────────────────────────────────────────────────

func CheckDiscord(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no Discord token"}
	}
	// Try bot token first, then user token
	authTypes := []string{"Bot " + token, token}
	for _, auth := range authTypes {
		code, body, err := apiGet("https://discord.com/api/users/@me", auth)
		if err != nil {
			continue
		}
		if code == 200 {
			var v struct {
				Username      string `json:"username"`
				Discriminator string `json:"discriminator"`
				Email         string `json:"email"`
			}
			_ = json.Unmarshal(body, &v)
			tag := v.Username + "#" + v.Discriminator
			return APIResult{
				Valid:   true,
				Info:    tag,
				Message: fmt.Sprintf("✓ VALID Discord — %s email=%s", tag, v.Email),
			}
		}
	}
	return APIResult{Valid: false, Message: "✗ Discord token invalid"}
}

// ── Heroku ────────────────────────────────────────────────────────────────────

func CheckHeroku(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no Heroku token"}
	}
	req, _ := http.NewRequest("GET", "https://api.heroku.com/account", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.heroku+json; version=3")
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			Email string `json:"email"`
			Name  string `json:"name"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    v.Email,
			Message: fmt.Sprintf("✓ VALID Heroku — %s (%s)", v.Email, v.Name),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Heroku HTTP %d", resp.StatusCode)}
}

// ── Vonage / Nexmo ────────────────────────────────────────────────────────────

func CheckVonage(apiKey, apiSecret string) APIResult {
	if apiKey == "" || apiSecret == "" {
		return APIResult{Message: "no Vonage credentials"}
	}
	apiURL := fmt.Sprintf("https://rest.nexmo.com/account/get-balance?api_key=%s&api_secret=%s", apiKey, apiSecret)
	code, body, err := apiGet(apiURL, "")
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var v struct {
			Value   float64 `json:"value"`
			AutoReload bool `json:"autoReload"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("balance=%.4f", v.Value),
			Message: fmt.Sprintf("✓ VALID Vonage/Nexmo — balance: %.4f EUR", v.Value),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Vonage HTTP %d", code)}
}

// ── extract helpers for new services ─────────────────────────────────────────

func (e Env) TwilioSID() string {
	return e.first("TWILIO_ACCOUNT_SID", "TWILIO_SID", "TWILIO_ACCOUNT")
}

func (e Env) TwilioToken() string {
	return e.first("TWILIO_AUTH_TOKEN", "TWILIO_TOKEN", "TWILIO_SECRET")
}

func (e Env) SlackToken() string {
	return e.first("SLACK_TOKEN", "SLACK_BOT_TOKEN", "SLACK_API_TOKEN", "SLACK_OAUTH_TOKEN", "SLACK_WEBHOOK_URL")
}

func (e Env) OpenAIKey() string {
	return e.first("OPENAI_API_KEY", "OPENAI_KEY", "OPENAI_SECRET_KEY")
}

func (e Env) CloudflareToken() string {
	return e.first("CLOUDFLARE_API_TOKEN", "CF_API_TOKEN", "CLOUDFLARE_TOKEN", "CF_TOKEN")
}

func (e Env) DigitalOceanToken() string {
	return e.first("DIGITALOCEAN_TOKEN", "DO_TOKEN", "DIGITALOCEAN_ACCESS_TOKEN", "DIGITAL_OCEAN_TOKEN")
}

func (e Env) DiscordToken() string {
	return e.first("DISCORD_TOKEN", "DISCORD_BOT_TOKEN", "DISCORD_API_TOKEN")
}

func (e Env) HerokuToken() string {
	return e.first("HEROKU_API_KEY", "HEROKU_TOKEN")
}

func (e Env) VonageKey() string {
	return e.first("VONAGE_API_KEY", "NEXMO_API_KEY", "NEXMO_KEY")
}

func (e Env) VonageSecret() string {
	return e.first("VONAGE_API_SECRET", "NEXMO_API_SECRET", "NEXMO_SECRET")
}

// SlackTokenFromValue extracts Slack token from a webhook URL or direct token value.
func slackTokenFromValue(val string) string {
	if strings.HasPrefix(val, "xox") {
		return val
	}
	return ""
}
