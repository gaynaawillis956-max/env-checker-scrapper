@echo off
REM 📧 Template Manager - Create & Rotate HTML & Text Templates
title Template Manager - Email Template Rotation

cd /d "%~dp0"

echo.
echo ========================================
echo   📧 EMAIL TEMPLATE ROTATOR
echo   Rotate HTML & Text Templates
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 template_rotator.py

pause
