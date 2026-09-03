@echo off
cd /d "%~dp0"
if exist "applications\desktop\DESKTOP_APP_BOT.bat" (
  call "applications\desktop\DESKTOP_APP_BOT.bat"
  exit /b %ERRORLEVEL%
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-desktop-app.ps1"
if errorlevel 1 (
  echo.
  echo Desktop app build failed.
  pause
  exit /b 1
)
pause
