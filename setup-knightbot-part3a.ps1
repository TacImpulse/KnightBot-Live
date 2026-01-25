# ═══════════════════════════════════════════════════════════════════════════════
# KNIGHTBOT SETUP - PART 3A (Fixed Dependencies + STT/TTS)
# Save as: setup-knightbot-part3a.ps1
# ═══════════════════════════════════════════════════════════════════════════════
$BaseDir = "F:\KnightBot"
New-Item -ItemType Directory -Force -Path "$BaseDir\pipecat" | Out-Null
Write-Host "`n🛡️ KNIGHTBOT PART 3A - Production STT/TTS`n" -ForegroundColor Cyan
# ─── FIXED REQUIREMENTS.TXT ───
@'
# Core
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
python-dotenv==1.0.1
pydantic==2.9.0
websockets==12.0
# PyTorch CUDA 12.x (RTX 5090 Blackwell)
--extra-index-url https://download.pytorch.org/whl/cu124
torch>=2.4.0
torchaudio>=2.4.0
# STT - Parakeet
nemo_toolkit[asr]>=2.0.0
onnxruntime-gpu>=1.18.0
librosa>=0.10.0
soundfile>=0.12.0
# TTS - Chatterbox (PINNED - newer versions have pkuseg bug)
chatterbox-tts==0.1.1
numpy==1.26.4
# Pipecat
pipecat-ai[silero,livekit]>=0.0.54
livekit-api>=0.7.0
# Memory
qdrant-client>=1.9.0
'@ | Set-Content "$BaseDir\requirements.txt" -Encoding UTF8
Write-Host "✓ requirements.txt (fixed)" -ForegroundColor Green
# ─── PARAKEET SERVER ───
@'
"""KnightBot Parakeet STT - Production"""
import os, io, torch
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
model, device = None, None
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🦜 Loading Parakeet on {device}...")
    if torch.cuda.is_available():
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
    try:
        import nemo.collections.asr as nemo_asr
        model = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v2")
        model = model.to(device).eval()
        print("✓ Parakeet ready!")
    except Exception as e:
        print(f"✗ Parakeet failed: {e}")
    yield
    if model: del model
    if torch.cuda.is_available(): torch.cuda.empty_cache()
app = FastAPI(title="Knight STT", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    if not model: return {"text": "", "error": "Model not loaded"}
    try:
        import torchaudio
        audio_bytes = await audio.read()
        waveform, sr = torchaudio.load(io.BytesIO(audio_bytes))
        if sr != 16000:
            waveform = torchaudio.transforms.Resample(sr, 16000)(waveform)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        with torch.no_grad():
            result = model.transcribe([waveform.squeeze().numpy()], batch_size=1)
        return {"text": result[0] if result else "", "duration": len(waveform.squeeze())/16000}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/health")
async def health():
    return {"status": "healthy" if model else "degraded", "model": "parakeet-tdt-0.6b-v2",
            "device": device, "loaded": model is not None}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8070)
'@ | Set-Content "$BaseDir\parakeet\server.py" -Encoding UTF8
Write-Host "✓ parakeet/server.py" -ForegroundColor Green
# ─── CHATTERBOX SERVER ───
@'
"""KnightBot Chatterbox TTS - Production with paralinguistics"""
import os, io, torch
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
model, device = None, None
VOICE_REF = Path("F:/KnightBot/data/voices/knight_voice.wav")
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🔊 Loading Chatterbox on {device}...")
    try:
        from chatterbox.tts import ChatterboxTTS
        model = ChatterboxTTS.from_pretrained(device=device)
        print("✓ Chatterbox ready!")
        if VOICE_REF.exists(): print(f"   Voice: {VOICE_REF}")
    except Exception as e:
        print(f"✗ Chatterbox failed: {e}")
    yield
    if model: del model
    if torch.cuda.is_available(): torch.cuda.empty_cache()
app = FastAPI(title="Knight TTS", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
class TTSRequest(BaseModel):
    text: str
    exaggeration: float = 0.5
@app.post("/synthesize")
async def synthesize(req: TTSRequest):
    if not model: raise HTTPException(503, "TTS not loaded")
    try:
        import torchaudio
        voice = str(VOICE_REF) if VOICE_REF.exists() else None
        audio = model.generate(text=req.text, audio_prompt_path=voice, exaggeration=req.exaggeration)
        buf = io.BytesIO()
        torchaudio.save(buf, audio.unsqueeze(0).cpu(), model.sr, format="wav")
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(500, str(e))
@app.get("/health")
async def health():
    return {"status": "healthy" if model else "unavailable", "model": "chatterbox",
            "device": device, "loaded": model is not None,
            "tags": ["[laugh]","[chuckle]","[sigh]","[cough]","[gasp]"]}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8060)
'@ | Set-Content "$BaseDir\chatterbox\server.py" -Encoding UTF8
Write-Host "✓ chatterbox/server.py" -ForegroundColor Green
Write-Host "`n✓ Part 3A complete. Run part3b next.`n" -ForegroundColor Green
Read-Host "Press Enter to exit"