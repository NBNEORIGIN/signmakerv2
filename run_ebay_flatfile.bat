@echo off
call config.bat
python generate_ebay_from_flatfile.py %*
