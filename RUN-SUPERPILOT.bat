@echo off
REM Unified Mail Tools - SuperPilot (Advanced Automated SMTP Testing)
title Unified Mail Tools - SuperPilot

cd /d "%~dp0"

echo.
echo ========================================
echo   Unified Mail Tools - SuperPilot
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

if "%1"=="" (
    echo Usage: RUN-SUPERPILOT.bat [smtp-list-file] [options]
    echo.
    echo Example:
    echo   RUN-SUPERPILOT.bat smtps.txt
    echo   RUN-SUPERPILOT.bat smtps.txt --threads 10 --warmup 60
    echo.
    echo Options:
    echo   --test-email EMAIL       Email for testing (default: test@example.com)
    echo   --threads NUMBER         Concurrent threads (default: 5)
    echo   --warmup SECONDS         Warmup between iterations (default: 30)
    echo   --iterations NUMBER      Number of iterations (default: 5)
    echo   --no-report              Skip HTML report generation
    echo.
    echo Features:
    echo   - Multi-threaded testing (5-10x faster)
    echo   - IMAP inbox verification
    echo   - HTML + CSV + JSON reports
    echo   - Detailed statistics
    echo   - Email sending tests
    echo.
    pause
    exit /b 1
)

echo Starting SuperPilot...
echo.
python3 superpilot.py %*

pause
