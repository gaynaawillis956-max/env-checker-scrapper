package output

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"env-checker/credcheck"
	"env-checker/util"
)

// ServiceDir is the subfolder name for each credential type.
// High-value services are listed first for easy scanning.
var ServiceDir = map[string]string{
	"smtp":         "smtp",
	"aws":          "aws",
	"stripe":       "stripe",
	"sendgrid":     "sendgrid",
	"mailgun":      "mailgun",
	"postmark":     "postmark",
	"sparkpost":    "sparkpost",
	"mailchimp":    "mailchimp",
	"github":       "github",
	"twilio":       "twilio",
	"slack":        "slack",
	"openai":       "openai",
	"cloudflare":   "cloudflare",
	"digitalocean": "digitalocean",
	"discord":      "discord",
	"heroku":       "heroku",
	"vonage":       "vonage",
}

// HighValueServices are the most commonly rewarded in bug bounty.
var HighValueServices = map[string]bool{
	"smtp": true, "aws": true, "stripe": true, "sendgrid": true,
	"mailgun": true, "openai": true, "twilio": true,
	"paypal": true, "shopify": true, "braintree": true, "square": true, "razorpay": true,
}

type svcHit struct {
	name  string
	valid bool
	info  string
}

func reportServices(r credcheck.CheckReport) []svcHit {
	smtpMsg := ""
	if r.SMTP != nil {
		smtpMsg = r.SMTP.Message
	}
	awsMsg := ""
	if r.AWS != nil {
		awsMsg = fmt.Sprintf("account=%s arn=%s", r.AWS.AccountID, r.AWS.ARN)
	}
	twMsg := ""
	if r.Twilio != nil {
		twMsg = r.Twilio.FriendlyName
	}
	a := func(v *credcheck.APIResult) (bool, string) {
		if v == nil {
			return false, ""
		}
		return v.Valid, v.Info
	}
	av := func(v *credcheck.APIResult) bool { ok, _ := a(v); return ok }
	ai := func(v *credcheck.APIResult) string { _, info := a(v); return info }

	return []svcHit{
		// Email / SMTP
		{"smtp", r.SMTP != nil && r.SMTP.AuthValid, smtpMsg},
		{"sendgrid", av(r.SendGrid), ai(r.SendGrid)},
		{"mailgun", av(r.Mailgun), ai(r.Mailgun)},
		{"postmark", av(r.Postmark), ai(r.Postmark)},
		{"sparkpost", av(r.SparkPost), ai(r.SparkPost)},
		{"mailchimp", av(r.Mailchimp), ai(r.Mailchimp)},
		{"vonage", av(r.Vonage), ai(r.Vonage)},
		// Cloud
		{"aws", r.AWS != nil && r.AWS.Valid, awsMsg},
		{"gcp", av(r.GCP), ai(r.GCP)},
		{"cloudflare", av(r.Cloudflare), ai(r.Cloudflare)},
		{"digitalocean", av(r.DigitalOcean), ai(r.DigitalOcean)},
		{"heroku", av(r.Heroku), ai(r.Heroku)},
		{"datadog", av(r.Datadog), ai(r.Datadog)},
		// Payment
		{"stripe", av(r.Stripe), ai(r.Stripe)},
		{"paypal", av(r.PayPal), ai(r.PayPal)},
		{"square", av(r.Square), ai(r.Square)},
		{"razorpay", av(r.Razorpay), ai(r.Razorpay)},
		{"braintree", av(r.Braintree), ai(r.Braintree)},
		// Social / Messaging
		{"slack", av(r.Slack), ai(r.Slack)},
		{"discord", av(r.Discord), ai(r.Discord)},
		{"twitter", av(r.Twitter), ai(r.Twitter)},
		{"facebook", av(r.Facebook), ai(r.Facebook)},
		{"pusher", av(r.Pusher), ai(r.Pusher)},
		// Dev / AI
		{"github", av(r.GitHub), ai(r.GitHub)},
		{"openai", av(r.OpenAI), ai(r.OpenAI)},
		{"sentry", av(r.Sentry), ai(r.Sentry)},
		// CRM
		{"hubspot", av(r.HubSpot), ai(r.HubSpot)},
		// Commerce
		{"shopify", av(r.Shopify), ai(r.Shopify)},
		// Comms
		{"twilio", r.Twilio != nil && r.Twilio.Valid, twMsg},
	}
}

// SaveByService writes rec into every per-service subfolder that has a valid credential.
// Returns which services were saved and whether any are high-value.
func SaveByService(outDir string, rec *Record, report credcheck.CheckReport) (saved []string, hasHighValue bool, err error) {
	hits := reportServices(report)
	header := buildFileHeader(rec, report)

	for _, h := range hits {
		if !h.valid {
			continue
		}
		dir := filepath.Join(outDir, h.name)
		if mkErr := os.MkdirAll(dir, 0o755); mkErr != nil {
			err = mkErr
			return
		}
		name := credFilename(rec)
		if writeErr := util.WriteFileAtomic(filepath.Join(dir, name), []byte(header+rec.Content)); writeErr != nil {
			err = writeErr
			return
		}
		saved = append(saved, h.name)
		if HighValueServices[h.name] {
			hasHighValue = true
		}
	}

	// multi/ when several services are valid at once
	if len(saved) > 1 {
		dir := filepath.Join(outDir, "multi")
		os.MkdirAll(dir, 0o755)
		util.WriteFileAtomic(filepath.Join(dir, credFilename(rec)), []byte(header+rec.Content))
	}

	return
}

// SaveUnknown saves a .env file that had no valid credentials to unknown/.
func SaveUnknown(outDir string, rec *Record) {
	dir := filepath.Join(outDir, "unknown")
	os.MkdirAll(dir, 0o755)
	header := fmt.Sprintf("# URL: %s://%s%s\n# Found: %s UTC\n# No valid credentials confirmed\n\n",
		rec.Mode, rec.Host, rec.Path,
		time.Now().UTC().Format("2006-01-02 15:04:05"),
	)
	util.WriteFileAtomic(filepath.Join(dir, credFilename(rec)), []byte(header+rec.Content))
}

func buildFileHeader(rec *Record, r credcheck.CheckReport) string {
	hits := reportServices(r)
	var valid []string
	for _, h := range hits {
		if h.valid {
			entry := h.name
			if h.info != "" {
				entry += ": " + h.info
			}
			valid = append(valid, entry)
		}
	}
	var sb strings.Builder
	sb.WriteString("# ═══════════════════════════════════════════════\n")
	sb.WriteString(fmt.Sprintf("# URL:       %s://%s%s\n", rec.Mode, rec.Host, rec.Path))
	sb.WriteString(fmt.Sprintf("# Host:      %s\n", rec.Host))
	sb.WriteString(fmt.Sprintf("# Found:     %s UTC\n", time.Now().UTC().Format("2006-01-02 15:04:05")))
	if len(valid) > 0 {
		sb.WriteString(fmt.Sprintf("# VALID:     %s\n", strings.Join(valid, " | ")))
	}
	sb.WriteString("# ═══════════════════════════════════════════════\n\n")
	return sb.String()
}

func credFilename(rec *Record) string {
	host := strings.NewReplacer(":", "_", ".", "_").Replace(rec.Host)
	path := strings.NewReplacer("/", "_", "\\", "_", "%", "pct", ".", "_").Replace(rec.Path)
	if len(path) > 60 {
		path = path[:60]
	}
	return fmt.Sprintf("%s__%s.txt", host, strings.TrimPrefix(path, "_"))
}
