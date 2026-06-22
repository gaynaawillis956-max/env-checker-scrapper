package scanner

import (
	"context"
	"crypto/tls"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const maxResponseSize = 2 * 1024 * 1024

// HTTPClientFactory constructs HTTP clients tailored per mode.
type HTTPClientFactory struct {
	timeout time.Duration
}

// NewHTTPClientFactory creates a new factory instance.
func NewHTTPClientFactory(timeout time.Duration) *HTTPClientFactory {
	return &HTTPClientFactory{timeout: timeout}
}

// Client returns a configured HTTP client for the given mode.
func (f *HTTPClientFactory) Client(mode Mode) *http.Client {
	transport := &http.Transport{
		Proxy:               http.ProxyFromEnvironment,
		TLSClientConfig:     &tls.Config{InsecureSkipVerify: true},
		MaxIdleConns:        1024,
		MaxIdleConnsPerHost: 256,
		IdleConnTimeout:     30 * time.Second,
		TLSHandshakeTimeout: 10 * time.Second,
	}

	if mode == ModeHTTP {
		transport.TLSClientConfig = nil
	}

	return &http.Client{
		Timeout:   f.timeout,
		Transport: transport,
	}
}

// BuildRequest constructs an HTTP request for the specified parameters.
func BuildRequest(ctx context.Context, mode Mode, host, path, resolved string) (*http.Request, error) {
	scheme := "https"
	switch mode {
	case ModeHTTP:
		scheme = "http"
	case ModeHTTPS, ModeHTTPSDNS:
		scheme = "https"
	}

	target := buildURL(scheme, host, path)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		return nil, err
	}
	if mode == ModeHTTPSDNS && resolved != "" {
		req.Host = resolved
	}
	req.Header.Set("User-Agent", "env-checker/1.0")
	return req, nil
}

func buildURL(scheme, host, path string) string {
	normalizedHost := host
	if strings.Contains(host, ":") && !strings.HasPrefix(host, "[") {
		normalizedHost = "[" + host + "]"
	}
	normalizedPath := path
	if normalizedPath == "" {
		normalizedPath = "/"
	}
	if !strings.HasPrefix(normalizedPath, "/") {
		normalizedPath = "/" + normalizedPath
	}

	u := url.URL{
		Scheme: scheme,
		Host:   normalizedHost,
		Path:   normalizedPath,
	}
	if strings.Contains(path, "%") {
		u.RawPath = normalizedPath
	}
	return u.String()
}

// Fetch executes the HTTP request and enforces body size limits.
func Fetch(client *http.Client, req *http.Request) (*http.Response, []byte, error) {
	resp, err := client.Do(req)
	if err != nil {
		return nil, nil, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseSize))
	if err != nil {
		return resp, nil, err
	}
	return resp, body, nil
}
