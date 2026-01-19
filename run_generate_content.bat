@echo off
title Amazon Publisher - Generate Amazon Content
echo ============================================================
echo   Amazon Publisher REV 2.0 - Content Generator
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

REM Load API keys from config
if exist "config.bat" (
    call config.bat
) else (
    echo ERROR: config.bat not found
    echo Please create config.bat with your API keys
    echo See config_template.bat for an example
    pause
    exit /b 1
)

REM Check if products.csv exists
if not exist "products.csv" (
    echo ERROR: products.csv not found
    pause
    exit /b 1
)

echo Starting content generation and image upload...
echo.

"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_amazon_content.py --csv products.csv --output amazon_flatfile.xlsx --upload-images

echo.
echo ============================================================
echo   Content generation complete!
echo   Output: amazon_flatfile.xlsx
echo ============================================================
pause
