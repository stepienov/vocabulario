# Local Maestro E2E runner — install debug APK + smoke suite.
# Requires: emulator/device via ADB, Maestro at C:\maestro, JDK 17 at C:\Java\jdk-17
# Optional: .env.e2e (or .env.e2e.example) for E2E_EMAIL / E2E_PASSWORD

param(
    [switch]$SkipInstall,
    [switch]$All,
    [string]$Tags = "smoke"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$maestroHome = if (Test-Path "C:\maestro\bin\maestro.bat") { "C:\maestro" } else { "$env:USERPROFILE\.maestro" }
$javaHome = if (Test-Path "C:\Java\jdk-17") { "C:\Java\jdk-17" } else { $env:JAVA_HOME }

if (-not $javaHome) {
    throw "JAVA_HOME / C:\Java\jdk-17 not found. Maestro needs Java 17+ (path without spaces preferred)."
}
if (-not (Test-Path "$sdk\platform-tools\adb.exe")) {
    throw "adb not found under ANDROID_HOME=$sdk"
}
if (-not (Test-Path "$maestroHome\bin\maestro.bat") -and -not (Test-Path "$maestroHome\bin\maestro")) {
    throw "Maestro CLI not found at $maestroHome\bin"
}

$env:JAVA_HOME = $javaHome
$env:ANDROID_HOME = $sdk
$env:PATH = "$maestroHome\bin;$javaHome\bin;$sdk\platform-tools;$env:PATH"
$env:MAESTRO_CLI_NO_ANALYTICS = "true"

function Read-DotEnv([string]$path) {
    $map = @{}
    if (-not (Test-Path $path)) { return $map }
    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $i = $line.IndexOf("=")
        if ($i -lt 1) { return }
        $map[$line.Substring(0, $i).Trim()] = $line.Substring($i + 1).Trim()
    }
    return $map
}

$envFile = Join-Path $repoRoot ".env.e2e"
if (-not (Test-Path $envFile)) { $envFile = Join-Path $repoRoot ".env.e2e.example" }
$vals = Read-DotEnv $envFile
$email = if ($vals["E2E_EMAIL"]) { $vals["E2E_EMAIL"] } else { "e2e.vocabulario@example.com" }
$password = if ($vals["E2E_PASSWORD"]) { $vals["E2E_PASSWORD"] } else { "e2e-test-pass-123" }

Write-Host "JAVA_HOME=$env:JAVA_HOME"
Write-Host "ANDROID_HOME=$env:ANDROID_HOME"
& adb devices

if (-not $SkipInstall) {
    Push-Location (Join-Path $repoRoot "android")
    try {
        Write-Host "Installing debug APK..."
        & .\gradlew.bat :app:installDebug --quiet
        if ($LASTEXITCODE -ne 0) { throw "installDebug failed with $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
}

$maestroRoot = Join-Path $repoRoot "e2e\maestro"
if ($All) {
    Write-Host "Running ALL Maestro flows in $maestroRoot"
    & maestro test -e "E2E_EMAIL=$email" -e "E2E_PASSWORD=$password" $maestroRoot
} else {
    Write-Host "Running Maestro tags=$Tags in $maestroRoot"
    & maestro test --include-tags $Tags -e "E2E_EMAIL=$email" -e "E2E_PASSWORD=$password" $maestroRoot
}
exit $LASTEXITCODE
