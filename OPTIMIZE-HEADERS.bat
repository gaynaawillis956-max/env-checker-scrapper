@echo off
REM Header Optimizer - DKIM, SPF, DMARC Setup
title Header Optimizer - Advanced Email Authentication

cd /d "%~dp0"

echo.
echo ========================================
echo   🔐 ADVANCED HEADER OPTIMIZER
echo   DKIM, SPF, DMARC Authentication
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 header_optimizer.py

pause
