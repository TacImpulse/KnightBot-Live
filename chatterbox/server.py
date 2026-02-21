"""KnightBot Chatterbox TTS - Production with paralinguistics"""

from pydub import AudioSegment
import io
import torch
import os
import json
import types
import asyncio
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.concurrency import run_in_threadpool
import torchaudio
import soundfile as sf
import uvicorn
import traceback
import transformers
from transformers import LlamaConfig
import sys


def _configure_stdio_safely() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


_configure_stdio_safely()

# NOTE:
# This repo has a local folder named "chatterbox/" which can shadow the pip package
# that provides ChatterboxTTS. To avoid import collisions, we try the most likely
# module names and, if needed, prioritize site-packages on sys.path.
def _import_chatterbox_tts():
    try:
        # Some distributions may expose this explicitly
        from chatterbox_tts import ChatterboxTTS  # type: ignore
        return ChatterboxTTS
    except Exception:
        pass

    try:
        import site
        import sys

        for p in site.getsitepackages():
            if p in sys.path:
                sys.path.remove(p)
            sys.path.insert(0, p)

        from chatterbox import ChatterboxTTS  # type: ignore
        return ChatterboxTTS
    except Exception as e:
        raise ImportError(
            "Unable to import ChatterboxTTS. Ensure 'chatterbox-tts' is installed in the venv and that local folder "
            "name collisions are resolved. Original error: " + str(e)
        )


ChatterboxTTS = _import_chatterbox_tts()
from PIL import Image
import shutil


def _ensure_perth_watermarker():
    """Ensure `perth.PerthImplicitWatermarker` is callable.

    On some Windows/CPU installs, the `resemble-perth` package may import but
    expose `PerthImplicitWatermarker = None` (usually due to missing optional
    native bits). ChatterboxTTS treats watermarking as mandatory.

    For KnightBot runtime, watermarking is not required for basic synthesis, so
    we patch in a no-op implementation if Perth is unavailable.
    """

    try:
        import perth  # type: ignore

        if getattr(perth, "PerthImplicitWatermarker", None) is None:
            print("⚠️  Perth watermarker unavailable; using NO-OP watermarker (audio will be unwatermarked).")

            class _NoOpWatermarker:
                def apply_watermark(self, wav, sample_rate=None):
                    return wav

            perth.PerthImplicitWatermarker = _NoOpWatermarker  # type: ignore
    except Exception as e:
        print(f"⚠️  Failed to import/patch perth ({e}); continuing without watermarking.")


def _patch_alignment_hook_for_optimized_attention() -> None:
    """Avoid crashes when optimized attention does not return attention weights.

    Chatterbox's alignment hook assumes `output[1]` is always a tensor and calls `.cpu()`.
    With SDPA/Flash backends this can be `None`, which crashes synthesis.
    """
    try:
        from chatterbox.models.t3.inference.alignment_stream_analyzer import AlignmentStreamAnalyzer  # type: ignore
    except Exception as e:
        print(f"⚠️  Could not import AlignmentStreamAnalyzer for patching: {e}")
        return

    if getattr(AlignmentStreamAnalyzer, "_knight_safe_attn_patch", False):
        return

    def _safe_add_attention_spy(self, tfmr, alignment_layer_idx):
        def attention_forward_hook(module, input, output):
            attn_weights = None
            if isinstance(output, (tuple, list)) and len(output) > 1:
                attn_weights = output[1]
            if attn_weights is None:
                # SDPA/flash can omit attention weights.
                return
            self.last_aligned_attn = attn_weights[0].mean(0).detach().cpu()

        target_layer = tfmr.layers[alignment_layer_idx].self_attn
        target_layer.register_forward_hook(attention_forward_hook)

        # Keep default behavior unless explicitly requested.
        force_attn = os.getenv("KB_TTS_FORCE_ALIGNMENT_ATTN", "0") == "1"
        if force_attn:
            original_forward = target_layer.forward

            def patched_forward(self, *args, **kwargs):
                kwargs["output_attentions"] = True
                return original_forward(*args, **kwargs)

            target_layer.forward = types.MethodType(patched_forward, target_layer)

    AlignmentStreamAnalyzer._add_attention_spy = _safe_add_attention_spy
    AlignmentStreamAnalyzer._knight_safe_attn_patch = True
    print("⚡ Patched Chatterbox alignment hook for optimized-attention compatibility")


# --- Configuration & Paths ---
VOICE_REF = Path("F:/KnightBot/data/voices/Knight.wav")
VOICE_DIR = Path("F:/KnightBot/data/voices")
AVATAR_DIR = Path("F:/KnightBot/data/avatars")
CONFIG_FILE = Path("F:/KnightBot/data/config.json")

# Ensure directories exist
if not VOICE_DIR.exists():
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
if not AVATAR_DIR.exists():
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)

# --- Global State ---
model, device = None, None
CURRENT_VOICE_ID = "Knight"
CURRENT_CONDITIONED_VOICE_PATH = None
SYNTH_LOCK = asyncio.Lock()
REQUEST_TTS_MAX_NEW_TOKENS = None
TTS_MAX_CHARS = int(os.getenv("KB_TTS_MAX_CHARS", "0"))
TTS_MAX_NEW_TOKENS = int(os.getenv("KB_TTS_MAX_NEW_TOKENS", "160"))
TTS_MIN_NEW_TOKENS = int(os.getenv("KB_TTS_MIN_NEW_TOKENS", "160"))
TTS_BASE_NEW_TOKENS = int(os.getenv("KB_TTS_BASE_NEW_TOKENS", "120"))
TTS_TOKENS_PER_CHAR = float(os.getenv("KB_TTS_TOKENS_PER_CHAR", "0.45"))


def clip_tts_text(text: str) -> str:
    normalized = " ".join((text or "").split()).strip()
    if not normalized or TTS_MAX_CHARS <= 0 or len(normalized) <= TTS_MAX_CHARS:
        return normalized

    clipped = normalized[:TTS_MAX_CHARS]
    last_period = clipped.rfind(". ")
    if last_period > 40:
        clipped = clipped[: last_period + 1]
    return f"{clipped} ..."


def tts_sdp_kernel_context():
    if device != "cuda":
        return nullcontext()

    enable_flash = os.getenv("KB_TTS_SDP_FLASH", "1") == "1"
    enable_math = os.getenv("KB_TTS_SDP_MATH", "1") == "1"
    enable_mem_efficient = os.getenv("KB_TTS_SDP_MEM_EFFICIENT", "1") == "1"
    return torch.backends.cuda.sdp_kernel(
        enable_flash=enable_flash,
        enable_math=enable_math,
        enable_mem_efficient=enable_mem_efficient,
    )


def choose_tts_max_new_tokens(text: str) -> int:
    if not text:
        return TTS_MIN_NEW_TOKENS

    estimated = TTS_BASE_NEW_TOKENS + int(len(text) * TTS_TOKENS_PER_CHAR)
    estimated = max(TTS_MIN_NEW_TOKENS, estimated)
    return min(estimated, TTS_MAX_NEW_TOKENS)

def load_config():
    global CURRENT_VOICE_ID
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                CURRENT_VOICE_ID = data.get("current_voice_id", "Knight")
                print(f"⚙️ Loaded active voice: {CURRENT_VOICE_ID}")
        else:
            print("⚙️ No config found, using default voice.")
    except Exception as e:
        print(f"⚠️ Failed to load config: {e}")

def save_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"current_voice_id": CURRENT_VOICE_ID}, f)
        print(f"💾 Config saved. Active voice: {CURRENT_VOICE_ID}")
    except Exception as e:
        print(f"⚠️ Failed to save config: {e}")

# --- Torch Setup ---
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, device, CURRENT_VOICE_ID, CURRENT_CONDITIONED_VOICE_PATH, REQUEST_TTS_MAX_NEW_TOKENS
    
    # Load Config
    load_config()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🔊 Loading Chatterbox on {device}...")
    try:
        _ensure_perth_watermarker()
        _patch_alignment_hook_for_optimized_attention()

        # Configure attention backend. On CUDA we prefer SDPA (uses PyTorch flash kernels).
        attn_impl = os.getenv("KB_CHATTERBOX_ATTN_IMPL", "sdpa" if device == "cuda" else "eager")
        print(f"🔧 Patching LlamaConfig.__init__ to use '{attn_impl}' attention...")
        original_init = LlamaConfig.__init__

        def patched_init(self, *args, **kwargs):
            if "_attn_implementation" not in kwargs or kwargs["_attn_implementation"] is None:
                kwargs["_attn_implementation"] = attn_impl
            original_init(self, *args, **kwargs)
            self._attn_implementation = kwargs.get("_attn_implementation", attn_impl)

        LlamaConfig.__init__ = patched_init

        model = ChatterboxTTS.from_pretrained(device=device)
        print("✓ Chatterbox ready!")
        CURRENT_CONDITIONED_VOICE_PATH = None

        # Perth watermarking can return None in some Windows/CUDA stacks.
        # For realtime local assistant use, unwatermarked audio is acceptable.
        if os.getenv("KB_DISABLE_WATERMARK", "1") == "1":
            try:
                def _no_watermark(_self, wav, sample_rate=None):
                    return wav

                if getattr(model, "watermarker", None) is not None:
                    model.watermarker.apply_watermark = types.MethodType(_no_watermark, model.watermarker)
                    print("⚡ Disabled Perth watermarking for stable low-latency synthesis")
            except Exception as e:
                print(f"⚠️ Failed to disable watermarking cleanly: {e}")

        if device == "cuda":
            print(
                "⚡ TTS SDP kernels "
                f"flash={os.getenv('KB_TTS_SDP_FLASH', '1')} "
                f"math={os.getenv('KB_TTS_SDP_MATH', '1')} "
                f"mem_efficient={os.getenv('KB_TTS_SDP_MEM_EFFICIENT', '1')}"
            )

        # Cap autoregressive speech token generation for better latency on CPU.
        if not hasattr(model.t3, "_knight_inference_wrapped"):
            original_inference = model.t3.inference

            def capped_inference(*args, **kwargs):
                requested = kwargs.get("max_new_tokens")
                if requested is None:
                    requested = REQUEST_TTS_MAX_NEW_TOKENS
                if requested is None:
                    requested = TTS_MAX_NEW_TOKENS
                requested = int(requested)
                kwargs["max_new_tokens"] = min(requested, TTS_MAX_NEW_TOKENS)
                return original_inference(*args, **kwargs)

            model.t3.inference = capped_inference
            model.t3._knight_inference_wrapped = True
            print(
                "⚡ TTS max_new_tokens "
                f"min={TTS_MIN_NEW_TOKENS} base={TTS_BASE_NEW_TOKENS} "
                f"per_char={TTS_TOKENS_PER_CHAR} cap={TTS_MAX_NEW_TOKENS}"
            )
        
        # Verify active voice exists, fallback if not
        active_path = VOICE_DIR / f"{CURRENT_VOICE_ID}.wav"
        if not active_path.exists():
            print(f"⚠️ Active voice '{CURRENT_VOICE_ID}' not found. Falling back to default.")
            if VOICE_REF.exists():
                CURRENT_VOICE_ID = "Knight"
                save_config()
            
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
    global CURRENT_CONDITIONED_VOICE_PATH, REQUEST_TTS_MAX_NEW_TOKENS

    if not model:
        raise HTTPException(503, "TTS not loaded")
    try:
        text = clip_tts_text(req.text)
        if not text:
            raise HTTPException(400, "Text is empty")

        voice_path = None
        
        # Priority 1: Request specific voice
        if req.voice_id:
            custom_voice = VOICE_DIR / f"{req.voice_id}.wav"
            if custom_voice.exists():
                voice_path = str(custom_voice)
        
        # Priority 2: Global active voice (Persistent)
        if not voice_path and CURRENT_VOICE_ID:
             active_voice = VOICE_DIR / f"{CURRENT_VOICE_ID}.wav"
             if active_voice.exists():
                 voice_path = str(active_voice)

        # Priority 3: Fallback default
        if not voice_path and VOICE_REF.exists():
            voice_path = str(VOICE_REF)

        if not voice_path:
            raise HTTPException(500, "No valid voice profile found")

        requested_max_new_tokens = choose_tts_max_new_tokens(text)
        print(f"🔉 TTS token budget request={requested_max_new_tokens} chars={len(text)}")

        async with SYNTH_LOCK:
            # Keep generation serialized; chatterbox shared model state is not fully thread-safe.
            REQUEST_TTS_MAX_NEW_TOKENS = requested_max_new_tokens
            try:
                with tts_sdp_kernel_context():
                    audio = model.generate(
                        text=text,
                        audio_prompt_path=voice_path,
                        exaggeration=req.exaggeration,
                    )

                if audio is None:
                    # One explicit retry after conditionals re-prep for resilience.
                    model.prepare_conditionals(voice_path, exaggeration=req.exaggeration)
                    with tts_sdp_kernel_context():
                        audio = model.generate(
                            text=text,
                            audio_prompt_path=voice_path,
                            exaggeration=req.exaggeration,
                        )

                if audio is None:
                    raise RuntimeError("Chatterbox returned empty audio buffer")
            finally:
                REQUEST_TTS_MAX_NEW_TOKENS = None
        buf = io.BytesIO()
        sf.write(buf, audio.squeeze().cpu().numpy(), model.sr, format="WAV")
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/wav")
    except Exception as e:
        traceback.print_exc()
        print(f"❌ TTS Error: {e}")
        raise HTTPException(500, str(e))


def process_audio_upload(file_bytes, file_path, trim_start, trim_end, normalize):
    audio = AudioSegment.from_file(io.BytesIO(file_bytes))

    # Trim
    if trim_start > 0 or trim_end > 0:
        start_ms = int(trim_start * 1000)
        end_ms = int(trim_end * 1000) if trim_end > 0 else len(audio)
        audio = audio[start_ms:end_ms]

    # Normalize/Optimize
    if normalize:
        audio = audio.set_channels(1)  # Mono
        audio = audio.set_frame_rate(22050)  # Standard for TTS

    # Export
    audio.export(file_path, format="wav")
    return file_path.stem


@app.post("/voices/upload")
async def upload_voice(
    file: UploadFile = File(...),
    name: str = None,
    trim_start: float = 0,
    trim_end: float = 0,
    normalize: bool = True,
):
    try:
        filename = name if name else file.filename
        if not filename.endswith(".wav"):
            filename += ".wav"

        file_path = VOICE_DIR / filename

        # Read file (async)
        file_bytes = await file.read()

        # Process in threadpool (non-blocking)
        voice_id = await run_in_threadpool(
            process_audio_upload, file_bytes, file_path, trim_start, trim_end, normalize
        )

        return {"status": "success", "voice_id": voice_id}
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(500, f"Upload failed: {e}")


@app.get("/voices")
async def list_voices():
    voices = []
    if VOICE_DIR.exists():
        voices = [f.stem for f in VOICE_DIR.glob("*.wav")]
    return {"voices": voices, "default": CURRENT_VOICE_ID}


@app.post("/voices/select")
async def select_voice(voice_id: str):
    global CURRENT_VOICE_ID, CURRENT_CONDITIONED_VOICE_PATH
    path = VOICE_DIR / f"{voice_id}.wav"
    if not path.exists():
        raise HTTPException(404, "Voice not found")
    
    CURRENT_VOICE_ID = voice_id
    CURRENT_CONDITIONED_VOICE_PATH = None
    save_config() # Persist selection
    return {"status": "success", "active_voice": voice_id}


@app.post("/voices/{voice_id}/avatar")
async def upload_avatar(voice_id: str, file: UploadFile = File(...)):
    try:
        # Verify voice exists
        voice_path = VOICE_DIR / f"{voice_id}.wav"
        if not voice_path.exists():
            raise HTTPException(404, "Voice profile not found")

        # Process image
        img = Image.open(file.file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize/Crop to square
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
        raise HTTPException(404, "Avatar not found")

    return StreamingResponse(open(avatar_path, "rb"), media_type="image/jpeg")


@app.post("/voices/{voice_id}/rename")
async def rename_voice(voice_id: str, new_name: str):
    global CURRENT_VOICE_ID, CURRENT_CONDITIONED_VOICE_PATH
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
            
        # Update active voice if needed
        if CURRENT_VOICE_ID == voice_id:
            CURRENT_VOICE_ID = new_name
            CURRENT_CONDITIONED_VOICE_PATH = None
            save_config()

        return {"status": "success", "new_id": new_name}
    except Exception as e:
        raise HTTPException(500, f"Rename failed: {e}")


@app.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    global CURRENT_VOICE_ID, CURRENT_CONDITIONED_VOICE_PATH
    try:
        file_path = VOICE_DIR / f"{voice_id}.wav"
        if file_path.exists():
            os.remove(file_path)
            # Delete avatar too
            avatar_path = AVATAR_DIR / f"{voice_id}.jpg"
            if avatar_path.exists():
                os.remove(avatar_path)
            
            # Reset active voice if deleted
            if CURRENT_VOICE_ID == voice_id:
                CURRENT_VOICE_ID = "knight_voice"
                CURRENT_CONDITIONED_VOICE_PATH = None
                save_config()
                
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
        "active_voice": CURRENT_VOICE_ID
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8060)
