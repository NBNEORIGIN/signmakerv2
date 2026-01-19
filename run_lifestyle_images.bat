@echo off
title Amazon Publisher - Generate Lifestyle Images
echo ============================================================
echo   Amazon Publisher REV 2.0 - Lifestyle Image Generator
echo ============================================================
echo.

REM Set working directory to this script's location
cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Load API keys from config
if exist "config.bat" (
    call config.bat
) else (
    echo ERROR: config.bat not found
    pause
    exit /b 1
)

echo Generating lifestyle images for products marked 'yes' in CSV...
echo.

python generate_lifestyle_images.py --csv products.csv

echo.
echo ============================================================
echo   Lifestyle image generation complete!
echo ============================================================
pause
