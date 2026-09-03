@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title GepLex AI - Connect Cloud Backend

echo ========================================================
echo    GepLex AI - Connect 24/7 Cloud Backend (Render)
echo ========================================================
echo.
echo Please enter your Cloud Backend URL from Render.com
echo Example: https://geplex-api.onrender.com
echo.
set /p BACKEND_URL="Backend URL: "

if "%BACKEND_URL%"=="" (
    echo [ERROR] No URL entered!
    pause
    exit /b 1
)

:: Trim trailing slash
if "%BACKEND_URL:~-1%"=="/" set "BACKEND_URL=%BACKEND_URL:~0,-1%"

echo.
echo [*] Setting Backend URL to: %BACKEND_URL%
set "GEPLEX_API_URL=%BACKEND_URL%"

echo [*] Rebuilding Cloudflare distribution with Cloud Backend...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:GEPLEX_API_URL='%BACKEND_URL%'; .\scripts\build-cloudflare-dist.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [*] Deploying update to Cloudflare Pages...
if exist ".\.cloudflare_token" (
    for /f "usebackq tokens=1,* delims==" %%A in (".cloudflare_token") do (
        set "%%A=%%B"
    )
)

call ".\node_modules\.bin\wrangler.cmd" pages deploy dist --project-name geplex --commit-dirty=true

echo.
echo ========================================================
echo   [SUCCESS] GepLex AI is now 100%% Connected 24/7 Worldwide!
echo ========================================================
echo   Frontend: https://geplex.pages.dev
echo   Backend:  %BACKEND_URL%
echo ========================================================
echo.
pause
