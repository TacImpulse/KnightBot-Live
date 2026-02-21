# KnightBot-Live SOTA Upgrade Plan (OSS-First)

## Goal
Build a fully local-first, realtime, barge-in capable voice agent stack with modern UX, robust orchestration, and fast rollback safety.

This plan is optimized for KnightBot's existing architecture:
- LiveKit (self-hosted) transport
- Pipecat realtime pipeline
- Parakeet STT
- Chatterbox Turbo TTS
- LM Studio local LLM endpoint

## Locked Decisions (2026-02-09)
- Priority ranking: **Naturalness > Latency > Reliability** (B > A > C)
- Hardware target: **RTX 5090 32GB VRAM**
- CPU/RAM target: **i9-14900KF + 64GB DDR5**
- Policy: **Strictly local-only** (no cloud fallbacks)
- Barge-in style: **Polite** (higher confidence threshold before interruption)
- UX scope: **Approved for larger redesign pass**
- Operations UX: **GUI-first canonical launcher** (script fallback retained)
- Model policy: Prefer **uncensored/heretic/abliterated low-refusal** model variants and **imatrix GGUF** where available
- Vision policy: Require VL-capable models and compatible **mmproj.gguf** paths in LM Studio for image analysis

Implication: we can run higher-quality local models while still targeting low perceived latency via streaming, chunked TTS playout, and interruption-aware turn management.

---

## Current-State Highlights (from workspace review)
- **Strong base is already present**: frontend widget, realtime LiveKit + Pipecat transport, STT/TTS microservices, memory service, launch tooling.
- **Barge-in exists** but is currently RMS-threshold centric; needs SOTA turn-taking + interruption policy.
- **Startup paths are fragmented** (PowerShell canonical + Python managers); should converge into one preferred orchestrator path with health/state panels.

---

## SOTA Target Architecture (Free + Open Source)

### 1) Realtime Transport & Agent Runtime
- Keep **LiveKit self-hosted** for RTC/media/data channels.
- Keep **Pipecat** for pipeline orchestration.
- Add/enable:
  - Silero VAD tuned for fast conversational endpointing.
  - Smart turn analyzer integration (Pipecat smart turn path).
  - Unified interruption state machine.

### 2) Barge-in / Turn-Taking Policy (Core UX feature)
Layered interruption detection:
1. VAD confidence/speech-duration gate
2. Transcript-assisted interruption trigger (interim/final)
3. Audio ducking before hard cut
4. Context truncation policy for interrupted assistant responses

### 3) ASR
- Keep **Parakeet** as primary.
- Add optional low-resource profile/fallback path for weaker GPUs.
- Expose endpointing controls in runtime profile config.

### 4) TTS
- Keep **Chatterbox Turbo** as default voice identity engine.
- Add cancellation token propagation end-to-end (UI → Pipecat → TTS stream).
- Add "Fast/Balanced/Expressive" output profiles.

### 5) LM Studio Integration
- Keep OpenAI-compatible API path.
- Add startup capability checks and active model profile validation.
- Add streaming response path (where supported) for earlier first-audio playback.

### 6) UX/UI
- Preserve dark-mode brand style.
- Add:
  - turn-state feedback (listening/thinking/speaking/interrupted)
  - latency HUD (ASR / LLM / TTS / round-trip)
  - configurable advanced voice panel (VAD, interruption aggressiveness, chunking)

### 7) Unified Launcher / Control Plane
- Choose one canonical launcher UX and keep legacy scripts as fallback.
- Required features:
  - deterministic startup order + retries
  - health checks by dependency stage
  - merged logs + per-service logs
  - profile selector (Quality / Balanced / Low-Latency)

---

## Phased Implementation Plan (with risk controls)

## Phase 0 — Baseline & Instrumentation
Deliverables:
- Structured logs for STT, LLM, TTS timings
- End-to-end latency metrics
- Baseline performance capture script/report

Risk control:
- No behavior change, observability only

Rollback:
- Remove instrumentation hooks behind a flag

## Phase 1 — Realtime Turn-Taking & Barge-in Hardening
Deliverables:
- Interruption state machine in Pipecat pipeline
- VAD + smart-turn tuned endpointing
- Transcript-assisted interruption path
- Optional duck-before-cut behavior

Risk control:
- Feature flag: `KB_INTERRUPTION_MODE=legacy|hybrid|smart`

Rollback:
- Set legacy mode to retain current behavior

## Phase 2 — ASR/TTS Runtime Profiles
Deliverables:
- Configurable profiles (`fast`, `balanced`, `quality`)
- STT/TTS chunk tuning per profile
- Cancellation-safe TTS playout path

Risk control:
- Keep current defaults as profile baseline

Rollback:
- Pin active profile to `legacy_current`

## Phase 3 — LM Studio Capability & Streaming Path
Deliverables:
- Model startup verification
- Optional streaming generation mode
- Stable fallback to non-streaming path

Risk control:
- Auto-disable streaming on first compatibility failure

Rollback:
- Force non-streaming mode

## Phase 4 — UI/UX Quality-of-Life Upgrade
Deliverables:
- turn-state animations
- latency HUD
- advanced voice controls panel
- improved hotkeys + interaction ergonomics

Risk control:
- UI feature toggles

Rollback:
- Switch to classic widget mode

## Phase 5 — Launcher Unification + Hardening
Deliverables:
- Canonical control-center path
- startup diagnostics wizard
- one-click environment validation
- docs + operator runbook

Risk control:
- Keep `start.ps1` and current scripts available

Rollback:
- fall back to script-first startup

---

## Candidate OSS Upgrades to Evaluate During Implementation
- **Pipecat smart-turn integration** for more natural handoff.
- **LiveKit data-channel event schema** for transcript/turn synchronization.
- **Optional RNNoise/noise suppression stage** where useful for mic quality.
- **Frontend UX improvements** with existing stack (Next.js + Tailwind + framer-motion).

All upgrades should remain free/open source and self-hostable by default.

---

## Recommended Local LM Studio Model Stack (for RTX 5090)
Use a 3-tier model policy so the launcher can auto-route by profile:

1. **Quality (default)**
   - Suggested: `qwen3-vl-32b-instruct-heretic-v2-i1`
   - Purpose: best voice naturalness and response quality

2. **Balanced**
   - Suggested: `ministral-3-14b-abliterated-i1`
   - Purpose: lower latency with strong quality

3. **Realtime Fast**
   - Suggested: `qwen3-vl-8b-thinking-abliterated-i1`
   - Purpose: fastest first-token and interruption responsiveness

Selection constraints:
- Must run via LM Studio OpenAI-compatible endpoint
- Prefer reliable streaming support
- Keep prompts optimized for concise spoken output

---

## LM Studio Inventory Assessment (queried from `192.168.68.111:1234`)
Observed strong existing coverage:
- **Primary VL candidates (already present):**
  - `qwen3-vl-32b-instruct-heretic-v2-i1`
  - `qwen3-vl-32b-thinking-heretic-v2-i1`
  - `qwen3-vl-32b-gemini-heretic-uncensored-thinking-i1`
- **Latency-friendly VL candidates:**
  - `qwen3-vl-8b-thinking-abliterated-i1`
  - `qwen3-vl-8b-nsfw-caption-v4.5-i1`
  - `huihui-qwen3-vl-4b-instruct-abliterated-i1`
- **Text-specialized low-latency candidate:**
  - `ministral-3-14b-abliterated-i1`

Conclusion: you already have sufficient model inventory to start Phase 0/1 without new downloads.

---

## Immediate Execution Plan (Next 2 Phases)

### Phase 0 (1-2 days): Baseline + Telemetry
- Add structured timing events:
  - `stt_start/stt_end`
  - `llm_start/first_token/llm_end`
  - `tts_start/first_audio/tts_end`
  - `interrupt_requested/interrupt_committed`
- Add per-session summary JSON under `data/logs/voice_metrics/`
- Add launcher panel for live latency counters

### Phase 1 (2-4 days): Polite Barge-in + Turn Management
- Replace RMS-only interruption with hybrid polite policy:
  - VAD confidence + minimum speech duration gate
  - transcript-assisted interrupt only after minimum word evidence
  - duck output first, then hard-cut when criteria sustained
- Add interruption mode setting:
  - `polite` (default)
  - `balanced`
  - `aggressive`
- Keep legacy mode behind feature flag rollback

### Phase 1.5 (parallel, 1-2 days): Multimodal UX Contract
- Add formal UI action matrix for expected QoL controls:
  - edit / resend / delete / branch message
  - auto-archive and conversation lifecycle controls
  - per-paragraph read-aloud and explicit stop-speech control
  - codeblock copy controls and markdown ergonomics
- Define message schema updates so these controls are first-class and testable

---

## Success Criteria
- Median first-response voice latency significantly reduced.
- Reliable barge-in across varied speaking styles/noise conditions.
- No service orchestration ambiguity (single preferred launch path).
- Clear operator observability and user-adjustable QoL controls.
