@echo off
REM Quick Start - Setup Templates & Send Test
title Quick Start - Email Templates

cd /d "%~dp0"

echo.
echo ========================================
echo   📧 QUICK START - EMAIL TEMPLATES
echo   Create & Test Template Rotation
echo ========================================
echo.

python3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 not found
    pause
    exit /b 1
)

echo.
echo [STEP 1/3] Creating sample templates...
echo.

python3 template_rotator.py << EOF
1
EOF

echo.
echo [STEP 2/3] Listing created templates...
echo.

python3 template_rotator.py << EOF
4
8
EOF

echo.
echo ========================================
echo   ✓ TEMPLATES READY!
echo ========================================
echo.
echo Next steps:
echo.
echo   1. Start web server:   RUN-WEB.bat
echo   2. Open browser:       http://127.0.0.1:5000
echo   3. Go to Mass Mailer tab
echo   4. Upload SMTP accounts
echo   5. Enter test emails
echo   6. Select a template from dropdown
echo   7. Click Send
echo.
echo For more info, see: TEMPLATES-README.md
echo.

pause
