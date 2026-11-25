param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$VersionCode,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9A-Za-z][0-9A-Za-z._-]*$')]
    [string]$VersionName
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$keyDir = Join-Path $root ".local\alpha-signing"
$keystore = Join-Path $keyDir "vocabulario-alpha.p12"
$passwordFile = Join-Path $keyDir "password.dpapi"
$publishedApk = Join-Path $root "backend\app\public_web\downloads\Vocabulario-alpha.apk"
$builtApk = Join-Path $root "android\app\build\outputs\apk\release\app-release.apk"
$dist = Join-Path $root "dist"
if (-not (Test-Path -LiteralPath $keystore) -or -not (Test-Path -LiteralPath $passwordFile)) {
    throw "Alpha signing key or its Windows-protected password is missing."
}

Add-Type -AssemblyName System.Security
$passwordBytes = [Security.Cryptography.ProtectedData]::Unprotect(
    [IO.File]::ReadAllBytes($passwordFile), $null,
    [Security.Cryptography.DataProtectionScope]::CurrentUser
)
$oldEnv = @{}
foreach ($name in @("UPLOAD_KEYSTORE_FILE", "UPLOAD_KEYSTORE_PASSWORD", "UPLOAD_KEY_ALIAS", "UPLOAD_KEY_PASSWORD")) {
    $oldEnv[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
try {
    $env:UPLOAD_KEYSTORE_FILE = $keystore
    $env:UPLOAD_KEYSTORE_PASSWORD = [Text.Encoding]::UTF8.GetString($passwordBytes)
    $env:UPLOAD_KEY_ALIAS = "vocabulario-alpha"
    $env:UPLOAD_KEY_PASSWORD = $env:UPLOAD_KEYSTORE_PASSWORD
    [Array]::Clear($passwordBytes, 0, $passwordBytes.Length)

    Push-Location (Join-Path $root "android")
    try {
        & .\gradlew.bat --console=plain :app:assembleRelease `
            "-Prelease.application.id=io.vocabulario.alpha" `
            "-Prelease.version.code=$VersionCode" "-Prelease.version.name=$VersionName" `
            "-Papi.base.url=https://vocabulario.io/api/v1"
        if ($LASTEXITCODE -ne 0) { throw "Alpha APK build failed." }
    } finally {
        Pop-Location
    }

    $checkArgs = @((Join-Path $root "scripts\check_alpha_apk.py"), $builtApk)
    if (Test-Path -LiteralPath $publishedApk) { $checkArgs += @("--previous", $publishedApk) }
    & python @checkArgs
    if ($LASTEXITCODE -ne 0) { throw "Alpha APK verification failed." }
    & python (Join-Path $root "scripts\check_aab_16kb.py") $builtApk
    if ($LASTEXITCODE -ne 0) { throw "Alpha APK 16 KB alignment check failed." }

    New-Item -ItemType Directory -Force -Path (Split-Path $publishedApk), $dist | Out-Null
    Copy-Item -LiteralPath $builtApk -Destination $publishedApk -Force
    $distApk = Join-Path $dist "Vocabulario.apk"
    Copy-Item -LiteralPath $builtApk -Destination $distApk -Force
    $expectedHash = (Get-FileHash -LiteralPath $builtApk -Algorithm SHA256).Hash
    foreach ($copy in @($publishedApk, $distApk)) {
        if ((Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ne $expectedHash) {
            throw "Copied APK does not match the verified build: $copy"
        }
    }
    Get-ChildItem -LiteralPath $dist -File -Filter "*.apk" |
        Where-Object { $_.Name -ne "Vocabulario.apk" } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName }
    Write-Output "Alpha APK ready for the PR: $publishedApk"
} finally {
    [Array]::Clear($passwordBytes, 0, $passwordBytes.Length)
    foreach ($name in $oldEnv.Keys) {
        [Environment]::SetEnvironmentVariable($name, $oldEnv[$name], "Process")
    }
}
