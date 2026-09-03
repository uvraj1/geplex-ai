@echo off
setlocal
cd /d "%~dp0"
title GepLex - 1-Click Cloudflare Auto-Deploy

echo ===================================================
echo     GepLex AI - 1-Click Cloudflare Auto-Deploy
echo ===================================================
echo.
echo [1/2] Building fresh distribution bundle...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-cloudflare-dist.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/2] Deploying directly to Cloudflare Pages...
if exist ".\.cloudflare_token" (
    for /f "usebackq tokens=1,* delims==" %%A in (".cloudflare_token") do (
        set "%%A=%%B"
    )
)

call ".\node_modules\.bin\wrangler.cmd" pages deploy dist --project-name geplex --commit-dirty=true
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Deployment failed!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ===================================================
echo   [SUCCESS] Deployed live to https://geplex.pages.dev
echo ===================================================
echo.
powershell -NoProfile -Command "Start-Sleep -Seconds 2"
exit /b 0
