package credcheck

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// AWSResult is the outcome of an AWS credential check via STS GetCallerIdentity.
type AWSResult struct {
	Valid     bool
	AccountID string
	UserID    string
	ARN       string
	Message   string
	Error     string
}

// CheckAWS calls STS GetCallerIdentity — a read-only, zero-privilege API call
// that returns account metadata if credentials are valid.
func CheckAWS(cfg *AWSConfig) AWSResult {
	if cfg == nil {
		return AWSResult{Message: "no AWS config extracted"}
	}

	endpoint := fmt.Sprintf("https://sts.%s.amazonaws.com/", cfg.Region)
	payload := "Action=GetCallerIdentity&Version=2011-06-15"

	req, err := http.NewRequest("POST", endpoint, strings.NewReader(payload))
	if err != nil {
		return AWSResult{Error: err.Error()}
	}

	now := time.Now().UTC()
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("X-Amz-Date", now.Format("20060102T150405Z"))
	if cfg.SessionToken != "" {
		req.Header.Set("X-Amz-Security-Token", cfg.SessionToken)
	}

	signV4(req, payload, cfg, now)

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return AWSResult{Error: err.Error()}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode != 200 {
		return AWSResult{
			Valid:   false,
			Message: fmt.Sprintf("HTTP %d — credentials invalid or expired", resp.StatusCode),
			Error:   string(body),
		}
	}

	var result struct {
		XMLName xml.Name `xml:"GetCallerIdentityResponse"`
		Result  struct {
			Account string `xml:"Account"`
			UserID  string `xml:"UserId"`
			ARN     string `xml:"Arn"`
		} `xml:"GetCallerIdentityResult"`
	}
	if err := xml.Unmarshal(body, &result); err != nil {
		return AWSResult{Valid: true, Message: "credentials valid (parse error)", Error: err.Error()}
	}

	return AWSResult{
		Valid:     true,
		AccountID: result.Result.Account,
		UserID:    result.Result.UserID,
		ARN:       result.Result.ARN,
		Message:   fmt.Sprintf("✓ VALID — account=%s arn=%s", result.Result.Account, result.Result.ARN),
	}
}

// ── AWS Signature Version 4 ───────────────────────────────────────────────────

func signV4(req *http.Request, payload string, cfg *AWSConfig, t time.Time) {
	service := "sts"
	dateStamp := t.Format("20060102")
	amzDate := t.Format("20060102T150405Z")

	// Canonical request
	payloadHash := hashSHA256(payload)
	canonicalHeaders := fmt.Sprintf("content-type:application/x-www-form-urlencoded\nhost:%s\nx-amz-date:%s\n",
		req.URL.Host, amzDate)
	if cfg.SessionToken != "" {
		canonicalHeaders += fmt.Sprintf("x-amz-security-token:%s\n", cfg.SessionToken)
	}
	signedHeaders := "content-type;host;x-amz-date"
	if cfg.SessionToken != "" {
		signedHeaders += ";x-amz-security-token"
	}
	canonicalReq := strings.Join([]string{
		"POST", "/", "",
		canonicalHeaders, signedHeaders, payloadHash,
	}, "\n")

	// String to sign
	credScope := strings.Join([]string{dateStamp, cfg.Region, service, "aws4_request"}, "/")
	stringToSign := strings.Join([]string{
		"AWS4-HMAC-SHA256", amzDate, credScope, hashSHA256(canonicalReq),
	}, "\n")

	// Signing key
	signingKey := hmacSHA256(
		hmacSHA256(
			hmacSHA256(
				hmacSHA256([]byte("AWS4"+cfg.SecretKey), dateStamp),
				cfg.Region,
			),
			service,
		),
		"aws4_request",
	)

	signature := hex.EncodeToString(hmacSHA256(signingKey, stringToSign))
	auth := fmt.Sprintf(
		"AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s",
		cfg.AccessKey, credScope, signedHeaders, signature,
	)
	req.Header.Set("Authorization", auth)
}

func hmacSHA256(key []byte, data string) []byte {
	h := hmac.New(sha256.New, key)
	h.Write([]byte(data))
	return h.Sum(nil)
}

func hashSHA256(s string) string {
	h := sha256.Sum256([]byte(s))
	return hex.EncodeToString(h[:])
}
