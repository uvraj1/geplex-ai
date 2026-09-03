$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python launcher not found. Please install Python 3 and try again." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Starting GepLex..." -ForegroundColor Cyan
& py .\start_geplex.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "GepLex did not start cleanly." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit $LASTEXITCODE
}
