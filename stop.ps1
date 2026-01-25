# KNIGHTBOT SHUTDOWN
Write-Host "`n🛑 Stopping KnightBot...`n" -ForegroundColor Yellow
Get-Process node -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Get-Process python -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Set-Location "F:\KnightBot"
docker-compose down 2>$null
Write-Host "✓ KnightBot stopped`n" -ForegroundColor Green
