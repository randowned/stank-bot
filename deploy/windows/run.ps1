# Local dev runner for Windows.
#
# Usage:
#   pwsh deploy\windows\run.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $repoRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    uv venv --python 3.12
}

Write-Host "Installing dependencies..."
uv pip install -e ".[dev]"

if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path data | Out-Null
}

Write-Host "Applying migrations..."
.\.venv\Scripts\python.exe -m alembic upgrade head

Write-Host "Starting StankBot..."
.\.venv\Scripts\python.exe -m stankbot
