@echo off
REM Warmup Scheduler - Gradually Warm Up SMTP Accounts
title Warmup Scheduler - Build Sender Reputation

cd /d "%~dp0"

echo.
echo ========================================
echo   📈 WARMUP SCHEDULER
echo   Gradually Build SMTP Account Reputation
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 warmup_scheduler.py

pause
