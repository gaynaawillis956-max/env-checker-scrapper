@echo off
REM Multi-Provider Deliverability Checker
title Multi-Provider Deliverability Test

cd /d "%~dp0"

echo.
echo ========================================
echo   Multi-Provider Deliverability Checker
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

if "%1"=="" (
    echo Usage: RUN-DELIVERABILITY.bat [email] [password] [options]
    echo.
    echo Examples:
    echo   RUN-DELIVERABILITY.bat user@gmail.com "app_password"
    echo   RUN-DELIVERABILITY.bat user@outlook.com "password" --provider outlook
    echo   RUN-DELIVERABILITY.bat user@custom.com "password" --imap imap.custom.com
    echo.
    echo Supported Providers:
    echo   - Gmail (app password required)
    echo   - Outlook / Microsoft 365
    echo   - Yahoo Mail (app password required)
    echo   - AOL (app password required)
    echo   - ProtonMail
    echo   - Zoho Mail
    echo   - iCloud (app password required)
    echo   - Custom IMAP/SMTP servers
    echo.
    echo Options:
    echo   --provider PROVIDER      Gmail, Outlook, Yahoo, etc
    echo   --imap HOST              Custom IMAP server
    echo   --imap-port PORT         IMAP port (default: 993)
    echo   --smtp HOST              Custom SMTP server
    echo   --smtp-port PORT         SMTP port (default: 587)
    echo   --timeout SECONDS        Connection timeout (default: 10)
    echo.
    pause
    exit /b 1
)

echo Testing %1...
echo.
python3 multi_deliverability.py %*

pause
