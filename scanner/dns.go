package scanner

import (
	"time"

	"env-checker/dns"
)

// DNSManager wraps the shared DNS resolver instance.
type DNSManager struct {
	resolver *dns.Resolver
}

// NewDNSManager constructs a DNS manager using provided servers.
func NewDNSManager(servers []string, timeout time.Duration, concurrency int) *DNSManager {
	return &DNSManager{resolver: dns.NewResolver(servers, timeout, concurrency)}
}

// ReverseLookup performs reverse DNS lookup.
func (d *DNSManager) ReverseLookup(ip string) (string, error) {
	return d.resolver.ReverseLookup(ip)
}
