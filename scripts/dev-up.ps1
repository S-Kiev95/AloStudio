# One-command dev environment bring-up.
#
#   powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1
#
# What it does, in order:
#   1. Is Docker responding? If yes, skip to step 4.
#   2. If Docker is down, apply fix-docker-run.ps1 (safe no-op if not needed)
#   3. Launch Docker Desktop and wait until 'docker ps' succeeds
#   4. 'docker compose up -d' for the alostudio dev deps
#   5. Wait until alostudio-postgres reports healthy
#   6. Print status
#
# Idempotent: safe to run every morning. If everything is already up, it
# just prints "all green" and exits.

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

function Write-Step([string]$msg) {
    Write-Host "[dev-up] $msg" -ForegroundColor Cyan
}
function Write-Ok([string]$msg) {
    Write-Host "[dev-up] $msg" -ForegroundColor Green
}

# ---- 1. Is Docker responsive? ----------------------------------------------
function Test-DockerReady {
    try {
        docker ps --format "{{.Names}}" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

if (-not (Test-DockerReady)) {
    Write-Step "Docker not responding - running fix-docker-run.ps1 with -Start"
    & "$scriptDir\fix-docker-run.ps1" -Start

    $deadline = (Get-Date).AddMinutes(3)
    while (-not (Test-DockerReady)) {
        if ((Get-Date) -gt $deadline) {
            Write-Host "[dev-up] Docker still not ready after 3 minutes. Check backend.error.json." -ForegroundColor Red
            exit 1
        }
        Start-Sleep -Seconds 3
    }
    Write-Ok "Docker daemon is ready."
}
else {
    Write-Ok "Docker already responsive."
}

# ---- 2. Bring up alostudio dev deps ----------------------------------------
Write-Step "docker compose up -d postgres redis mailhog minio"
docker compose up -d postgres redis mailhog minio
if ($LASTEXITCODE -ne 0) {
    Write-Host "[dev-up] compose up failed." -ForegroundColor Red
    exit 1
}

# ---- 3. Wait for postgres healthy ------------------------------------------
Write-Step "Waiting for alostudio-postgres to report healthy..."
$deadline = (Get-Date).AddMinutes(2)
while ($true) {
    $health = docker inspect -f "{{.State.Health.Status}}" alostudio-postgres 2>$null
    if ($health -eq "healthy") { break }
    if ((Get-Date) -gt $deadline) {
        Write-Host "[dev-up] postgres did not become healthy in 2 minutes." -ForegroundColor Red
        exit 1
    }
    Start-Sleep -Seconds 2
}
Write-Ok "alostudio-postgres healthy."

# ---- 4. Summary ------------------------------------------------------------
docker compose ps
Write-Ok "Dev environment ready. You can now run uv run alembic upgrade head / pytest."
