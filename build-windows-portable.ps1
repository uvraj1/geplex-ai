#Requires -Version 5.1
<#
  Build a portable Windows distribution for GepLex.

  Output layout:
    applications\desktop\GepLex\GepLex.exe
    applications\desktop\GepLex\static\...
    applications\desktop\GepLex\scripts\...
    applications\desktop\GepLex\mcp_servers\...
    applications\desktop\GepLex\services\hwfit\data\...

  The app then keeps using its normal filesystem layout when frozen.

  Usage:
    powershell -ExecutionPolicy Bypass -File .\build-windows-portable.ps1
#>

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$applicationsRoot = Join-Path $PSScriptRoot "applications"

function Write-Step($msg) { Write-Host ""; Write-Host ("==> " + $msg) -ForegroundColor Cyan }
function Fail($msg) {
    Write-Host ""
    Write-Host ("ERROR: " + $msg) -ForegroundColor Red
    exit 1
}

Write-Step "Checking for Python"
$pyExe = $null
if (Test-Path ".\.venv\Scripts\python.exe") {
    $pyExe = (Resolve-Path ".\.venv\Scripts\python.exe").Path
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $pyExe = (Resolve-Path ".\venv\Scripts\python.exe").Path
} else {
    foreach ($c in @("py", "python")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { $pyExe = $cmd.Source; break }
    }
    if ($pyExe -like "*WindowsApps*python.exe") {
        $pyCmd = Get-Command py -ErrorAction SilentlyContinue
        if ($pyCmd) {
            $pyExe = $pyCmd.Source
        }
    }
}
if (-not $pyExe) {
    Fail "Python not found on PATH. Install Python 3.11+ first."
}
Write-Host ("Using Python: " + $pyExe)

Write-Step "Installing build dependencies"
& $pyExe -m pip install --upgrade pip --quiet
& $pyExe -m pip install -r requirements.txt pyinstaller pystray Pillow
if ($LASTEXITCODE -ne 0) { Fail "Dependency install failed." }

Write-Step "Building portable exe bundle"
$desktopOutput = Join-Path $PSScriptRoot "applications\desktop"
$desktopWork = Join-Path $PSScriptRoot "applications\desktop-build"
# Safety boundary: only generated application folders may be removed.
if (([IO.Path]::GetFullPath($desktopOutput)).StartsWith(([IO.Path]::GetFullPath($applicationsRoot) + [IO.Path]::DirectorySeparatorChar))) {
    # expected: output is inside applications, never the repository root
} else {
    Fail "Unsafe desktop output path."
}
Remove-Item -Recurse -Force $desktopOutput, $desktopWork -ErrorAction SilentlyContinue
# Remove only legacy PyInstaller output folders; all source directories are kept.
Remove-Item -Recurse -Force (Join-Path $applicationsRoot "desktop-build") -ErrorAction SilentlyContinue

$dataArgs = @(
    "--add-data", "static;static",
    "--add-data", "assets;assets",
    "--add-data", "scripts;scripts",
    "--add-data", "mcp_servers;mcp_servers",
    "--add-data", "services/hwfit/data;services/hwfit/data",
    "--add-data", "config;config",
    "--add-data", ".env.example;.env.example"
)

& $pyExe -m PyInstaller --noconfirm --clean --onedir --noconsole `
    --distpath $desktopOutput --workpath $desktopWork `
    --icon=static/icon.ico --name GepLex @dataArgs launcher.py
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller build failed." }
Remove-Item -Recurse -Force $desktopWork -ErrorAction SilentlyContinue
$desktopData = Join-Path $desktopOutput "GepLex\data"
New-Item -ItemType Directory -Path $desktopData -Force | Out-Null
Set-Content -Path (Join-Path $desktopData "README.txt") -Value "GepLex runtime data is stored in this folder." -Encoding UTF8

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "Desktop app folder: $desktopOutput\GepLex" -ForegroundColor Green
Write-Host "Distribute the whole folder (or zip it) so static assets and scripts stay with the exe." -ForegroundColor Green