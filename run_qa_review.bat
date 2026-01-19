@echo off
title Amazon Publisher - Generate QA Review
echo ============================================================
echo   Amazon Publisher REV 2.0 - QA Review Generator
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

echo Generating QA review page...
echo.

python generate_qa_review.py --csv products.csv --exports exports --output qa_review.html

echo.
echo ============================================================
echo   QA Review page generated: qa_review.html
echo   Opening in browser...
echo ============================================================

start qa_review.html
pause
