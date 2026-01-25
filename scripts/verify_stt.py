import httpx
import asyncio
import os

async def verify_stt():
    print("🎤 Testing STT Transcription...")
    
    # Use the voice file we just downloaded as a test sample
    test_file = r"F:\KnightBot\data\voices\knight_voice.wav"
    
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {'audio': ('test.wav', open(test_file, 'rb'), 'audio/wav')}
            r = await client.post("http://localhost:8070/transcribe", files=files)
            
            if r.status_code == 200:
                result = r.json()
                print(f"✅ STT Success! Transcription: '{result.get('text')}'")
            else:
                print(f"❌ STT Failed: {r.status_code} - {r.text}")
                
    except Exception as e:
        print(f"❌ STT Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_stt())
