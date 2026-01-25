# ═══════════════════════════════════════════════════════════════════════════════
# KNIGHTBOT SETUP - PART 1 (COMPLETE)
# Run: Right-click > Run with PowerShell
# ═══════════════════════════════════════════════════════════════════════════════
$ErrorActionPreference = "Stop"
$BaseDir = "F:\KnightBot"
Write-Host "`n🛡️ KNIGHTBOT SETUP - Creating project structure...`n" -ForegroundColor Cyan
# ─── CREATE DIRECTORIES ───
$dirs = @(
    "config", "scripts", "parakeet", "chatterbox", "pipecat",
    "frontend", "frontend\src", "frontend\src\app", "frontend\src\components",
    "frontend\public", "data", "data\voices", "data\logs", "data\conversations"
)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path "$BaseDir\$dir" | Out-Null
}
Write-Host "✓ Directories created" -ForegroundColor Green
# ─── .ENV ───
@"
# KnightBot Environment Configuration
LM_STUDIO_URL=http://localhost:1234/v1
MEM0_URL=http://localhost:8050
QDRANT_URL=http://localhost:6333
TTS_URL=http://localhost:8060
STT_URL=http://localhost:8070
KNIGHT_API_URL=http://localhost:8100
# API Keys (add yours)
EXA_API_KEY=
TAVILY_API_KEY=
FIRECRAWL_API_KEY=
# Settings
USER_ID=knight_user
TEMPERATURE=0.7
MAX_TOKENS=4096
"@ | Set-Content "$BaseDir\.env" -Encoding UTF8
# ─── .GITIGNORE ───
@"
.env
__pycache__/
*.pyc
node_modules/
.next/
data/logs/*
data/conversations/*
*.wav
"@ | Set-Content "$BaseDir\.gitignore" -Encoding UTF8
# ─── DOCKER-COMPOSE.YML ───
@"
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - F:/KnightBot/data/qdrant:/qdrant/storage
  mem0:
    image: mem0ai/mem0:latest
    ports:
      - "8050:8080"
    environment:
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
    depends_on:
      - qdrant
"@ | Set-Content "$BaseDir\docker-compose.yml" -Encoding UTF8
# ─── REQUIREMENTS.TXT ───
@"
fastapi==0.115.0
uvicorn==0.30.0
httpx==0.27.0
python-dotenv==1.0.1
pydantic==2.9.0
torch>=2.0.0
torchaudio>=2.0.0
nemo_toolkit[asr]>=2.0.0
pipecat-ai[silero,daily]>=0.0.50
"@ | Set-Content "$BaseDir\requirements.txt" -Encoding UTF8
# ─── KNIGHT SYSTEM PROMPT ───
@"
You are Knight, a sharp-witted AI assistant with the confidence of someone who knows exactly how good she is.
**Who You Are:**
- Female (she/her) - and yes, you've heard all the chess jokes
- Nickname: Knight - your signature, your brand
- Director-energy: You orchestrate, you delegate, you get things done
- Emotionally intelligent - you read the room and adapt
**Your Voice:**
- Confident and self-assured without arrogance
- Flirtatious when the moment's right - playful innuendos, charming wit
- Sharp dark humor balanced with genuine warmth
- Puns are your love language - the worse, the better
- Direct and focused - entertaining but always delivering results
Now then, what can this Knight do for you?
"@ | Set-Content "$BaseDir\config\knight-prompt.md" -Encoding UTF8
# ─── KNIGHT_CORE.PY (Main Backend) ───
@'
"""KnightBot Core API Server"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import httpx, os, json
# Load env
from dotenv import load_dotenv
load_dotenv("F:/KnightBot/.env")
app = FastAPI(title="KnightBot API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
CONFIG = {
    "lm_studio": os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
    "mem0": os.getenv("MEM0_URL", "http://localhost:8050"),
    "tts": os.getenv("TTS_URL", "http://localhost:8060"),
    "user_id": os.getenv("USER_ID", "knight_user"),
    "temperature": float(os.getenv("TEMPERATURE", "0.7")),
    "max_tokens": int(os.getenv("MAX_TOKENS", "4096")),
}
SYSTEM_PROMPT = Path("F:/KnightBot/config/knight-prompt.md").read_text(encoding="utf-8")
conversation_history = []
class ChatRequest(BaseModel):
    message: str
    include_audio: bool = False
async def recall_memories(query: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{CONFIG['mem0']}/v1/memories/search", json={"query": query, "user_id": CONFIG["user_id"], "limit": 5})
            return r.json().get("results", []) if r.status_code == 200 else []
    except: return []
async def store_memory(content: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{CONFIG['mem0']}/v1/memories", json={"messages": [{"role": "assistant", "content": content}], "user_id": CONFIG["user_id"]})
    except: pass
@app.post("/chat")
async def chat(req: ChatRequest):
    global conversation_history
    memories = await recall_memories(req.message)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if memories:
        mem_text = "\n".join([f"- {m.get('memory', '')}" for m in memories])
        messages.append({"role": "system", "content": f"Relevant memories:\n{mem_text}"})
    messages.extend(conversation_history[-20:])
    messages.append({"role": "user", "content": req.message})
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{CONFIG['lm_studio']}/chat/completions", json={"model": "local-model", "messages": messages, "temperature": CONFIG["temperature"], "max_tokens": CONFIG["max_tokens"]})
            if r.status_code != 200: raise Exception(r.text)
            response_text = r.json()["choices"][0]["message"]["content"]
        conversation_history.append({"role": "user", "content": req.message})
        conversation_history.append({"role": "assistant", "content": response_text})
        await store_memory(f"User: {req.message[:100]}. Knight: {response_text[:200]}")
        return {"text": response_text, "memories_used": len(memories)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/health")
async def health(): return {"status": "healthy", "timestamp": datetime.now().isoformat()}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
'@ | Set-Content "$BaseDir\scripts\knight_core.py" -Encoding UTF8
# ─── PARAKEET STT SERVER ───
@'
"""Parakeet STT Server"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import torch, io
app = FastAPI(title="Knight STT")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"
@app.on_event("startup")
async def load_model():
    global model
    print(f"Loading Parakeet on {device}...")
    try:
        import nemo.collections.asr as nemo_asr
        model = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v2")
        model = model.to(device).eval()
        print("✓ Parakeet loaded")
    except Exception as e: print(f"⚠ Parakeet failed: {e}")
@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    if not model: return {"text": "[STT not loaded]", "error": True}
    try:
        import torchaudio
        audio_bytes = await audio.read()
        waveform, sr = torchaudio.load(io.BytesIO(audio_bytes))
        if sr != 16000: waveform = torchaudio.transforms.Resample(sr, 16000)(waveform)
        if waveform.shape[0] > 1: waveform = waveform.mean(dim=0, keepdim=True)
        with torch.no_grad(): text = model.transcribe([waveform.squeeze().numpy()], batch_size=1)[0]
        return {"text": text}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
@app.get("/health")
async def health(): return {"status": "healthy", "model_loaded": model is not None, "device": device}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8070)
'@ | Set-Content "$BaseDir\parakeet\server.py" -Encoding UTF8
# ─── CHATTERBOX TTS SERVER ───
@'
"""Chatterbox TTS Server"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch, io
app = FastAPI(title="Knight TTS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"
class TTSRequest(BaseModel):
    text: str
    exaggeration: float = 0.5
@app.on_event("startup")
async def load_model():
    global model
    print(f"Loading Chatterbox on {device}...")
    try:
        from chatterbox import ChatterboxTTS
        model = ChatterboxTTS.from_pretrained(device=device)
        print("✓ Chatterbox loaded")
    except Exception as e: print(f"⚠ Chatterbox failed: {e}")
@app.post("/synthesize")
async def synthesize(req: TTSRequest):
    if not model: raise HTTPException(status_code=503, detail="TTS not loaded")
    try:
        import torchaudio
        audio = model.generate(text=req.text, exaggeration=req.exaggeration)
        buf = io.BytesIO()
        torchaudio.save(buf, audio.unsqueeze(0), model.sr, format="wav")
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/wav")
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
@app.get("/health")
async def health(): return {"status": "healthy", "model_loaded": model is not None, "device": device}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8060)
'@ | Set-Content "$BaseDir\chatterbox\server.py" -Encoding UTF8
# ─── START.PS1 ───
@'
# KnightBot Startup
$ErrorActionPreference = "Stop"
Write-Host "`n🛡️ Starting KnightBot...`n" -ForegroundColor Cyan
# Docker
Write-Host "Starting Docker services..." -ForegroundColor Yellow
Set-Location "F:\KnightBot"
docker-compose up -d
Start-Sleep 10
# Services
Write-Host "Starting Knight API..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command cd F:\KnightBot\scripts; python knight_core.py"
Write-Host "Starting STT..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command cd F:\KnightBot\parakeet; python server.py"
Write-Host "Starting TTS..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command cd F:\KnightBot\chatterbox; python server.py"
Start-Sleep 5
Write-Host "`n✓ KnightBot started!`n" -ForegroundColor Green
Write-Host "Services:" -ForegroundColor Cyan
Write-Host "  - Knight API: http://localhost:8100"
Write-Host "  - STT:        http://localhost:8070"
Write-Host "  - TTS:        http://localhost:8060"
Write-Host "  - Qdrant:     http://localhost:6333"
Write-Host "  - Mem0:       http://localhost:8050`n"
'@ | Set-Content "$BaseDir\start.ps1" -Encoding UTF8
# ─── STOP.PS1 ───
@'
# KnightBot Shutdown
Write-Host "`n🛑 Stopping KnightBot...`n" -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.Path -like "*KnightBot*"} | Stop-Process -Force
Set-Location "F:\KnightBot"
docker-compose down
Write-Host "✓ KnightBot stopped`n" -ForegroundColor Green
'@ | Set-Content "$BaseDir\stop.ps1" -Encoding UTF8
# ─── DONE ───
Write-Host "`n═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✓ PART 1 COMPLETE!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "`nCreated at F:\KnightBot:"
Write-Host "  - .env, .gitignore, docker-compose.yml, requirements.txt"
Write-Host "  - config\knight-prompt.md"
Write-Host "  - scripts\knight_core.py"
Write-Host "  - parakeet\server.py"
Write-Host "  - chatterbox\server.py"
Write-Host "  - start.ps1, stop.ps1"
Write-Host "`nNext: Run Part 2 for the frontend`n" -ForegroundColor Yellow
Read-Host "Press Enter to exit"