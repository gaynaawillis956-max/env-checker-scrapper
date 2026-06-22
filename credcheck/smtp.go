package credcheck

import (
	"crypto/tls"
	"fmt"
	"net"
	"net/smtp"
	"strings"
	"time"
)

// SMTPResult is the outcome of an SMTP credential check.
type SMTPResult struct {
	Reachable bool   // TCP port is open
	AuthValid bool   // credentials accepted by server
	Banner    string // EHLO banner from the server
	Message   string // human-readable verdict
	Error     string
}

// CheckSMTP probes the SMTP server and attempts AUTH LOGIN.
func CheckSMTP(cfg *SMTPConfig) SMTPResult {
	if cfg == nil {
		return SMTPResult{Message: "no SMTP config extracted"}
	}

	addr := net.JoinHostPort(cfg.Host, cfg.Port)

	// 1. TCP reachability
	conn, err := net.DialTimeout("tcp", addr, 10*time.Second)
	if err != nil {
		return SMTPResult{
			Message: "port not reachable",
			Error:   err.Error(),
		}
	}
	conn.Close()

	res := SMTPResult{Reachable: true}

	if cfg.User == "" || cfg.Pass == "" {
		res.Message = fmt.Sprintf("port %s open — no credentials to test", cfg.Port)
		return res
	}

	// 2. SMTP auth
	var client *smtp.Client
	var authErr error

	switch cfg.Port {
	case "465": // SMTPS (implicit TLS)
		tlsCfg := &tls.Config{InsecureSkipVerify: true, ServerName: cfg.Host}
		tlsConn, err := tls.DialWithDialer(
			&net.Dialer{Timeout: 12 * time.Second}, "tcp", addr, tlsCfg,
		)
		if err != nil {
			res.Message = "TLS connect failed"
			res.Error = err.Error()
			return res
		}
		client, authErr = smtp.NewClient(tlsConn, cfg.Host)

	default: // 25, 587, 2525 — plain + optional STARTTLS
		client, authErr = smtp.Dial(addr)
		if authErr == nil {
			if ok, _ := client.Extension("STARTTLS"); ok {
				_ = client.StartTLS(&tls.Config{InsecureSkipVerify: true})
			}
		}
	}

	if authErr != nil {
		res.Message = "SMTP handshake failed"
		res.Error = authErr.Error()
		return res
	}
	defer client.Close()

	// Capture banner (EHLO)
	if err := client.Hello("env-checker"); err == nil {
		res.Banner = cfg.Host
	}

	// Try PLAIN auth first, then LOGIN
	authed := false
	for _, authFn := range []smtp.Auth{
		smtp.PlainAuth("", cfg.User, cfg.Pass, cfg.Host),
		loginAuth(cfg.User, cfg.Pass),
	} {
		if err := client.Auth(authFn); err == nil {
			authed = true
			break
		}
	}

	if authed {
		res.AuthValid = true
		res.Message = fmt.Sprintf("✓ VALID — user=%s host=%s:%s", cfg.User, cfg.Host, cfg.Port)
	} else {
		res.AuthValid = false
		res.Message = fmt.Sprintf("✗ AUTH FAILED — user=%s host=%s:%s", cfg.User, cfg.Host, cfg.Port)
	}
	return res
}

// loginAuth implements SMTP AUTH LOGIN (some servers only support this).
type loginAuthImpl struct{ user, pass string }

func loginAuth(user, pass string) smtp.Auth { return &loginAuthImpl{user, pass} }

func (a *loginAuthImpl) Start(*smtp.ServerInfo) (string, []byte, error) {
	return "LOGIN", nil, nil
}
func (a *loginAuthImpl) Next(fromServer []byte, more bool) ([]byte, error) {
	if !more {
		return nil, nil
	}
	prompt := strings.ToLower(string(fromServer))
	switch {
	case strings.Contains(prompt, "username") || strings.Contains(prompt, "user"):
		return []byte(a.user), nil
	case strings.Contains(prompt, "password") || strings.Contains(prompt, "pass"):
		return []byte(a.pass), nil
	}
	return nil, fmt.Errorf("unexpected server prompt: %s", fromServer)
}
