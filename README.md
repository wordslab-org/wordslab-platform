# wordslab-platform

**Own your intelligence.** A 100% open-source local AI platform for AI enthusiasts at home and small businesses — running and composing local versions of the main AI services (chat, image, voice, documents, agents, workflows...) on the machines you already own.

- One-click install on Windows (via WSL) and Linux
- Each service is an independent component with its own database, UI and API
- All service APIs share the same concepts
- Smart model management: weights cached in RAM, loaded/unloaded on demand, cloud fallback per service
- Runs across multiple machines and multiple disks
- Centralized auth, users, logs, stats, monitoring, evaluation, updates

## Status

**Design phase.** The platform's architecture is being charted as a decision map — see the [wayfinder map](https://github.com/wordslab-org/wordslab-platform/issues) (issue labelled `wayfinder:map`). The destination is a complete, buildable spec written down in this repo's docs.

The conceptual foundation comes from the studies in [wordslab-agent](https://github.com/wordslab-org/wordslab-agent) (`platform-studies/`): a vendor-neutral map of the whole AI service universe (architecture.md), a full API synthesis (api_summary.md), and an enterprise-grade implementation plan (implementation.md). This platform is the deliberate inverse: minimal, simple, understandable — the same concepts, radically lighter execution.

The installer/UX pattern is inspired by [wordslab-notebooks](https://github.com/wordslab-org/wordslab-notebooks).

## License

Apache-2.0
