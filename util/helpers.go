package util

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"hash/fnv"
	"net"
	"os"
	"path/filepath"
	"runtime/debug"
	"strconv"
	"strings"
	"sync"
	"time"
)

// SplitAndTrim splits a comma-separated string and trims whitespace.
func SplitAndTrim(s string) []string {
	parts := strings.Split(s, ",")
	res := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			res = append(res, trimmed)
		}
	}
	return res
}

// ApplyMemoryLimit configures Go's soft memory limit in megabytes.
func ApplyMemoryLimit(limitMB int) {
	if limitMB <= 0 {
		return
	}
	debug.SetMemoryLimit(int64(limitMB) * 1024 * 1024)
}

// HashContent returns the SHA256 hex digest for the provided byte slice.
func HashContent(data []byte) string {
	checksum := sha256.Sum256(data)
	return hex.EncodeToString(checksum[:])
}

// ReadLinesFromOffset streams lines from a file starting at the specified offset index.
func ReadLinesFromOffset(path string, offset int, handler func(int, string) error) error {
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()

	if offset < 0 {
		offset = 0
	}

	scanner := bufio.NewScanner(file)
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 4*1024*1024)
	index := 0
	for scanner.Scan() {
		line := scanner.Text()
		if index >= offset {
			trimmed := strings.TrimSpace(line)
			if trimmed != "" {
				if err := handler(index, trimmed); err != nil {
					return err
				}
			}
		}
		index++
	}
	if err := scanner.Err(); err != nil {
		return err
	}
	return nil
}

// IterateCIDR visits each address contained within the CIDR block.
func IterateCIDR(cidr string, visitor func(string) error) error {
	_, network, err := net.ParseCIDR(cidr)
	if err != nil {
		return err
	}

	start := network.IP.Mask(network.Mask)
	for ip := make(net.IP, len(start)); ; {
		copy(ip, start)
		if !network.Contains(ip) {
			break
		}
		if err := visitor(ip.String()); err != nil {
			return err
		}
		incrementIP(start)
	}
	return nil
}

func incrementIP(ip net.IP) {
	for i := len(ip) - 1; i >= 0; i-- {
		ip[i]++
		if ip[i] != 0 {
			break
		}
	}
}

// FileExists returns true when the provided path exists.
func FileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// EnsureDir creates the directory if it does not exist.
func EnsureDir(path string) error {
	if path == "" {
		return errors.New("empty directory path")
	}
	return os.MkdirAll(path, 0o755)
}

// WriteFileAtomic writes to a temporary file before renaming to the target path.
func WriteFileAtomic(path string, data []byte) error {
	dir := filepath.Dir(path)
	if err := EnsureDir(dir); err != nil {
		return err
	}
	temp := fmt.Sprintf("%s.tmp-%d", path, time.Now().UnixNano())
	if err := os.WriteFile(temp, data, 0o600); err != nil {
		return err
	}
	return os.Rename(temp, path)
}

// AtomicWriteLines writes lines to the target file atomically.
func AtomicWriteLines(path string, lines []string) error {
	builder := strings.Builder{}
	for _, line := range lines {
		builder.WriteString(line)
		builder.WriteByte('\n')
	}
	return WriteFileAtomic(path, []byte(builder.String()))
}

// ReadLines reads a file into memory trimming whitespace.
func ReadLines(path string) ([]string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
	lines := make([]string, 0)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" {
			lines = append(lines, line)
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return lines, nil
}

// ExpandCIDR walks a CIDR range and returns all hosts.
func ExpandCIDR(cidr string, includeIPs bool) ([]string, error) {
	entries := make([]string, 0)
	err := IterateCIDR(cidr, func(addr string) error {
		if includeIPs {
			entries = append(entries, addr)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return entries, nil
}

// ParsePort parses a port string into integer.
func ParsePort(val string) (int, error) {
	port, err := strconv.Atoi(val)
	if err != nil {
		return 0, err
	}
	if port <= 0 || port > 65535 {
		return 0, fmt.Errorf("invalid port: %d", port)
	}
	return port, nil
}

// SafeTruncate shortens a string for logging purposes.
func SafeTruncate(s string, limit int) string {
	if len(s) <= limit {
		return s
	}
	if limit <= 3 {
		return s[:limit]
	}
	return s[:limit-3] + "..."
}

// NowUTC returns the current UTC timestamp.
func NowUTC() time.Time {
	return time.Now().UTC()
}

// CountLines counts newlines in a file efficiently using block reads.
// Used for ETA calculation; the result may be off by one if the file lacks a
// trailing newline, which is acceptable for progress estimation.
func CountLines(path string) (int64, error) {
	f, err := os.Open(path)
	if err != nil {
		return 0, err
	}
	defer f.Close()
	var count int64
	buf := make([]byte, 32*1024)
	for {
		n, rerr := f.Read(buf)
		for i := 0; i < n; i++ {
			if buf[i] == '\n' {
				count++
			}
		}
		if rerr != nil {
			break
		}
	}
	return count, nil
}

// ClusterCoordinator distributes work across peers using consistent hashing.
type ClusterCoordinator struct {
	peers  []string
	index  int
	modulo int
	once   sync.Once
}

// NewClusterCoordinator constructs a cluster coordinator from peer definitions.
func NewClusterCoordinator(peers []string) *ClusterCoordinator {
	cc := &ClusterCoordinator{peers: append([]string(nil), peers...)}
	if len(peers) == 0 {
		return cc
	}
	idx := 0
	if val := os.Getenv("ENV_CHECKER_CLUSTER_INDEX"); val != "" {
		if parsed, err := strconv.Atoi(val); err == nil && parsed >= 0 {
			idx = parsed
		}
	}
	cc.modulo = len(peers)
	if cc.modulo > 0 {
		cc.index = idx % cc.modulo
	}
	return cc
}

// Enabled reports whether clustering is active.
func (c *ClusterCoordinator) Enabled() bool {
	return c.modulo > 0
}

// Index returns the local cluster index.
func (c *ClusterCoordinator) Index() int {
	if c.modulo == 0 {
		return 0
	}
	return c.index
}

// ShouldProcess returns true when the host should be processed by this node.
func (c *ClusterCoordinator) ShouldProcess(host string) bool {
	if !c.Enabled() {
		return true
	}
	h := fnv.New32a()
	_, _ = h.Write([]byte(host))
	return int(h.Sum32()%uint32(c.modulo)) == c.index
}
