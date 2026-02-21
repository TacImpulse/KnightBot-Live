# KNIGHTBOT - CANONICAL STARTUP SCRIPT (Windows / PowerShell)
# Notes:
# - Uses `docker compose` when available (Docker Desktop), falls back to legacy `docker-compose`.
# - If ffmpeg is missing, STT + Pipecat are skipped (chat + TTS still work).

$ErrorActionPreference = "Stop"

$K = "F:\KnightBot"
$VenvActivate = "$K\venv\Scripts\Activate.ps1"
$PythonExe = "$K\venv\Scripts\python.exe"

function Invoke-DockerCompose {
    param(
        [Parameter(Mandatory = $true)][string[]]$Args
    )

    # Prefer plugin: `docker compose ...`
    try {
        $null = docker compose version 2>$null
        & docker compose @Args
        return $LASTEXITCODE
    }
    catch {
        # Fall back to legacy binary: `docker-compose ...`
        & docker-compose @Args
        return $LASTEXITCODE
    }
}

function Test-PortInUse {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
        return $null -ne $conn
    }
    catch {
        return $false
    }
}

function Start-KnightService {
    param(
        [string]$Name,
        [string]$Command,
        [int]$DelaySeconds = 2
    )

    Write-Host ("Starting " + $Name + "...") -ForegroundColor Yellow
    $wrappedCommand = '$ErrorActionPreference="Stop"; $env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"; ' + $Command
    $proc = Start-Process powershell -ArgumentList "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", $wrappedCommand -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds $DelaySeconds
    Write-Host ("  OK: " + $Name + " launch command issued (PID " + $proc.Id + ")") -ForegroundColor Green
}

try {
    if ($Host -and $Host.UI -and $Host.UI.RawUI) {
        Clear-Host
    }
}
catch {
    # Non-interactive shells can throw on RawUI operations.
}
Write-Host "" 
Write-Host "KnightBot startup (canonical)" -ForegroundColor Cyan
Write-Host "" 

if (-not (Test-Path $PythonExe)) {
    Write-Host ("ERROR: Python venv not found at " + $PythonExe) -ForegroundColor Red
    Write-Host "Run: .\install.ps1" -ForegroundColor Yellow
    exit 1
}

# Ensure we run from the repo root regardless of where the script was invoked from.
Set-Location $K

# Stage LiveKit config to a C: path for Docker Desktop mounts.
# Some Docker Desktop setups cannot bind-mount directly from external drives.
$dockerConfigRoot = Join-Path $env:USERPROFILE ".knightbot\config"
$dockerLiveKitConfig = Join-Path $dockerConfigRoot "livekit.yaml"
New-Item -ItemType Directory -Path $dockerConfigRoot -Force | Out-Null
Copy-Item -Path (Join-Path $K "config\livekit.yaml") -Destination $dockerLiveKitConfig -Force
$env:LIVEKIT_CONFIG_PATH = ($dockerLiveKitConfig -replace "\\", "/")

$skipSTT = $false
$skipSTTReason = ""
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    $skipSTT = $true
    $skipSTTReason = "ffmpeg"
    Write-Host "WARNING: ffmpeg not found in PATH. STT will be skipped (voice input disabled)." -ForegroundColor Yellow
    Write-Host "         Install ffmpeg, then restart KnightBot to enable STT." -ForegroundColor DarkGray
}

function Test-PythonModule {
    param([Parameter(Mandatory = $true)][string]$Module)
    try {
        & $PythonExe -c "import importlib; importlib.import_module('$Module')" 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

# Dependency checks: if modules are missing, the STT/TTS services will crash immediately.
$skipTTS = $false
$sttMissing = @()
$ttsMissing = @()

if (-not (Test-PythonModule -Module "torch")) {
    $sttMissing += "torch"
    $ttsMissing += "torch"
}

if (-not (Test-PythonModule -Module "torchaudio")) {
    $ttsMissing += "torchaudio"
}

if (-not (Test-PythonModule -Module "soundfile")) {
    $ttsMissing += "soundfile"
}

# NOTE: Importing `nemo.collections.asr` can pull in optional dependency chains (metrics/diarization/etc.)
# and is heavier than what we actually need for Parakeet.
#
# To avoid false negatives from import-time side effects, prefer a file-existence check for NeMo ASR.
$asrModelFile = Join-Path $K "venv\Lib\site-packages\nemo\collections\asr\models\asr_model.py"
$sttOk = (Test-Path $asrModelFile)
if (-not $sttOk) {
    # Fallback to an actual import check.
    $sttOk = (Test-PythonModule -Module "nemo.collections.asr.models.asr_model")
}
if (-not $sttOk) {
    $sttMissing += "nemo-toolkit (NeMo ASR not found)"
}

if (-not (Test-PythonModule -Module "pydub")) {
    # Not strictly required for basic synthesis, but used by voice upload processing.
    $ttsMissing += "pydub"
}

if (-not (Test-PythonModule -Module "PIL")) {
    $ttsMissing += "Pillow (PIL)"
}

if (-not (Test-PythonModule -Module "transformers")) {
    $ttsMissing += "transformers"
}

if ($sttMissing.Count -gt 0) {
    $skipSTT = $true
    if (-not $skipSTTReason) { $skipSTTReason = "deps" }
    Write-Host ("WARNING: STT dependencies missing: " + ($sttMissing -join ", ") + ". STT will be skipped.") -ForegroundColor Yellow
    Write-Host "         Fix by running .\install.ps1 (or pip install -r requirements.txt)" -ForegroundColor DarkGray
}

if ($ttsMissing.Count -gt 0) {
    $skipTTS = $true
    Write-Host ("WARNING: TTS dependencies missing: " + ($ttsMissing -join ", ") + ". TTS will be skipped.") -ForegroundColor Yellow
    Write-Host "         Fix by running .\install.ps1 (or pip install -r requirements.txt)" -ForegroundColor DarkGray
}

# Ports we require to be free before launching
# STT: 8071 = Faster Whisper (preferred), 8070 = Parakeet (fallback)
$requiredPorts = @(3000, 8050, 8100, 7880, 6333)
if (-not $skipTTS) { $requiredPorts += 8060 }
if (-not $skipSTT) { $requiredPorts += @(8070, 8071) }

$occupied = @($requiredPorts | Where-Object { Test-PortInUse -Port $_ })
if ($occupied.Count -gt 0) {
    Write-Host ("ERROR: Required ports already in use: " + ($occupied -join ", ")) -ForegroundColor Red
    Write-Host "Run: .\stop.ps1, then retry." -ForegroundColor Yellow
    exit 1
}

try {
    docker info | Out-Null
}
catch {
    Write-Host "ERROR: Docker is not running. Start Docker Desktop and retry." -ForegroundColor Red
    exit 1
}

Write-Host "Starting Docker services (LiveKit, Qdrant, Mem0)..." -ForegroundColor Yellow
Invoke-DockerCompose -Args @("up", "-d", "--remove-orphans") | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker compose startup failed." -ForegroundColor Red
    exit 1
}
Start-Sleep -Seconds 6
Write-Host "OK: Docker services started" -ForegroundColor Green

# Check LM Studio (non-fatal)
$lmStudioUrl = if ($env:LM_STUDIO_URL -and $env:LM_STUDIO_URL.Trim()) {
    $env:LM_STUDIO_URL.Trim().TrimEnd("/")
} else {
    "http://192.168.68.111:1234/v1"
}
if (-not $env:LM_STUDIO_URL) {
    $env:LM_STUDIO_URL = $lmStudioUrl
}
$lmStudioModelsUrl = "$lmStudioUrl/models"
try {
    $null = Invoke-RestMethod -Uri $lmStudioModelsUrl -Method Get -TimeoutSec 3
    Write-Host ("OK: LM Studio API reachable at " + $lmStudioModelsUrl) -ForegroundColor Green
}
catch {
    Write-Host ("WARNING: LM Studio not reachable at " + $lmStudioModelsUrl + ". Chat will fail until model server is running.") -ForegroundColor Yellow
}

# Start services
Start-KnightService -Name "Knight Core (8100)" -Command "& '$VenvActivate'; Set-Location '$K'; & '$PythonExe' '$K\scripts\knight_core.py'" -DelaySeconds 3
# Check for Faster Whisper (preferred) vs Parakeet (fallback)
$skipFasterWhisper = $false
if (-not (Test-PythonModule -Module "faster_whisper")) {
    Write-Host "NOTE: Faster Whisper not found - will use Parakeet fallback" -ForegroundColor Cyan
    $skipFasterWhisper = $true
}

if (-not $skipSTT) {
    # Start Faster Whisper (port 8071) - preferred STT
    if (-not $skipFasterWhisper) {
        Start-KnightService -Name "Faster Whisper STT (8071)" -Command "& '$VenvActivate'; Set-Location '$K'; $env:KB_FASTER_WHISPER_DEVICE='cuda'; $env:KB_FASTER_WHISPER_COMPUTE='float16'; & '$PythonExe' '$K\\faster_whisper\\server.py'" -DelaySeconds 3
    }
    # Start Parakeet (port 8070) - fallback STT
    Start-KnightService -Name "Parakeet STT (8070)" -Command "& '$VenvActivate'; Set-Location '$K'; & '$PythonExe' '$K\\parakeet\\server.py'" -DelaySeconds 3
} else {
    Write-Host "Skipping STT (disabled)" -ForegroundColor DarkGray
}

if (-not $skipTTS) {
    Start-KnightService -Name "Chatterbox TTS (8060)" -Command "& '$VenvActivate'; Set-Location '$K'; $env:KB_CHATTERBOX_ATTN_IMPL='sdpa'; $env:KB_TTS_MAX_NEW_TOKENS='520'; $env:KB_TTS_MIN_NEW_TOKENS='180'; $env:KB_TTS_BASE_NEW_TOKENS='120'; $env:KB_TTS_TOKENS_PER_CHAR='0.45'; $env:KB_TTS_SDP_FLASH='1'; $env:KB_TTS_SDP_MEM_EFFICIENT='1'; $env:KB_TTS_SDP_MATH='1'; $env:KB_TTS_FORCE_ALIGNMENT_ATTN='0'; & '$PythonExe' '$K\\chatterbox\\server.py'" -DelaySeconds 3
} else {
    Write-Host "Skipping TTS (missing python deps)" -ForegroundColor DarkGray
}

if (-not $skipSTT) {
    Start-KnightService -Name "Pipecat (LiveKit pipeline)" -Command "& '$VenvActivate'; Set-Location '$K'; & '$PythonExe' '$K\pipecat\pipeline.py'" -DelaySeconds 2
} else {
    Write-Host "Skipping Pipecat (depends on STT)" -ForegroundColor DarkGray
}

Start-KnightService -Name "Frontend (3000)" -Command "Set-Location '$K\frontend'; npm run dev" -DelaySeconds 2

Write-Host "" 
Write-Host "KnightBot launch sequence complete" -ForegroundColor Green
Write-Host "Frontend:   http://localhost:3000" -ForegroundColor White
Write-Host "Knight API: http://localhost:8100" -ForegroundColor White
if (-not $skipSTT) {
    if (-not $skipFasterWhisper) {
        Write-Host "STT:        Faster Whisper (8071) + Parakeet (8070)" -ForegroundColor White
    } else {
        Write-Host "STT:        Parakeet (8070)" -ForegroundColor White
    }
} else {
    if ($skipSTTReason -eq "ffmpeg") {
        Write-Host "STT:        disabled (install ffmpeg)" -ForegroundColor DarkGray
    } else {
        Write-Host "STT:        disabled (missing python deps)" -ForegroundColor DarkGray
    }
}
if (-not $skipTTS) {
    Write-Host "TTS:        Chatterbox Turbo (8060)" -ForegroundColor White
} else {
    Write-Host "TTS:        disabled (missing python deps)" -ForegroundColor DarkGray
}
Write-Host "LiveKit:    ws://localhost:7880" -ForegroundColor White

try {
    Start-Process "http://localhost:3000" | Out-Null
}
catch {
    Write-Host "NOTE: Could not auto-open browser. Frontend is still at http://localhost:3000" -ForegroundColor DarkGray
}
