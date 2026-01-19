@echo off
REM ============================================================
REM   Generate eBay Listings
REM ============================================================
REM Creates eBay listings for approved products in products.csv

call config.bat

echo.
echo eBay Listings Generator
echo =======================
echo.

REM Default: process all approved products at £9.99 each
python generate_ebay_listings.py --csv products.csv --price 9.99 --qa-filter approved

echo.
pause
