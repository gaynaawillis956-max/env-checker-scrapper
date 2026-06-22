package validation

import (
	"bytes"
	"net/http"
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"
)

var canaryMarkers = [][]byte{
	[]byte("canarytokens.org"),
	[]byte("canarytokens.com"),
	[]byte("canarytoken"),
	[]byte("portswigger"),
	[]byte("burpcollaborator"),
	[]byte("interact.sh"),
	[]byte("oastify.com"),
}

// canaryURL matches any http/https URL in a value position — a lone URL as a
// credential value is a strong honeypot signal.
var canaryURL = regexp.MustCompile(`(?i)https?://[^\s"']+\.(canarytokens\.org|canarytokens\.com|burpcollaborator\.net|oastify\.com|interact\.sh)`)

const (
	maxContentLength = 2 * 1024 * 1024 // 2MB
)

// IsBinaryContent attempts to detect binary data via printable rune ratio.
func IsBinaryContent(data []byte) bool {
	if len(data) == 0 {
		return true
	}
	runes := utf8.RuneCount(data)
	if runes == 0 {
		return true
	}
	printable := 0
	for len(data) > 0 {
		r, size := utf8.DecodeRune(data)
		if r == utf8.RuneError && size == 1 {
			return true
		}
		if r == '\n' || r == '\r' || r == '\t' || unicode.IsPrint(r) {
			printable++
		}
		data = data[size:]
	}
	return float64(printable)/float64(runes) < 0.5
}

// LooksLikeHTML performs a lightweight HTML detection heuristic.
func LooksLikeHTML(data []byte) bool {
	lower := bytes.ToLower(data)
	return bytes.Contains(lower, []byte("<html")) || bytes.Contains(lower, []byte("<!doctype html"))
}

// IsHoneypot attempts to detect endlessly repeating honeypot responses.
func IsHoneypot(data []byte) bool {
	if len(data) < 128 {
		return false
	}
	segment := data[:64]
	if bytes.Count(data, segment)*len(segment) >= len(data)*8/10 {
		return true
	}
	lines := bytes.Split(data, []byte("\n"))
	if len(lines) > 1 {
		first := bytes.TrimSpace(lines[0])
		repeats := 0
		for _, line := range lines[1:] {
			if bytes.Equal(bytes.TrimSpace(line), first) {
				repeats++
			}
		}
		if repeats > len(lines)/2 {
			return true
		}
	}
	return false
}

// IsCanaryToken detects honeypot canary files planted to identify scanners.
func IsCanaryToken(data []byte) bool {
	lower := bytes.ToLower(data)
	for _, marker := range canaryMarkers {
		if bytes.Contains(lower, marker) {
			return true
		}
	}
	return canaryURL.Match(data)
}

// ShouldDiscardResponse determines whether the response body should be ignored.
// Callers are responsible for filtering non-2xx status codes before calling this.
func ShouldDiscardResponse(resp *http.Response, body []byte) bool {
	if resp == nil {
		return true
	}
	if len(body) == 0 || len(body) > maxContentLength {
		return true
	}
	contentType := strings.ToLower(resp.Header.Get("Content-Type"))
	if strings.Contains(contentType, "text/html") || LooksLikeHTML(body) {
		return true
	}
	if IsBinaryContent(body) {
		return true
	}
	if IsHoneypot(body) {
		return true
	}
	if IsCanaryToken(body) {
		return true
	}
	return false
}
