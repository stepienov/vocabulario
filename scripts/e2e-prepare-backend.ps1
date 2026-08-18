# Seed E2E user + language profile against local API.
# Does not start Docker/backend itself — assumes API is already up (.\start-backend.ps1).
# Optional: set LLM_MOCK=true in backend .env before restart for deterministic AI flows.

param(
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Read-DotEnv([string]$path) {
    $map = @{}
    if (-not (Test-Path $path)) { return $map }
    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $i = $line.IndexOf("=")
        if ($i -lt 1) { return }
        $k = $line.Substring(0, $i).Trim()
        $v = $line.Substring($i + 1).Trim()
        $map[$k] = $v
    }
    return $map
}

$envPath = if ($EnvFile) { $EnvFile } else {
    $cand = Join-Path $repoRoot ".env.e2e"
    if (Test-Path $cand) { $cand } else { Join-Path $repoRoot ".env.e2e.example" }
}
$vals = Read-DotEnv $envPath

$email = if ($vals["E2E_EMAIL"]) { $vals["E2E_EMAIL"] } else { "e2e.vocabulario@example.com" }
$password = if ($vals["E2E_PASSWORD"]) { $vals["E2E_PASSWORD"] } else { "e2e-test-pass-123" }
$native = if ($vals["E2E_NATIVE_LANG"]) { $vals["E2E_NATIVE_LANG"] } else { "en" }
$learning = if ($vals["E2E_LEARNING_LANG"]) { $vals["E2E_LEARNING_LANG"] } else { "es" }
$cefr = if ($vals["E2E_CEFR"]) { $vals["E2E_CEFR"] } else { "A2" }
$api = if ($vals["E2E_API_BASE"]) { $vals["E2E_API_BASE"] } else { "http://127.0.0.1:8000/api/v1" }

Write-Host "API=$api"
Write-Host "User=$email native=$native learning=$learning"

# Health
try {
    $health = Invoke-RestMethod -Uri ($api -replace "/api/v1$", "/health") -TimeoutSec 5
    Write-Host "Health: $($health.status)"
} catch {
    throw "Backend not reachable at $api. Start with .\\start-backend.ps1 first. $_"
}

$bodyRegister = @{ email = $email; password = $password } | ConvertTo-Json
$token = $null
try {
    $reg = Invoke-RestMethod -Method Post -Uri "$api/auth/register" -ContentType "application/json" -Body $bodyRegister
    $token = $reg.access_token
    Write-Host "Registered new E2E user"
} catch {
    $loginBody = @{ email = $email; password = $password } | ConvertTo-Json
    try {
        $login = Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType "application/json" -Body $loginBody
        $token = $login.access_token
        Write-Host "Logged in existing E2E user"
    } catch {
        throw "Register/login failed for $email. $_"
    }
}

$headers = @{ Authorization = "Bearer $token" }
$profiles = Invoke-RestMethod -Method Get -Uri "$api/profiles" -Headers $headers
$match = @($profiles | Where-Object {
    $_.native_lang -eq $native -and $_.learning_lang -eq $learning
})
if ($match.Count -gt 0) {
    $profileId = $match[0].id
    if (-not $match[0].is_active) {
        Invoke-RestMethod -Method Put -Uri "$api/profiles/$profileId/activate" -Headers $headers | Out-Null
        Write-Host "Activated existing profile $profileId"
    } else {
        Write-Host "Active profile already OK ($profileId)"
    }
} else {
    # Default ES tenses when learning es; otherwise empty (backend accepts list)
    $tenses = if ($learning -eq "es") {
        @("presente", "preterito_indefinido", "preterito_imperfecto")
    } elseif ($learning -eq "en") {
        @("present_simple", "past_simple", "present_continuous")
    } else { @() }
    $create = @{
        native_lang = $native
        learning_lang = $learning
        cefr_level = $cefr
        selected_tenses = $tenses
    } | ConvertTo-Json
    $created = Invoke-RestMethod -Method Post -Uri "$api/profiles" -Headers $headers -ContentType "application/json" -Body $create
    Write-Host "Created profile $($created.id)"
}

# Seed ready cards for practice / lists (dev endpoint, no LLM)
try {
    $seedUrl = "$api/dev/e2e-seed?email=$([uri]::EscapeDataString($email))&count=12"
    $seed = Invoke-RestMethod -Method Post -Uri $seedUrl -TimeoutSec 30
    Write-Host "E2E seed cards: created=$($seed.created.Count) reused=$($seed.reused.Count) total=$($seed.count)"
} catch {
    Write-Host "WARN: e2e-seed failed (restart backend after pulling /dev/e2e-seed). $_"
}

Write-Host ""
Write-Host "Pass to Maestro:"
Write-Host "  maestro test -e E2E_EMAIL=$email -e E2E_PASSWORD=$password e2e\maestro\flows"
