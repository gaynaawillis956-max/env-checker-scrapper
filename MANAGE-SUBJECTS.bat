@echo off
REM Subject Line Manager - Create & Rotate Email Subjects
title Subject Line Manager - Email Subject Rotation

cd /d "%~dp0"

echo.
echo ========================================
echo   📧 SUBJECT LINE ROTATOR
echo   Create & Rotate Email Subjects
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 subject_rotator.py

pause
