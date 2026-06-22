package benchmark

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"env-checker/cli"
)

// Run executes benchmark configurations defined in the provided file.
func Run(cfg *cli.Config) error {
	file, err := os.Open(cfg.BenchmarkFile)
	if err != nil {
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	lineNo := 0
	for scanner.Scan() {
		lineNo++
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		args := strings.Fields(line)
		cmdArgs := append([]string{"run", "."}, args...)
		if cfg.InputFile != "" {
			cmdArgs = append(cmdArgs, "-i", cfg.InputFile)
		}
		fmt.Printf("[benchmark] configuration %d: go %s\n", lineNo, strings.Join(cmdArgs, " "))
		start := time.Now()
		cmd := exec.Command("go", cmdArgs...)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			fmt.Printf("[benchmark] configuration %d failed: %v\n", lineNo, err)
		} else {
			fmt.Printf("[benchmark] configuration %d completed in %s\n", lineNo, time.Since(start))
		}
	}
	return scanner.Err()
}
