@echo off
title Setup New User Workspace
setlocal enabledelayedexpansion

echo ============================================================
echo   AMAZON PUBLISHER - New User Workspace Setup
echo ============================================================
echo.
echo This will create a complete copy of the publisher for a new user.
echo.

REM Get the source directory (where this script is located)
set "SOURCE_DIR=%~dp0"
set "SOURCE_DIR=%SOURCE_DIR:~0,-1%"

REM Ask for user name
set /p USERNAME="Enter staff member name (e.g., John): "
if "%USERNAME%"=="" (
    echo ERROR: Name cannot be empty
    pause
    exit /b 1
)

REM Ask for destination
echo.
echo Where should the workspace be created?
echo   [1] Same parent folder as this one (recommended for Google Drive)
echo   [2] Custom location
echo.
set /p DEST_CHOICE="Select option (1 or 2): "

if "%DEST_CHOICE%"=="1" (
    for %%I in ("%SOURCE_DIR%") do set "PARENT_DIR=%%~dpI"
    set "DEST_DIR=!PARENT_DIR!AMAZON PUBLISHER - %USERNAME%"
) else if "%DEST_CHOICE%"=="2" (
    set /p CUSTOM_PATH="Enter full path for workspace: "
    set "DEST_DIR=!CUSTOM_PATH!\AMAZON PUBLISHER - %USERNAME%"
) else (
    echo Invalid option
    pause
    exit /b 1
)

echo.
echo Source: %SOURCE_DIR%
echo Destination: %DEST_DIR%
echo.

if exist "%DEST_DIR%" (
    echo ERROR: Destination folder already exists!
    echo        %DEST_DIR%
    pause
    exit /b 1
)

echo Creating workspace for %USERNAME%...
echo.

REM Create destination directory
mkdir "%DEST_DIR%"

REM Copy Python scripts
echo Copying Python scripts...
copy "%SOURCE_DIR%\*.py" "%DEST_DIR%\" >nul

REM Copy batch files
echo Copying batch files...
copy "%SOURCE_DIR%\*.bat" "%DEST_DIR%\" >nul

REM Copy requirements
echo Copying requirements...
copy "%SOURCE_DIR%\requirements.txt" "%DEST_DIR%\" >nul

REM Copy config (with credentials)
echo Copying configuration...
if exist "%SOURCE_DIR%\config.bat" (
    copy "%SOURCE_DIR%\config.bat" "%DEST_DIR%\" >nul
) else (
    copy "%SOURCE_DIR%\config_template.bat" "%DEST_DIR%\config.bat" >nul
    echo WARNING: config.bat not found, copied template instead
    echo          You will need to add API keys to config.bat
)

REM Copy eBay/Etsy tokens
echo Copying authentication tokens...
if exist "%SOURCE_DIR%\ebay_tokens.json" copy "%SOURCE_DIR%\ebay_tokens.json" "%DEST_DIR%\" >nul
if exist "%SOURCE_DIR%\ebay_policies.json" copy "%SOURCE_DIR%\ebay_policies.json" "%DEST_DIR%\" >nul

REM Copy asset folders
echo Copying assets (this may take a moment)...
xcopy "%SOURCE_DIR%\001 ICONS" "%DEST_DIR%\001 ICONS\" /E /I /Q >nul
xcopy "%SOURCE_DIR%\002 LAYOUTS" "%DEST_DIR%\002 LAYOUTS\" /E /I /Q >nul
xcopy "%SOURCE_DIR%\assets" "%DEST_DIR%\assets\" /E /I /Q >nul

REM Create empty user folders
echo Creating user folders...
mkdir "%DEST_DIR%\003 FLATFILES"
mkdir "%DEST_DIR%\exports"

REM Create empty products.csv with headers
echo Creating empty products.csv...
echo m_number,description,icon,color,size,material,mounting,layout_mode,text_line_1,text_line_2,text_line_3,text_line_4,icon_scale,text_scale,lifestyle_image,qa_status,qa_comment>"%DEST_DIR%\products.csv"

REM Copy documentation
echo Copying documentation...
if exist "%SOURCE_DIR%\README.md" copy "%SOURCE_DIR%\README.md" "%DEST_DIR%\" >nul
if exist "%SOURCE_DIR%\STAFF_GUIDE.md" copy "%SOURCE_DIR%\STAFF_GUIDE.md" "%DEST_DIR%\" >nul

REM Copy examples folder if it exists
if exist "%SOURCE_DIR%\examples" (
    echo Copying examples...
    xcopy "%SOURCE_DIR%\examples" "%DEST_DIR%\examples\" /E /I /Q >nul
)

echo.
echo ============================================================
echo   SETUP COMPLETE!
echo ============================================================
echo.
echo Workspace created at:
echo   %DEST_DIR%
echo.
echo NEXT STEPS for %USERNAME%:
echo   1. Open the new folder
echo   2. Run PUBLISHER_WEB.bat to start the web interface
echo   3. Read STAFF_GUIDE.md for instructions
echo.
echo Press any key to open the new workspace folder...
pause >nul

explorer "%DEST_DIR%"
