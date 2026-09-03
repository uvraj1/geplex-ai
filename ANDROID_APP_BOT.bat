@echo off
cd /d "%~dp0"
if exist "applications\android\ANDROID_APP_BOT.bat" (
  call "applications\android\ANDROID_APP_BOT.bat"
  exit /b %ERRORLEVEL%
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-android-app.ps1"
if errorlevel 1 (
  echo.
  echo Android app build failed.
  pause
  exit /b 1
)
pause
