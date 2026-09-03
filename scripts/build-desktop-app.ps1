#Requires -Version 5.1
<#
  GepLex Desktop Bot - one-click Windows application builder.
  Creates applications\desktop\GepLex\GepLex.exe using the existing portable build pipeline.
#>
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

Write-Host "GepLex Desktop Bot" -ForegroundColor Cyan
Write-Host "Building the Windows desktop application..." -ForegroundColor Cyan

$builder = Join-Path $PWD "build-windows-portable.ps1"
if (-not (Test-Path $builder)) {
    throw "build-windows-portable.ps1 was not found."
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $builder
if ($LASTEXITCODE -ne 0) {
    throw "Desktop build failed."
}

Write-Host "Desktop app ready: $PWD\applications\desktop\GepLex\GepLex.exe" -ForegroundColor Green
