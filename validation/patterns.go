package validation

import "regexp"

// Patterns encapsulates compiled regular expressions used during response validation.
type Patterns struct {
	EnvLine       *regexp.Regexp
	AWSAccess     *regexp.Regexp
	AWSSecret     *regexp.Regexp
	GenericSecret *regexp.Regexp
	JSONPair      *regexp.Regexp
	GitHubToken   *regexp.Regexp
	StripeKey     *regexp.Regexp
	SlackToken    *regexp.Regexp
	GCPCredential *regexp.Regexp
	PrivateKey    *regexp.Regexp
	JWTToken      *regexp.Regexp

	// SMTP / mail service patterns
	SMTPHost       *regexp.Regexp // SMTP_HOST, MAIL_HOST
	SMTPCredential *regexp.Regexp // SMTP_USER/PASS, MAIL_USERNAME/PASSWORD
	SendGridKey    *regexp.Regexp // SG.xxx
	MailgunKey     *regexp.Regexp // key-xxx (32 hex)
	PostmarkToken  *regexp.Regexp // POSTMARK_API_TOKEN
	SparkPostKey   *regexp.Regexp // SPARKPOST_API_KEY
	MailchimpKey   *regexp.Regexp // xxx-us1 Mailchimp style
	AWSSESRegion   *regexp.Regexp // SES credentials block
}

// BuildPatterns compiles the default pattern set.
func BuildPatterns() (*Patterns, error) {
	envLine, err := regexp.Compile(`(?m)^[A-Z0-9_]+\s*=\s*[^\s]+`)
	if err != nil {
		return nil, err
	}
	awsAccess, err := regexp.Compile(`AKIA[0-9A-Z]{16}`)
	if err != nil {
		return nil, err
	}
	awsSecret, err := regexp.Compile(`(?i)aws[_-]?secret[_-]?access[_-]?key`)
	if err != nil {
		return nil, err
	}
	genericSecret, err := regexp.Compile(`(?i)(password|pass|secret|apikey|api_key|token|credential|database_url)\s*=\s*.+`)
	if err != nil {
		return nil, err
	}
	jsonPair, err := regexp.Compile(`"[A-Za-z0-9_\-]+"\s*:\s*"[^"]+"`)
	if err != nil {
		return nil, err
	}

	// GitHub personal access tokens (classic: ghp_, OAuth: gho_, server: ghs_, user: ghu_; fine-grained: github_pat_)
	githubToken, err := regexp.Compile(`gh[pousp]_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{82,}`)
	if err != nil {
		return nil, err
	}
	// Stripe live secret / restricted keys
	stripeKey, err := regexp.Compile(`(?:sk|rk)_live_[0-9a-zA-Z]{24,}`)
	if err != nil {
		return nil, err
	}
	// Slack bot/app/user/workspace tokens
	slackToken, err := regexp.Compile(`xox[baprs]-[0-9A-Za-z\-]{10,}`)
	if err != nil {
		return nil, err
	}
	// GCP service account JSON
	gcpCredential, err := regexp.Compile(`"type"\s*:\s*"service_account"`)
	if err != nil {
		return nil, err
	}
	// PEM private keys (RSA, EC, OPENSSH, PKCS8)
	privateKey, err := regexp.Compile(`-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----`)
	if err != nil {
		return nil, err
	}
	// JWT tokens (header.payload — two base64url segments)
	jwtToken, err := regexp.Compile(`eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}`)
	if err != nil {
		return nil, err
	}

	// SMTP host key (SMTP_HOST, MAIL_HOST, EMAIL_HOST, MAILER_HOST)
	smtpHost, err := regexp.Compile(`(?i)(smtp_host|mail_host|email_host|mailer_host|smtp_server|mail_server)\s*=\s*\S+`)
	if err != nil {
		return nil, err
	}
	// SMTP username / password / port in any combination
	smtpCredential, err := regexp.Compile(`(?i)(smtp_(?:user(?:name)?|pass(?:word)?|port|from|auth)|mail_(?:username|password|port|from|encryption)|email_(?:username|password)|mailer_(?:username|password))\s*=\s*\S+`)
	if err != nil {
		return nil, err
	}
	// SendGrid API key: starts with SG. followed by 69 base64 chars
	sendgridKey, err := regexp.Compile(`SG\.[A-Za-z0-9_\-]{22,}\.[A-Za-z0-9_\-]{43,}`)
	if err != nil {
		return nil, err
	}
	// Mailgun private API key: key- followed by 32 hex chars
	mailgunKey, err := regexp.Compile(`key-[0-9a-f]{32}`)
	if err != nil {
		return nil, err
	}
	// Postmark server / account token (UUID-like or POSTMARK_API_TOKEN assignment)
	postmarkToken, err := regexp.Compile(`(?i)postmark[_-]?(api[_-]?)?token\s*=\s*\S+`)
	if err != nil {
		return nil, err
	}
	// SparkPost API key assignment
	sparkpostKey, err := regexp.Compile(`(?i)sparkpost[_-]?api[_-]?key\s*=\s*\S+`)
	if err != nil {
		return nil, err
	}
	// Mailchimp API key: 32-char hex + datacenter suffix (e.g. abc123…-us1)
	mailchimpKey, err := regexp.Compile(`[0-9a-f]{32}-us[0-9]+`)
	if err != nil {
		return nil, err
	}
	// AWS SES: region assignment alongside access key signals SES usage
	awsSESRegion, err := regexp.Compile(`(?i)(ses[_-]?region|aws[_-]?ses[_-]?(access|secret|key|region))\s*=\s*\S+`)
	if err != nil {
		return nil, err
	}

	return &Patterns{
		EnvLine:       envLine,
		AWSAccess:     awsAccess,
		AWSSecret:     awsSecret,
		GenericSecret: genericSecret,
		JSONPair:      jsonPair,
		GitHubToken:   githubToken,
		StripeKey:     stripeKey,
		SlackToken:    slackToken,
		GCPCredential: gcpCredential,
		PrivateKey:    privateKey,
		JWTToken:      jwtToken,

		SMTPHost:       smtpHost,
		SMTPCredential: smtpCredential,
		SendGridKey:    sendgridKey,
		MailgunKey:     mailgunKey,
		PostmarkToken:  postmarkToken,
		SparkPostKey:   sparkpostKey,
		MailchimpKey:   mailchimpKey,
		AWSSESRegion:   awsSESRegion,
	}, nil
}
