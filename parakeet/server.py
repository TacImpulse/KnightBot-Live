"""KnightBot Parakeet STT - Production"""
import os, io, torch
import subprocess
import tempfile
import traceback
import uvicorn
import sys
# NOTE: Importing `nemo.collections.asr` triggers a large dependency chain (pyannote,
# etc.) that isn't required for running Parakeet inference. Import the ASRModel
# class directly to keep runtime deps lighter on Windows.
from nemo.collections.asr.models.asr_model import ASRModel
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


def _configure_stdio_safely() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


_configure_stdio_safely()

model, device = None, None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🦜 Loading Parakeet on {device}...")
    if torch.cuda.is_available():
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
    try:
        model = ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v2")
        model = model.to(device).eval()
        
        # Disable lhotse to avoid version mismatch errors
        for ds_name in ['train_ds', 'validation_ds', 'test_ds']:
            if hasattr(model, 'cfg') and ds_name in model.cfg and hasattr(model.cfg[ds_name], 'use_lhotse'):
                print(f"🔧 Disabling Lhotse in model config [{ds_name}]...")
                model.cfg[ds_name].use_lhotse = False
            
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
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
            
        wav_path = tmp_path.replace(".webm", ".wav")

        try:
            print(f"🎤 Transcribing {tmp_path}...")
            
            # Convert to WAV using ffmpeg
            subprocess.run(["ffmpeg", "-y", "-i", tmp_path, "-ar", "16000", "-ac", "1", wav_path], 
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            with torch.no_grad():
                # Pass the WAV file to transcribe
                result = model.transcribe(audio=[wav_path], batch_size=1)
            
            # Extract text from Hypothesis object if needed
            if result and hasattr(result[0], 'text'):
                text = result[0].text
            else:
                text = str(result[0]) if result else ""
                
            print(f"📝 Transcription: {text}")
            return {"text": text}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(wav_path):
                os.remove(wav_path)
                
    except Exception as e:
        traceback.print_exc()
        print(f"❌ Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy" if model else "degraded", "model": "parakeet-tdt-0.6b-v2",
            "device": device, "loaded": model is not None}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8070)
