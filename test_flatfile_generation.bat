@echo off
echo Testing Amazon Flatfile Generation
echo ===================================
echo.

cd /d "%~dp0"

REM Load API keys
call config.bat

REM Test with dry-run (no file creation)
echo Running dry-run test...
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_amazon_content.py --csv products.csv --output test_flatfile.xlsx --dry-run --qa-filter all

if errorlevel 1 (
    echo.
    echo ERROR: Script failed. Check error message above.
    pause
    exit /b 1
)

echo.
echo ===================================
echo Dry-run test PASSED!
echo.
echo Now testing actual flatfile generation...
echo.

REM Generate actual flatfile
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" generate_amazon_content.py --csv products.csv --output amazon_flatfile_test.xlsx --qa-filter all

if errorlevel 1 (
    echo.
    echo ERROR: Flatfile generation failed. Check error message above.
    pause
    exit /b 1
)

echo.
echo ===================================
echo SUCCESS! Flatfile generated.
echo.
echo Check for: amazon_flatfile_test.xlsx
echo.
pause
