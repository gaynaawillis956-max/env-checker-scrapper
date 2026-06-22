package credcheck

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

// ── PayPal ────────────────────────────────────────────────────────────────────

func CheckPayPal(clientID, secret string) APIResult {
	if clientID == "" || secret == "" {
		return APIResult{Message: "no PayPal credentials"}
	}
	// Try live first, then sandbox
	for _, base := range []string{"https://api-m.paypal.com", "https://api-m.sandbox.paypal.com"} {
		req, _ := http.NewRequest("POST", base+"/v1/oauth2/token", strings.NewReader("grant_type=client_credentials"))
		req.SetBasicAuth(clientID, secret)
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("Accept", "application/json")
		resp, err := httpClient.Do(req)
		if err != nil {
			continue
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode == 200 {
			var v struct {
				Scope     string `json:"scope"`
				TokenType string `json:"token_type"`
				AppID     string `json:"app_id"`
			}
			_ = json.Unmarshal(body, &v)
			env := "LIVE"
			if strings.Contains(base, "sandbox") {
				env = "SANDBOX"
			}
			return APIResult{
				Valid:   true,
				Info:    fmt.Sprintf("app=%s env=%s", v.AppID, env),
				Message: fmt.Sprintf("✓ VALID PayPal %s — app_id=%s", env, v.AppID),
			}
		}
	}
	return APIResult{Valid: false, Message: "✗ PayPal credentials invalid"}
}

// ── Google Cloud API Key ──────────────────────────────────────────────────────

func CheckGCPKey(key string) APIResult {
	if key == "" || !strings.HasPrefix(key, "AIza") {
		return APIResult{Message: "no GCP API key"}
	}
	// Test against Maps Geocoding — a read-only, no-charge probe
	testURL := "https://maps.googleapis.com/maps/api/geocode/json?address=1600+Pennsylvania+Ave+NW&key=" + url.QueryEscape(key)
	code, body, err := apiGet(testURL, "")
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	var v struct {
		Status       string `json:"status"`
		ErrorMessage string `json:"error_message"`
	}
	_ = json.Unmarshal(body, &v)
	switch v.Status {
	case "OK", "ZERO_RESULTS":
		return APIResult{
			Valid:   true,
			Info:    "Google Maps API enabled",
			Message: "✓ VALID GCP API Key — Maps Geocoding API accessible",
		}
	case "REQUEST_DENIED":
		if strings.Contains(v.ErrorMessage, "not authorized") {
			return APIResult{Valid: false, Message: "✗ GCP key: not authorized for Maps API (key may be restricted)"}
		}
		return APIResult{Valid: false, Message: fmt.Sprintf("✗ GCP key: %s", v.ErrorMessage)}
	case "OVER_DAILY_LIMIT", "OVER_QUERY_LIMIT":
		// Key IS valid — just over quota
		return APIResult{
			Valid:   true,
			Info:    "quota exceeded (key is valid)",
			Message: "✓ VALID GCP API Key — over quota (key confirmed real)",
		}
	}
	// Also try Firebase API key validation endpoint
	firebaseURL := "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=" + url.QueryEscape(key)
	req, _ := http.NewRequest("POST", firebaseURL, strings.NewReader(`{}`))
	req.Header.Set("Content-Type", "application/json")
	resp2, err2 := httpClient.Do(req)
	if err2 == nil {
		defer resp2.Body.Close()
		if resp2.StatusCode != 400 {
			return APIResult{
				Valid:   true,
				Info:    "Firebase/GCP key valid",
				Message: fmt.Sprintf("✓ VALID GCP/Firebase API Key — HTTP %d", resp2.StatusCode),
			}
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ GCP key: status=%s HTTP=%d", v.Status, code)}
}

// ── Shopify ───────────────────────────────────────────────────────────────────

func CheckShopify(store, token string) APIResult {
	if store == "" || token == "" {
		return APIResult{Message: "no Shopify credentials"}
	}
	// Normalise store name — strip .myshopify.com if present
	store = strings.TrimSuffix(store, "/")
	store = strings.TrimSuffix(store, ".myshopify.com")
	store = strings.TrimPrefix(store, "https://")
	store = strings.TrimPrefix(store, "http://")
	apiURL := fmt.Sprintf("https://%s.myshopify.com/admin/api/2024-01/shop.json", store)
	req, _ := http.NewRequest("GET", apiURL, nil)
	req.Header.Set("X-Shopify-Access-Token", token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			Shop struct {
				Name            string `json:"name"`
				Email           string `json:"myshopify_domain"`
				PlanName        string `json:"plan_name"`
				Domain          string `json:"domain"`
				PrimaryLocale   string `json:"primary_locale"`
			} `json:"shop"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("%s plan=%s", v.Shop.Name, v.Shop.PlanName),
			Message: fmt.Sprintf("✓ VALID Shopify — store=%s plan=%s", v.Shop.Name, v.Shop.PlanName),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Shopify HTTP %d", resp.StatusCode)}
}

// ── Twitter / X ───────────────────────────────────────────────────────────────

func CheckTwitter(bearerToken string) APIResult {
	if bearerToken == "" {
		return APIResult{Message: "no Twitter bearer token"}
	}
	code, body, err := apiGet("https://api.twitter.com/2/users/me?user.fields=name,username,public_metrics", "Bearer "+bearerToken)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var v struct {
			Data struct {
				Name     string `json:"name"`
				Username string `json:"username"`
			} `json:"data"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("@%s (%s)", v.Data.Username, v.Data.Name),
			Message: fmt.Sprintf("✓ VALID Twitter — @%s", v.Data.Username),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Twitter HTTP %d", code)}
}

// ── Facebook / Meta ───────────────────────────────────────────────────────────

func CheckFacebook(appID, appSecret string) APIResult {
	if appID == "" || appSecret == "" {
		return APIResult{Message: "no Facebook credentials"}
	}
	// Get an app access token
	appToken := appID + "|" + appSecret
	apiURL := fmt.Sprintf("https://graph.facebook.com/v18.0/me?access_token=%s", url.QueryEscape(appToken))
	code, body, err := apiGet(apiURL, "")
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	var v struct {
		ID    string `json:"id"`
		Name  string `json:"name"`
		Error struct {
			Message string `json:"message"`
			Code    int    `json:"code"`
		} `json:"error"`
	}
	_ = json.Unmarshal(body, &v)
	if code == 200 && v.ID != "" {
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("app_id=%s name=%s", v.ID, v.Name),
			Message: fmt.Sprintf("✓ VALID Facebook App — id=%s (%s)", v.ID, v.Name),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Facebook: %s (HTTP %d)", v.Error.Message, code)}
}

// ── Square ────────────────────────────────────────────────────────────────────

func CheckSquare(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no Square token"}
	}
	code, body, err := apiGet("https://connect.squareup.com/v2/locations", "Bearer "+token)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var v struct {
			Locations []struct {
				ID      string `json:"id"`
				Name    string `json:"name"`
				Country string `json:"country"`
				Status  string `json:"status"`
			} `json:"locations"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("%d location(s)", len(v.Locations)),
			Message: fmt.Sprintf("✓ VALID Square — %d location(s)", len(v.Locations)),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Square HTTP %d", code)}
}

// ── Razorpay ──────────────────────────────────────────────────────────────────

func CheckRazorpay(keyID, keySecret string) APIResult {
	if keyID == "" || keySecret == "" {
		return APIResult{Message: "no Razorpay credentials"}
	}
	req, _ := http.NewRequest("GET", "https://api.razorpay.com/v1/payments?count=1", nil)
	req.SetBasicAuth(keyID, keySecret)
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			Count int `json:"count"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("payments count=%d", v.Count),
			Message: fmt.Sprintf("✓ VALID Razorpay — %d payment(s) accessible", v.Count),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Razorpay HTTP %d", resp.StatusCode)}
}

// ── HubSpot ───────────────────────────────────────────────────────────────────

func CheckHubSpot(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no HubSpot token"}
	}
	// HubSpot private app token (PAT) or legacy API key
	var req *http.Request
	if strings.HasPrefix(token, "pat-") {
		req, _ = http.NewRequest("GET", "https://api.hubapi.com/crm/v3/objects/contacts?limit=1", nil)
		req.Header.Set("Authorization", "Bearer "+token)
	} else {
		req, _ = http.NewRequest("GET", "https://api.hubapi.com/crm/v3/objects/contacts?limit=1&hapikey="+url.QueryEscape(token), nil)
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			Total int `json:"total"`
		}
		_ = json.Unmarshal(body, &v)
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("contacts=%d", v.Total),
			Message: fmt.Sprintf("✓ VALID HubSpot — %d contact(s) accessible", v.Total),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ HubSpot HTTP %d", resp.StatusCode)}
}

// ── Datadog ───────────────────────────────────────────────────────────────────

func CheckDatadog(apiKey, appKey string) APIResult {
	if apiKey == "" {
		return APIResult{Message: "no Datadog API key"}
	}
	req, _ := http.NewRequest("GET", "https://api.datadoghq.com/api/v1/validate", nil)
	req.Header.Set("DD-API-KEY", apiKey)
	if appKey != "" {
		req.Header.Set("DD-APPLICATION-KEY", appKey)
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 200 {
		var v struct {
			Valid bool `json:"valid"`
		}
		_ = json.Unmarshal(body, &v)
		if v.Valid {
			info := "api-key-only"
			if appKey != "" {
				info = "api+app-key"
			}
			return APIResult{
				Valid:   true,
				Info:    info,
				Message: "✓ VALID Datadog API key",
			}
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Datadog HTTP %d", resp.StatusCode)}
}

// ── Sentry ────────────────────────────────────────────────────────────────────

func CheckSentry(token string) APIResult {
	if token == "" {
		return APIResult{Message: "no Sentry token"}
	}
	code, body, err := apiGet("https://sentry.io/api/0/projects/", "Bearer "+token)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	if code == 200 {
		var projects []struct {
			Slug         string `json:"slug"`
			Organization struct {
				Slug string `json:"slug"`
			} `json:"organization"`
		}
		_ = json.Unmarshal(body, &projects)
		orgs := map[string]bool{}
		for _, p := range projects {
			orgs[p.Organization.Slug] = true
		}
		orgList := ""
		for o := range orgs {
			orgList += o + " "
		}
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("%d project(s) in orgs: %s", len(projects), strings.TrimSpace(orgList)),
			Message: fmt.Sprintf("✓ VALID Sentry — %d project(s)", len(projects)),
		}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Sentry HTTP %d", code)}
}

// ── Braintree ─────────────────────────────────────────────────────────────────

func CheckBraintree(merchantID, publicKey, privateKey string) APIResult {
	if merchantID == "" || publicKey == "" || privateKey == "" {
		return APIResult{Message: "no Braintree credentials"}
	}
	// Try production, then sandbox
	for _, env := range []struct{ name, base string }{
		{"production", "https://api.braintreegateway.com:443"},
		{"sandbox", "https://api.sandbox.braintreegateway.com:443"},
	} {
		apiURL := fmt.Sprintf("%s/merchants/%s/transactions?page=1&per_page=1", env.base, merchantID)
		req, _ := http.NewRequest("GET", apiURL, nil)
		req.SetBasicAuth(publicKey, privateKey)
		req.Header.Set("X-ApiVersion", "6")
		req.Header.Set("Accept", "application/xml")
		resp, err := httpClient.Do(req)
		if err != nil {
			continue
		}
		resp.Body.Close()
		if resp.StatusCode == 200 || resp.StatusCode == 422 {
			return APIResult{
				Valid:   true,
				Info:    fmt.Sprintf("merchant=%s env=%s", merchantID, env.name),
				Message: fmt.Sprintf("✓ VALID Braintree — merchant=%s (%s)", merchantID, env.name),
			}
		}
	}
	return APIResult{Valid: false, Message: "✗ Braintree credentials invalid"}
}

// ── Pusher ────────────────────────────────────────────────────────────────────

func CheckPusher(appID, key, secret, cluster string) APIResult {
	if appID == "" || key == "" || secret == "" {
		return APIResult{Message: "no Pusher credentials"}
	}
	if cluster == "" {
		cluster = "mt1"
	}
	// GET channels list — requires auth signature but at minimum we can verify the endpoint
	apiURL := fmt.Sprintf("https://api-%s.pusher.com/apps/%s/channels", cluster, appID)
	req, _ := http.NewRequest("GET", apiURL, nil)
	req.Header.Set("Authorization", "Bearer "+key+":"+secret)
	resp, err := httpClient.Do(req)
	if err != nil {
		return APIResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	// 200 = valid, 403 = key exists but wrong auth, 404 = no such app
	if resp.StatusCode == 200 {
		return APIResult{
			Valid:   true,
			Info:    fmt.Sprintf("app_id=%s cluster=%s", appID, cluster),
			Message: fmt.Sprintf("✓ VALID Pusher — app=%s cluster=%s", appID, cluster),
		}
	}
	if resp.StatusCode == 403 {
		// App ID exists, try to confirm key is valid via different endpoint
		return APIResult{Valid: false, Message: fmt.Sprintf("✗ Pusher app found but auth rejected (app_id=%s)", appID)}
	}
	return APIResult{Valid: false, Message: fmt.Sprintf("✗ Pusher HTTP %d — %s", resp.StatusCode, string(body[:min(len(body), 100)]))}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// ── extract helpers ───────────────────────────────────────────────────────────

func (e Env) PayPalClientID() string {
	return e.first("PAYPAL_CLIENT_ID", "PAYPAL_APP_CLIENT_ID", "PP_CLIENT_ID", "PAYPAL_KEY")
}
func (e Env) PayPalSecret() string {
	return e.first("PAYPAL_CLIENT_SECRET", "PAYPAL_APP_SECRET", "PP_CLIENT_SECRET", "PAYPAL_SECRET")
}

func (e Env) GCPAPIKey() string {
	v := e.first("GOOGLE_API_KEY", "GCP_API_KEY", "GOOGLE_MAPS_API_KEY", "MAPS_API_KEY",
		"FIREBASE_API_KEY", "GOOGLE_CLOUD_API_KEY", "GOOGLE_KEY")
	if strings.HasPrefix(v, "AIza") {
		return v
	}
	return ""
}

func (e Env) ShopifyStore() string {
	return e.first("SHOPIFY_STORE", "SHOPIFY_SHOP_NAME", "SHOPIFY_DOMAIN", "SHOP_NAME",
		"SHOPIFY_SHOP", "SHOPIFY_URL")
}
func (e Env) ShopifyToken() string {
	return e.first("SHOPIFY_ACCESS_TOKEN", "SHOPIFY_ADMIN_API_ACCESS_TOKEN", "SHOPIFY_TOKEN",
		"SHOPIFY_API_PASSWORD", "SHOPIFY_PRIVATE_APP_PASSWORD")
}

func (e Env) TwitterBearer() string {
	return e.first("TWITTER_BEARER_TOKEN", "TWITTER_API_BEARER_TOKEN", "TWITTER_BEARER",
		"X_BEARER_TOKEN", "TWITTER_ACCESS_TOKEN")
}

func (e Env) FacebookAppID() string {
	return e.first("FACEBOOK_APP_ID", "FB_APP_ID", "META_APP_ID", "FB_CLIENT_ID")
}
func (e Env) FacebookAppSecret() string {
	return e.first("FACEBOOK_APP_SECRET", "FB_APP_SECRET", "META_APP_SECRET", "FB_CLIENT_SECRET")
}

func (e Env) SquareToken() string {
	return e.first("SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN", "SQ_ACCESS_TOKEN",
		"SQUAREUP_ACCESS_TOKEN")
}

func (e Env) RazorpayKeyID() string {
	return e.first("RAZORPAY_KEY_ID", "RAZORPAY_KEY", "RZP_KEY_ID")
}
func (e Env) RazorpaySecret() string {
	return e.first("RAZORPAY_KEY_SECRET", "RAZORPAY_SECRET", "RZP_KEY_SECRET")
}

func (e Env) HubSpotToken() string {
	return e.first("HUBSPOT_API_KEY", "HUBSPOT_TOKEN", "HS_API_KEY", "HUBSPOT_PRIVATE_APP_TOKEN",
		"HUBSPOT_ACCESS_TOKEN")
}

func (e Env) DatadogAPIKey() string {
	return e.first("DATADOG_API_KEY", "DD_API_KEY", "DATADOG_KEY")
}
func (e Env) DatadogAppKey() string {
	return e.first("DATADOG_APP_KEY", "DD_APP_KEY", "DATADOG_APPLICATION_KEY")
}

func (e Env) SentryToken() string {
	return e.first("SENTRY_AUTH_TOKEN", "SENTRY_TOKEN", "SENTRY_API_TOKEN")
}

func (e Env) BraintreeMerchantID() string {
	return e.first("BRAINTREE_MERCHANT_ID", "BT_MERCHANT_ID")
}
func (e Env) BraintreePublicKey() string {
	return e.first("BRAINTREE_PUBLIC_KEY", "BT_PUBLIC_KEY")
}
func (e Env) BraintreePrivateKey() string {
	return e.first("BRAINTREE_PRIVATE_KEY", "BT_PRIVATE_KEY")
}

func (e Env) PusherAppID() string {
	return e.first("PUSHER_APP_ID", "PUSHER_ID")
}
func (e Env) PusherKey() string {
	return e.first("PUSHER_APP_KEY", "PUSHER_KEY")
}
func (e Env) PusherSecret() string {
	return e.first("PUSHER_APP_SECRET", "PUSHER_SECRET")
}
func (e Env) PusherCluster() string {
	return e.first("PUSHER_APP_CLUSTER", "PUSHER_CLUSTER")
}
