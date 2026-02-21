"""KnightBot Faster Whisper STT - SOTA Local Speech Recognition

This service provides high-performance local STT using Faster Whisper with CTranslate2 
optimization for real-time inference on GPU.

Usage:
    python faster_whisper/server.py
    
Environment Variables:
    KB_FASTER_WHISPER_MODEL - Model to use (default: large-v3)
    KB_FASTER_WHISPER_DEVICE - Device (default: cuda)
    KB_FASTER_WHISPER_COMPUTE - Compute type (default: float16)
"""

import os
import io
import torch
import subprocess
import tempfile
import traceback
from pathlib import Path
from contextlib import asynccontextmanager
import sys

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Faster Whisper import
from faster_whisper import WhisperModel


def _configure_stdio_safely() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


_configure_stdio_safely()

# Configuration
MODEL_NAME = os.getenv("KB_FASTER_WHISPER_MODEL", "large-v3")
DEVICE = os.getenv("KB_FASTER_WHISPER_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
COMPUTE_TYPE = os.getenv("KB_FASTER_WHISPER_COMPUTE", "float16" if DEVICE == "cuda" else "int8")

# Global model instance
model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    print(f"🔊 Loading Faster Whisper on {DEVICE}...")
    print(f"   Model: {MODEL_NAME}")
    print(f"   Compute: {COMPUTE_TYPE}")
    
    if torch.cuda.is_available():
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
    
    try:
        # Load Faster Whisper model
        # Using int8 for CPU, float16 for CUDA for best performance
        model = WhisperModel(
            MODEL_NAME,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            download_root=os.getenv("HF_HOME", None)  # Use HuggingFace cache
        )
        print("✓ Faster Whisper ready!")
        
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        traceback.print_exc()
        
    yield
    
    # Cleanup
    if model:
        del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


app = FastAPI(title="Knight STT (Faster Whisper)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


class TranscriptionResult(BaseModel):
    text: str
    language: str | None = None
    duration: float | None = None


@app.post("/transcribe", response_model=TranscriptionResult)
async def transcribe(audio: UploadFile = File(...), language: str | None = None):
    """Transcribe audio file to text.
    
    Args:
        audio: Audio file (webm, wav, mp3, etc.)
        language: Optional language hint (e.g., 'en')
    """
    if not model:
        raise HTTPException(503, "Model not loaded")
    
    try:
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
            
        wav_path = tmp_path.replace(".webm", ".wav")

        try:
            print(f"🎤 Transcribing {tmp_path}...")
            
            # Convert to WAV using ffmpeg (16kHz mono required for Whisper)
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_path, "-ar", "16000", "-ac", "1", "-af", "highpass=f=200,lowpass=f=3000", wav_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Run transcription
            segments, info = model.transcribe(
                wav_path,
                language=language,
                beam_size=5,
                vad_filter=True,  # Enable voice activity detection
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # Collect all segments
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            
            full_text = " ".join(text_parts)
            
            print(f"📝 Transcription: {full_text}")
            print(f"   Language: {info.language} (probability: {info.language_probability:.2f})")
            print(f"   Duration: {info.duration:.2f}s")
            
            return TranscriptionResult(
                text=full_text,
                language=info.language,
                duration=info.duration
            )
            
        finally:
            # Cleanup temp files
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(wav_path):
                os.remove(wav_path)
                
    except subprocess.ffmpeg_not_found:
        raise HTTPException(500, "FFmpeg not installed")
    except Exception as e:
        traceback.print_exc()
        print(f"❌ Transcription failed: {e}")
        raise HTTPException(500, str(e))


@app.post("/transcribe/stream")
async def transcribe_stream(audio: UploadFile = File(...), language: str | None = None):
    """Streaming transcription - returns segments as they become available.
    
    For real-time use with Pipecat.
    """
    if not model:
        raise HTTPException(503, "Model not loaded")
    
    try:
        # Read audio data
        audio_data = await audio.read()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
            
        try:
            # Stream transcription
            segments, info = model.transcribe(
                tmp_path,
                language=language,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            results = []
            async for segment in segments:
                results.append({
                    "text": segment.text.strip(),
                    "start": segment.start,
                    "end": segment.end
                })
            
            return {
                "segments": results,
                "language": info.language,
                "duration": info.duration
            }
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        print(f"❌ Stream transcription failed: {e}")
        raise HTTPException(500, str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy" if model else "degraded",
        "model": MODEL_NAME,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "loaded": model is not None,
        "gpu_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    }


@app.get("/models")
async def list_models():
    """List available models and their sizes."""
    # Popular Faster Whisper models
    models = [
        {"id": "tiny", "params": "39M", "english_only": False},
        {"id": "base", "params": "74M", "english_only": False},
        {"id": "small", "params": "244M", "english_only": False},
        {"id": "medium", "params": "769M", "english_only": False},
        {"id": "large-v1", "params": "1550M", "english_only": False},
        {"id": "large-v2", "params": "1550M", "english_only": False},
        {"id": "large-v3", "params": "1550M", "english_only": False},
        {"id": "tiny.en", "params": "39M", "english_only": True},
        {"id": "base.en", "params": "74M", "english_only": True},
        {"id": "small.en", "params": "244M", "english_only": True},
        {"id": "medium.en", "params": "769M", "english_only": True},
    ]
    return {
        "current": MODEL_NAME,
        "device": DEVICE,
        "available_models": models
    }


if __name__ == "__main__":
    port = int(os.getenv("KB_STT_PORT", "8071"))
    print(f"🚀 Starting Faster Whisper STT server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
