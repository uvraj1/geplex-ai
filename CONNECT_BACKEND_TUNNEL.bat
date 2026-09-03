@echo off
setlocal
cd /d "%~dp0"
title GepLex AI - Connect Backend to Cloudflare

echo =======================================================
echo    GepLex AI - 1-Click Cloudflare Tunnel Connector
echo =======================================================
echo.

if exist ".\venv\Scripts\python.exe" (
    set PYTHON_EXE=.\venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python.exe
)

%PYTHON_EXE% .\bots\start_tunnel_bot.py
pause
