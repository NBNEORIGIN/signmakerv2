@echo off
echo ========================================
echo Amazon Publisher - Async Job Worker
echo ========================================
echo.

cd /d "%~dp0"

REM Load environment variables
call config.bat

REM Check Python
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)

echo Starting worker process...
echo Press Ctrl+C to stop
echo.

REM Run worker
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" worker.py

pause
