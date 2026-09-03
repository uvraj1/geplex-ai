@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python launcher not found. Please install Python 3 and try again.
    pause
    exit /b 1
)

echo Starting GepLex...
py start_geplex.py
if errorlevel 1 (
    echo.
    echo GepLex did not start cleanly.
    pause
)
