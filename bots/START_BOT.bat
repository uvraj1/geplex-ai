@echo off
setlocal enabledelayedexpansion
title GepLex AI Workspace - 1-Click Start Bot
color 0b

:: Navigate to project root (one level up from bots)
cd /d "%~dp0.."

echo ===================================================================
echo    ______               __               ___     ____ 
echo   / ____/ ___   ____   / /   ___  _  __ /   ^|   /  _/ 
echo  / / __  / _ \ / __ \ / /   / _ \^| ^|_// //^| ^|   / /   
echo / /_/ / /  __// /_/ // /___/  __/^>  ^< / ___ ^|_ / /    
echo \____/  \___// .___//_____/\___/_/^|_^|/_/  ^|_(_)___/   
echo             /_/                                       
echo        ^>^> GepLex / GepLex 1-Click Start Bot ^<^<
echo ===================================================================
echo.

:: 1. Check if virtual environment python exists
if exist "venv\Scripts\python.exe" (
    set "VENV_PYTHON=venv\Scripts\python.exe"
    goto :ready
)

:: 2. Locate System Python if venv not found
echo [*] Checking Python environment...
set "PY_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=py -3.11"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=python"
    )
)

if "%PY_CMD%"=="" (
    color 0c
    echo [ERROR] Python 3.11+ was not found on your system PATH.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [*] Creating virtual environment (venv)...
%PY_CMD% -m venv venv
if errorlevel 1 (
    color 0c
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [*] Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip --quiet
venv\Scripts\python.exe -m pip install -r requirements.txt

set "VENV_PYTHON=venv\Scripts\python.exe"

:ready
:: Auto-update Cloudflare dist & geplex-cloudflare-upload.zip from source changes
echo [*] Auto-refreshing Cloudflare dist and geplex-cloudflare-upload.zip...
"%VENV_PYTHON%" scripts\build_dist.py

:: Run first-time setup if .env is missing
if not exist ".env" (
    echo [*] Running first-time configuration setup...
    %VENV_PYTHON% setup.py
)

echo -------------------------------------------------------------------
echo  [1] Start GepLex AI (Direct 1-Click Launch + Auto Browser)
echo  [2] Open Start Bot Control Center GUI (Dark Dashboard)
echo  [3] Create / Refresh Desktop Shortcut
echo  [4] Update / Re-install Dependencies
echo -------------------------------------------------------------------
echo Auto-starting Option [1] in 3 seconds... (Or press 2, 3, 4)
echo.

choice /c 1234 /n /t 3 /d 1 /m "Option [1-4]: "
set "OPT=%ERRORLEVEL%"

if "%OPT%"=="2" (
    echo [*] Opening GepLex Control Center GUI...
    start "" "%CD%\%VENV_PYTHON%" "%CD%\bots\start_bot_gui.py"
    exit /b 0
)

if "%OPT%"=="3" (
    echo [*] Creating Desktop Shortcut...
    %VENV_PYTHON% create_shortcut.py
    echo.
    pause
    exit /b 0
)

if "%OPT%"=="4" (
    echo [*] Updating dependencies...
    %VENV_PYTHON% -m pip install --upgrade pip
    %VENV_PYTHON% -m pip install -r requirements.txt
    echo [+] Dependencies updated!
    pause
    exit /b 0
)

:: Option 1: Direct 1-Click Launch
echo [*] Starting GepLex AI Workspace...
"%CD%\%VENV_PYTHON%" "%CD%\bots\start_bot_headless.py"

if errorlevel 1 (
    echo.
    echo [!] Server stopped or encountered an issue.
    pause
)
