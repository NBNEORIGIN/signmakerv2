@echo off
title Amazon Publisher - Install Dependencies
echo ============================================================
echo   Amazon Publisher REV 2.0 - Dependency Installer
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from python.org
    pause
    exit /b 1
)

echo Installing Python dependencies...
echo.

pip install -r requirements.txt

echo.
echo ============================================================
echo   Dependencies installed successfully!
echo ============================================================
echo.
echo IMPORTANT: You also need Inkscape installed for image generation.
echo Download from: https://inkscape.org/release/
echo Make sure Inkscape is added to your system PATH.
echo.
pause
