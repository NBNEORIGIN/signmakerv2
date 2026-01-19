@echo off
title Etsy Pipeline - Generate Shop Uploader
echo ============================================================
echo   ETSY PIPELINE - Generate Shop Uploader File
echo ============================================================
echo.
echo NOTE: JPEG images are now created during the Amazon pipeline.
echo       This step just generates the Shop Uploader file.
echo.

REM Set working directory to this script's location
cd /d "%~dp0"

REM Check for flatfile argument
if "%~1"=="" (
    echo.
    echo Available flatfiles in 003 FLATFILES:
    echo.
    dir /b "003 FLATFILES\*.xlsm" 2>nul | findstr /v "_jpeg" | findstr /v "~$"
    echo.
    echo Usage: run_etsy_pipeline.bat "003 FLATFILES\YOUR_FLATFILE.xlsm"
    echo.
    pause
    exit /b 1
)

set FLATFILE=%~1

REM Check if flatfile exists
if not exist "%FLATFILE%" (
    echo ERROR: Flatfile not found: %FLATFILE%
    pause
    exit /b 1
)

echo.
echo Input flatfile: %FLATFILE%
echo.

REM Derive output name from flatfile (use first word of filename)
for %%F in ("%FLATFILE%") do set FILENAME=%%~nF
for /f "tokens=1" %%A in ("%FILENAME%") do set PRODUCT_NAME=%%A
set SHOP_UPLOADER_OUTPUT=003 FLATFILES\%PRODUCT_NAME%_shop_uploader.xlsx

echo ============================================================
echo   Generating Shop Uploader XLSX
echo ============================================================
echo.
echo   (PNG URLs will be automatically converted to JPEG URLs)
echo.
python generate_etsy_shop_uploader.py --input "%FLATFILE%" --output "%SHOP_UPLOADER_OUTPUT%"
if errorlevel 1 (
    echo ERROR: Shop Uploader generation failed
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   ETSY PIPELINE COMPLETE!
echo ============================================================
echo.
echo Output: %SHOP_UPLOADER_OUTPUT%
echo.
echo NEXT STEP: Upload to Shop Uploader
echo            https://www.shopuploader.com/
echo.
pause
