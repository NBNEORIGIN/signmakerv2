@echo off
title Fix Etsy JPEG Images
echo ============================================================
echo   FIX ETSY JPEG IMAGES
echo ============================================================
echo.
echo This will re-convert all PNG images to Etsy-compatible JPEGs
echo and re-upload them to R2.
echo.

REM Set working directory
cd /d "%~dp0"

REM Load config
if exist "config.bat" (
    call config.bat
) else (
    echo ERROR: config.bat not found
    pause
    exit /b 1
)

echo.
python fix_etsy_jpegs.py %*

echo.
echo Press any key to exit...
pause >nul
