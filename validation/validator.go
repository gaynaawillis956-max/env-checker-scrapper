package validation

import (
	"bytes"
	"strings"
)

// Validator performs response inspection for credential indicators.
type Validator struct {
	patterns *Patterns
}

// NewValidator constructs a Validator instance.
func NewValidator(patterns *Patterns) *Validator {
	return &Validator{patterns: patterns}
}

// Result represents validation outcome metadata.
type Result struct {
	Valid       bool
	Indicators  []string
	ContentType string
}

// Validate inspects response bodies for sensitive patterns.
func (v *Validator) Validate(body []byte, contentType string) Result {
	indicators := make([]string, 0, 4)

	if v.patterns.EnvLine.Match(body) {
		indicators = append(indicators, "env-line")
	}
	if v.patterns.AWSAccess.Match(body) {
		indicators = append(indicators, "aws-access-key")
	}
	if v.patterns.AWSSecret.Match(body) {
		indicators = append(indicators, "aws-secret-key")
	}
	if v.patterns.GenericSecret.Match(body) {
		indicators = append(indicators, "generic-secret")
	}
	if bytes.Contains(body, []byte("DATABASE_URL")) {
		indicators = append(indicators, "database-url")
	}
	if v.patterns.JSONPair.Match(body) {
		indicators = append(indicators, "json-kv")
	}
	if v.patterns.GitHubToken.Match(body) {
		indicators = append(indicators, "github-token")
	}
	if v.patterns.StripeKey.Match(body) {
		indicators = append(indicators, "stripe-key")
	}
	if v.patterns.SlackToken.Match(body) {
		indicators = append(indicators, "slack-token")
	}
	if v.patterns.GCPCredential.Match(body) {
		indicators = append(indicators, "gcp-service-account")
	}
	if v.patterns.PrivateKey.Match(body) {
		indicators = append(indicators, "private-key")
	}
	if v.patterns.JWTToken.Match(body) {
		indicators = append(indicators, "jwt-token")
	}

	// SMTP / mail service indicators
	if v.patterns.SMTPHost.Match(body) {
		indicators = append(indicators, "smtp-host")
	}
	if v.patterns.SMTPCredential.Match(body) {
		indicators = append(indicators, "smtp-credential")
	}
	if v.patterns.SendGridKey.Match(body) {
		indicators = append(indicators, "sendgrid-api-key")
	}
	if v.patterns.MailgunKey.Match(body) {
		indicators = append(indicators, "mailgun-api-key")
	}
	if v.patterns.PostmarkToken.Match(body) {
		indicators = append(indicators, "postmark-token")
	}
	if v.patterns.SparkPostKey.Match(body) {
		indicators = append(indicators, "sparkpost-api-key")
	}
	if v.patterns.MailchimpKey.Match(body) {
		indicators = append(indicators, "mailchimp-api-key")
	}
	if v.patterns.AWSSESRegion.Match(body) {
		indicators = append(indicators, "aws-ses-credential")
	}

	valid := len(indicators) > 0
	if contentType == "" {
		contentType = inferContentType(body)
	}

	return Result{Valid: valid, Indicators: indicators, ContentType: contentType}
}

func inferContentType(body []byte) string {
	snippet := strings.ToLower(string(body[:min(len(body), 256)]))
	switch {
	case strings.Contains(snippet, "aws"):
		return "text/aws"
	case strings.Contains(snippet, "database"):
		return "text/database"
	case strings.Contains(snippet, "token"):
		return "text/token"
	default:
		return "text/plain"
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
