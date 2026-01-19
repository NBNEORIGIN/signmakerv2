@echo off
title Signage Publisher - Main Menu
setlocal enabledelayedexpansion

:MENU
cls
echo ============================================================
echo   SIGNAGE PUBLISHER - Main Menu
echo ============================================================
echo.
echo   WORKFLOW: products.csv -^> Amazon -^> Create XLSM flatfile -^> eBay/Etsy
echo.
echo   --- STEP 1: Generate Products ---
echo   [1] Amazon Pipeline (products.csv -^> images + content + flatfile)
echo.
echo   --- STEP 2: Publish to Channels (requires XLSM flatfile) ---
echo   [2] eBay Pipeline (publish from flatfile)
echo   [3] Etsy Pipeline (convert images + Shop Uploader file)
echo.
echo   --- Utilities ---
echo   [4] Generate Images Only
echo   [5] Generate Lifestyle Images Only
echo   [6] QA Review Server
echo.
echo   [Q] Quit
echo.
echo ============================================================
set /p CHOICE="  Select option: "

if /i "%CHOICE%"=="1" goto AMAZON
if /i "%CHOICE%"=="2" goto EBAY
if /i "%CHOICE%"=="3" goto ETSY
if /i "%CHOICE%"=="4" goto IMAGES
if /i "%CHOICE%"=="5" goto LIFESTYLE
if /i "%CHOICE%"=="6" goto QA
if /i "%CHOICE%"=="Q" goto END

echo Invalid option. Press any key to try again...
pause >nul
goto MENU

:AMAZON
cls
echo ============================================================
echo   AMAZON PIPELINE
echo ============================================================
echo.
echo This will run the full Amazon workflow:
echo   1. Generate product images
echo   2. Generate lifestyle images
echo   3. Generate content + upload images
echo   4. Create Amazon flatfile
echo.
echo Press any key to continue or CTRL+C to cancel...
pause >nul

REM Set working directory
cd /d "%~dp0"

REM Load config
if exist "config.bat" (
    call config.bat
) else (
    echo ERROR: config.bat not found
    pause
    goto MENU
)

REM Check products.csv
if not exist "products.csv" (
    echo ERROR: products.csv not found
    pause
    goto MENU
)

echo.
echo ============================================================
echo   STEP 1: Generating Product Images
echo ============================================================
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_images_v2.py --csv products.csv
if errorlevel 1 (
    echo ERROR: Image generation failed
    pause
    goto MENU
)

echo.
echo ============================================================
echo   STEP 2: Generating Lifestyle Images
echo ============================================================
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_lifestyle_images.py --csv products.csv

echo.
echo ============================================================
echo   STEP 3: Generating Amazon Content + Uploading Images
echo ============================================================
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_amazon_content.py --csv products.csv --output amazon_flatfile.xlsx --upload-images
if errorlevel 1 (
    echo ERROR: Content generation failed
    pause
    goto MENU
)

echo.
echo ============================================================
echo   AMAZON PIPELINE COMPLETE!
echo ============================================================
echo.
echo Output: amazon_flatfile.xlsx
echo.
echo NEXT STEPS:
echo   1. Add EAN codes to amazon_flatfile.xlsx
echo   2. Upload to Amazon Seller Central
echo   3. Create XLSM flatfile in 003 FLATFILES\ with pricing
echo   4. Return here to run eBay [2] and Etsy [3] pipelines
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:EBAY
cls
echo ============================================================
echo   EBAY PIPELINE
echo ============================================================
echo.
echo Available flatfiles:
echo.
dir /b "003 FLATFILES\*.xlsm" 2>nul | findstr /v "_jpeg" | findstr /v "~$"
echo.
set /p FLATFILE="Enter flatfile name (e.g., NODOGS SIGNAGE FLATFILE REV1.xlsm): "
if "%FLATFILE%"=="" goto MENU

echo.
echo Options:
echo   [1] Publish + Promote (5%% ad rate)
echo   [2] Publish only (no promotion)
echo   [3] Dry run (preview only)
echo.
set /p EBAY_OPT="Select option: "

if "%EBAY_OPT%"=="1" (
    call run_ebay_flatfile.bat "003 FLATFILES\%FLATFILE%" --promote --ad-rate 5.0
) else if "%EBAY_OPT%"=="2" (
    call run_ebay_flatfile.bat "003 FLATFILES\%FLATFILE%"
) else if "%EBAY_OPT%"=="3" (
    call run_ebay_flatfile.bat "003 FLATFILES\%FLATFILE%" --dry-run
)

echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:ETSY
cls
echo ============================================================
echo   ETSY PIPELINE
echo ============================================================
echo.
echo Available flatfiles:
echo.
dir /b "003 FLATFILES\*.xlsm" 2>nul | findstr /v "_jpeg" | findstr /v "~$"
echo.
set /p FLATFILE="Enter flatfile name (e.g., NODOGS SIGNAGE FLATFILE REV1.xlsm): "
if "%FLATFILE%"=="" goto MENU

call run_etsy_pipeline.bat "003 FLATFILES\%FLATFILE%"

echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:IMAGES
cls
echo ============================================================
echo   GENERATE IMAGES ONLY
echo ============================================================
echo.
call run_generate_images.bat
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:LIFESTYLE
cls
echo ============================================================
echo   GENERATE LIFESTYLE IMAGES ONLY
echo ============================================================
echo.
call run_lifestyle_images.bat
echo.
echo Press any key to return to menu...
pause >nul
goto MENU

:QA
cls
echo ============================================================
echo   QA REVIEW SERVER
echo ============================================================
echo.
echo Starting QA server... (Press CTRL+C to stop)
echo.
call run_qa_server_v2.bat
goto MENU

:END
echo.
echo Goodbye!
exit /b 0
