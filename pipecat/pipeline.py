"""KnightBot Pipecat Voice Pipeline with LiveKit - Faster Whisper STT + Chatterbox TTS"""

import asyncio
import time
import os
import sys
import json
from pathlib import Path


def _configure_stdio_safely() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


_configure_stdio_safely()

# Avoid local project folder shadowing the installed `pipecat` package.
# Put parent directory at the end so pip-installed pipecat is found first
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
# Remove the local KnightBot pipecat folder from path to avoid shadowing
sys.path = [p for p in sys.path if p not in ("", _PROJECT_ROOT, str(Path(__file__).parent))]
# Also make sure we can import from our local custom modules
sys.path.insert(0, str(Path(__file__).parent))  # pipecat/ subfolder

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.frames.frames import Frame, AudioRawFrame, TextFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.transports.services.livekit import LiveKitTransport, LiveKitParams

# Import Faster Whisper STT service for native Pipecat integration
# Try our custom implementation first, then fall back to HTTP
_faster_whisper_available = False
try:
    from pipecat.faster_whisper_stt import FasterWhisperSTT, create_faster_whisper_stt
    _faster_whisper_available = True
    print("✓ Custom Faster Whisper STT service available")
except ImportError as e:
    print(f"[warn] Custom FasterWhisperSTT not available: {e}")
    print("[warn] Will try HTTP fallback to STT services")

# Try to import Silero VAD
try:
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    _silero_import_error = None
except Exception as e:
    SileroVADAnalyzer = None
    _silero_import_error = e

# Import httpx for fallback HTTP STT
import httpx

# LiveKit Config
LIVEKIT_URL = os.getenv("KB_LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("KB_LIVEKIT_KEY", "devkey")
API_SECRET = os.getenv("KB_LIVEKIT_SECRET", "secret")

# Configuration
_TTS_COOLDOWN = float(os.getenv("KB_TTS_COOLDOWN_S", "0.15"))
_INTERRUPT_RMS_THRESHOLD = int(os.getenv("KB_INTERRUPT_RMS", "700"))
_TTS_CHUNK_MS = int(os.getenv("KB_TTS_CHUNK_MS", "40"))
_INTERRUPTION_MODE = os.getenv("KB_INTERRUPTION_MODE", "polite").strip().lower()
_INTERRUPT_MIN_MS = float(os.getenv("KB_INTERRUPT_MIN_MS", "300"))
_INTERRUPT_MIN_WORDS = int(os.getenv("KB_INTERRUPT_MIN_WORDS", "3"))
_INTERRUPT_PROBE_COOLDOWN_S = float(os.getenv("KB_INTERRUPT_PROBE_COOLDOWN_S", "0.35"))
_VOICE_METRICS_ENABLED = os.getenv("KB_VOICE_METRICS_ENABLED", "1") != "0"

# Faster Whisper Config
_FASTER_WHISPER_MODEL = os.getenv("KB_FASTER_WHISPER_MODEL", "large-v3")
_FASTER_WHISPER_DEVICE = os.getenv("KB_FASTER_WHISPER_DEVICE", "cuda")  # cuda or cpu

# Fallback STT Config (Parakeet)
_FALLBACK_STT_URL = os.getenv("KB_STT_URL", "http://localhost:8070/transcribe")

# Metrics tracking
_PROJECT_DIR = Path(__file__).resolve().parents[1]
_VOICE_METRICS_DIR = _PROJECT_DIR / "data" / "logs" / "voice_metrics"
if _VOICE_METRICS_ENABLED:
    _VOICE_METRICS_DIR.mkdir(parents=True, exist_ok=True)

_SESSION_ID = time.strftime("%Y%m%d-%H%M%S")
_TURN_COUNTER = 0
_CURRENT_TURN_ID = None
_TURN_METRICS = {}

# Bot speaking state
_bot_speaking = False
_last_tts_time = 0
_interrupt_requested = False


def _now() -> float:
    return time.perf_counter()


def _event(event_name: str, **kwargs):
    payload = {"event": event_name, **kwargs}
    print(f"[voice-metrics] {json.dumps(payload, ensure_ascii=False)}")


def _new_turn(user_text: str) -> int:
    global _TURN_COUNTER, _CURRENT_TURN_ID
    _TURN_COUNTER += 1
    turn_id = _TURN_COUNTER
    _CURRENT_TURN_ID = turn_id
    _TURN_METRICS[turn_id] = {
        "session_id": _SESSION_ID,
        "turn_id": turn_id,
        "user_text_preview": user_text[:200],
        "created_at": time.time(),
    }
    return turn_id


def _mark_turn(turn_id: int | None, key: str, value: float | str | int | bool | None = None):
    if not _VOICE_METRICS_ENABLED or turn_id is None:
        return
    if turn_id not in _TURN_METRICS:
        _TURN_METRICS[turn_id] = {"session_id": _SESSION_ID, "turn_id": turn_id}
    _TURN_METRICS[turn_id][key] = _now() if value is None else value


def _flush_turn(turn_id: int | None, status: str = "completed"):
    if not _VOICE_METRICS_ENABLED or turn_id is None:
        return
    m = _TURN_METRICS.get(turn_id)
    if not m:
        return

    m["status"] = status
    m["flushed_at"] = time.time()

    # Derive durations if timestamps exist.
    for a, b, out_key in [
        ("stt_start", "stt_end", "stt_s"),
        ("llm_start", "llm_end", "llm_s"),
        ("tts_start", "tts_end", "tts_s"),
        ("tts_start", "tts_first_audio", "first_audio_s"),
        ("stt_end", "tts_first_audio", "stt_to_first_audio_s"),
        ("llm_start", "tts_first_audio", "llm_to_first_audio_s"),
        ("interrupt_requested", "interrupt_committed", "barge_in_commit_s"),
    ]:
        if a in m and b in m:
            m[out_key] = round(float(m[b]) - float(m[a]), 4)

    out_path = _VOICE_METRICS_DIR / f"{_SESSION_ID}-turn-{turn_id:04d}.json"
    try:
        out_path.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[voice-metrics] failed writing turn metrics: {e}")

    _TURN_METRICS.pop(turn_id, None)


def _words(text: str) -> int:
    return len([w for w in text.strip().split() if w])


def _frame_duration_s(frame: AudioRawFrame) -> float:
    sample_rate = max(1, int(getattr(frame, "sample_rate", 16000) or 16000))
    num_channels = max(1, int(getattr(frame, "num_channels", 1) or 1))
    bytes_per_sample = 2
    return len(frame.audio) / float(sample_rate * num_channels * bytes_per_sample)


def audio_rms(pcm_bytes: bytes) -> int:
    try:
        import audioop
        return audioop.rms(pcm_bytes, 2)
    except Exception:
        return 0


def _interrupt_rms_threshold() -> int:
    mode = _INTERRUPTION_MODE
    if mode == "aggressive":
        return max(250, _INTERRUPT_RMS_THRESHOLD - 150)
    if mode == "polite":
        return _INTERRUPT_RMS_THRESHOLD + 150
    return _INTERRUPT_RMS_THRESHOLD


def _interrupt_min_speech_s() -> float:
    mode = _INTERRUPTION_MODE
    if mode == "aggressive":
        return max(0.08, _INTERRUPT_MIN_MS / 1000.0 * 0.6)
    if mode == "polite":
        return max(0.20, _INTERRUPT_MIN_MS / 1000.0 * 1.2)
    return max(0.12, _INTERRUPT_MIN_MS / 1000.0)


class FallbackSTTProcessor(FrameProcessor):
    """Fallback STT processor that uses HTTP to call Parakeet service.
    
    Used when Faster Whisper is not available.
    """
    def __init__(self):
        super().__init__()
        self.buffer = bytearray()
        self._stt_target_chunk = 32000  # ~1 second of 16kHz audio
        self._stt_max_buffer = self._stt_target_chunk * 4
        self._empty_stt_count = 0
        self._interrupt_speech_s = 0.0
        self._last_interrupt_probe = 0.0
        self.client = httpx.AsyncClient(timeout=30)

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        global _bot_speaking, _last_tts_time, _interrupt_requested

        # Barge-in detection while bot is speaking
        if isinstance(frame, AudioRawFrame) and _bot_speaking:
            rms = audio_rms(frame.audio)
            frame_s = _frame_duration_s(frame)
            threshold = _interrupt_rms_threshold()

            self.buffer.extend(frame.audio)
            if len(self.buffer) > (16000 * 3):
                del self.buffer[: len(self.buffer) - (16000 * 3)]

            if rms >= threshold:
                self._interrupt_speech_s += frame_s
            else:
                self._interrupt_speech_s = max(0.0, self._interrupt_speech_s - frame_s * 2.0)

            if _INTERRUPTION_MODE == "legacy" and rms >= _INTERRUPT_RMS_THRESHOLD:
                _interrupt_requested = True
                _bot_speaking = False
                _mark_turn(_CURRENT_TURN_ID, "interrupt_committed")
                _event("interrupt_committed", mode="legacy")
                self.buffer.clear()
                self._interrupt_speech_s = 0.0
                return

            if self._interrupt_speech_s >= _interrupt_min_speech_s():
                now = _now()
                if now - self._last_interrupt_probe >= _INTERRUPT_PROBE_COOLDOWN_S and len(self.buffer) >= 4096:
                    self._last_interrupt_probe = now
                    _mark_turn(_CURRENT_TURN_ID, "interrupt_requested")
                    text = await self._transcribe()
                    wc = _words(text)
                    should_commit = wc >= max(1, _INTERRUPT_MIN_WORDS) or _INTERRUPTION_MODE == "aggressive"
                    
                    if should_commit:
                        _interrupt_requested = True
                        _bot_speaking = False
                        _mark_turn(_CURRENT_TURN_ID, "interrupt_committed")
                        _mark_turn(_CURRENT_TURN_ID, "interrupt_text_preview", text[:120])
                        _event("interrupt_committed", mode=_INTERRUPTION_MODE, words=wc)
                        self.buffer.clear()
                        self._interrupt_speech_s = 0.0
            return

        # Cooldown after TTS
        if time.time() - _last_tts_time < _TTS_COOLDOWN:
            self.buffer.clear()
            return

        if isinstance(frame, AudioRawFrame):
            self.buffer.extend(frame.audio)
            if len(self.buffer) >= self._stt_target_chunk:
                stt_start = _now()
                text = await self._transcribe()
                stt_end = _now()
                
                if text and text.strip():
                    self._empty_stt_count = 0
                    turn_id = _new_turn(text)
                    _mark_turn(turn_id, "stt_start", stt_start)
                    _mark_turn(turn_id, "stt_end", stt_end)
                    _mark_turn(turn_id, "stt_text", text)
                    duration = stt_end - stt_start
                    print(f"🎤 STT: {text} ({duration:.3f}s)")
                    await self.push_frame(
                        TranscriptionFrame(text=text, user_id="user", timestamp=0)
                    )
                    self.buffer.clear()
                else:
                    self._empty_stt_count += 1
                    if len(self.buffer) >= self._stt_max_buffer or self._empty_stt_count >= 3:
                        self.buffer.clear()
                        self._empty_stt_count = 0
        else:
            await self.push_frame(frame, direction)

    async def _transcribe(self):
        """Transcribe using fallback HTTP to Parakeet service."""
        import struct
        hdr = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", len(self.buffer) + 36, b"WAVE", b"fmt ",
            16, 1, 1, 16000, 32000, 2, 16, b"data", len(self.buffer)
        )
        try:
            r = await self.client.post(
                _FALLBACK_STT_URL,
                files={"audio": ("a.wav", hdr + bytes(self.buffer), "audio/wav")},
            )
            return r.json().get("text", "") if r.status_code == 200 else ""
        except Exception as e:
            print(f"STT Error: {e}")
            return ""


class LLMProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.client = httpx.AsyncClient(timeout=120)
        self._llm_url = os.getenv("KB_LLM_URL", "http://localhost:8100/chat")

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            turn_id = _CURRENT_TURN_ID
            text = frame.text.strip()
            if len(text) < 2:
                return
            if turn_id is None or turn_id not in _TURN_METRICS:
                turn_id = _new_turn(text)
                _mark_turn(turn_id, "stt_text", text)
            print(f"🧠 LLM processing: {text}")
            try:
                _mark_turn(turn_id, "llm_start")
                start_time = time.time()
                r = await self.client.post(self._llm_url, json={"message": text})
                if r.status_code == 200:
                    payload = r.json()
                    resp = payload.get("text", "")
                    backend_metrics = payload.get("metrics") if isinstance(payload, dict) else None
                    if isinstance(backend_metrics, dict):
                        llm_mode = backend_metrics.get("llm_mode")
                        if llm_mode:
                            _mark_turn(turn_id, "llm_mode", str(llm_mode))
                        for k in ("llm_first_token_s", "llm_total_s"):
                            v = backend_metrics.get(k)
                            if v is None:
                                continue
                            try:
                                _mark_turn(turn_id, f"{k}_backend", round(float(v), 4))
                            except (TypeError, ValueError):
                                pass
                    _mark_turn(turn_id, "llm_end")
                    _mark_turn(turn_id, "assistant_text_preview", resp[:300])
                    duration = time.time() - start_time
                    print(f"🤖 Knight: {resp} ({duration:.3f}s)")
                    await self.push_frame(TextFrame(text=resp))
            except Exception as e:
                _mark_turn(turn_id, "llm_error", str(e))
                print(f"LLM Error: {e}")
                await self.push_frame(TextFrame(text=f"Error: {e}"))
        else:
            await self.push_frame(frame, direction)


class TTSProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.client = httpx.AsyncClient(timeout=60)
        self._tts_url = os.getenv("KB_TTS_URL", "http://localhost:8060/synthesize")

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame) and frame.text:
            global _bot_speaking, _last_tts_time, _interrupt_requested
            turn_id = _CURRENT_TURN_ID

            print("🔊 TTS synthesizing...")
            _interrupt_requested = False
            _bot_speaking = True
            _mark_turn(turn_id, "tts_start")
            first_audio_pushed = False

            try:
                start_time = time.time()
                r = await self.client.post(
                    self._tts_url,
                    json={"text": frame.text, "exaggeration": 0.5},
                )
                if r.status_code == 200:
                    # Skip WAV header (44 bytes)
                    audio_data = r.content[44:]
                    duration = time.time() - start_time
                    print(f"🔊 TTS Audio Ready ({len(audio_data)} bytes) ({duration:.3f}s)")

                    # Stream in realtime-sized chunks for barge-in
                    sample_rate = 22050
                    bytes_per_sample = 2
                    chunk_ms = _TTS_CHUNK_MS
                    chunk_size = int(sample_rate * (chunk_ms / 1000.0) * bytes_per_sample)

                    for i in range(0, len(audio_data), chunk_size):
                        if _interrupt_requested:
                            print("[barge-in] TTS playback interrupted")
                            _mark_turn(turn_id, "tts_interrupted", True)
                            _flush_turn(turn_id, status="interrupted")
                            break

                        chunk = audio_data[i : i + chunk_size]
                        if not first_audio_pushed:
                            _mark_turn(turn_id, "tts_first_audio")
                            first_audio_pushed = True
                        await self.push_frame(
                            AudioRawFrame(audio=chunk, sample_rate=sample_rate, num_channels=1)
                        )

                        chunk_duration_s = len(chunk) / float(sample_rate * bytes_per_sample)
                        await asyncio.sleep(max(0.0, chunk_duration_s * 0.9))
            except Exception as e:
                _mark_turn(turn_id, "tts_error", str(e))
                print(f"TTS Error: {e}")
            finally:
                _mark_turn(turn_id, "tts_end")
                _flush_turn(turn_id, status="completed")
                _bot_speaking = False
                _last_tts_time = time.time()
        else:
            await self.push_frame(frame, direction)


async def run_pipeline():
    global _bot_speaking, _interrupt_requested
    
    print("🚀 Starting KnightBot Pipecat Agent with Faster Whisper STT...")
    print(f"⚙️ Config: mode={_INTERRUPTION_MODE}, interrupt_rms={_INTERRUPT_RMS_THRESHOLD}")
    print(f"⚙️ STT: {'Faster Whisper ' + _FASTER_WHISPER_MODEL if _faster_whisper_available else 'Fallback HTTP (Parakeet)'}")
    print(f"⚙️ Metrics: {_VOICE_METRICS_ENABLED}")

    # Connect to LiveKit
    print(f"🔌 Connecting to LiveKit at {LIVEKIT_URL}...")
    from livekit import api

    grant = api.VideoGrants(
        room_join=True, room="knight-room", can_publish=True, can_subscribe=True
    )
    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_grants(grant)
        .with_identity("knight-bot")
        .with_name("KnightBot")
        .to_jwt()
    )

    # Setup VAD
    vad = None
    if SileroVADAnalyzer is not None:
        vad = SileroVADAnalyzer(
            sample_rate=16000,
            params=VADParams(confidence=0.6, start_silence_timeout=0.5),
        )
        print("✓ Silero VAD loaded")
    else:
        print(f"[warn] Silero VAD unavailable: {_silero_import_error}")

    livekit_params = {
        "audio_in_enabled": True,
        "audio_out_enabled": True,
        "vad_enabled": bool(vad),
    }
    if vad is not None:
        livekit_params["vad_analyzer"] = vad

    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=token,
        room_name="knight-room",
        params=LiveKitParams(**livekit_params),
    )

    # Build pipeline based on STT availability
    pipeline_components = [
        transport.input(),  # Get audio from LiveKit
        LLMProcessor(),     # Generate text
        TTSProcessor(),     # Synthesize audio
        transport.output(), # Send audio back to LiveKit
    ]

    if _faster_whisper_available:
        # Use native Faster Whisper STT service (our custom implementation)
        print(f"📦 Loading Faster Whisper model: {_FASTER_WHISPER_MODEL} on {_FASTER_WHISPER_DEVICE}")
        stt_service = create_faster_whisper_stt(
            model=_FASTER_WHISPER_MODEL,
            device=_FASTER_WHISPER_DEVICE,
        )
        # Insert STT service after transport input
        pipeline_components.insert(1, stt_service)
        print("✓ Pipeline: LiveKit → Faster Whisper → LLM → TTS → LiveKit")
    else:
        # Use fallback HTTP STT processor
        print("✓ Pipeline: LiveKit → FallbackSTT → LLM → TTS → LiveKit")
        pipeline_components.insert(1, FallbackSTTProcessor())

    # Create pipeline
    pipeline = Pipeline(pipeline_components)

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

    print("🎯 Starting pipeline... (Press Ctrl+C to stop)")
    from pipecat.pipeline.base_task import PipelineTaskParams
    await task.run(PipelineTaskParams(loop=asyncio.get_event_loop()))


if __name__ == "__main__":
    asyncio.run(run_pipeline())
