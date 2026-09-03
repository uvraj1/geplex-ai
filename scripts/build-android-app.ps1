#Requires -Version 5.1
<#
  GepLex Android Bot - one-click Android WebView package builder.
  Prerequisites: Node.js, Java 17+, Android SDK, and an available Gradle toolchain.
#>
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

function Require-Command($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$name was not found. $hint"
    }
}

Require-Command "node" "Install Node.js 18+ and restart the terminal."
Require-Command "npm" "Install Node.js 18+ and restart the terminal."
Require-Command "java" "Install Java 17+ and set JAVA_HOME."

$mobile = Join-Path $PWD "applications\android\GepLexAndroid"
$sourceRoot = [IO.Path]::GetFullPath($PWD)
$applicationRoot = [IO.Path]::GetFullPath((Join-Path $PWD "applications"))
if (-not ([IO.Path]::GetFullPath($mobile)).StartsWith($applicationRoot + [IO.Path]::DirectorySeparatorChar)) {
    throw "Unsafe Android output path."
}
if (-not (Test-Path $mobile)) {
    New-Item -ItemType Directory -Path $mobile | Out-Null
}

if (-not (Test-Path (Join-Path $mobile "package.json"))) {
    Push-Location $mobile
    & npm init -y
    & npm install @capacitor/core @capacitor/cli @capacitor/android
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Capacitor dependency installation failed." }
    & npx cap init GepLex com.geplex.app --web-dir www --skip-using-npm
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Capacitor initialization failed." }
    Pop-Location
}

$www = Join-Path $mobile "www"
if (Test-Path $www) { Remove-Item -Recurse -Force $www }
New-Item -ItemType Directory -Path $www | Out-Null
Copy-Item (Join-Path $PWD "static\*") $www -Recurse -Force
$androidData = Join-Path $mobile "data"
New-Item -ItemType Directory -Path $androidData -Force | Out-Null
Set-Content -Path (Join-Path $androidData "README.txt") -Value "Android application build metadata and local app data belong here." -Encoding UTF8

Push-Location $mobile
if (-not (Test-Path "android")) {
    & npx cap add android
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Android platform creation failed. Check Android SDK setup." }
}
& npx cap sync android
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Capacitor Android sync failed." }

$gradle = Join-Path $PWD "android\gradlew.bat"
if (-not (Test-Path $gradle)) {
    Pop-Location
    throw "Android Gradle wrapper was not created."
}
& $gradle assembleDebug
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Android APK build failed." }
Pop-Location

$apk = Join-Path $mobile "android\app\build\outputs\apk\debug\app-debug.apk"
Write-Host "Android app ready: $apk" -ForegroundColor Green
