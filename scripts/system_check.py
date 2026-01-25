import httpx
import asyncio


async def check_services():
    print("🔍 Starting Full System Diagnostic...")

    services = {
        "Core": "http://localhost:8100",
        "TTS": "http://localhost:8060",
        "STT": "http://localhost:8070",
        "Frontend": "http://localhost:3000",
    }

    # 1. Health Checks
    print("\n--- Health Checks ---")
    all_healthy = True
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in services.items():
            try:
                # Frontend might not have /health, check root
                endpoint = "/health" if name != "Frontend" else "/"
                r = await client.get(f"{url}{endpoint}")
                if r.status_code == 200:
                    print(f"✅ {name}: UP ({url})")
                else:
                    print(f"❌ {name}: DOWN (Status {r.status_code})")
                    all_healthy = False
            except Exception as e:
                print(f"❌ {name}: DOWN (Connection failed: {e})")
                all_healthy = False

    if not all_healthy:
        print("\n⚠️  CRITICAL: Some services are down. Aborting functional tests.")
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

    print("\nDiagnostic Complete.")


if __name__ == "__main__":
    asyncio.run(check_services())
