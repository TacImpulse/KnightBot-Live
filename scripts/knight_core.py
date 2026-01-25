"""KnightBot Core API Server"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import httpx, os
from livekit import api

# Load env
from dotenv import load_dotenv

load_dotenv("F:/KnightBot/.env")
app = FastAPI(title="KnightBot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
CONFIG = {
    "lm_studio": os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
    "mem0": os.getenv("MEM0_URL", "http://localhost:8050"),
    "tts": os.getenv("TTS_URL", "http://localhost:8060"),
    "user_id": os.getenv("USER_ID", "knight_user"),
    "temperature": float(os.getenv("TEMPERATURE", "0.7")),
    "max_tokens": int(os.getenv("MAX_TOKENS", "4096")),
    "model_id": os.getenv(
        "MODEL_ID",
        "spatial-ssrl-qwen3vl-4b-i1",
    ),
    "vision_model_id": os.getenv(
        "VISION_MODEL_ID", "llama-joycaption-beta-one-hf-llava"
    ),
    "livekit_url": os.getenv("LIVEKIT_URL", "ws://localhost:7880"),
    "livekit_api_key": os.getenv("LIVEKIT_API_KEY", "devkey"),
    "livekit_api_secret": os.getenv("LIVEKIT_API_SECRET", "secret"),
}
SYSTEM_PROMPT = Path("F:/KnightBot/config/knight-prompt.md").read_text(encoding="utf-8")
conversation_history = []


class TokenRequest(BaseModel):
    room_name: str
    participant_name: str


@app.post("/token")
async def create_token(req: TokenRequest):
    grant = api.VideoGrants(room_join=True, room=req.room_name)
    token = (
        api.AccessToken(CONFIG["livekit_api_key"], CONFIG["livekit_api_secret"])
        .with_grants(grant)
        .with_identity(req.participant_name)
        .with_name(req.participant_name)
    )

    return {"token": token.to_jwt(), "url": CONFIG["livekit_url"]}


class ChatRequest(BaseModel):
    message: str
    include_audio: bool = False
    voice_id: str | None = None
    system_prompt: str | None = None
    images: list[str] | None = None  # List of base64 strings


async def recall_memories(query: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{CONFIG['mem0']}/v1/memories/search",
                json={"query": query, "user_id": CONFIG["user_id"], "limit": 5},
            )
            return r.json().get("results", []) if r.status_code == 200 else []
    except:
        return []


async def store_memory(content: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{CONFIG['mem0']}/v1/memories",
                json={
                    "messages": [{"role": "assistant", "content": content}],
                    "user_id": CONFIG["user_id"],
                },
            )
    except Exception:
        pass


@app.post("/chat")
async def chat(req: ChatRequest):
    global conversation_history
    print(
        f"📩 Incoming request: msg='{req.message[:50]}...' images={len(req.images) if req.images else 0}"
    )

    memories = await recall_memories(req.message)

    current_system_prompt = req.system_prompt or SYSTEM_PROMPT
    messages = [{"role": "system", "content": current_system_prompt}]

    if memories:
        mem_text = "\n".join([f"- {m.get('memory', '')}" for m in memories])
        messages.append(
            {"role": "system", "content": f"Relevant memories:\n{mem_text}"}
        )

    messages.extend(conversation_history[-20:])

    # Handle Multimodal Content
    if req.images:
        print(f"📸 Received {len(req.images)} images. Switching to vision model.")
        user_content = [{"type": "text", "text": req.message}]
        for img_b64 in req.images:
            # Check if it has a prefix, if not add it (LM Studio sometimes needs it, sometimes doesn't)
            # But the error "must be a base64 encoded image" from some endpoints means they want PURE base64.
            # However, OpenAI spec wants data URI.
            # Let's try to ensure it is a data URI first.
            if not img_b64.startswith("data:"):
                # Assume png if not specified (safest bet for now)
                img_url = f"data:image/png;base64,{img_b64}"
            else:
                img_url = img_b64

            # DEBUG: Log the first 50 chars of the image string
            print(f"🖼️ Image URL (first 50 chars): {img_url[:50]}")

            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": img_url},
                }
            )
        # Vision models often don't support system messages or history well, so we simplify
        messages = [{"role": "user", "content": user_content}]
        # For the spatial model, we should probably stick to the vision model ID or the spatial one if it supports vision
        # The user switched MODEL_ID to spatial-ssrl-qwen3vl-4b-i1.
        # If that model supports vision, we should use it.
        # But VISION_MODEL_ID is hardcoded to llama-joycaption...
        # Let's use the current MODEL_ID if it looks like a VL model, otherwise fallback.
        if "vl" in CONFIG["model_id"].lower():
            model_to_use = CONFIG["model_id"]
        else:
            model_to_use = CONFIG["vision_model_id"]
    else:
        messages.append({"role": "user", "content": req.message})
        model_to_use = CONFIG["model_id"]

    print(f"🤖 Using model: {model_to_use}")

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(
                f"{CONFIG['lm_studio']}/chat/completions",
                json={
                    "model": model_to_use,
                    "messages": messages,
                    "temperature": CONFIG["temperature"],
                    "max_tokens": CONFIG["max_tokens"],
                },
            )
            if r.status_code != 200:
                print(f"❌ LM Studio Error: {r.status_code} - {r.text}")
                raise Exception(r.text)
            response_text = r.json()["choices"][0]["message"]["content"]

        conversation_history.append({"role": "user", "content": req.message})
        conversation_history.append({"role": "assistant", "content": response_text})
        await store_memory(f"User: {req.message[:100]}. Knight: {response_text[:200]}")

        return {"text": response_text, "memories_used": len(memories)}
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"🔥 Server Error: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/config")
async def get_config():
    return {
        "system_prompt": SYSTEM_PROMPT,
        "temperature": CONFIG["temperature"],
        "max_tokens": CONFIG["max_tokens"],
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    import logging

    # Suppress health check logs
    class HealthCheckFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return record.getMessage().find("GET /health") == -1

    logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())

    uvicorn.run(app, host="0.0.0.0", port=8100)
