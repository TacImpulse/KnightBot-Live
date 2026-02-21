# KnightBot-Live Implementation Intake Checklist

Use this checklist to lock decisions before implementation.

## 1) Priority Order (choose one ranking)
- [x] Lowest latency first
- [x] Most natural voice first
- [x] Maximum reliability first

Write your ranking (example: Reliability > Naturalness > Latency):

```
Most Natural Voice (B) > Lowest Latency (A) > Maximum Reliability (C)
```

## 2) Hardware Profile
- GPU model: NVIDIA GeForce RTX 5090
- VRAM: 32 GB
- CPU: Intel i9-14900KF
- RAM: 64 GB DDR5
- Target environment:
  - [x] Desktop only
  - [ ] Desktop + lower-end fallback profile

## 3) LM Studio Model Policy
List 2–3 preferred models for realtime voice chat:

1. qwen3-vl-32b-instruct-heretic-v2-i1 (primary multimodal quality)
2. ministral-3-14b-abliterated-i1 (fast text-centric fallback)
3. qwen3-vl-8b-thinking-abliterated-i1 (low-latency multimodal fallback)

Constraints/preferences:
- [x] Must support OpenAI-compatible chat completions
- [x] Prefer streaming support
- [x] Vision model also needed

Extra requirement notes:
- Prefer uncensored/heretic/abliterated style models with generally low refusal tendencies.
- Prefer imatrix-style GGUF builds where available.
- Vision path must support image analysis and mmproj compatibility in LM Studio.

## 4) Local-Only Policy
- [x] Strictly local only (no cloud fallback)
- [ ] Local-first with optional cloud fallback

If fallback is allowed, list approved providers/services:

```

```

## 5) Launcher/Operations Preference
Pick canonical operator experience:
- [ ] Keep `start.ps1` as primary, GUI as optional
- [x] Make Control Center GUI primary, scripts fallback

Launcher preference notes:
- Build a contained, neat, SOTA control center experience (Flet not required).

## 6) Barge-in Preference
- [ ] Aggressive interruption (fast cut)
- [ ] Balanced
- [x] Polite interruption (higher confidence before cut)

## 7) UX Scope
- [ ] Iterative polish on current Neural Link UI
- [x] Larger redesign pass

Must-have UX improvements (top 5):
1. Full multimodal I/O controls (text, voice, image upload, future web-image analysis hooks)
2. Robust message controls (resend, delete, edit, branch)
3. Conversation lifecycle QoL (auto-archiving, removal, memory-aware organization)
4. Codeblock-first ergonomics (copy/paste-friendly formatting and controls)
5. Per-paragraph read-aloud button + explicit stop-voice control

## 8) Acceptance Targets
Fill target KPIs (initial goal values):
- First-audio latency target (ms): Optimize aggressively, establish baseline in Phase 0, then iterate down
- Barge-in reaction time target (ms): Optimize for polite-but-responsive behavior, baseline then iterate
- Session stability target (minutes without restart): Max practical stability; define numeric target after baseline soak
- Startup success target (%): Max practical reliability; define numeric SLO after baseline observations

## 9) Approval
Once completed, this file becomes the implementation contract for Phase 1.

- Owner:
- Date:
