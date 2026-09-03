#Requires -Version 5.1
<#
  Refresh the static Cloudflare Pages bundle without touching main source.
  Output: dist\index.html, dist\static\, dist\assets\
#>
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

$dist = Join-Path $PWD "dist"
$uploadZip = Join-Path $PWD "geplex-cloudflare-upload.zip"
if (([IO.Path]::GetFullPath($dist)) -eq ([IO.Path]::GetFullPath($PWD))) {
    throw "Unsafe Cloudflare dist path."
}

Remove-Item -Recurse -Force $dist -ErrorAction SilentlyContinue
Remove-Item -Force $uploadZip -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $dist | Out-Null
Copy-Item ".\static" (Join-Path $dist "static") -Recurse -Force
Copy-Item ".\assets" (Join-Path $dist "assets") -Recurse -Force
Copy-Item ".\static\index.html" (Join-Path $dist "index.html") -Force
Copy-Item ".\static\login.html" (Join-Path $dist "login.html") -Force
# The Pages entry files live at the upload root. Remove their source copies so
# the dashboard receives one canonical URL for each page.
Remove-Item (Join-Path $dist "static\index.html") -Force
Remove-Item (Join-Path $dist "static\login.html") -Force

# Strip Python backend nonce placeholders for static Cloudflare hosting
$cleanIndex = (Get-Content (Join-Path $dist "index.html") -Raw).Replace(' nonce="{{CSP_NONCE}}"', '').Replace('{{CSP_NONCE}}', '')
$cleanIndex | Set-Content (Join-Path $dist "index.html") -Encoding UTF8
$cleanIndex | Set-Content (Join-Path $dist "404.html") -Encoding UTF8

$cleanLogin = (Get-Content (Join-Path $dist "login.html") -Raw).Replace(' nonce="{{CSP_NONCE}}"', '').Replace('{{CSP_NONCE}}', '')
$cleanLogin | Set-Content (Join-Path $dist "login.html") -Encoding UTF8

$apiBase = if ($env:GEPLEX_API_URL) { $env:GEPLEX_API_URL.TrimEnd('/') } else { "" }
$defaultFirebaseConfig = '{"apiKey":"AIzaSyCvefrQ-bJZ_mr97j_aLiYptlfKYb3blAs","authDomain":"geplex-ai.firebaseapp.com","databaseURL":"https://geplex-ai-default-rtdb.firebaseio.com","projectId":"geplex-ai","storageBucket":"geplex-ai.firebasestorage.app","messagingSenderId":"587292925892","appId":"1:587292925892:web:1450a207788d49a379ce91","measurementId":"G-R0EX7E2VYG"}'
$firebaseConfig = if ($env:GEPLEX_FIREBASE_CONFIG_JSON) { $env:GEPLEX_FIREBASE_CONFIG_JSON } else { $defaultFirebaseConfig }
if (-not $apiBase) { $apiBase = "" }
@"
window.GEPLEX_DEPLOYMENT = {
  apiBase: "$apiBase",
  firebaseConfig: $firebaseConfig
};
"@ | Set-Content (Join-Path $dist "static\deployment-config.js") -Encoding UTF8
Copy-Item ".\static\deployment.js" (Join-Path $dist "static\deployment.js") -Force

@'
# GepLex Cloudflare Pages bundle
/*
  Referrer-Policy: strict-origin-when-cross-origin

/static/*
  Cache-Control: public, max-age=3600

/assets/*
  Cache-Control: public, max-age=86400
  Access-Control-Allow-Origin: *
'@ | Set-Content (Join-Path $dist "_headers") -Encoding UTF8

# Remove any old _redirects file so Cloudflare Pages serves real static files natively
Remove-Item (Join-Path $dist "_redirects") -Force -ErrorAction SilentlyContinue

$requiredFiles = @("index.html", "login.html", "404.html", "_headers", "static\deployment-config.js")
foreach ($requiredFile in $requiredFiles) {
  if (-not (Test-Path (Join-Path $dist $requiredFile) -PathType Leaf)) {
    throw "Cloudflare bundle is incomplete: $requiredFile is missing."
  }
}

# Store the files directly at the archive root. Cloudflare Pages accepts this
# zip from the dashboard without creating an extra nested dist directory.
Compress-Archive -Path (Join-Path $dist "*") -DestinationPath $uploadZip -CompressionLevel Optimal

$parentZip = Join-Path (Split-Path -Parent $PWD) "geplex-cloudflare-upload.zip"
Copy-Item $uploadZip $parentZip -Force -ErrorAction SilentlyContinue

Write-Host "Cloudflare dist ready: $dist" -ForegroundColor Green
Write-Host "Cloudflare upload zip ready: $uploadZip" -ForegroundColor Green
