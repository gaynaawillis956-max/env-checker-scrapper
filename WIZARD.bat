@echo off
REM Interactive Setup & Troubleshooting Wizard
title Unified Mail Tools - Wizard

cd /d "%~dp0"

echo.
echo ========================================
echo   Unified Mail Tools - Wizard
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

python3 wizard.py

pause
