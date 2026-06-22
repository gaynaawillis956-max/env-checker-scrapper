@echo off
REM Content Rotator - Create Email Body Variations
title Content Rotator - Email Body Variations

cd /d "%~dp0"

echo.
echo ========================================
echo   📧 CONTENT ROTATOR
echo   Create Email Body Variations
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 content_rotator.py

pause
