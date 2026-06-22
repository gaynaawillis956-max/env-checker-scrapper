@echo off
title env-checker

echo [*] Building env-checker...
go build -o env-checker.exe . 2>&1
if errorlevel 1 (
    echo [!] Build failed. Make sure Go is installed: https://go.dev/dl/
    pause
    exit /b 1
)

echo [*] Starting web UI on http://127.0.0.1:8080
start "" "http://127.0.0.1:8080"
env-checker.exe --web --addr 127.0.0.1:8080
pause
