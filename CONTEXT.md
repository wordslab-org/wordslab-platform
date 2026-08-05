# CONTEXT — Wordslab Platform (home-scale AI platform)

Working vocabulary for the effort. Home of the design conversation; the spec it produces lives in this repo's docs.

## Glossary

- **Platform** — the whole system: a local AI platform, 100% built from open-source components and models, aimed at AI enthusiasts at home and small businesses who want to own their intelligence. Deployed in a trusted environment at very small scale. Simplicity is the main feature.
- **Service** — an independent, composable component of the platform (document, audio, image, chat, agent, workflow, ...). Each service has its own database, business logic, UI, and API, and can run fully independently — on this machine, on another machine, or in the cloud.
- **Platform services (centralized)** — the parts the platform centralizes across all services: authentication, users, log collection, stats, availability monitoring, evaluation, updates. *(Term to sharpen — candidate: "platform core".)*
- **Machine (node)** — a physical PC/workstation (e.g. a gaming PC with an NVIDIA GPU) that hosts one or more services. The platform runs on multiple machines and multiple disks per machine.
- **Inference provider** — where a service's model actually runs: the local GPU of a machine, or a cloud API. Each service can choose per deployment; cloud is the fallback when local hardware is insufficient.
- **Spec (the destination)** — the complete platform design, written down in repo docs so that building becomes mechanical execution. The deliverable of this effort.
