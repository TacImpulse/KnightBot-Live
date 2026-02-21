"""KnightBot Core API Server"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import httpx, os, json, time, asyncio, re
import sqlite3
from typing import List, Dict, Any
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
    "lm_studio": os.getenv("LM_STUDIO_URL", "http://192.168.68.111:1234/v1"),
    "mem0": os.getenv("MEM0_URL", "http://localhost:8050"),
    "tts": os.getenv("TTS_URL", "http://localhost:8060"),
    "user_id": os.getenv("USER_ID", "knight_user"),
    "temperature": float(os.getenv("TEMPERATURE", "0.7")),
    "max_tokens": int(os.getenv("MAX_TOKENS", "4096")),
    "voice_max_tokens": int(os.getenv("VOICE_MAX_TOKENS", "260")),
    "voice_max_words": int(os.getenv("VOICE_MAX_WORDS", "70")),
    "voice_max_sentences": int(os.getenv("VOICE_MAX_SENTENCES", "4")),
    "voice_reply_style": os.getenv(
        "VOICE_REPLY_STYLE",
        "Voice mode: reply in 2-4 natural sentences, avoid markdown symbols, and stay concise unless the user asks for detail.",
    ),
    "voice_dynamic_profiles": os.getenv("VOICE_DYNAMIC_PROFILES", "1").strip().lower()
    in {"1", "true", "yes", "on"},
    "voice_explicit_profile_strict": os.getenv(
        "VOICE_EXPLICIT_PROFILE_STRICT", "1"
    ).strip().lower()
    in {"1", "true", "yes", "on"},
    "voice_latency_target_s": float(os.getenv("VOICE_LATENCY_TARGET_S", "8.0")),
    "voice_latency_critical_s": float(os.getenv("VOICE_LATENCY_CRITICAL_S", "14.0")),
    "voice_latency_fast_s": float(os.getenv("VOICE_LATENCY_FAST_S", "4.0")),
    "voice_latency_ema_alpha": float(os.getenv("VOICE_LATENCY_EMA_ALPHA", "0.35")),
    "max_history_messages": int(os.getenv("MAX_HISTORY_MESSAGES", "6")),
    "model_id": os.getenv(
        "MODEL_ID",
        "spatial-ssrl-qwen3vl-4b-i1",
    ),
    "voice_model_id": os.getenv(
        "VOICE_MODEL_ID",
        os.getenv("MODEL_ID", "spatial-ssrl-qwen3vl-4b-i1"),
    ),
    "vision_model_id": os.getenv(
        "VISION_MODEL_ID", "llama-joycaption-beta-one-hf-llava"
    ),
    "livekit_url": os.getenv("LIVEKIT_URL", "ws://localhost:7880"),
    "livekit_api_key": os.getenv("LIVEKIT_API_KEY", "devkey"),
    "livekit_api_secret": os.getenv("LIVEKIT_API_SECRET", "secret"),
}
CONFIG["lm_studio"] = (CONFIG["lm_studio"] or "http://192.168.68.111:1234/v1").strip().rstrip("/")
SYSTEM_PROMPT = Path("F:/KnightBot/config/knight-prompt.md").read_text(encoding="utf-8")
conversation_history = []
LOCAL_MEMORY_DB = Path("F:/KnightBot/data/memory/knight_memory.db")
VOICE_PROFILE_ORDER = ["brief", "chat", "story", "story_max"]

# OpenMemory/Mem0 sometimes requires the user_id to be "initialized" via the MCP SSE endpoint
# before the REST API will accept memory operations. We cache a best-effort init flag.
_MEM0_USER_READY = False
VOICE_RUNTIME: Dict[str, Any] = {
    "llm_total_s_ema": None,
    "last_llm_total_s": None,
    "last_llm_first_token_s": None,
    "samples": 0,
    "last_profile": "chat",
}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def build_voice_profiles() -> Dict[str, Dict[str, Any]]:
    base_temp = float(CONFIG["temperature"])
    base_tokens = int(CONFIG["voice_max_tokens"])
    base_words = int(CONFIG["voice_max_words"])
    base_sentences = int(CONFIG["voice_max_sentences"])
    base_style = str(CONFIG["voice_reply_style"])

    return {
        "brief": {
            "max_tokens": _env_int("VOICE_PROFILE_BRIEF_TOKENS", 120),
            "max_words": _env_int("VOICE_PROFILE_BRIEF_WORDS", 36),
            "max_sentences": _env_int("VOICE_PROFILE_BRIEF_SENTENCES", 2),
            "temperature": _env_float("VOICE_PROFILE_BRIEF_TEMP", max(base_temp - 0.1, 0.2)),
            "style_prompt": os.getenv(
                "VOICE_PROFILE_BRIEF_STYLE",
                "Voice mode (brief): answer in 1-2 concise sentences, no markdown symbols.",
            ),
        },
        "chat": {
            "max_tokens": base_tokens,
            "max_words": base_words,
            "max_sentences": base_sentences,
            "temperature": _env_float("VOICE_PROFILE_CHAT_TEMP", base_temp),
            "style_prompt": base_style,
        },
        "story": {
            "max_tokens": _env_int("VOICE_PROFILE_STORY_TOKENS", 520),
            "max_words": _env_int("VOICE_PROFILE_STORY_WORDS", 160),
            "max_sentences": _env_int("VOICE_PROFILE_STORY_SENTENCES", 7),
            "temperature": _env_float("VOICE_PROFILE_STORY_TEMP", min(base_temp + 0.08, 1.2)),
            "style_prompt": os.getenv(
                "VOICE_PROFILE_STORY_STYLE",
                "Voice mode (story): reply with a rich, immersive narrative in 4-7 sentences. Keep it spoken, vivid, and markdown-free.",
            ),
        },
        "story_max": {
            "max_tokens": _env_int("VOICE_PROFILE_STORY_MAX_TOKENS", 900),
            "max_words": _env_int("VOICE_PROFILE_STORY_MAX_WORDS", 280),
            "max_sentences": _env_int("VOICE_PROFILE_STORY_MAX_SENTENCES", 12),
            "temperature": _env_float("VOICE_PROFILE_STORY_MAX_TEMP", min(base_temp + 0.12, 1.25)),
            "style_prompt": os.getenv(
                "VOICE_PROFILE_STORY_MAX_STYLE",
                "Voice mode (story max): deliver an extended, highly detailed narrative in 8-12 sentences. Keep it natural speech and avoid markdown symbols.",
            ),
        },
    }


VOICE_PROFILES = build_voice_profiles()


def normalize_voice_profile(value: str | None) -> str | None:
    if not value:
        return None
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "normal": "chat",
        "default": "chat",
        "long": "story",
        "longform": "story",
        "rich": "story",
        "detailed": "story",
        "max": "story_max",
        "longest": "story_max",
        "full": "story_max",
        "fullsend": "story_max",
    }
    key = aliases.get(key, key)
    return key if key in VOICE_PROFILES else None


def shift_voice_profile(profile: str, delta: int) -> str:
    if profile not in VOICE_PROFILE_ORDER:
        profile = "chat"
    idx = VOICE_PROFILE_ORDER.index(profile)
    new_idx = max(0, min(len(VOICE_PROFILE_ORDER) - 1, idx + delta))
    return VOICE_PROFILE_ORDER[new_idx]


def infer_voice_profile_from_message(message: str) -> tuple[str, bool, bool, str]:
    text = (message or "").strip().lower()
    if not text:
        return "chat", False, False, "default chat profile"

    story_max_pattern = re.compile(
        r"\b(story max|max story|full story|go long|go longer|long-form|long form|very detailed|maximum detail|max detail)\b"
    )
    brief_pattern = re.compile(r"\b(brief|short|concise|quick|tl;dr|tldr|one sentence)\b")
    story_pattern = re.compile(
        r"\b(story|narrative|scene|chapter|roleplay|role-play|fantasy|nsfw|erotic|sensual|describe in detail)\b"
    )

    if story_max_pattern.search(text):
        return "story_max", True, True, "message requests maximum detail/length"
    if brief_pattern.search(text):
        return "brief", True, False, "message requests brevity"
    if story_pattern.search(text):
        return "story", False, True, "message indicates narrative/detail intent"
    return "chat", False, False, "default chat profile"


def select_voice_profile(message: str, requested_profile: str | None) -> tuple[str, Dict[str, Any], Dict[str, Any]]:
    requested = normalize_voice_profile(requested_profile)
    explicit_requested = requested is not None
    if requested:
        base_profile = requested
        forced = True
        story_intent = requested in {"story", "story_max"}
        reason = f"explicit voice_profile='{requested}'"
    else:
        base_profile, forced, story_intent, reason = infer_voice_profile_from_message(message)

    selected = base_profile
    latency_ema = VOICE_RUNTIME.get("llm_total_s_ema")

    apply_latency_adjustments = (
        CONFIG.get("voice_dynamic_profiles", True)
        and isinstance(latency_ema, (int, float))
        and not (
            explicit_requested and CONFIG.get("voice_explicit_profile_strict", True)
        )
    )
    if apply_latency_adjustments:
        latency_ema = float(latency_ema)
        target = float(CONFIG.get("voice_latency_target_s", 8.0))
        critical = float(CONFIG.get("voice_latency_critical_s", 14.0))
        fast = float(CONFIG.get("voice_latency_fast_s", 4.0))

        if latency_ema >= critical:
            selected = shift_voice_profile(base_profile, -1 if forced else -2)
            reason += f"; downgraded for critical latency ema={latency_ema:.2f}s"
        elif latency_ema >= target:
            selected = shift_voice_profile(base_profile, -1)
            reason += f"; downgraded for elevated latency ema={latency_ema:.2f}s"
        elif (not forced) and story_intent and latency_ema <= fast:
            selected = shift_voice_profile(base_profile, +1)
            if selected != base_profile:
                reason += f"; upgraded for fast latency ema={latency_ema:.2f}s"
    elif explicit_requested and CONFIG.get("voice_explicit_profile_strict", True):
        reason += "; explicit profile honored"

    profile_cfg = dict(VOICE_PROFILES.get(selected, VOICE_PROFILES["chat"]))
    meta = {
        "requested": base_profile,
        "selected": selected,
        "forced": forced,
        "reason": reason,
        "latency_ema_s": latency_ema,
    }
    return selected, profile_cfg, meta


def update_voice_runtime_from_metrics(metrics: Dict[str, Any], selected_profile: str) -> None:
    llm_total = metrics.get("llm_total_s")
    llm_first = metrics.get("llm_first_token_s")

    if isinstance(llm_total, (int, float)) and llm_total > 0:
        alpha = float(CONFIG.get("voice_latency_ema_alpha", 0.35))
        alpha = max(0.05, min(0.9, alpha))
        prev = VOICE_RUNTIME.get("llm_total_s_ema")
        if isinstance(prev, (int, float)) and prev > 0:
            ema = (alpha * float(llm_total)) + ((1.0 - alpha) * float(prev))
        else:
            ema = float(llm_total)
        VOICE_RUNTIME["llm_total_s_ema"] = round(ema, 4)
        VOICE_RUNTIME["last_llm_total_s"] = round(float(llm_total), 4)
        VOICE_RUNTIME["samples"] = int(VOICE_RUNTIME.get("samples", 0)) + 1

    if isinstance(llm_first, (int, float)) and llm_first > 0:
        VOICE_RUNTIME["last_llm_first_token_s"] = round(float(llm_first), 4)

    VOICE_RUNTIME["last_profile"] = selected_profile


def compact_voice_reply(text: str, max_words: int, max_sentences: int) -> str:
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return ""

    candidate = normalized
    if max_sentences > 0:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]
        if sentences:
            candidate = " ".join(sentences[:max_sentences])

    words = candidate.split()
    if len(words) > max_words > 0:
        candidate = " ".join(words[:max_words]).rstrip(",;:-")

    if candidate and candidate[-1] not in ".!?":
        candidate += "."
    return candidate


async def warmup_lm_model() -> None:
    """Best-effort background warmup to reduce first-turn latency after restart."""
    if os.getenv("KB_LLM_WARMUP", "1") != "1":
        return

    try:
        model_ids = [CONFIG["voice_model_id"]]
        if (
            os.getenv("KB_WARM_MAIN_MODEL", "0") == "1"
            and CONFIG["model_id"] not in model_ids
        ):
            model_ids.append(CONFIG["model_id"])

        async with httpx.AsyncClient(timeout=120.0) as client:
            for model_id in model_ids:
                started = time.perf_counter()
                await run_lm_studio_chat(
                    client,
                    model=model_id,
                    messages=[{"role": "user", "content": "Reply with one word: ready."}],
                    temperature=0.1,
                    max_tokens=16,
                )
                elapsed = round(time.perf_counter() - started, 3)
                print(f"[warmup] LM model '{model_id}' ready in {elapsed}s")
    except Exception as e:
        print(f"[warmup] skipped/failed: {e}")


async def ensure_mem0_user_ready() -> None:
    """Best-effort init of the Mem0/OpenMemory user.

    The openmemory-mcp container exposes an SSE endpoint at:
      /mcp/{client_name}/sse/{user_id}

    In some versions, REST memory endpoints return 404 {"detail":"User not found"}
    until this endpoint has been hit at least once.
    """

    global _MEM0_USER_READY
    if _MEM0_USER_READY:
        return

    user_id = CONFIG.get("user_id")
    mem0_base = CONFIG.get("mem0")
    if not user_id or not mem0_base:
        return

    sse_url = f"{mem0_base}/mcp/knightbot/sse/{user_id}"
    try:
        timeout = httpx.Timeout(3.0, connect=2.0, read=1.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("GET", sse_url) as r:
                # Any 2xx is enough to consider the user initialized.
                if 200 <= r.status_code < 300:
                    # Read a small chunk then close.
                    async for _ in r.aiter_text():
                        break
                    _MEM0_USER_READY = True
    except Exception:
        # Non-fatal. Knight Core has a local sqlite fallback.
        return


def init_local_memory_db() -> None:
    LOCAL_MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(LOCAL_MEMORY_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'local',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def local_store_memory(content: str) -> None:
    try:
        init_local_memory_db()
        with sqlite3.connect(LOCAL_MEMORY_DB) as conn:
            conn.execute(
                "INSERT INTO memories (user_id, content, source, created_at) VALUES (?, ?, ?, ?)",
                (CONFIG["user_id"], content, "local", datetime.now().isoformat()),
            )
            conn.commit()
    except Exception as e:
        print(f"[warn] Local memory store failed: {e}")


def local_recall_memories(query: str, limit: int = 3) -> List[Dict[str, str]]:
    try:
        init_local_memory_db()
        terms = [t.strip() for t in query.split() if t.strip()]
        with sqlite3.connect(LOCAL_MEMORY_DB) as conn:
            conn.row_factory = sqlite3.Row
            if terms:
                where = " OR ".join(["LOWER(content) LIKE LOWER(?)" for _ in terms])
                params = [f"%{t}%" for t in terms]
                rows = conn.execute(
                    f"""
                    SELECT content FROM memories
                    WHERE user_id = ? AND ({where})
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    [CONFIG["user_id"], *params, limit],
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT content FROM memories WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                    (CONFIG["user_id"], limit),
                ).fetchall()

        return [{"memory": r["content"]} for r in rows]
    except Exception as e:
        print(f"[warn] Local memory recall failed: {e}")
        return []


@app.on_event("startup")
async def startup_background_warmup():
    asyncio.create_task(warmup_lm_model())


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
    voice_profile: str | None = None
    system_prompt: str | None = None
    images: list[str] | None = None  # List of base64 strings


async def run_lm_studio_chat(
    client: httpx.AsyncClient,
    *,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
) -> tuple[str, dict]:
    """Call LM Studio and capture first-token latency when streaming is available."""
    target_url = f"{CONFIG['lm_studio']}/chat/completions"
    base_payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    started = time.perf_counter()
    try:
        stream_payload = dict(base_payload)
        stream_payload["stream"] = True
        async with client.stream("POST", target_url, json=stream_payload) as r:
            if r.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"LM Studio stream returned status {r.status_code}",
                    request=r.request,
                    response=r,
                )

            chunks: list[str] = []
            first_token_s: float | None = None

            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                raw = line[5:].strip()
                if not raw:
                    continue
                if raw == "[DONE]":
                    break

                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                choices = payload.get("choices") or []
                if not choices:
                    continue

                choice0 = choices[0] or {}
                delta = choice0.get("delta") or {}
                token_piece = delta.get("content")
                if isinstance(token_piece, str) and token_piece:
                    if first_token_s is None:
                        first_token_s = round(time.perf_counter() - started, 4)
                    chunks.append(token_piece)
                    continue

                message = choice0.get("message") or {}
                message_piece = message.get("content")
                if isinstance(message_piece, str) and message_piece:
                    if first_token_s is None:
                        first_token_s = round(time.perf_counter() - started, 4)
                    chunks.append(message_piece)

            response_text = "".join(chunks).strip()
            if response_text:
                total_s = round(time.perf_counter() - started, 4)
                return response_text, {
                    "llm_mode": "stream",
                    "llm_first_token_s": first_token_s if first_token_s is not None else total_s,
                    "llm_total_s": total_s,
                }
    except Exception as e:
        # Keep chat alive if stream mode is unavailable for a model/backend.
        print(f"[warn] LM Studio streaming unavailable, using fallback mode: {e}")

    r = await client.post(target_url, json=base_payload)
    if r.status_code != 200:
        raise Exception(f"LM Studio Error: {r.status_code} - {r.text}")

    response_text = r.json()["choices"][0]["message"]["content"]
    total_s = round(time.perf_counter() - started, 4)
    return response_text, {
        "llm_mode": "nonstream",
        "llm_first_token_s": total_s,
        "llm_total_s": total_s,
    }


async def recall_memories(query: str):
    try:
        await ensure_mem0_user_ready()
        async with httpx.AsyncClient(timeout=3.0) as client:
            # OpenMemory API (newer): /api/v1/memories/filter
            r = await client.post(
                f"{CONFIG['mem0']}/api/v1/memories/filter",
                json={
                    "user_id": CONFIG["user_id"],
                    "search_query": query,
                    "page": 1,
                    "size": 3,
                },
            )
            if r.status_code == 200:
                items = r.json().get("items", [])
                parsed = [
                    {"memory": m.get("content", "")} for m in items if m.get("content")
                ]
                if parsed:
                    return parsed

            # Some mem0 versions require a user initialization step.
            if r.status_code == 404 and "User not found" in (r.text or ""):
                await ensure_mem0_user_ready()
                r2 = await client.post(
                    f"{CONFIG['mem0']}/api/v1/memories/filter",
                    json={
                        "user_id": CONFIG["user_id"],
                        "search_query": query,
                        "page": 1,
                        "size": 3,
                    },
                )
                if r2.status_code == 200:
                    items = r2.json().get("items", [])
                    parsed = [
                        {"memory": m.get("content", "")} for m in items if m.get("content")
                    ]
                    if parsed:
                        return parsed

            return local_recall_memories(query, limit=3)
    except Exception as e:
        print(f"[warn] Memory search failed: {e}")
        return local_recall_memories(query, limit=3)


async def store_memory(content: str):
    stored_remote = False
    try:
        await ensure_mem0_user_ready()
        async with httpx.AsyncClient(timeout=10.0) as client:
            # OpenMemory API (newer): /api/v1/memories/
            r = await client.post(
                f"{CONFIG['mem0']}/api/v1/memories/",
                json={
                    "user_id": CONFIG["user_id"],
                    "text": content,
                    "infer": True,
                    # Keep OpenMemory's default app; store origin as metadata instead.
                    "metadata": {"source": "knightbot"},
                },
            )
            if r.status_code in (200, 201):
                try:
                    body = r.json()
                except Exception:
                    body = {}
                if not (isinstance(body, dict) and body.get("error")):
                    stored_remote = True
            elif r.status_code == 404 and "User not found" in (r.text or ""):
                # Retry once after attempting user init.
                await ensure_mem0_user_ready()
                r2 = await client.post(
                    f"{CONFIG['mem0']}/api/v1/memories/",
                    json={
                        "user_id": CONFIG["user_id"],
                        "text": content,
                        "infer": True,
                        "metadata": {"source": "knightbot"},
                    },
                )
                if r2.status_code in (200, 201):
                    stored_remote = True
    except Exception as e:
        print(f"[warn] Remote memory store failed: {e}")

    # Always persist locally for deterministic fallback durability.
    local_store_memory(content)

    if not stored_remote:
        print("[warn] Stored memory locally (remote mem0 unavailable or degraded)")


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

    # Keep history window bounded to reduce prompt latency.
    history_window = max(0, int(CONFIG.get("max_history_messages", 6)))
    if history_window > 0:
        messages.extend(conversation_history[-history_window:])

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
        model_to_use = CONFIG["voice_model_id"] if req.include_audio else CONFIG["model_id"]

    voice_profile_name = "chat"
    voice_profile_cfg = VOICE_PROFILES["chat"]
    voice_profile_meta: Dict[str, Any] | None = None
    temperature = CONFIG["temperature"]
    max_tokens = CONFIG["max_tokens"]

    if req.include_audio:
        voice_profile_name, voice_profile_cfg, voice_profile_meta = select_voice_profile(
            req.message, req.voice_profile
        )
        temperature = float(voice_profile_cfg.get("temperature", CONFIG["temperature"]))
        max_tokens = int(voice_profile_cfg.get("max_tokens", CONFIG["voice_max_tokens"]))
        messages.append(
            {
                "role": "system",
                "content": str(voice_profile_cfg.get("style_prompt", CONFIG["voice_reply_style"])),
            }
        )

    print(f"🤖 Using model: {model_to_use}")
    print(
        f"🧠 max_tokens={max_tokens} include_audio={req.include_audio} "
        f"profile={voice_profile_name} temp={temperature}"
    )

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response_text, lm_metrics = await run_lm_studio_chat(
                client,
                model=model_to_use,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if req.include_audio:
                update_voice_runtime_from_metrics(lm_metrics, voice_profile_name)
                response_text = compact_voice_reply(
                    response_text,
                    int(voice_profile_cfg.get("max_words", CONFIG.get("voice_max_words", 70))),
                    int(voice_profile_cfg.get("max_sentences", CONFIG.get("voice_max_sentences", 4))),
                )

        conversation_history.append({"role": "user", "content": req.message})
        conversation_history.append({"role": "assistant", "content": response_text})
        # Memory persistence is best-effort and should not block chat latency.
        asyncio.create_task(
            store_memory(f"User: {req.message[:100]}. Knight: {response_text[:200]}")
        )

        payload: Dict[str, Any] = {
            "text": response_text,
            "memories_used": len(memories),
            "metrics": lm_metrics,
        }
        if req.include_audio:
            payload["voice_profile"] = voice_profile_meta
            payload["voice_runtime"] = {
                "llm_total_s_ema": VOICE_RUNTIME.get("llm_total_s_ema"),
                "last_llm_total_s": VOICE_RUNTIME.get("last_llm_total_s"),
                "last_llm_first_token_s": VOICE_RUNTIME.get("last_llm_first_token_s"),
                "samples": VOICE_RUNTIME.get("samples", 0),
                "last_profile": VOICE_RUNTIME.get("last_profile", "chat"),
            }
        return payload
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
        "voice_model_id": CONFIG["voice_model_id"],
        "voice_max_tokens": CONFIG["voice_max_tokens"],
        "voice_max_words": CONFIG["voice_max_words"],
        "voice_max_sentences": CONFIG["voice_max_sentences"],
        "voice_reply_style": CONFIG["voice_reply_style"],
        "voice_dynamic_profiles": CONFIG["voice_dynamic_profiles"],
        "voice_latency_target_s": CONFIG["voice_latency_target_s"],
        "voice_latency_critical_s": CONFIG["voice_latency_critical_s"],
        "voice_latency_fast_s": CONFIG["voice_latency_fast_s"],
        "voice_explicit_profile_strict": CONFIG["voice_explicit_profile_strict"],
        "voice_profiles": VOICE_PROFILES,
        "voice_runtime": VOICE_RUNTIME,
        "max_history_messages": CONFIG["max_history_messages"],
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
    init_local_memory_db()

    uvicorn.run(app, host="0.0.0.0", port=8100)
