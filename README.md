# KnightBot - Live

**The Ultimate Voice Bridge & AI Companion**

KnightBot is a cutting-edge, local-first AI assistant that bridges the gap between text, voice, and visual interaction. Leveraging state-of-the-art (SOTA) open-source models, it provides a seamless, low-latency conversational experience with personality, memory, and now—customizable voice and avatar identities.

![KnightBot Banner](https://placeholder-banner-link-if-exists)

## 🌟 New Features (v2.0 - "Neural Link")

*   **Neural Link Widget**: A sleek, draggable, collapsible voice interface that sits overlayed on your screen.
*   **Voice Cloning Lab**: Upload any clean WAV file (10-20s) to instantly clone and switch Knight's voice.
*   **Avatar System**: Assign visual avatars (images) to voice profiles. (Future: Real-time animation support).
*   **LiveKit Integration**: Robust, ultra-low latency audio streaming pipeline (Pipecat) for "interruptible" conversations.
*   **Persistent Memory**: Remembers context across sessions using Vector DB.

## 📝 Latest Progress Report

- `docs/PROGRESS-2026-02-21-KNIGHTBOT.md` documents the latest voice-pipeline stabilization work, latency wins, and file-level implementation summary before this push.

## 🚀 Quick Start

### Prerequisites
*   **OS**: Windows 10/11 (Preferred) or Linux.
*   **Python**: 3.10+
*   **Node.js**: 18+
*   **Docker**: Required for Qdrant, LiveKit, and Mem0/OpenMemory.
*   **LM Studio**: Must be running locally (Port 1234) with a loaded LLM (e.g., Llama 3, Mistral).
*   **GPU**: NVIDIA RTX 3060 or better recommended for local TTS/STT.

### Installation

1.  **Clone the Repository**
    ```powershell
    git clone https://github.com/TacImpulse/KnightBot-Live.git
    cd KnightBot-Live
    ```

2.  **Run Installer**
    ```powershell
    .\install.ps1
    ```
    *This script sets up the Python venv, verifies prerequisites (including `ffmpeg`), and installs backend/frontend dependencies.*

3.  **Start KnightBot**
    ```powershell
    .\start.ps1
    ```
    *This is the canonical launcher. It performs preflight checks (ports, Docker, venv, ffmpeg, LM Studio reachability) and launches services in sequence:*
    *   `frontend` (Next.js): http://localhost:3000
    *   `knight_core` (Orchestrator): Port 8100
    *   `chatterbox` (TTS): Port 8060
    *   `parakeet` (STT): Port 8070
    *   `pipecat` (Real-time Audio): Background process

4.  **Stop KnightBot**
    ```powershell
    .\stop.ps1
    ```
    *This is the canonical shutdown script. It stops KnightBot-bound ports and then brings Docker services down.*

### Voice Round-Trip Smoke Test (STT -> Knight Core -> TTS)

After `start.ps1` is up, you can run a single diagnostic that verifies the basic back-and-forth path end-to-end.

```powershell
python .\scripts\system_check.py
```

What this now checks:

1. Service health (`Core`, `TTS`, `STT`, `Frontend`)
2. Core chat response (`/chat`)
3. TTS synthesis (`/synthesize`)
4. **End-to-end voice round-trip**:
   - sends sample audio to STT (`/transcribe`)
   - sends transcript to Knight Core (`/chat`)
   - sends reply text to TTS (`/synthesize`)
   - validates returned audio bytes are non-empty

Sample audio auto-discovery order:

- `data/stt_test.webm`
- `data/voices/knight_voice.wav`

If neither sample is present, only the round-trip step is skipped and all other diagnostics still run.

### Persistent Memory Validation (Mem0/OpenMemory)

If you want to confirm robust memory wiring after startup:

1. Run the deterministic verifier:
   ```powershell
   F:\KnightBot\venv\Scripts\python.exe F:\KnightBot\scripts\verify_mem0.py
   ```
2. Inspect report output:
   - `F:\KnightBot\data\logs\mem0_verify.json`
   - `F:\KnightBot\data\logs\mem0_verify_stdout.txt`

Expected healthy signals in `mem0_verify.json`:
- `openapi_status: 200`
- `store_status: 200` or `201`
- `filter_status: 200`
- `filter_token_found: true`
- `ok: true`

If `store_body_preview.error` shows `"Memory client is not available"`, OpenMemory is reachable but vector-backed persistence is degraded. In that case:
- ensure Docker mem0 service was recreated from this repo compose file,
- ensure startup bootstrap ran (`start.ps1` now auto-initializes `USER_ID` + `knightbot` app),
- ensure your model backend and vector dependencies are reachable from the mem0 container.

### Usage

*   **Access UI**: Open http://localhost:3000
*   **Voice Mode**: Click the **Microphone** icon or press `Ctrl+V`.
*   **Settings**: Click the **Gear** icon on the Neural Link widget to:
    *   Upload/Delete Voice Clones.
    *   Set/Upload Avatar Images.
    *   Rename Profiles.
*   **Stop**: Press `Esc` to stop TTS playback instantly.

### Realtime Voice Tuning (Pipecat)

You can tune interruption behavior and telemetry via environment variables before launching:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `KB_INTERRUPTION_MODE` | `polite` | Interruption policy: `polite`, `balanced`, `aggressive`, or `legacy` |
| `KB_INTERRUPT_RMS` | `700` | Base RMS threshold for speech-energy interruption detection |
| `KB_INTERRUPT_MIN_MS` | `300` | Minimum sustained speech energy before interruption probe |
| `KB_INTERRUPT_MIN_WORDS` | `3` | Minimum STT-confirmed words to commit interruption (non-legacy modes) |
| `KB_INTERRUPT_PROBE_COOLDOWN_S` | `0.35` | Cooldown between interruption STT probes |
| `KB_STT_CHUNK_BYTES` | `16000` | STT chunk size; lower can reduce latency but increase overhead |
| `KB_TTS_CHUNK_MS` | `40` | TTS stream chunk duration in ms |
| `KB_TTS_COOLDOWN_S` | `0.15` | Post-TTS cooldown to reduce self-transcription feedback |
| `KB_VOICE_METRICS_ENABLED` | `1` | Enables structured per-turn telemetry output |

When telemetry is enabled, turn metrics are written to:

- `data/logs/voice_metrics/*.json`

Each turn file includes STT/LLM/TTS timings plus interruption events to support iterative optimization.

## 🏗️ Architecture

KnightBot follows a microservices architecture for modularity and scalability:

| Service | Port | Description | Tech Stack |
| :--- | :--- | :--- | :--- |
| **Frontend** | 3000 | User Interface & Neural Link | Next.js, React, Tailwind, LiveKit Client |
| **Knight Core** | 8100 | Brain/Orchestrator | FastAPI, LangChain, Mem0 |
| **Chatterbox** | 8060 | Text-to-Speech Engine | FastAPI, XTTS/VITS (Custom), PyTorch |
| **Parakeet** | 8070 | Speech-to-Text Engine | FastAPI, Faster-Whisper |
| **Pipecat** | N/A | Real-time Voice Pipeline | Python, Pipecat, LiveKit Server |
| **Qdrant** | 6333 | Vector Database | Docker |
| **Mem0 / OpenMemory** | 8050 | Persistent memory API used by Knight Core | Docker |

## 🧪 Development & Contribution

We follow **Standard Operating Procedures (SOP)** for high-quality code contributions.

### Directory Structure
```
KnightBot/
├── frontend/       # Next.js Application
├── scripts/        # Knight Core (Backend)
├── chatterbox/     # TTS Service
├── parakeet/       # STT Service
├── pipecat/        # LiveKit Pipeline Agent
├── data/           # Persistent data (voices, avatars, memory)
└── docs/           # Documentation
```

### Workflow
1.  **Branching**: Use feature branches (`feature/new-avatar-system`).
2.  **Commit Messages**: Clear and descriptive (e.g., `feat: add avatar upload endpoint`).
3.  **Testing**: Verify all services start and intercommunicate before pushing.

### SOTA Planning Docs
- **Upgrade roadmap**: `docs/SOTA-Upgrade-Plan.md`
- **Implementation intake checklist**: `docs/Implementation-Intake-Checklist.md`

Use these docs to track the phased rollout for realtime barge-in upgrades, UX improvements, launcher unification, and LM Studio optimization.

## 🔮 Future Roadmap

*   **Real-time Animated Avatars**: Integration of `TalkingHead` (ThreeJS) or `MuseTalk` for lip-synced visual personas.
*   **Video Input**: "Vision" capabilities for Knight to "see" via webcam.
*   **Mobile App**: React Native bridge.

## 📜 License

MIT License. See `LICENSE` for details.

---
*Built with ❤️ by TacImpulse & KnightBot Dev Team*
