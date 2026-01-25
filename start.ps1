# ═══════════════════════════════════════════════════════════════════════════════
# KNIGHTBOT STARTUP (venv-aware)
# ═══════════════════════════════════════════════════════════════════════════════
$K = "F:\KnightBot"
$V = "$K\venv\Scripts\Activate.ps1"
$Py = "$K\venv\Scripts\python.exe"
Write-Host @"
  ██╗  ██╗███╗   ██╗██╗ ██████╗ ██╗  ██╗████████╗
  ██║ ██╔╝████╗  ██║██║██╔════╝ ██║  ██║╚══██╔══╝
  █████╔╝ ██╔██╗ ██║██║██║  ███╗███████║   ██║
  ██╔═██╗ ██║╚██╗██║██║██║   ██║██╔══██║   ██║
  ██║  ██╗██║ ╚████║██║╚██████╔╝██║  ██║   ██║
  ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝
  Ultimate Voice Bridge v1.0
"@ -ForegroundColor Cyan
# Check venv exists
if (-not (Test-Path $Py)) {
    Write-Host "✗ venv not found at $K\venv" -ForegroundColor Red
    Write-Host "  Run: python -m venv $K\venv" -ForegroundColor Yellow
    exit 1
}
Write-Host "[1/5] Docker (Qdrant + Mem0)..." -ForegroundColor Yellow
Set-Location $K
docker-compose up -d 2>$null
Start-Sleep 8
Write-Host "      ✓ Docker ready" -ForegroundColor Green
Write-Host "[2/5] Knight API (8100)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$V'; cd '$K\scripts'; python knight_core.py" -WindowStyle Minimized
Start-Sleep 3
Write-Host "      ✓ Knight API started" -ForegroundColor Green
Write-Host "[3/5] Parakeet STT (8070)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$V'; cd '$K\parakeet'; python server.py" -WindowStyle Minimized
Start-Sleep 2
Write-Host "      ✓ Parakeet STT started" -ForegroundColor Green
Write-Host "[4/5] Chatterbox TTS (8060)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$V'; cd '$K\chatterbox'; python server.py" -WindowStyle Minimized
Start-Sleep 2
Write-Host "      ✓ Chatterbox TTS started" -ForegroundColor Green
Write-Host "[5/6] Frontend (3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$K\frontend'; npm run dev" -WindowStyle Minimized
Start-Sleep 3
Write-Host "      ✓ Frontend started" -ForegroundColor Green
Write-Host "[6/6] Pipecat Agent..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$V'; cd '$K\pipecat'; python pipeline.py" -WindowStyle Minimized
Write-Host "      ✓ Pipecat Agent started" -ForegroundColor Green
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✓ KNIGHTBOT READY!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend:   http://localhost:3000" -ForegroundColor White
Write-Host "  Knight API: http://localhost:8100" -ForegroundColor White
Write-Host "  STT:        http://localhost:8070" -ForegroundColor White
Write-Host "  TTS:        http://localhost:8060" -ForegroundColor White
Write-Host "  Qdrant:     http://localhost:6333" -ForegroundColor White
Write-Host "  Mem0:       http://localhost:8050" -ForegroundColor White
Write-Host ""
Write-Host "  Shortcuts: Ctrl+V = Voice | Escape = Stop" -ForegroundColor DarkGray
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Start-Process "http://localhost:3000"
