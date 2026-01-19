@echo off
title Installing Python Packages for Amazon Publisher
cd /d "%~dp0"

echo ============================================================
echo   Amazon Publisher - Package Installer
echo ============================================================
echo.

REM Check Python is installed
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo Python found:
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" --version
echo.

echo Installing required packages...
echo.

"C:\Users\Admin\AppData\Local\Python\bin\python.exe" -m pip install flask lxml anthropic openai boto3 openpyxl requests Pillow

echo.
echo ============================================================
echo   Installation Complete!
echo ============================================================
echo.
echo Testing imports...
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" -c "import flask, lxml, anthropic, openai, boto3, openpyxl, requests, PIL; print('All packages installed successfully!')"

if errorlevel 1 (
    echo.
    echo WARNING: Some packages may have failed to install.
    echo Check the output above for errors.
) else (
    echo.
    echo You can now run PUBLISHER_WEB.bat to start the application.
)

echo.
pause
