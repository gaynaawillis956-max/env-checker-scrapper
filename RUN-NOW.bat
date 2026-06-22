@echo off
REM ⚡ ULTIMATE AUTOPILOT - 1 CLICK DOES EVERYTHING
title Ultimate AutoPilot - 1 Click to Do All

cd /d "%~dp0"

echo.
echo ========================================
echo   ⚡ ULTIMATE AUTOPILOT
echo   1 Click to Do Everything
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

if "%1"=="" (
    echo Usage: RUN-NOW.bat [credential_file]
    echo.
    echo Example:
    echo   RUN-NOW.bat combos.txt
    echo   RUN-NOW.bat your_accounts.txt
    echo.
    echo That's it! Everything else is automatic.
    echo.
    pause
    exit /b 1
)

echo.
python3 ultimate_autopilot.py %1

echo.
pause
