@echo off
title Amazon Publisher - Apply QA Tuning
echo ============================================================
echo   Amazon Publisher REV 2.0 - AI-Assisted QA Tuning
echo ============================================================
echo.

REM Set working directory to this script's location
cd /d "%~dp0"

REM Load config
if exist config.bat (
    call config.bat
) else (
    echo ERROR: config.bat not found. Copy config_template.bat to config.bat
    echo and fill in your API keys.
    pause
    exit /b 1
)

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo This will use Claude AI to interpret qa_comment fields
echo and automatically apply suggested changes to products.csv
echo.
echo Products with qa_comment will be processed.
echo Changes will be marked with [APPLIED] prefix.
echo.

set /p CONFIRM="Continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo Applying AI-assisted tuning...
echo.

python apply_qa_tuning.py --csv products.csv

echo.
echo ============================================================
echo   Tuning complete!
echo   Review products.csv to see applied changes.
echo   Run generate_images to regenerate with new settings.
echo ============================================================
pause
