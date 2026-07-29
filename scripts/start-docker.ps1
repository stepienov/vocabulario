Set-Location $PSScriptRoot\..\infra
docker compose up -d
Write-Host "Postgres: localhost:5433 | Redis: localhost:6379"
