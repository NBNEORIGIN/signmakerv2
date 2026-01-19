@echo off
REM ============================================================
REM   eBay Business Policies Setup
REM ============================================================
REM Run this once after authentication to set up business policies.
REM Policy IDs will be saved to ebay_policies.json for future use.

call config.bat

echo.
echo eBay Business Policies Setup
echo ============================
echo.

python ebay_setup_policies.py

echo.
pause
