@echo off
REM Unified Mail Tools - Web Server
title Unified Mail Tools - Web Server

cd /d "%~dp0"

echo.
echo ========================================
echo   Unified Mail Tools - Web Server
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo Launching Web Server...
echo.
echo Opening: http://127.0.0.1:5000
echo.

python3 start.py web

pause
