@echo off
setlocal enabledelayedexpansion
title GepLex Backend Control ^& Test Bot
color 0b

cd /d "%~dp0"

if exist "bots\BACKEND_BOT.bat" (
    call "bots\BACKEND_BOT.bat"
    exit /b %ERRORLEVEL%
)

echo [ERROR] bots\BACKEND_BOT.bat not found!
pause
exit /b 1
