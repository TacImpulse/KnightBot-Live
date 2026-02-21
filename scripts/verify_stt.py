import httpx
import asyncio
import os
from pathlib import Path


def _pick_sample_file() -> Path | None:
    candidates = [
        Path("data/stt_test.webm"),
        Path("data/voices/knight_voice.wav"),
        Path("data/uploads/stt_probe.wav"),
    ]
    for path in candidates:
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".wav":
        return "audio/wav"
    if ext == ".webm":
        return "audio/webm"
    return "application/octet-stream"

async def verify_stt():
    print("🎤 Testing STT Transcription...")

    test_file = _pick_sample_file()
    if test_file is None:
        print("❌ No test file found. Expected one of:")
        print("   - data/stt_test.webm")
        print("   - data/voices/knight_voice.wav")
        print("   - data/uploads/stt_probe.wav")
        return

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            mime = _guess_mime(test_file)
            print(f"Using sample: {test_file} ({mime})")

            with test_file.open("rb") as f:
                files = {"audio": (test_file.name, f, mime)}
                r = await client.post("http://localhost:8070/transcribe", files=files)

            if r.status_code == 200:
                result = r.json()
                text = (result.get("text") or "").strip()
                if text:
                    print(f"✅ STT Success! Transcription: '{text}'")
                    return

                print("⚠️ STT returned empty transcript for sample file. Probing with generated TTS audio...")

                probe_text = "KnightBot STT probe phrase alpha bravo charlie"
                tts = await client.post(
                    "http://localhost:8060/synthesize",
                    json={"text": probe_text, "exaggeration": 0.5},
                )
                if tts.status_code != 200 or len(tts.content) < 1000:
                    print(f"❌ Could not generate STT probe audio from TTS (status={tts.status_code}, bytes={len(tts.content)})")
                    return

                probe_path = Path("data/uploads/stt_probe.wav")
                probe_path.parent.mkdir(parents=True, exist_ok=True)
                probe_path.write_bytes(tts.content)

                with probe_path.open("rb") as f2:
                    probe_files = {"audio": (probe_path.name, f2, "audio/wav")}
                    r2 = await client.post("http://localhost:8070/transcribe", files=probe_files)

                if r2.status_code != 200:
                    print(f"❌ STT probe failed: {r2.status_code} - {r2.text}")
                    return

                probe_result = r2.json()
                probe_transcript = (probe_result.get("text") or "").strip()
                if probe_transcript:
                    print(f"✅ STT Probe Success! Transcription: '{probe_transcript}'")
                else:
                    print(f"❌ STT probe transcript still empty: {probe_result}")
            else:
                print(f"❌ STT Failed: {r.status_code} - {r.text}")
                
    except Exception as e:
        print(f"❌ STT Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_stt())
