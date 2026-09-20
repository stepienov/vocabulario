# Builds dist\Vocabulario.apk against production API.
# Shared debug keystore so both PCs produce the same signature.
# Usage (repo root): .\build-apk.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Resolve-JavaHome {
    $candidates = @()
    if ($env:JAVA_HOME) { $candidates += $env:JAVA_HOME }
    $candidates += Get-ChildItem "C:\Program Files\Microsoft" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "jdk-*" } |
        ForEach-Object { $_.FullName }
    $candidates += @(
        "C:\Program Files\Android\Android Studio\jbr",
        "C:\Program Files\Eclipse Adoptium\jdk-17",
        "C:\Program Files\Java\jdk-17"
    )
    foreach ($jdkDir in $candidates) {
        if ($jdkDir -and (Test-Path (Join-Path $jdkDir "bin\java.exe"))) { return $jdkDir }
    }
    $cmd = Get-Command java -ErrorAction SilentlyContinue
    if ($cmd) { return (Split-Path (Split-Path $cmd.Source)) }
    return $null
}

$javaHome = Resolve-JavaHome
if (-not $javaHome) {
    throw "JDK not found. Install Microsoft OpenJDK 17 or Android Studio, then re-run."
}
$env:JAVA_HOME = $javaHome
$env:Path = "$javaHome\bin;" + $env:Path

$keystore = Join-Path $PSScriptRoot "android\keystore\debug.keystore"
if (-not (Test-Path $keystore)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $keystore) | Out-Null
    $keytool = @(
        "${env:JAVA_HOME}\bin\keytool.exe",
        "C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe"
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if (-not $keytool) {
        $cmd = Get-Command keytool -ErrorAction SilentlyContinue
        if ($cmd) { $keytool = $cmd.Source }
    }
    if (-not $keytool) {
        throw "keytool not found. Install JDK/Android Studio, or copy android\keystore\debug.keystore from the other PC."
    }
    & $keytool -genkeypair -keystore $keystore -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -storepass android -keypass android -dname "CN=Vocabulario Debug, OU=Debug, O=Vocabulario, L=NA, ST=NA, C=PL"
    if ($LASTEXITCODE -ne 0) { throw "Failed to create debug.keystore" }
    Write-Host "Created $keystore - commit this file so the other PC signs with the same key."
}

$dist = Join-Path $PSScriptRoot "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null

Push-Location (Join-Path $PSScriptRoot "android")
try {
    & .\gradlew.bat :app:assembleDebug "-Papi.base.url=https://vocabulario.up.railway.app/api/v1/"
    if ($LASTEXITCODE -ne 0) { throw "Gradle assembleDebug failed" }
    & .\gradlew.bat --stop | Out-Null
} finally {
    Pop-Location
}

$apk = Join-Path $PSScriptRoot "android\app\build\outputs\apk\debug\app-debug.apk"
$dest = Join-Path $dist "Vocabulario.apk"
Copy-Item -Force $apk $dest
$out = Get-Item $dest
$mb = [math]::Round($out.Length / 1048576, 1)
Write-Host ("Gotowe: " + $out.FullName + "  size=" + $mb.ToString() + "MB")
