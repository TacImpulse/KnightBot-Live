# ============================================================================
# KNIGHTBOT INSTALLATION (Windows / PowerShell)
# - Creates/refreshes venv
# - Installs Python + Node dependencies
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -RecreateVenv
# ============================================================================

param(
    [switch]$RecreateVenv
)

$ErrorActionPreference = "Stop"

$K = (Resolve-Path (Split-Path -Parent $PSCommandPath)).Path
$VenvDir = Join-Path $K "venv"
$Activate = Join-Path $VenvDir "Scripts\Activate.ps1"

function Stop-ProcessesInPath {
    param([Parameter(Mandatory=$true)][string]$PrefixPath)

    $procs = @()
    try {
        $procs = Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and ($_.ExecutablePath -like "$PrefixPath\\*")
        }
    } catch {
        return
    }

    foreach ($p in $procs) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "" 
Write-Host "KNIGHTBOT INSTALL" -ForegroundColor Cyan
Write-Host "Repo: $K" -ForegroundColor DarkGray
Write-Host "" 

# --- Preconditions ---
Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow
try {
    $pyV = python --version 2>&1
    Write-Host "      OK: $pyV" -ForegroundColor Green
}
catch {
    Write-Host "      ERROR: Python not found. Install Python 3.10+" -ForegroundColor Red
    exit 1
}

Write-Host "[2/6] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeV = node --version 2>&1
    Write-Host "      OK: Node $nodeV" -ForegroundColor Green
}
catch {
    Write-Host "      ERROR: Node.js not found. Install Node 18+" -ForegroundColor Red
    exit 1
}

Write-Host "[3/6] Checking ffmpeg (recommended for STT)..." -ForegroundColor Yellow
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    Write-Host "      WARNING: ffmpeg not found in PATH. STT will be disabled until you install ffmpeg." -ForegroundColor Yellow
}
else {
    Write-Host "      OK: ffmpeg found" -ForegroundColor Green
}

# --- Python venv ---
Write-Host "[4/6] Setting up Python venv..." -ForegroundColor Yellow
if ($RecreateVenv -and (Test-Path $VenvDir)) {
    Write-Host "      Removing existing venv..." -ForegroundColor Yellow

    # Best effort: stop any Python processes still running from this venv.
    Stop-ProcessesInPath -PrefixPath $VenvDir

    $deleted = $false
    for ($i = 0; $i -lt 5; $i++) {
        try {
            Remove-Item -Recurse -Force $VenvDir -ErrorAction Stop
            $deleted = $true
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if (-not $deleted -and (Test-Path $VenvDir)) {
        # Fallback: rename rather than delete (Windows file locks are common).
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $backup = Join-Path $K ("venv.old." + $stamp)
        Write-Host "      WARNING: venv is locked; renaming to $backup" -ForegroundColor Yellow
        try {
            Move-Item -Force $VenvDir $backup -ErrorAction Stop
        } catch {
            Write-Host "      ERROR: Could not remove or rename venv (locked). Close any terminals/services using venv, then rerun install.ps1 -RecreateVenv." -ForegroundColor Red
            throw
        }
    }
}

if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
    Write-Host "      OK: venv created" -ForegroundColor Green
}
else {
    Write-Host "      OK: venv exists" -ForegroundColor Green
}

Write-Host "[5/6] Installing Python dependencies..." -ForegroundColor Yellow
Set-Location $K

& $Activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

# Install Chatterbox TTS package pinned, with manual deps (per repo history)
Write-Host "      Installing chatterbox-tts + extras..." -ForegroundColor Yellow
python -m pip install chatterbox-tts==0.1.1 --no-deps
python -m pip install resemble-perth s3tokenizer diffusers conformer

Write-Host "      Verifying key imports (this can take a minute)..." -ForegroundColor Yellow
python -c "import torch; import torchaudio; import soundfile; import transformers; import pydub; import nemo.collections.asr; print('OK: torch/torchaudio/nemo/tts deps import')"
Write-Host "      OK: Python deps installed" -ForegroundColor Green

# --- Frontend ---
Write-Host "[6/6] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location (Join-Path $K "frontend")

if (Test-Path (Join-Path (Get-Location) "package-lock.json")) {
    npm install
}
else {
    npm install
}

Write-Host "      OK: frontend deps installed" -ForegroundColor Green

Write-Host "" 
Write-Host "INSTALL COMPLETE" -ForegroundColor Green
Write-Host "Next:" -ForegroundColor White
Write-Host "  1) Start LM Studio and load your model" -ForegroundColor DarkGray
Write-Host "  2) Run: .\start.ps1" -ForegroundColor DarkGray
Write-Host "  3) To stop: .\stop.ps1" -ForegroundColor DarkGray
Write-Host "" 
