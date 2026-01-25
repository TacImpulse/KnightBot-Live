"""KnightBot Pipecat Voice Pipeline with LiveKit"""

import asyncio
import httpx
import struct
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.frames.frames import Frame, AudioRawFrame, TextFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.transports.services.livekit import LiveKitTransport, LiveKitParams

# LiveKit Config
LIVEKIT_URL = "ws://localhost:7880"
API_KEY = "devkey"
API_SECRET = "secret"


class STTProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.buffer = bytearray()

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, AudioRawFrame):
            self.buffer.extend(frame.audio)
            # 32000 bytes = 1 second at 16khz 16bit mono
            if len(self.buffer) >= 32000:
                text = await self._transcribe()
                if text:
                    print(f"🎤 STT: {text}")
                    await self.push_frame(
                        TranscriptionFrame(text=text, user_id="user", timestamp=0)
                    )
                self.buffer.clear()
        else:
            await self.push_frame(frame, direction)

    async def _transcribe(self):
        hdr = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            len(self.buffer) + 36,
            b"WAVE",
            b"fmt ",
            16,
            1,
            1,
            16000,
            32000,
            2,
            16,
            b"data",
            len(self.buffer),
        )
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    "http://localhost:8070/transcribe",
                    files={"audio": ("a.wav", hdr + bytes(self.buffer), "audio/wav")},
                )
                return r.json().get("text", "") if r.status_code == 200 else ""
        except Exception as e:
            print(f"STT Error: {e}")
            return ""


class LLMProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            print(f"🧠 LLM processing: {frame.text}")
            try:
                async with httpx.AsyncClient(timeout=120) as c:
                    r = await c.post(
                        "http://localhost:8100/chat", json={"message": frame.text}
                    )
                    if r.status_code == 200:
                        resp = r.json().get("text", "")
                        print(f"🤖 Knight: {resp}")
                        await self.push_frame(TextFrame(text=resp))
            except Exception as e:
                print(f"LLM Error: {e}")
                await self.push_frame(TextFrame(text=f"[sigh] Error: {e}"))
        else:
            await self.push_frame(frame, direction)


class TTSProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame) and frame.text:
            print("🔊 TTS synthesizing...")
            try:
                async with httpx.AsyncClient(timeout=60) as c:
                    r = await c.post(
                        "http://localhost:8060/synthesize",
                        json={"text": frame.text, "exaggeration": 0.5},
                    )
                    if r.status_code == 200:
                        # Skip WAV header (44 bytes)
                        audio_data = r.content[44:]
                        # Chatterbox output is 22050Hz, LiveKit usually wants 16k or 24k or 48k.
                        # Pipecat might resample if configured, or we might need to resample.
                        # For now, let's send it and see if LiveKit handles it or if we sound like a chipmunk.
                        # NOTE: LiveKitTransport defaults to input/output sample rate of 16000 or 24000 usually.
                        # We might need to resample here if pitch is off.
                        await self.push_frame(
                            AudioRawFrame(
                                audio=audio_data, sample_rate=22050, num_channels=1
                            )
                        )
            except Exception as e:
                print(f"TTS Error: {e}")
        else:
            await self.push_frame(frame, direction)


async def run_pipeline():
    print("🚀 Starting KnightBot Pipecat Agent...")

    print("🔌 Connecting to LiveKit room 'knight-room'...")
    # Helper to generate token for the bot itself
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

    vad = SileroVADAnalyzer(sample_rate=16000, params=VADParams(confidence=0.5))

    transport = LiveKitTransport(
        url=LIVEKIT_URL,
        token=token,
        room_name="knight-room",
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=vad,
        ),
    )

    # Pipeline: Transport Input -> STT -> LLM -> TTS -> Transport Output
    pipeline = Pipeline(
        [
            transport.input(),  # Get audio from LiveKit
            STTProcessor(),  # Transcribe
            LLMProcessor(),  # Generate text
            TTSProcessor(),  # Synthesize audio
            transport.output(),  # Send audio back to LiveKit
        ]
    )

    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))

    await task.run()


if __name__ == "__main__":
    asyncio.run(run_pipeline())
