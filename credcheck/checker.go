package credcheck

// CheckReport is the full validation result for one found file.
type CheckReport struct {
	// ── Email / SMTP ───────────────────────────────────────
	SMTP      *SMTPResult `json:"smtp,omitempty"`
	SendGrid  *APIResult  `json:"sendgrid,omitempty"`
	Mailgun   *APIResult  `json:"mailgun,omitempty"`
	Postmark  *APIResult  `json:"postmark,omitempty"`
	SparkPost *APIResult  `json:"sparkpost,omitempty"`
	Mailchimp *APIResult  `json:"mailchimp,omitempty"`
	Vonage    *APIResult  `json:"vonage,omitempty"`

	// ── Cloud / Infrastructure ─────────────────────────────
	AWS          *AWSResult `json:"aws,omitempty"`
	GCP          *APIResult `json:"gcp,omitempty"`
	Cloudflare   *APIResult `json:"cloudflare,omitempty"`
	DigitalOcean *APIResult `json:"digitalocean,omitempty"`
	Heroku       *APIResult `json:"heroku,omitempty"`
	Datadog      *APIResult `json:"datadog,omitempty"`

	// ── Payment ────────────────────────────────────────────
	Stripe     *APIResult `json:"stripe,omitempty"`
	PayPal     *APIResult `json:"paypal,omitempty"`
	Square     *APIResult `json:"square,omitempty"`
	Razorpay   *APIResult `json:"razorpay,omitempty"`
	Braintree  *APIResult `json:"braintree,omitempty"`

	// ── Social / Messaging ─────────────────────────────────
	Slack   *APIResult `json:"slack,omitempty"`
	Discord *APIResult `json:"discord,omitempty"`
	Twitter *APIResult `json:"twitter,omitempty"`
	Facebook *APIResult `json:"facebook,omitempty"`
	Pusher  *APIResult `json:"pusher,omitempty"`

	// ── Dev / AI ───────────────────────────────────────────
	GitHub  *APIResult `json:"github,omitempty"`
	OpenAI  *APIResult `json:"openai,omitempty"`
	Sentry  *APIResult `json:"sentry,omitempty"`

	// ── CRM / Marketing ────────────────────────────────────
	HubSpot *APIResult `json:"hubspot,omitempty"`

	// ── Commerce ───────────────────────────────────────────
	Shopify *APIResult `json:"shopify,omitempty"`

	// ── Comms ──────────────────────────────────────────────
	Twilio *TwilioResult `json:"twilio,omitempty"`

	HasValid bool `json:"hasValid"`
}

// Check parses the raw content of a found file and validates every
// credential type it contains.
func Check(content string) CheckReport {
	env := Parse(content)
	r := CheckReport{}

	if smtp := env.ExtractSMTP(); smtp != nil {
		res := CheckSMTP(smtp)
		r.SMTP = &res
		if res.AuthValid {
			r.HasValid = true
		}
	}

	if aws := env.ExtractAWS(); aws != nil {
		res := CheckAWS(aws)
		r.AWS = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if key := env.SendGridKey(); key != "" {
		res := CheckSendGrid(key)
		r.SendGrid = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if key := env.MailgunKey(); key != "" {
		res := CheckMailgun(key, env.MailgunDomain())
		r.Mailgun = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.PostmarkToken(); tok != "" {
		res := CheckPostmark(tok)
		r.Postmark = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if key := env.SparkPostKey(); key != "" {
		res := CheckSparkPost(key)
		r.SparkPost = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if key := env.StripeKey(); key != "" {
		res := CheckStripe(key)
		r.Stripe = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.GitHubToken(); tok != "" {
		res := CheckGitHub(tok)
		r.GitHub = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if key := env.MailchimpKey(); key != "" {
		res := CheckMailchimp(key)
		r.Mailchimp = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	// ── new services ──────────────────────────────────────────────────────────

	if sid, tok := env.TwilioSID(), env.TwilioToken(); sid != "" && tok != "" {
		res := CheckTwilio(sid, tok)
		r.Twilio = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.SlackToken(); tok != "" {
		if clean := slackTokenFromValue(tok); clean != "" {
			res := CheckSlack(clean)
			r.Slack = &res
			if res.Valid {
				r.HasValid = true
			}
		}
	}

	if key := env.OpenAIKey(); key != "" {
		res := CheckOpenAI(key)
		r.OpenAI = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.CloudflareToken(); tok != "" {
		res := CheckCloudflare(tok)
		r.Cloudflare = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.DigitalOceanToken(); tok != "" {
		res := CheckDigitalOcean(tok)
		r.DigitalOcean = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.DiscordToken(); tok != "" {
		res := CheckDiscord(tok)
		r.Discord = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.HerokuToken(); tok != "" {
		res := CheckHeroku(tok)
		r.Heroku = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if key, secret := env.VonageKey(), env.VonageSecret(); key != "" && secret != "" {
		res := CheckVonage(key, secret)
		r.Vonage = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	// ── new services ──────────────────────────────────────────────────────────

	if id, sec := env.PayPalClientID(), env.PayPalSecret(); id != "" && sec != "" {
		res := CheckPayPal(id, sec)
		r.PayPal = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if key := env.GCPAPIKey(); key != "" {
		res := CheckGCPKey(key)
		r.GCP = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if store, tok := env.ShopifyStore(), env.ShopifyToken(); store != "" && tok != "" {
		res := CheckShopify(store, tok)
		r.Shopify = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.TwitterBearer(); tok != "" {
		res := CheckTwitter(tok)
		r.Twitter = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if id, sec := env.FacebookAppID(), env.FacebookAppSecret(); id != "" && sec != "" {
		res := CheckFacebook(id, sec)
		r.Facebook = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.SquareToken(); tok != "" {
		res := CheckSquare(tok)
		r.Square = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if id, sec := env.RazorpayKeyID(), env.RazorpaySecret(); id != "" && sec != "" {
		res := CheckRazorpay(id, sec)
		r.Razorpay = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.HubSpotToken(); tok != "" {
		res := CheckHubSpot(tok)
		r.HubSpot = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if apiKey := env.DatadogAPIKey(); apiKey != "" {
		res := CheckDatadog(apiKey, env.DatadogAppKey())
		r.Datadog = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if tok := env.SentryToken(); tok != "" {
		res := CheckSentry(tok)
		r.Sentry = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if mid, pub, priv := env.BraintreeMerchantID(), env.BraintreePublicKey(), env.BraintreePrivateKey(); mid != "" && pub != "" && priv != "" {
		res := CheckBraintree(mid, pub, priv)
		r.Braintree = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	if appID, key, sec := env.PusherAppID(), env.PusherKey(), env.PusherSecret(); appID != "" && key != "" && sec != "" {
		res := CheckPusher(appID, key, sec, env.PusherCluster())
		r.Pusher = &res
		if res.Valid {
			r.HasValid = true
		}
	}

	return r
}
