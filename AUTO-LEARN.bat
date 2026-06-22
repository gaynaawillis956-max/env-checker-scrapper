@echo off
REM Self-Optimizer - Autonomous Learning & Optimization Engine
title Self-Optimizer - Continuous Learning System

cd /d "%~dp0"

echo.
echo ========================================
echo   🤖 SELF-OPTIMIZER
echo   Autonomous Learning Engine
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

python3 self_optimizer.py

pause
