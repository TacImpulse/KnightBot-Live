# ═══════════════════════════════════════════════════════════════════════════════
# KNIGHTBOT INSTALLATION (Creates venv + installs deps)
# ═══════════════════════════════════════════════════════════════════════════════
$K = "F:\KnightBot"
Write-Host "`n🛡️ KNIGHTBOT INSTALLATION`n" -ForegroundColor Cyan
# Check Python
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
try {
    $pyV = python --version 2>&1
    Write-Host "      ✓ $pyV" -ForegroundColor Green
} catch {
    Write-Host "      ✗ Python not found. Install Python 3.10+" -ForegroundColor Red
    exit 1
}
# Check Node
Write-Host "[2/5] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeV = node --version 2>&1
    Write-Host "      ✓ Node $nodeV" -ForegroundColor Green
} catch {
    Write-Host "      ✗ Node.js not found. Install Node 18+" -ForegroundColor Red
    exit 1
}
# Create venv if needed
Write-Host "[3/5] Setting up Python venv..." -ForegroundColor Yellow
if (-not (Test-Path "$K\venv")) {
    python -m venv "$K\venv"
    Write-Host "      ✓ Created venv" -ForegroundColor Green
} else {
    Write-Host "      ✓ venv exists" -ForegroundColor Green
}
# Activate and install Python deps
Write-Host "[4/5] Installing Python dependencies..." -ForegroundColor Yellow
& "$K\venv\Scripts\Activate.ps1"
Set-Location $K
pip install --upgrade pip
# Install main requirements (excluding conflicting packages)
pip install -r requirements.txt
# Install Chatterbox manually to bypass strict numpy check (conflict with Pipecat)
Write-Host "      Installing Chatterbox and dependencies..." -ForegroundColor Yellow
pip install chatterbox-tts==0.1.1 --no-deps
pip install resemble-perth s3tokenizer diffusers conformer
Write-Host "      ✓ Python deps installed" -ForegroundColor Green
# Install Node deps
Write-Host "[5/5] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location "$K\frontend"
npm install
Write-Host "      ✓ Frontend deps installed" -ForegroundColor Green
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✓ INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    1. Start LM Studio and load your model" -ForegroundColor DarkGray
Write-Host "    2. Run: cd F:\KnightBot" -ForegroundColor DarkGray
Write-Host "    3. Run: .\start.ps1" -ForegroundColor DarkGray
Write-Host ""
