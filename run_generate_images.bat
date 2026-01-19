@echo off
title Amazon Publisher - Generate Images
echo ============================================================
echo   Amazon Publisher REV 2.0 - Image Generator
echo ============================================================
echo.

REM Set working directory to this script's location
cd /d "%~dp0"

REM Check if Python is available
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from python.org
    pause
    exit /b 1
)

REM Check if products.csv exists
if not exist "products.csv" (
    echo ERROR: products.csv not found
    echo Please create products.csv with your product data
    pause
    exit /b 1
)

echo Starting image generation...
echo.

"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_images_v2.py --csv products.csv

echo.
echo ============================================================
echo   Image generation complete!
echo   Check the 'exports' folder for output
echo ============================================================
pause
