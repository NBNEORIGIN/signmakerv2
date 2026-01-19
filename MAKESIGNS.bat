@echo off
title Signage Publisher - Web GUI
cd /d "%~dp0"

REM Load config
if exist "config.bat" call config.bat

REM Check if Flask is installed
python -c "import flask" 2>nul
if errorlevel 1 (
    echo Installing Flask...
    pip install flask
)

REM Launch web GUI
echo Starting Signage Publisher Web GUI...
echo.
echo The browser will open automatically.
echo Press Ctrl+C to stop the server.
echo.
python publisher_web.py
