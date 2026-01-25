# ═══════════════════════════════════════════════════════════════════════════════
# KNIGHTBOT SETUP - PART 3B (Pipecat + Startup Scripts with VENV)
# Save as: setup-knightbot-part3b.ps1
# ═══════════════════════════════════════════════════════════════════════════════
$BaseDir = "F:\KnightBot"
Write-Host "`n🛡️ KNIGHTBOT PART 3B - Pipecat + Scripts (venv-aware)`n" -ForegroundColor Cyan
# ─── PIPECAT PIPELINE ───
@'
"""KnightBot Pipecat Voice Pipeline"""
import asyncio, httpx, struct
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.frames.frames import Frame, AudioRawFrame, TextFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.silero import SileroVADAnalyzer
class STTProcessor(FrameProcessor):
    def __init__(self): super().__init__(); self.buffer = bytearray()
    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, AudioRawFrame):
            self.buffer.extend(frame.audio)
            if len(self.buffer) >= 32000:
                text = await self._transcribe()
                if text: await self.push_frame(TranscriptionFrame(text=text, user_id="user"))
                self.buffer.clear()
        else: await self.push_frame(frame, direction)
    async def _transcribe(self):
        hdr = struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', len(self.buffer)+36, b'WAVE',
            b'fmt ', 16, 1, 1, 16000, 32000, 2, 16, b'data', len(self.buffer))
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post("http://localhost:8070/transcribe",
                    files={"audio": ("a.wav", hdr+bytes(self.buffer), "audio/wav")})
                return r.json().get("text", "") if r.status_code == 200 else ""
        except: return ""
class LLMProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            try:
                async with httpx.AsyncClient(timeout=120) as c:
                    r = await c.post("http://localhost:8100/chat", json={"message": frame.text})
                    if r.status_code == 200:
                        await self.push_frame(TextFrame(text=r.json().get("text", "")))
            except Exception as e: await self.push_frame(TextFrame(text=f"[sigh] Error: {e}"))
        else: await self.push_frame(frame, direction)
class TTSProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame) and frame.text:
            try:
                async with httpx.AsyncClient(timeout=60) as c:
                    r = await c.post("http://localhost:8060/synthesize",
                        json={"text": frame.text, "exaggeration": 0.5})
                    if r.status_code == 200:
                        await self.push_frame(AudioRawFrame(audio=r.content[44:], sample_rate=22050, num_channels=1))
            except: pass
        else: await self.push_frame(frame, direction)
async def run_pipeline():
    vad = SileroVADAnalyzer(sample_rate=16000, params=SileroVADAnalyzer.VADParams(threshold=0.5))
    pipeline = Pipeline([vad, STTProcessor(), LLMProcessor(), TTSProcessor()])
    print("🎙️ Voice pipeline ready")
    await PipelineTask(pipeline, PipelineParams(allow_interruptions=True)).run()
if __name__ == "__main__": asyncio.run(run_pipeline())
'@ | Set-Content "$BaseDir\pipecat\pipeline.py" -Encoding UTF8
Write-Host "✓ pipecat/pipeline.py" -ForegroundColor Green
# ─── UPDATED API.TS ───
@'
const KNIGHT_API = '/api/knight';
const STT_API = '/api/stt';
const TTS_API = '/api/tts';
export async function sendMessage(message: string) {
  const r = await fetch(`${KNIGHT_API}/chat`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }) });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function synthesizeSpeech(text: string, exaggeration = 0.5): Promise<Blob> {
  const r = await fetch(`${TTS_API}/synthesize`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, exaggeration }) });
  if (!r.ok) throw new Error('TTS failed');
  return r.blob();
}
export async function transcribeAudio(blob: Blob) {
  const fd = new FormData(); fd.append('audio', blob, 'rec.wav');
  const r = await fetch(`${STT_API}/transcribe`, { method: 'POST', body: fd });
  return r.json();
}
export async function checkHealth() {
  const h = { knight: false, stt: false, tts: false };
  try { h.knight = (await fetch(`${KNIGHT_API}/health`)).ok; } catch {}
  try { h.stt = (await fetch(`${STT_API}/health`)).ok; } catch {}
  try { h.tts = (await fetch(`${TTS_API}/health`)).ok; } catch {}
  return h;
}
'@ | Set-Content "$BaseDir\frontend\src\lib\api.ts" -Encoding UTF8
Write-Host "✓ api.ts" -ForegroundColor Green
# ─── START.PS1 (VENV-AWARE) ───
@'
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
Write-Host "[5/5] Frontend (3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$K\frontend'; npm run dev" -WindowStyle Minimized
Start-Sleep 3
Write-Host "      ✓ Frontend started" -ForegroundColor Green
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
'@ | Set-Content "$BaseDir\start.ps1" -Encoding UTF8
Write-Host "✓ start.ps1 (venv-aware)" -ForegroundColor Green
# ─── STOP.PS1 ───
@'
# KNIGHTBOT SHUTDOWN
Write-Host "`n🛑 Stopping KnightBot...`n" -ForegroundColor Yellow
Get-Process node -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Get-Process python -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Set-Location "F:\KnightBot"
docker-compose down 2>$null
Write-Host "✓ KnightBot stopped`n" -ForegroundColor Green
'@ | Set-Content "$BaseDir\stop.ps1" -Encoding UTF8
Write-Host "✓ stop.ps1" -ForegroundColor Green
# ─── INSTALL.PS1 (VENV-AWARE) ───
@'
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
pip install -r requirements.txt
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
'@ | Set-Content "$BaseDir\install.ps1" -Encoding UTF8
Write-Host "✓ install.ps1 (creates venv + installs)" -ForegroundColor Green
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✓ PART 3B COMPLETE" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  All scripts ready! Run in order:" -ForegroundColor White
Write-Host "    1. setup-knightbot-part1.ps1" -ForegroundColor DarkGray
Write-Host "    2. setup-knightbot-part2a.ps1" -ForegroundColor DarkGray
Write-Host "    3. setup-knightbot-part2b.ps1" -ForegroundColor DarkGray
Write-Host "    4. setup-knightbot-part2c.ps1" -ForegroundColor DarkGray
Write-Host "    5. setup-knightbot-part3a.ps1" -ForegroundColor DarkGray
Write-Host "    6. setup-knightbot-part3b.ps1  ← DONE" -ForegroundColor Green
Write-Host ""
Write-Host "  Then:" -ForegroundColor White
Write-Host "    cd F:\KnightBot" -ForegroundColor Cyan
Write-Host "    .\install.ps1    (creates venv + installs everything)" -ForegroundColor Cyan
Write-Host "    .\start.ps1      (launches all services)" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"