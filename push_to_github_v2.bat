@echo off
echo ========================================
echo Push to GitHub: signmakerv2
echo ========================================
echo.

cd /d "%~dp0"

REM Try common Git installation paths
set GIT_PATH=
if exist "C:\Program Files\Git\cmd\git.exe" set GIT_PATH=C:\Program Files\Git\cmd\git.exe
if exist "C:\Program Files (x86)\Git\cmd\git.exe" set GIT_PATH=C:\Program Files (x86)\Git\cmd\git.exe
if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set GIT_PATH=%LOCALAPPDATA%\Programs\Git\cmd\git.exe

if "%GIT_PATH%"=="" (
    echo ERROR: Git not found in common locations
    echo.
    echo Please close this window, restart PowerShell, and try again
    echo Git needs a terminal restart after installation
    echo.
    pause
    exit /b 1
)

echo Found Git at: %GIT_PATH%
echo.

echo Step 1: Initializing Git repository...
"%GIT_PATH%" init
if errorlevel 1 goto error

echo.
echo Step 2: Adding remote repository...
"%GIT_PATH%" remote add origin https://github.com/NBNEORIGIN/signmakerv2.git 2>nul
if errorlevel 1 (
    echo Remote already exists, updating URL...
    "%GIT_PATH%" remote set-url origin https://github.com/NBNEORIGIN/signmakerv2.git
)

echo.
echo Step 3: Configuring Git identity...
"%GIT_PATH%" config user.email "admin@nbneorigin.com"
"%GIT_PATH%" config user.name "NBNEORIGIN"

echo.
echo Step 4: Adding all files...
"%GIT_PATH%" add .
if errorlevel 1 goto error

echo.
echo Step 5: Committing files...
"%GIT_PATH%" commit -m "Add async job queue system - tested and working"
if errorlevel 1 (
    echo.
    echo Note: If no changes to commit, this is normal
    echo.
)

echo.
echo Step 6: Setting branch to main...
"%GIT_PATH%" branch -M main

echo.
echo Step 7: Pushing to GitHub...
echo.
echo You will be prompted for credentials:
echo   Username: NBNEORIGIN
echo   Password: Personal Access Token (get from github.com/settings/tokens)
echo.
echo Press any key when ready...
pause >nul

"%GIT_PATH%" push -u origin main
if errorlevel 1 goto error

echo.
echo ========================================
echo SUCCESS! Code pushed to GitHub
echo ========================================
echo.
echo Repository: https://github.com/NBNEORIGIN/signmakerv2
echo.
pause
exit /b 0

:error
echo.
echo ========================================
echo ERROR occurred
echo ========================================
echo.
echo If you just installed Git, you need to:
echo 1. Close this window
echo 2. Close PowerShell
echo 3. Open a NEW PowerShell window
echo 4. Try again
echo.
echo This allows Windows to update the PATH
echo.
pause
exit /b 1
