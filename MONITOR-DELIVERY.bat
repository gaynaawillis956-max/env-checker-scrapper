@echo off
REM Delivery Monitor - Check Inbox vs Spam Delivery
title Delivery Monitor - Check Campaign Performance

cd /d "%~dp0"

echo.
echo ========================================
echo   📧 DELIVERY MONITOR
echo   Check Which Emails Land In Inbox vs Spam
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 delivery_monitor.py

pause
