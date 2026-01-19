@echo off
REM ============================================================
REM   eBay OAuth Authentication
REM ============================================================
REM Run this once to authenticate with eBay and generate tokens.
REM Tokens will be saved to ebay_tokens.json for future use.

call config.bat

echo.
echo eBay OAuth Authentication
echo =========================
echo.
echo This will open your browser to authorize the application.
echo After authorization, you'll be redirected back to localhost.
echo.

python ebay_auth.py

echo.
pause
