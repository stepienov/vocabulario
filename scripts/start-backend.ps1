Set-Location $PSScriptRoot\..\backend
if (-not (Test-Path .\.venv)) {
    python -m venv .venv
    .\.venv\Scripts\pip install -e .
}
.\.venv\Scripts\python run.py
