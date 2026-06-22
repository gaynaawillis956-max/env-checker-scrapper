@echo off
REM Format Converter - Auto-detect and convert credential formats
title Format Converter

cd /d "%~dp0"

echo.
echo ========================================
echo   Credential Format Converter
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

if "%1"=="" (
    echo Usage: RUN-CONVERTER.bat [input-file] [options]
    echo.
    echo Examples:
    echo   RUN-CONVERTER.bat combos.txt --detect
    echo   RUN-CONVERTER.bat combos.txt --output converted.txt
    echo.
    echo Options:
    echo   --detect           Just show format detection stats
    echo   --output FILE      Save converted credentials
    echo   --port PORT        Default SMTP port (default: 587)
    echo.
    echo Supported Input Formats:
    echo   • email@domain.com:password
    echo   • user@domain.com:password
    echo   • smtp.server.com:password
    echo   • smtp.server.com:587:user@domain.com:password
    echo.
    pause
    exit /b 1
)

echo Running converter...
python3 format_converter.py %*

pause
