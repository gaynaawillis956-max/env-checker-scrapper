package scanner

// Mode represents a scanning transport strategy.
type Mode string

const (
	// ModeHTTPS connects over HTTPS directly via IP or hostname.
	ModeHTTPS Mode = "HTTPS"
	// ModeHTTP connects over plain HTTP.
	ModeHTTP Mode = "HTTP"
	// ModeHTTPSDNS performs HTTPS with virtual host substitution.
	ModeHTTPSDNS Mode = "HTTPS-DNS"
)

// Modes returns the ordered list of scanning modes.
func Modes() []Mode {
	return []Mode{ModeHTTPS, ModeHTTP, ModeHTTPSDNS}
}
