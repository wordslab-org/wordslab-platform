# Building, learning, and the lifecycle

> Part of the wordslab-platform architecture document. This chapter is the conceptual lifecycle view: how a builder takes an idea from development to a deployed, published thing, and how install/update/publish are shaped by the soul. Source of truth: ADR-0024 (learning experience / guided build), ADR-0020 (evaluation), ADR-0025 (training), ADR-0014/0016 (install/update), ADR-0018/0019 (governance/publishing), ADR-0022 (license). This chapter cites, never restates. The per-concern detail lives in `20-concerns/23` (learning & operability), `20-concerns/22` (license), `20-concerns/25` (lifecycle & updates); the owning services are **Development** (`30-services/37`) and **Publishing & Governance** (`30-services/39`).

## The three ways a builder works

Building on the platform happens through the **Development service's `agentic-development-workflow`** — the human surface that embodies the guided build process. Three things make the process educational rather than an expert tool:

- **A versioned, first-class skill set** — the Matt Pocock engineering skills (wayfinder, grilling, TDD, code-review, …), adapted/whitelabelled by the platform to call the platform's own capabilities, extended with ML + evaluation best practices (Shankar/Husain — evaluation designed *into* the build flow, steering to the eval capability). Surfaced through the Development service. *(ADR-0024 §3.)*
- **A human-readable process documentation** that teaches the process before the learner uses the skills. *(ADR-0024 §3.)*
- **The continual learning assistant and the per-service learning bar** — a personal assistant (Hermes Agent) accessible everywhere and a graded bar of docs/skills/tools/diagnostics on every service and implementation. Detail is in `20-concerns/23`; here it suffices that every surface teaches.

Evaluation and training are the **builder-run, notebook-driven, deliberately-not-centralized** half of the story:

- **Evaluation** (ADR-0020) follows **Analyze–Measure–Improve**: dataset → simulate → open coding → axial coding (binary failure modes) → **LLM-as-judge validated against human labels** (the judge scores *known* failure modes; discovery stays human) → report, with history kept in the project repo. Real usage reaches eval datasets **only** through the core's filtered + anonymized extraction (the consent boundary, `20-concerns/24`).
- **Training** (ADR-0025) is the dev-side counterpart to Inference: `train.dataset` / `train.fine-tune` / `train.publish`, notebook-driven (JupyterLab is the human surface), **Trackio** for training metrics, the **license gate at `train.fine-tune`** (ADR-0022), and a trained artifact **publishing back to Inference as a new implementation**. Detail: the Training and Evaluation chapter (`30-services/36`).

## From developed thing to published thing

**Publishing is the deploy/expose layer** for the result of a development activity (ADR-0019) — the path by which the Development service's output becomes something the builder, their family, or their learning group can reach. It is deliberately **small-scale** (a home platform, not "serve millions").

- A **published thing is light by default** — a static site or a long-running container (no serverless in v1); the full service contract is opt-in.
- **Exposure** in v1 is the **LAN** (front door) + a **private-mesh overlay** with auto-managed default-deny ACLs (share an app with a friend = one invite link, one visible rule); the public-internet gateway is deferred to v1.1 (Connectors).
- **Compliance is coupled to publishing only** — an operational-facts + EU-AI-Act/GDPR **exit-early checklist**, advisory, stored as documentation. License follows the two regimes (`20-concerns/22`).
- **Agent-generated code** runs **one OS container per app**, network-scoped, with a visible "runs agent code" trust badge.

Detail: the Publishing & Governance chapter (`30-services/39`) and ADR-0019.

## The install → update → publish lifecycle

All three are **guided, never silent** — the soul's "no magic, no black box" applies to the machine as much as the AI.

- **Install** is a guided, phased wizard (native console → Python TUI → web UI) that ends with a recap and leaves a **resident launcher** on every machine. Invariant: **updates never touch data volumes** (ADR-0014).
- **Updates**: three tiers versioned by what they are — the date-based **platform bundle** (the one user-facing version), service semver, implementation artifact versions — on a per-capability-API-version substrate. **No automatic updates in any tier**; a persistent, leader-centralized updates list; one-click per item at the user's pace. Rollback = the previous consistency unit (ADR-0016).
- **Publishing** is where a developed thing joins the deployable catalog or the platform's own update list (ADR-0018/0019, above).

Detail: `20-concerns/25` (lifecycle & updates) and `20-concerns/26` (dashboard).

## The machine, at a glance

A Wordslab installation is a **fleet of machines** — your PCs, possibly a rented cloud box — running **independent services** (each with its own DB, business logic, UI, API), a **platform core on every machine** (control only, never the request path), a **bootstrap layer** (native installer/updater), and a **front door** (a tiny static reverse proxy on the leader: `wordslab.local`, the one stable address for the dashboard and every service UI). One machine is the **leader** (single, no HA in v1); the others are **workers** that join via a short type-in code. Detail: `10-concepts/12`.
