@echo off
setlocal enabledelayedexpansion
title GepLex Backend Control ^& Test Bot
color 0b

:: Navigate to project root (one level up from bots)
cd /d "%~dp0.."

:: 1. Locate python
if exist "venv\Scripts\python.exe" (
    set "PY_CMD=venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

:: 2. Launch Backend Control Bot inside bots folder
%PY_CMD% "%CD%\bots\backend_control_bot.py"

if errorlevel 1 (
    echo.
    echo [!] Backend Bot encountered an issue or exited.
    pause
)
