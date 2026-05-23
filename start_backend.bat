@echo off
chcp 65001 >nul
echo ========================================
echo   Backend Server Starting
echo ========================================
echo.

cd /d "%~dp0backend"
if not exist "app.py" (
    echo Error: Cannot find app.py in backend directory
    pause
    exit /b 1
)

echo [Step 1/3] Checking Python dependencies...
python -c "import flask; import flask_cors; import flask_sqlalchemy; import pymysql" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Python dependencies...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
) else (
    echo Dependencies check passed
)

echo.
echo [Step 2/3] Initializing MySQL database...
python init_mysql_db.py
if %errorlevel% neq 0 (
    echo Warning: Database initialization may have failed, continuing...
)

echo.
echo [Step 3/3] Starting Flask server...
echo Server will run at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.
python app.py
if %errorlevel% neq 0 (
    echo.
    echo Error: Server failed to start
    echo Please run diagnostic script: python test_startup.py
    pause
    exit /b 1
)

pause
