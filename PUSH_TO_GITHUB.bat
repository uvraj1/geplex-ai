@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title GepLex AI - Push to GitHub

echo ========================================================
echo         GepLex AI - Push Code to GitHub
echo ========================================================
echo.
set "DEFAULT_URL=https://github.com/uvraj1/geplex-ai.git"
echo Repository URL (Press Enter for %DEFAULT_URL%):
set /p REPO_URL="URL: "

if "%REPO_URL%"=="" set "REPO_URL=%DEFAULT_URL%"

echo.
echo [*] Adding all changes...
git add .

echo [*] Committing changes...
git commit -m "Deploy GepLex AI backend to Render"

echo [*] Setting branch to main...
git branch -M main

echo [*] Configuring remote origin...
git remote remove origin 2>nul
git remote add origin %REPO_URL%

echo [*] Pushing to GitHub (Aapko GitHub login prompt dikh sakta hai)...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo   [SUCCESS] Code successfully pushed to GitHub!
    echo ========================================================
    echo   Ab Render.com par jakar is repo ko connect kijiye!
    echo ========================================================
) else (
    echo.
    echo [!] Push failed. Please check your GitHub credentials or repository URL.
)
echo.
pause
