@echo off
REM Launch Web Interface (Flask)
REM Access at http://127.0.0.1:5000

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Unified Mail Tools - Web Server
echo ========================================
echo.

REM Check Python 3
python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 is not installed or not in PATH
    pause
    exit /b 1
)

REM Get script directory
set SCRIPT_DIR=%~dp0

REM Install dependencies
echo Installing dependencies...
python3 -m pip install -q -r "%SCRIPT_DIR%requirements.txt"

REM Run in web mode
echo Starting Web Server...
echo.
echo Open your browser to: http://127.0.0.1:5000
echo.
python3 "%SCRIPT_DIR%run.py" --mode web

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to start Web Server
    echo.
    pause
    exit /b 1
)

pause
