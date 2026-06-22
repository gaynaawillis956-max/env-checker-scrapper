#!/usr/bin/env bash
set -e

echo "[*] Building env-checker..."
go build -o env-checker . || { echo "[!] Build failed. Make sure Go is installed: https://go.dev/dl/"; exit 1; }

echo "[*] Starting web UI on http://127.0.0.1:8080"

# Open browser in background (works on Linux, macOS, WSL)
if command -v xdg-open &>/dev/null; then
    (sleep 1 && xdg-open "http://127.0.0.1:8080") &
elif command -v open &>/dev/null; then
    (sleep 1 && open "http://127.0.0.1:8080") &
fi

./env-checker --web --addr 127.0.0.1:8080
