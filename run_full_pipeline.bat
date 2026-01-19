@echo off
title Amazon Publisher - Full Pipeline
echo ============================================================
echo   Amazon Publisher REV 2.0 - FULL PIPELINE
echo ============================================================
echo.
echo This will run the complete workflow:
echo   1. Generate product images (SVG to PNG)
echo   2. Generate lifestyle images (if marked in CSV)
echo   3. Generate Amazon content (titles, descriptions, bullets)
echo   4. Upload images to Cloudflare R2
echo   5. Create Amazon flatfile (XLSX)
echo.
echo Press any key to continue or CTRL+C to cancel...
pause >nul

REM Set working directory to this script's location
cd /d "%~dp0"

REM Check if Python is available
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" --version >nul 2>&1
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

REM Check if products.csv exists
if not exist "products.csv" (
    echo ERROR: products.csv not found
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   STEP 1: Generating Product Images
echo ============================================================
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_images_v2.py --csv products.csv
if errorlevel 1 (
    echo ERROR: Image generation failed
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   STEP 2: Generating Lifestyle Images
echo ============================================================
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_lifestyle_images.py --csv products.csv
if errorlevel 1 (
    echo WARNING: Lifestyle image generation had issues
)

echo.
echo ============================================================
echo   STEP 3: Generating Amazon Content + Uploading Images
echo ============================================================
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_amazon_content.py --csv products.csv --output amazon_flatfile.xlsx --upload-images
if errorlevel 1 (
    echo ERROR: Content generation failed
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   PIPELINE COMPLETE!
echo ============================================================
echo.
echo Output files:
echo   - exports\         (product folders with images)
echo   - amazon_flatfile.xlsx (ready for Amazon upload)
echo.
pause
