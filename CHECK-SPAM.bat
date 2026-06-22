@echo off
REM Spam Analyzer - Check If Email Gets Inbox or Spam
title Spam Analyzer - Email Content Check

cd /d "%~dp0"

echo.
echo ========================================
echo   📧 SPAM ANALYZER
echo   Check If Your Email Will Go To Spam
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 spam_analyzer.py

pause
