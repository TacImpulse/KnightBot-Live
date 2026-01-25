"""KnightBot Chatterbox TTS - Production with paralinguistics"""

import io
import torch
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torchaudio
import soundfile as sf
import uvicorn
import traceback
import transformers
from transformers import LlamaConfig
from chatterbox import ChatterboxTTS
from PIL import Image
import shutil

# REVERTED to the state where we just DISABLE SDPA completely.
# The "Invalid backend" error we saw earlier was likely because we tried to set env var "0" AND context manager.
# But when we didn't use context manager and just set env var, it worked on CPU but failed on GPU with "Invalid backend".
# This means PyTorch Nightly GPU Math kernel might be broken or not registering as "math".
#
# NEW APPROACH:
# Use the `torch.backends.cuda.sdp_kernel(enable_flash=False, enable_math=True, enable_mem_efficient=False)` context manager
# BUT we also need to make sure the model isn't trying to force something else.
# The AttributeError means output[1] is None. output[1] is attention weights.
# Attention weights are None when using Flash Attention (SDPA) because it doesn't return them.
# So we MUST force a kernel that supports returning attention weights.
# The "math" kernel usually supports it.
# If "math" kernel is failing with "No available kernel", it implies the inputs (dtype/shape) aren't supported by the math kernel implementation in this specific PyTorch build.
#
# WORKAROUND:
# Force the model to use the "eager" implementation from Transformers library, bypassing PyTorch SDPA entirely.
# Transformers uses `_attn_implementation` config.
# We can try to patch the model after loading to use "eager" implementation.

# Resetting flags
torch.backends.cuda.enable_flash_sdp(True)
torch.backends.cuda.enable_mem_efficient_sdp(True)
torch.backends.cuda.enable_math_sdp(True)

# Monkeypatch torch.load to handle CPU-only environments for CUDA-saved models
original_load = torch.load


def safe_load(*args, **kwargs):
    if not torch.cuda.is_available() and "map_location" not in kwargs:
        kwargs["map_location"] = torch.device("cpu")
    return original_load(*args, **kwargs)


torch.load = safe_load

model, device = None, None
VOICE_REF = Path("F:/KnightBot/data/voices/knight_voice.wav")
VOICE_DIR = Path("F:/KnightBot/data/voices")
AVATAR_DIR = Path("F:/KnightBot/data/avatars")
CURRENT_VOICE_ID = "knight_voice"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🔊 Loading Chatterbox on {device}...")
    try:
        # 🔧 MONKEY PATCH: Force Transformers to use standard Eager Attention
        # We patch LlamaConfig to default _attn_implementation to 'eager'.
        # This avoids using Flash Attention (SDPA) which fails with "NoneType" error in alignment hooks.

        print("🔧 Patching LlamaConfig.__init__ to force 'eager' attention...")

        original_init = LlamaConfig.__init__

        def patched_init(self, *args, **kwargs):
            if "_attn_implementation" not in kwargs:
                kwargs["_attn_implementation"] = "eager"
            original_init(self, *args, **kwargs)
            # Force it again just in case
            self._attn_implementation = "eager"

        LlamaConfig.__init__ = patched_init

        model = ChatterboxTTS.from_pretrained(device=device)
        print("✓ Chatterbox ready!")
        if not VOICE_DIR.exists():
            VOICE_DIR.mkdir(parents=True, exist_ok=True)
        if VOICE_REF.exists():
            print(f"   Voice: {VOICE_REF}")
    except Exception as e:
        traceback.print_exc()
        print(f"✗ Chatterbox failed: {e}")
    yield
    if model:
        del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


app = FastAPI(title="Knight TTS", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class TTSRequest(BaseModel):
    text: str
    exaggeration: float = 0.5
    voice_id: str | None = None


@app.post("/synthesize")
async def synthesize(req: TTSRequest):
    if not model:
        raise HTTPException(503, "TTS not loaded")
    try:
        import torchaudio
        import soundfile as sf

        voice_path = None
        if req.voice_id:
            custom_voice = VOICE_DIR / f"{req.voice_id}.wav"
            if custom_voice.exists():
                voice_path = str(custom_voice)

        if not voice_path and VOICE_REF.exists():
            voice_path = str(VOICE_REF)

        # Try running WITHOUT the sdp_kernel context manager first, relying on PyTorch's auto-dispatch.
        # If the model internally uses SDPA, it should now find at least one kernel (Math) since we enabled all globally.
        # The previous error "AttributeError: 'NoneType' object has no attribute 'cpu'" happened because
        # Flash Attention (which was picked automatically) ignored output_attentions=True hook.
        # So we MUST disable Flash/MemEfficient for this call, but keep Math enabled.

        # We disable Flash and MemEfficient, leaving ONLY Math enabled.
        with torch.backends.cuda.sdp_kernel(
            enable_flash=False, enable_math=True, enable_mem_efficient=False
        ):
            audio = model.generate(
                text=req.text,
                audio_prompt_path=voice_path,
                exaggeration=req.exaggeration,
            )
        buf = io.BytesIO()
        # Use soundfile directly to bypass torchaudio/torchcodec issues on Nightly
        # audio is (1, T), squeeze to (T,)
        sf.write(buf, audio.squeeze().cpu().numpy(), model.sr, format="WAV")
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/wav")
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"❌ TTS Error: {e}")
        raise HTTPException(500, str(e))


@app.post("/voices/upload")
async def upload_voice(file: UploadFile = File(...), name: str = None):
    try:
        if not VOICE_DIR.exists():
            VOICE_DIR.mkdir(parents=True, exist_ok=True)

        filename = name if name else file.filename
        if not filename.endswith(".wav"):
            filename += ".wav"

        file_path = VOICE_DIR / filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {"status": "success", "voice_id": file_path.stem}
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {e}")


@app.get("/voices")
async def list_voices():
    voices = []
    if VOICE_DIR.exists():
        voices = [f.stem for f in VOICE_DIR.glob("*.wav")]
    return {"voices": voices, "default": "knight_voice" if VOICE_REF.exists() else None}


@app.post("/voices/{voice_id}/avatar")
async def upload_avatar(voice_id: str, file: UploadFile = File(...)):
    try:
        if not AVATAR_DIR.exists():
            AVATAR_DIR.mkdir(parents=True, exist_ok=True)

        # Verify voice exists
        voice_path = VOICE_DIR / f"{voice_id}.wav"
        if not voice_path.exists():
            raise HTTPException(404, "Voice profile not found")

        # Process image
        img = Image.open(file.file)
        # Convert to RGB (in case of RGBA/P)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize/Crop to square (center crop then resize)
        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) / 2
        top = (h - min_dim) / 2
        right = (w + min_dim) / 2
        bottom = (h + min_dim) / 2

        img = img.crop((left, top, right, bottom))
        img = img.resize((512, 512), Image.Resampling.LANCZOS)

        save_path = AVATAR_DIR / f"{voice_id}.jpg"
        img.save(save_path, "JPEG", quality=90)

        return {"status": "success", "url": f"/voices/{voice_id}/avatar"}
    except Exception as e:
        raise HTTPException(500, f"Avatar upload failed: {e}")


@app.get("/voices/{voice_id}/avatar")
async def get_avatar(voice_id: str):
    avatar_path = AVATAR_DIR / f"{voice_id}.jpg"
    if not avatar_path.exists():
        # Return default placeholder or 404?
        # Let's return a generated identicon or just 404 and let frontend handle fallback
        raise HTTPException(404, "Avatar not found")

    return StreamingResponse(open(avatar_path, "rb"), media_type="image/jpeg")


@app.post("/voices/{voice_id}/rename")
async def rename_voice(voice_id: str, new_name: str):
    try:
        if not new_name or new_name == voice_id:
            return {"status": "ignored"}

        old_wav = VOICE_DIR / f"{voice_id}.wav"
        new_wav = VOICE_DIR / f"{new_name}.wav"

        if not old_wav.exists():
            raise HTTPException(404, "Voice not found")
        if new_wav.exists():
            raise HTTPException(409, "Name already exists")

        os.rename(old_wav, new_wav)

        # Rename avatar if exists
        old_avatar = AVATAR_DIR / f"{voice_id}.jpg"
        new_avatar = AVATAR_DIR / f"{new_name}.jpg"
        if old_avatar.exists():
            os.rename(old_avatar, new_avatar)

        return {"status": "success", "new_id": new_name}
    except Exception as e:
        raise HTTPException(500, f"Rename failed: {e}")


@app.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    try:
        file_path = VOICE_DIR / f"{voice_id}.wav"
        if file_path.exists():
            os.remove(file_path)
            # Delete avatar too
            avatar_path = AVATAR_DIR / f"{voice_id}.jpg"
            if avatar_path.exists():
                os.remove(avatar_path)
            return {"status": "success", "message": f"Deleted {voice_id}"}
        raise HTTPException(404, "Voice not found")
    except Exception as e:
        raise HTTPException(500, f"Delete failed: {e}")


@app.get("/health")
async def health():
    return {
        "status": "healthy" if model else "unavailable",
        "model": "chatterbox-turbo",
        "device": device,
        "loaded": model is not None,
        "tags": ["[laugh]", "[chuckle]", "[sigh]", "[cough]", "[gasp]"],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8060)
