# Jedna komenda z roota repo: .\start-backend.ps1
Set-Location $PSScriptRoot\backend
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    python -m venv .venv
    .\.venv\Scripts\pip install -e .
}
& .\.venv\Scripts\python.exe run.py
