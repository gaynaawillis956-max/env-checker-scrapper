package dns

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/netip"
	"os"
	"strings"
	"sync"
	"time"
)

// Resolver performs distributed reverse DNS lookups.
type Resolver struct {
	Servers     []string
	Timeout     time.Duration
	Concurrency int
	cache       sync.Map
}

// NewResolver constructs a Resolver instance.
func NewResolver(servers []string, timeout time.Duration, concurrency int) *Resolver {
	if concurrency <= 0 {
		concurrency = 50
	}
	return &Resolver{Servers: servers, Timeout: timeout, Concurrency: concurrency}
}

// LoadServers loads DNS servers from file or remote source with fallbacks.
func LoadServers(path string) ([]string, error) {
	if path != "" {
		if servers, err := loadServersFromFile(path); err == nil && len(servers) > 0 {
			return servers, nil
		}
	}
	if servers, err := downloadPublicServers(); err == nil && len(servers) > 0 {
		return servers, nil
	}
	return defaultPublicResolvers(), nil
}

func loadServersFromFile(path string) ([]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	servers := make([]string, 0, 128)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		servers = append(servers, line)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return servers, nil
}

func downloadPublicServers() ([]string, error) {
	client := http.Client{Timeout: 20 * time.Second}
	resp, err := client.Get("https://public-dns.info/nameservers.txt")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %d from public-dns.info", resp.StatusCode)
	}

	scanner := bufio.NewScanner(resp.Body)
	servers := make([]string, 0, 256)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if ip := net.ParseIP(line); ip == nil {
			continue
		}
		servers = append(servers, line)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	if len(servers) == 0 {
		return nil, errors.New("no public DNS servers retrieved")
	}
	return servers, nil
}

func defaultPublicResolvers() []string {
	return []string{
		"1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "149.112.112.112",
		"208.67.222.222", "208.67.220.220", "64.6.64.6", "64.6.65.6", "185.228.168.9", "45.90.28.0",
	}
}

// ReverseLookup performs a reverse lookup with caching.
func (r *Resolver) ReverseLookup(ip string) (string, error) {
	if value, ok := r.cache.Load(ip); ok {
		return value.(string), nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), r.Timeout)
	defer cancel()

	sem := make(chan struct{}, r.Concurrency)
	results := make(chan string, 1)
	var wg sync.WaitGroup

	for _, server := range r.Servers {
		if net.ParseIP(server) == nil {
			continue
		}
		wg.Add(1)
		sem <- struct{}{}
		go func(srv string) {
			defer wg.Done()
			defer func() { <-sem }()

			resolver := &net.Resolver{
				PreferGo: true,
				Dial: func(ctx context.Context, network, address string) (net.Conn, error) {
					d := net.Dialer{Timeout: r.Timeout}
					return d.DialContext(ctx, "udp", net.JoinHostPort(srv, "53"))
				},
			}

			names, err := resolver.LookupAddr(ctx, ip)
			if err != nil || len(names) == 0 {
				return
			}
			select {
			case results <- strings.TrimSuffix(names[0], "."):
			default:
			}
		}(server)
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	select {
	case name, ok := <-results:
		if !ok {
			return "", fmt.Errorf("no reverse DNS for %s", ip)
		}
		r.cache.Store(ip, name)
		return name, nil
	case <-ctx.Done():
		return "", fmt.Errorf("reverse lookup timeout for %s", ip)
	}
}

// SupportsIPv6 reports whether the resolver address is IPv6.
func SupportsIPv6(addr string) bool {
	host, _, err := net.SplitHostPort(addr)
	if err != nil {
		host = addr
	}
	ip, err := netip.ParseAddr(host)
	if err != nil {
		return false
	}
	return ip.Is6()
}
