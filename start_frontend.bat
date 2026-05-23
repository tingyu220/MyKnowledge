@echo off
REM Set UTF-8 code page first
chcp 65001 >nul 2>&1

echo Starting frontend service...
cd /d "%~dp0frontend"
if not exist "package.json" (
    echo Error: Cannot find package.json in frontend directory
    pause
    exit /b 1
)

echo Checking and installing Node.js dependencies...
call npm install
if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Starting development server...
echo HTTPS certificate will be regenerated for current local IPs before startup.
echo Frontend will run at: https://localhost:3000
echo Press Ctrl+C to stop the server
echo.
call npm run dev

pause
