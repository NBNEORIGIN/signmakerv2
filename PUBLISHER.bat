@echo off
cd /d "%~dp0"

REM Load config
if exist "config.bat" call config.bat

REM Launch GUI without console window
start "" pythonw publisher_gui.py
