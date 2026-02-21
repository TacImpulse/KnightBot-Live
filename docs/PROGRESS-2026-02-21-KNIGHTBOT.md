# KnightBot Progress Report - 2026-02-21

## Objective
Stabilize real-time voice-to-voice operation, cut end-to-end latency, prevent response/audio truncation, and make runtime behavior tunable for richer replies.

## Key Outcomes
- Voice-to-voice is now functional (record -> STT -> LLM -> TTS -> playback) with materially better responsiveness.
- STT responsiveness improved to near-instant in current tests after introducing Faster-Whisper-first routing with fallback.
- Text response time improved from prior minute-scale behavior to low-second responses in successful runs.
- Mic/transmit control behavior improved so voice mode can be toggled intentionally instead of getting stuck in an ON state.
- TTS first-sentence cutoff/truncation was reduced via dynamic per-request token budgeting.
- Voice reply behavior now supports profile-based and latency-aware control, with strict honoring of explicitly requested profiles.

## User-Observed Milestones During This Iteration
- Earlier state: ~3+ minute total loop.
- Intermediate state: ~26s text + ~2:05 delayed voice.
- Improved state: transcription near-instant, text ~1-3s, voice-to-voice back-and-forth restored.

## Implementation Summary

### 1) TTS Stability + Truncation Control
- Added dynamic request-scoped token budgeting for TTS generation.
- Added environment-driven controls for minimum/base/per-character token sizing.
- Ensured request budget is applied safely around TTS inference calls.

Primary files:
- `chatterbox/server.py`
- `start.ps1`

### 2) Voice Mode UX and Toggle Reliability
- Added suppression guard for auto-restart races in microphone lifecycle handling.
- Adjusted voice button semantics to clean ON/OFF toggling.

Primary files:
- `frontend/src/app/page.tsx`
- `frontend/src/components/InputBar.tsx`

### 3) Voice Profile Intelligence (Dynamic + Strict Explicit)
- Added profile-based reply tuning and runtime adaptation hooks.
- Added strict mode so explicitly requested profile is not auto-downgraded.
- Extended config visibility for profile settings.

Primary files:
- `scripts/knight_core.py`
- `config/knight-prompt.md`

### 4) STT Path Hardening (Primary + Fallback)
- Added Faster-Whisper path for primary STT with fallback behavior for resilience.
- Added frontend API STT routing logic with timeout/fallback behavior.
- Updated launch/check scripts and pipeline wiring for dual STT strategy.

Primary files:
- `faster_whisper/server.py`
- `pipecat/faster_whisper_stt.py`
- `pipecat/pipeline.py`
- `frontend/src/app/api/stt/transcribe/route.ts`
- `frontend/src/app/api/stt/health/route.ts`
- `start.ps1`
- `scripts/system_check.py`
- `scripts/verify_stt.py`

### 5) Frontend API Proxy Hardening
- Added explicit API route handlers for Knight/STT/TTS proxy calls used by the frontend app.

Primary files:
- `frontend/src/app/api/knight/chat/route.ts`
- `frontend/src/app/api/knight/health/route.ts`
- `frontend/src/app/api/knight/token/route.ts`
- `frontend/src/app/api/tts/health/route.ts`
- `frontend/src/app/api/tts/synthesize/route.ts`
- `frontend/src/lib/api.ts`

## Notes / Remaining Work
- TTS latency still varies with CPU-bound model characteristics and current runtime conditions.
- Rich long-form story output can be further improved by model/profile tuning and tighter coupling between response length policy and active latency budget.
- Additional profiling should be done per stage (STT -> LLM first token -> LLM complete -> TTS synth -> playback start) for continued optimization.

