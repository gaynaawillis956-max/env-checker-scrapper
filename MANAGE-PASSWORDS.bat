@echo off
REM Secure Credential Manager
title Credential Manager - Save & Use Passwords Forever

cd /d "%~dp0"

echo.
echo ========================================
echo   📝 CREDENTIAL MANAGER
echo   Save passwords once, use forever
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 credential_manager.py --interactive

pause
