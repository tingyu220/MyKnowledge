@echo off
REM Set UTF-8 code page first
chcp 65001 >nul 2>&1

echo ========================================
echo   Personal Library Management System
echo ========================================
echo.
echo Starting backend service in new window...
start "Backend Server" cmd /k "cd /d %~dp0 && start_backend.bat"
timeout /t 3 /nobreak >nul
echo Starting frontend service in new window...
start "Frontend Server" cmd /k "cd /d %~dp0 && start_frontend.bat"
echo.
echo Both services started in new windows!
echo Backend: http://localhost:5000
echo Frontend: http://localhost:3000

pause
