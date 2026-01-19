@echo off
echo Testing R2 Connection
echo =====================
echo.

cd /d "%~dp0"

REM Load API keys
call config.bat

REM Test R2 connection
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" test_r2_upload.py

pause
