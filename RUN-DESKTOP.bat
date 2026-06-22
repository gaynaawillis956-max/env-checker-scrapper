@echo off
REM Unified Mail Tools - Desktop GUI
title Unified Mail Tools - Desktop

cd /d "%~dp0"

echo.
echo ========================================
echo   Unified Mail Tools - Desktop GUI
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo Launching Desktop GUI...
echo.
python3 start.py desktop

pause
