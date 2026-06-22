@echo off
REM Launch Desktop GUI (Tkinter)
REM Works from any location

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Unified Mail Tools - Desktop GUI
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

REM Run in desktop mode
echo Starting Desktop Interface...
python3 "%SCRIPT_DIR%run.py" --mode desktop

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to start Desktop GUI
    echo.
    pause
    exit /b 1
)

pause
