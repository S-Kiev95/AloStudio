# Unblocks Docker Desktop on Windows after the AF_UNIX reparse-point
# crashloop ("initializing Inference manager: ... remove
# ...\run\dockerInference: El sistema no tiene acceso al archivo").
#
# The Inference Manager in Docker Desktop 4.43.x creates a socket at
# %LOCALAPPDATA%\Docker\run\dockerInference with a reparse tag Windows
# can't dereference from userland (ERROR_CANT_ACCESS_FILE 1920). When
# the backend crashes, the file survives as a stale reparse point; on
# the next boot ListenUnix tries os.Remove() on it, fails, and Docker
# refuses to start. The setting EnableDockerAI=false does NOT prevent
# the Inference Manager from initializing in 4.43.
#
# The only reliable recovery is to rename the *parent* run\ folder
# (which is renameable even though its children aren't deletable) so
# Docker creates a fresh one. This script:
#
#   1. Stops Docker Desktop if running
#   2. Waits for backend processes to exit
#   3. Renames run -> run_stale_<timestamp> (idempotent; skips if run
#      is healthy or doesn't exist)
#   4. Optionally relaunches Docker Desktop if -Start was passed
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\fix-docker-run.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\fix-docker-run.ps1 -Start

param(
    [switch]$Start
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "[fix-docker-run] $msg"
}

$runDir = Join-Path $env:LOCALAPPDATA "Docker\run"
$dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# ---- 1. Stop Docker Desktop (GUI + backend) --------------------------------
$dockerProcs = @(
    "Docker Desktop",
    "com.docker.backend",
    "com.docker.service",
    "com.docker.build",
    "com.docker.proxy"
)

$stoppedAny = $false
foreach ($name in $dockerProcs) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Step "Stopping $name ($($procs.Count) process)..."
        $procs | Stop-Process -Force -ErrorAction SilentlyContinue
        $stoppedAny = $true
    }
}

if ($stoppedAny) {
    Start-Sleep -Seconds 3
}

# ---- 2. Rename stale run/ ---------------------------------------------------
if (-not (Test-Path $runDir)) {
    Write-Step "$runDir does not exist, nothing to rename."
}
else {
    $stale = $false
    try {
        $children = Get-ChildItem -Force $runDir -ErrorAction Stop |
            Where-Object { $_.Name -eq "dockerInference" }
        if ($children) {
            # Any attribute read failure on the reparse point = stale.
            try {
                [void]($children | ForEach-Object { $_.Length })
            }
            catch {
                $stale = $true
            }
            # Even if Length read, Docker writes a fresh socket on start —
            # the safe thing is to always rename when the dir exists AFTER
            # a forced process stop.
            $stale = $true
        }
    }
    catch {
        $stale = $true
    }

    if ($stale) {
        $ts = Get-Date -Format "yyyyMMdd_HHmmss"
        $newName = "run_stale_$ts"
        try {
            Rename-Item -Path $runDir -NewName $newName -ErrorAction Stop
            Write-Step "Renamed run -> $newName"
        }
        catch {
            Write-Step "Rename failed: $($_.Exception.Message)"
            Write-Step "Try running this script from an elevated PowerShell."
            exit 1
        }
    }
    else {
        Write-Step "run\ looks clean, skipping rename."
    }
}

# ---- 3. Optional relaunch ---------------------------------------------------
if ($Start) {
    if (Test-Path $dockerExe) {
        Write-Step "Launching Docker Desktop..."
        Start-Process -FilePath $dockerExe
        Write-Step "Poll 'docker ps' to wait for daemon readiness."
    }
    else {
        Write-Step "Docker Desktop not found at $dockerExe; skipping relaunch."
    }
}
else {
    Write-Step "Done. Launch Docker Desktop manually, or re-run with -Start."
}
