// Package credcheck extracts and validates credentials found in leaked env files.
package credcheck

import (
	"bufio"
	"strings"
)

// Env holds parsed KEY=VALUE pairs from an env file body.
type Env map[string]string

// Parse extracts key-value pairs from raw env file content.
// Handles quoted values, inline comments, and blank lines.
func Parse(content string) Env {
	env := make(Env)
	scanner := bufio.NewScanner(strings.NewReader(content))
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		idx := strings.IndexByte(line, '=')
		if idx < 1 {
			continue
		}
		key := strings.TrimSpace(strings.ToUpper(line[:idx]))
		val := strings.TrimSpace(line[idx+1:])
		// Strip inline comment (unquoted)
		if !strings.HasPrefix(val, `"`) && !strings.HasPrefix(val, `'`) {
			if ci := strings.Index(val, " #"); ci > 0 {
				val = strings.TrimSpace(val[:ci])
			}
		}
		// Strip surrounding quotes
		if len(val) >= 2 {
			if (val[0] == '"' && val[len(val)-1] == '"') ||
				(val[0] == '\'' && val[len(val)-1] == '\'') {
				val = val[1 : len(val)-1]
			}
		}
		if key != "" && val != "" {
			env[key] = val
		}
	}
	return env
}

// first returns the value of the first key found, or "".
func (e Env) first(keys ...string) string {
	for _, k := range keys {
		if v, ok := e[k]; ok && v != "" {
			return v
		}
	}
	return ""
}

// ── SMTP ─────────────────────────────────────────────────────────────────────

// SMTPConfig holds extracted SMTP connection settings.
type SMTPConfig struct {
	Host string
	Port string
	User string
	Pass string
	From string
}

// ExtractSMTP finds SMTP settings in the parsed env.
func (e Env) ExtractSMTP() *SMTPConfig {
	cfg := &SMTPConfig{
		Host: e.first("SMTP_HOST", "MAIL_HOST", "EMAIL_HOST", "MAILER_HOST", "SMTP_SERVER", "MAIL_SERVER"),
		Port: e.first("SMTP_PORT", "MAIL_PORT", "EMAIL_PORT", "MAILER_PORT"),
		User: e.first("SMTP_USERNAME", "SMTP_USER", "MAIL_USERNAME", "EMAIL_USERNAME", "MAILER_USERNAME", "SMTP_LOGIN"),
		Pass: e.first("SMTP_PASSWORD", "SMTP_PASS", "MAIL_PASSWORD", "EMAIL_PASSWORD", "MAILER_PASSWORD", "SMTP_SECRET"),
		From: e.first("MAIL_FROM", "SMTP_FROM", "EMAIL_FROM", "MAIL_FROM_ADDRESS", "SENDER_EMAIL"),
	}
	if cfg.Host == "" {
		return nil
	}
	if cfg.Port == "" {
		cfg.Port = "587"
	}
	return cfg
}

// ── AWS ───────────────────────────────────────────────────────────────────────

// AWSConfig holds extracted AWS credentials.
type AWSConfig struct {
	AccessKey string
	SecretKey string
	Region    string
	SessionToken string
}

// ExtractAWS finds AWS credentials in the parsed env.
func (e Env) ExtractAWS() *AWSConfig {
	cfg := &AWSConfig{
		AccessKey:    e.first("AWS_ACCESS_KEY_ID", "AWS_ACCESS_KEY", "SES_ACCESS_KEY", "SES_KEY"),
		SecretKey:    e.first("AWS_SECRET_ACCESS_KEY", "AWS_SECRET_KEY", "SES_SECRET_KEY", "SES_SECRET"),
		Region:       e.first("AWS_DEFAULT_REGION", "AWS_REGION", "SES_REGION"),
		SessionToken: e.first("AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"),
	}
	if cfg.AccessKey == "" || cfg.SecretKey == "" {
		return nil
	}
	if cfg.Region == "" {
		cfg.Region = "us-east-1"
	}
	return cfg
}

// ── API tokens ────────────────────────────────────────────────────────────────

func (e Env) SendGridKey() string {
	return e.first("SENDGRID_API_KEY", "SENDGRID_KEY", "SG_API_KEY")
}

func (e Env) MailgunKey() string {
	return e.first("MAILGUN_API_KEY", "MAILGUN_SECRET", "MG_API_KEY")
}

func (e Env) MailgunDomain() string {
	return e.first("MAILGUN_DOMAIN", "MG_DOMAIN")
}

func (e Env) PostmarkToken() string {
	return e.first("POSTMARK_API_TOKEN", "POSTMARK_SERVER_TOKEN", "POSTMARK_TOKEN")
}

func (e Env) SparkPostKey() string {
	return e.first("SPARKPOST_API_KEY", "SPARKPOST_KEY")
}

func (e Env) StripeKey() string {
	return e.first("STRIPE_SECRET_KEY", "STRIPE_API_KEY", "STRIPE_KEY")
}

func (e Env) GitHubToken() string {
	return e.first("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_API_TOKEN", "GITHUB_ACCESS_TOKEN")
}

func (e Env) MailchimpKey() string {
	return e.first("MAILCHIMP_API_KEY", "MC_API_KEY")
}
