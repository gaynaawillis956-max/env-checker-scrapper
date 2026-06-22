@echo off
REM Campaign Analytics - Track Performance & Insights
title Campaign Analytics - Performance Tracking

cd /d "%~dp0"

echo.
echo ========================================
echo   📊 CAMPAIGN ANALYTICS
echo   Track Performance by SMTP/Content
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 advanced_analytics.py

pause
