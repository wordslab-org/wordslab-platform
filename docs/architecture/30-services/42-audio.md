# 42 — Audio

> **Status:** written at the resolution of wayfinder ticket "Write the four light service chapters (Generation, Image, Audio, Media transformations)" (#45). **Source of truth:** the CONTEXT.md *Audio service* glossary entry, ADR-0029 (task-shaped `stt.model` / `tts.model` capability names), ADR-0027 (implementation declarations in `implementation.toml`; a model is an implementation), ADR-0001 (family 4 WebRTC realtime), ADR-0023 (representations — stored together in document bundles), ADR-0007 (realtime voice chat driven by the **agent service**, not plain inference). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **Audio service** is the platform's **voice surface**: it turns speech into text (STT), text into speech (TTS), and carries real-time voice conversation. Each face of speech is a distinct capability (CONTEXT.md *Audio service*); the models underneath ride the Inference service's task-shaped model capabilities.

## Capabilities

- **stt** — speech-to-text, **batch**.
- **stt-realtime** — speech-to-text, **streaming**.
- **tts** — text-to-speech, **batch**.
- **tts-streaming** — streaming text-to-speech.
- **vad** — voice-activity detection.
- **voice cloning & design** — crafting and cloning voices.
- **realtime voice chat** — real-time voice conversation (family **4**, WebRTC). Composed locally from **stt-realtime + tts-streaming + vad**, but **driven by the agent service** (its tools, skills, and sessions) — not plain LLM inference (ADR-0007).
- **Dictation** — mic → stt-realtime → text, a **shared UI-kit affordance** every service with long-text inputs gets, not Audio-exclusive.
- **Document-bundle contributions** — the Audio service contributes **transcriptions + speaker diarization + audio embeddings** to Document bundles as **representations** (CONTEXT.md *Representation*), stored alongside the other modalities.

## ADR cross-references

ADR-0001 (family 4 — WebRTC realtime for the browser dashboard) · ADR-0007 (realtime voice chat composed locally but driven by the agent service, not plain inference) · ADR-0023 (representations stored together in document bundles across modalities) · ADR-0027 (a model is an implementation, declared in its own `implementation.toml`) · ADR-0029 (the task-shaped `stt.model` / `tts.model` capability names). Mostly CONTEXT.md (*Audio service* and *Representation* entries).
