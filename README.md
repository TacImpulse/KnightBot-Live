# KnightBot - Live

**The Ultimate Voice Bridge & AI Companion**

KnightBot is a cutting-edge, local-first AI assistant that bridges the gap between text, voice, and visual interaction. Leveraging state-of-the-art (SOTA) open-source models, it provides a seamless, low-latency conversational experience with personality, memory, and now—customizable voice and avatar identities.

![KnightBot Banner](https://placeholder-banner-link-if-exists)

## 🌟 New Features (v2.0 - "Neural Link")

*   **Neural Link Widget**: A sleek, draggable, collapsible voice interface that sits overlay on your screen.
*   **Voice Cloning Lab**: Upload any clean WAV file (10-20s) to instantly clone and switch Knight's voice.
*   **Avatar System**: Assign visual avatars (images) to voice profiles. (Future: Real-time animation support).
*   **LiveKit Integration**: Robust, ultra-low latency audio streaming pipeline (Pipecat) for "interruptible" conversations.
*   **Persistent Memory**: Remembers context across sessions using Vector DB.

## 🚀 Quick Start

### Prerequisites
*   **OS**: Windows 10/11 (Preferred) or Linux.
*   **Python**: 3.10+
*   **Node.js**: 18+
*   **Docker**: Required for Qdrant (Vector DB).
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
    *This script sets up Python venvs, installs dependencies for all microservices, and configures the environment.*

3.  **Start KnightBot**
    ```powershell
    .\start.ps1
    ```
    *This launches all 5 microservices in separate terminals:*
    *   `frontend` (Next.js): http://localhost:3000
    *   `knight_core` (Orchestrator): Port 8100
    *   `chatterbox` (TTS): Port 8060
    *   `parakeet` (STT): Port 8070
    *   `pipecat` (Real-time Audio): Background process

### Usage

*   **Access UI**: Open http://localhost:3000
*   **Voice Mode**: Click the **Microphone** icon or press `Ctrl+V`.
*   **Settings**: Click the **Gear** icon on the Neural Link widget to:
    *   Upload/Delete Voice Clones.
    *   Set/Upload Avatar Images.
    *   Rename Profiles.
*   **Stop**: Press `Esc` to stop TTS playback instantly.

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

## 🔮 Future Roadmap

*   **Real-time Animated Avatars**: Integration of `TalkingHead` (ThreeJS) or `MuseTalk` for lip-synced visual personas.
*   **Video Input**: "Vision" capabilities for Knight to "see" via webcam.
*   **Mobile App**: React Native bridge.

## 📜 License

MIT License. See `LICENSE` for details.

---
*Built with ❤️ by TacImpulse & KnightBot Dev Team*
