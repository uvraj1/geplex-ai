@echo off
setlocal enabledelayedexpansion
title GepLex Cloudflare Pages Deployment Assistant
color 0b

cd /d "%~dp0"

echo ===================================================================
echo     ____  __                 __ ____ __                     
echo    / __ \/ /___  __  ______ / // __// /___ _________        
echo   / / / / / __ \/ / / / __ `/ // /_ / / __ `/ ___/ _ \       
echo  / /_/ / / /_/ / /_/ / /_/ / // __// / /_/ / /  /  __/       
echo /_____/_/\____/\__,_/\__,_/_//_/  /_/\__,_/_/   \___/        
echo                                                              
echo        ^>^> Cloudflare Pages Direct Deployment Bot ^<^<
echo ===================================================================
echo.

echo [*] Do you have a public HTTPS backend URL (e.g., VPS, Render, or Tunnel)?
echo     Example: https://api.mygeplex.com
echo     (If not, just press ENTER to build with default local settings)
echo.
set /p BACKEND_URL="Backend API URL (optional): "

if not "%BACKEND_URL%"=="" (
    set "GEPLEX_API_URL=%BACKEND_URL%"
    echo [+] Configured backend API URL: %BACKEND_URL%
)

echo.
echo [*] Building production Cloudflare Pages upload package...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-cloudflare-dist.ps1"
if errorlevel 1 (
    color 0c
    echo [ERROR] Failed to build Cloudflare package.
    pause
    exit /b 1
)

echo.
echo ===================================================================
echo  [+] DEPLOYMENT PACKAGE IS READY!
echo  Zip file: "%CD%\geplex-cloudflare-upload.zip"
echo ===================================================================
echo.
echo  STEP-BY-STEP DEPLOYMENT ON dash.cloudflare.com:
echo  -------------------------------------------------------------
echo  1. Browser me Cloudflare Dashboard khulega (dash.cloudflare.com).
echo  2. Left menu me "Workers & Pages" par click karein.
echo  3. "Create application" button dabayein, fir "Pages" tab chunein.
echo  4. "Upload assets" option par click karein.
echo  5. Project name enter karein (e.g. "geplex-ai").
echo  6. Selected ZIP file ko drag & drop karein:
echo     "%CD%\geplex-cloudflare-upload.zip"
echo  7. "Deploy site" par click karein!
echo  -------------------------------------------------------------
echo.

echo [*] Opening dash.cloudflare.com in browser...
start "" "https://dash.cloudflare.com/?to=/:account/pages"

echo [*] Opening folder and highlighting geplex-cloudflare-upload.zip...
explorer /select,"%CD%\geplex-cloudflare-upload.zip"

echo.
echo Press any key when you are done.
pause >nul
