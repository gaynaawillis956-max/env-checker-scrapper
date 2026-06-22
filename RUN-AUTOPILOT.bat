@echo off
REM Unified Mail Tools - AutoPilot (Automated SMTP Testing)
title Unified Mail Tools - AutoPilot

cd /d "%~dp0"

echo.
echo ========================================
echo   Unified Mail Tools - AutoPilot
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

if "%1"=="" (
    echo Usage: RUN-AUTOPILOT.bat [smtp-list-file] [options]
    echo.
    echo Example:
    echo   RUN-AUTOPILOT.bat smtps.txt
    echo   RUN-AUTOPILOT.bat smtps.txt --warmup 60 --iterations 3
    echo.
    echo Options:
    echo   --test-email EMAIL       Email for inbox testing (default: test@example.com)
    echo   --warmup SECONDS         Wait time between iterations (default: 30)
    echo   --iterations NUMBER      Number of test iterations (default: 5)
    echo.
    pause
    exit /b 1
)

echo Starting AutoPilot...
python3 autopilot.py %*

pause
