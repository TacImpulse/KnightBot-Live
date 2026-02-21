import asyncio
import mimetypes
from pathlib import Path
import shutil

import httpx


def _pick_sample_audio() -> Path | None:
    """Prefer known local samples for STT -> Core -> TTS round-trip checks."""
    candidates = [
        Path("data/stt_test.webm"),
        Path("data/voices/knight_voice.wav"),
    ]
    for path in candidates:
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            return path
    return None


async def _run_voice_roundtrip_test(client: httpx.AsyncClient, audio_path: Path) -> bool:
    """Run STT -> Core chat -> TTS and validate each leg."""
    print("Testing End-to-End Voice Round-Trip (STT -> Core -> TTS)...")
    print(f"Using sample audio: {audio_path}")

    mime_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"

    # 1) STT
    with audio_path.open("rb") as f:
        stt = await client.post(
            "http://localhost:8070/transcribe",
            files={"audio": (audio_path.name, f, mime_type)},
        )

    if stt.status_code != 200:
        print(f"❌ Round-trip STT failed: {stt.status_code} - {stt.text[:200]}")
        return False

    stt_json = stt.json()
    transcript = (stt_json.get("text") or "").strip()
    if not transcript:
        print(f"⚠️  Round-trip STT returned empty transcription for sample file: {stt_json}")
        print("   Falling back to generated TTS probe audio for STT validation...")

        probe_text = "KnightBot STT fallback probe phrase alpha bravo charlie"
        probe_tts = await client.post(
            "http://localhost:8060/synthesize",
            json={"text": probe_text, "exaggeration": 0.5},
        )
        if probe_tts.status_code != 200 or len(probe_tts.content) < 1000:
            print(
                "❌ Round-trip fallback probe failed to synthesize audio "
                f"(status={probe_tts.status_code}, bytes={len(probe_tts.content)})"
            )
            return False

        probe_path = Path("data/uploads/stt_probe.wav")
        probe_path.parent.mkdir(parents=True, exist_ok=True)
        probe_path.write_bytes(probe_tts.content)

        with probe_path.open("rb") as f:
            probe_stt = await client.post(
                "http://localhost:8070/transcribe",
                files={"audio": (probe_path.name, f, "audio/wav")},
            )

        if probe_stt.status_code != 200:
            print(
                f"❌ Round-trip fallback STT probe failed: "
                f"{probe_stt.status_code} - {probe_stt.text[:200]}"
            )
            return False

        probe_json = probe_stt.json()
        transcript = (probe_json.get("text") or "").strip()
        if not transcript:
            print(f"❌ Round-trip fallback STT probe still empty: {probe_json}")
            return False

        print(f"✅ Round-trip fallback STT transcript: {transcript[:80]!r}")

    print(f"✅ Round-trip STT transcript: {transcript[:80]!r}")

    # 2) Core chat
    chat = await client.post("http://localhost:8100/chat", json={"message": transcript})
    if chat.status_code != 200:
        print(f"❌ Round-trip Core chat failed: {chat.status_code} - {chat.text[:200]}")
        return False

    chat_json = chat.json()
    reply = (chat_json.get("text") or chat_json.get("response") or "").strip()
    if not reply:
        print(f"❌ Round-trip Core chat returned empty text: {chat_json}")
        return False

    print(f"✅ Round-trip Core reply: {reply[:80]!r}")

    # 3) TTS
    tts = await client.post(
        "http://localhost:8060/synthesize",
        json={"text": reply[:300], "exaggeration": 0.5},
    )
    if tts.status_code != 200:
        print(f"❌ Round-trip TTS failed: {tts.status_code} - {tts.text[:200]}")
        return False

    if len(tts.content) < 1000:
        print(f"❌ Round-trip TTS returned too little audio data: {len(tts.content)} bytes")
        return False

    print(f"✅ Round-trip TTS generated {len(tts.content)} bytes")
    print("✅ End-to-end voice round-trip passed")
    return True


async def check_services():
    print("🔍 Starting Full System Diagnostic...")

    stt_required = shutil.which("ffmpeg") is not None

    services = {
        "Core": {"url": "http://localhost:8100", "endpoint": "/health", "required": True},
        "TTS": {"url": "http://localhost:8060", "endpoint": "/health", "required": True},
        "STT": {"url": "http://localhost:8070", "endpoint": "/health", "required": stt_required},
        "Frontend": {"url": "http://localhost:3000", "endpoint": "/", "required": True},
    }

    # 1. Health Checks
    print("\n--- Health Checks ---")
    all_healthy = True
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, meta in services.items():
            url = meta["url"]
            endpoint = meta["endpoint"]
            required = meta["required"]
            try:
                r = await client.get(f"{url}{endpoint}")
                if r.status_code == 200:
                    print(f"✅ {name}: UP ({url})")
                else:
                    label = "DOWN" if required else "DOWN (optional)"
                    print(f"❌ {name}: {label} (Status {r.status_code})")
                    if required:
                        all_healthy = False
            except Exception as e:
                label = "DOWN" if required else "DOWN (optional)"
                print(f"❌ {name}: {label} (Connection failed: {e})")
                if required:
                    all_healthy = False

    if not all_healthy:
        print("\n⚠️  CRITICAL: One or more REQUIRED services are down. Aborting functional tests.")
        return

    # 2. Functional Tests
    print("\n--- Functional Tests ---")

    # Test Core Chat
    print("Testing Core Chat (LLM)...")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                "http://localhost:8100/chat", json={"message": "Say 'Test Successful'"}
            )
            if r.status_code == 200:
                print(f"✅ Core Chat Response: {r.json()['text'][:50]}...")
            else:
                print(f"❌ Core Chat Failed: {r.text}")
    except Exception as e:
        print(f"❌ Core Chat Error: {e}")

    # Test TTS
    print("Testing TTS (Voice)...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "http://localhost:8060/synthesize",
                json={"text": "System check complete."},
            )
            if r.status_code == 200 and len(r.content) > 1000:
                print(f"✅ TTS Generated {len(r.content)} bytes of audio")
            else:
                print(f"❌ TTS Failed: Status {r.status_code}")
    except Exception as e:
        print(f"❌ TTS Error: {e}")

    # Test STT (optional)
    if stt_required:
        print("Testing STT (Speech-to-text)...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("http://localhost:8070/health")
                if r.status_code == 200:
                    print("✅ STT Health OK")
                else:
                    print(f"❌ STT Health Failed: Status {r.status_code}")
        except Exception as e:
            print(f"❌ STT Error: {e}")
    else:
        print("Skipping STT test (ffmpeg not found in PATH; STT is optional in this environment).")

    # Test end-to-end voice round-trip
    if stt_required:
        sample_audio = _pick_sample_audio()
        if sample_audio is None:
            print(
                "⚠️  Skipping round-trip test (no sample audio found at data/stt_test.webm "
                "or data/voices/knight_voice.wav)."
            )
        else:
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    await _run_voice_roundtrip_test(client, sample_audio)
            except Exception as e:
                print(f"❌ Round-trip test error: {e}")

    print("\nDiagnostic Complete.")


if __name__ == "__main__":
    asyncio.run(check_services())
