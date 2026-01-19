@echo off
REM ============================================================
REM   QA Review Server - Interactive Web Interface
REM ============================================================

cd /d "%~dp0"

echo Starting QA Review Server...
echo.
echo Open your browser to: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.

python qa_server.py

pause
