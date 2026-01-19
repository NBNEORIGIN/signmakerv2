@echo off
echo ========================================
echo Push to GitHub: signmakerv2
echo ========================================
echo.

cd /d "%~dp0"

REM Check if git is installed
where git >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed or not in PATH
    echo.
    echo Please install Git from: https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)

echo Step 1: Initializing Git repository...
git init
if errorlevel 1 (
    echo ERROR: Failed to initialize git repository
    pause
    exit /b 1
)

echo.
echo Step 2: Adding remote repository...
git remote add origin https://github.com/NBNEORIGIN/signmakerv2.git 2>nul
if errorlevel 1 (
    echo Remote already exists, updating URL...
    git remote set-url origin https://github.com/NBNEORIGIN/signmakerv2.git
)

echo.
echo Step 3: Adding all files...
git add .
if errorlevel 1 (
    echo ERROR: Failed to add files
    pause
    exit /b 1
)

echo.
echo Step 4: Committing files...
git commit -m "Add async job queue system - tested and working"
if errorlevel 1 (
    echo ERROR: Failed to commit (or no changes to commit)
    pause
    exit /b 1
)

echo.
echo Step 5: Setting branch to main...
git branch -M main

echo.
echo Step 6: Pushing to GitHub...
echo.
echo You will be prompted for GitHub credentials:
echo - Username: NBNEORIGIN
echo - Password: Use a Personal Access Token (NOT your password)
echo.
echo To create a token:
echo 1. Go to: https://github.com/settings/tokens
echo 2. Click "Generate new token (classic)"
echo 3. Select "repo" scope
echo 4. Copy the token and use it as password
echo.
echo Press any key when ready to push...
pause >nul

git push -u origin main 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Failed to push to GitHub
    echo.
    echo Common issues:
    echo - Wrong credentials (use Personal Access Token, not password)
    echo - Repository doesn't exist or you don't have access
    echo - Network connection issues
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS! Code pushed to GitHub
echo ========================================
echo.
echo Repository: https://github.com/NBNEORIGIN/signmakerv2
echo.
pause
