@echo off
setlocal enabledelayedexpansion
title GepLex AI Workspace - 1-Click Start Bot
color 0b

cd /d "%~dp0"

if exist "bots\START_BOT.bat" (
    call "bots\START_BOT.bat"
    exit /b %ERRORLEVEL%
)

echo [ERROR] bots\START_BOT.bat not found!
pause
exit /b 1
