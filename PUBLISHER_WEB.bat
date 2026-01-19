@echo off
title Signage Publisher - Web GUI
cd /d "%~dp0"

REM Load config
if exist "config.bat" call config.bat

REM Check if Flask is installed
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" -c "import flask" 2>nul
if errorlevel 1 (
    echo Installing Flask...
    "C:\Users\Admin\AppData\Local\Python\bin\python.exe" -m pip install flask
)

REM Launch web GUI
echo Starting Signage Publisher Web GUI...
echo.
echo The browser will open automatically.
echo Press Ctrl+C to stop the server.
echo.
"C:\Users\Admin\AppData\Local\Python\bin\python.exe" publisher_web.py
