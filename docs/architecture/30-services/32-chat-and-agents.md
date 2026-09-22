# 32 — Chat + Agents

> **Status:** written at the resolution of wayfinder ticket "Design the Chat + Agents service chapter (foundational)" (#42). **Source of truth:** ADR-0007 (composition: the agent primitive, the MAF native loop vs harness images, the agent→workflow graduation path), ADR-0008 (the capability registry: **agent** and **skill** entries live here; per-agent scoping enforced server-side; the `chat.<name>` / `skill.<name>` authored namespace), ADR-0012 (the memory substrate: raw episodic memory in Document bundles, derived profile in Knowledge, working memory in the loop), ADR-0024 (the continual learning assistant = Hermes Agent; the skills home), ADR-0017 (container network policy for agent-session containers), ADR-0001/0002 (family 9 authoring; callable surfaces). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **Chat + Agents service** is the platform's **agentic front door**: the home of the **agent** composition primitive and of authored **agent** and **skill** registry entries, the host of the agent loop (the MAF native loop and the containerized harness-image session runners), the **loop-side home of the agent memory substrate** (working memory lives here; the raw and derived layers are backed by Document and Knowledge), and the host of the platform's **continual learning assistant** (= Hermes Agent).

It pairs with the **Workflow** service as the platform's two composition services (ADR-0028 §6): Chat + Agents is the **interactive / reactive** side — a flexible, costly, non-deterministic *loop*; Workflow is the **deterministic** side (ADR-0007 §1). The two interoperate and processes **graduate from agent → workflow** as their real-world variations become understood — explore in the agent, lock in as a workflow.

## User guide

### What the user sees and does

- **Chat** with the platform and its services through a vendored **Open WebUI** human surface (the chat UI; image/audio and other capabilities surface here as first-class agent tools).
- **Author an agent**: pick a model, write the system prompt, and declare the **accessible tool set** (which registry tools the agent may search and invoke) plus the **preloaded subset** (a subset of accessible, always in the system prompt) — alongside the **skills** it can draw on.
- **Run agent sessions** two ways: a **stateless** session runs the native MAF loop in-process (structured, inspectable); or a **workspace session** runs a **containerized harness image** (Hermes Agent, OpenCode, Pi) as a **workspace-session runner** for real agentic work in a disposable container.
- **Own skills**: author skill entries (a SKILL.md body) that live in this service and register as discoverable `skill` registry entries on publish.
- **Use the continual learning assistant** (Hermes Agent) anywhere — mounted with every installed service/implementation's learning-bar artifacts, with docs for everyone and **tools by role** (ADR-0024 §2).

### Representative use cases

1. **"Help me draft a workflow"** (User) — open chat, ask the agent-chat companion to author/refine a workflow conversationally, visibly (ADR-0007 §4); the result lands in the Workflow service.
2. **"Build a summarizer I can reuse"** (Builder) — author an agent definition (`model` + system prompt + accessible tools + preloaded subset), publish it → it registers as `chat.<name>`, discoverable = launchable (ADR-0008 §6), reused by id from every session.
3. **"Remember what I care about across chats"** (User) — the loop's **working memory**; long-term recall pulls the **raw episodic** bundles (Document) and the **derived profile** (Knowledge) via the memory-retrieval capability, with cited, provenance-linked context (ADR-0012 Part 1).
4. **"Run a long agentic task in its own environment"** (Builder) — a **workspace session**: launch a harness-image agent in a container with a persistent **agent workspace** (host directory, durable) and the harness's own **harness home**, both surviving container destruction (ADR-0007 §2/§8).
5. **"Teach me to build with the platform"** (any user) — the **continual learning assistant** (Hermes Agent), with every installed service's docs + skills + MCP tools + diagnostics mounted, docs for all roles, admin/builder tools withheld from users lacking the role (ADR-0024 §2).

## Reference

### The agent primitive (ADR-0007 §1/§9)

The **agent** is the *interactive/reactive* unit — a reusable, versioned **definition** (model + system prompt + accessible tool set + preloaded subset), executed as a **loop**: flexible, costly, non-deterministic. Family 9 `/v1/agents`. It is created once and referenced by id from every session. It calls tools via **MCP** (the natural-language tool surface, ADR-0007 §5). It interoperates with workflows and follows the **agent → workflow → skill graduation path** (ADR-0007 §1, ADR-0012 Part 2).

### The native loop (MAF) and bring-your-own-loop harness images (ADR-0007 §2)

- **MAF** — the platform-native agent loop: in-process, Python, **stateless**, **structured sessions in the service DB** — structured, inspectable, attributable (action context), provider/privacy-aware, MCP-tool-uniform. It is the **composition primitive** this service defines: the properties a *composition* needs (composability, observability, controllability). It does not claim to be a more capable agent than the vendored harnesses.
- **Containerized harness images** (Hermes Agent, OpenCode, Pi) — **bring-your-own-loop**, second-class for composition, driven as **workspace-session runners** for real agentic work. They are **opaque** to the platform (harness home; two-tier sessions) and can **lend tool implementations** to MAF where useful — no walled garden (ADR-0007 §2).

### Agent & skill registry entries (ADR-0008)

Authored **agent** and **skill** entries live in this service and are registered by it on **publish only** — drafts stay private; **discoverable = launchable** (ADR-0008 §6). The registry holds the one-line description + a reference to the owning service; the **full definition** (the agent definition; the SKILL.md body + metadata) is fetched on demand via `load(entry_id)` (ADR-0008 §3). Authored entries use the namespaced names `chat.<name>` (agent) and `skill.<name>` (ADR-0008 §8), reserved by the leader core's **name authority**. Models are **not** entries: an agent's model is explicitly chosen, and other-model capabilities (image gen, STT/TTS…) surface as **tool** entries (ADR-0008 §2). Skills are also the delivery vehicle of the platform's guided AI-build process and the per-capability "how an agent drives me" bar artifacts (ADR-0024 §1/§3).

### Per-agent scoping (ADR-0007 §9, ADR-0008 §5)

The **accessible tool set lives in the agent definition** (this service) — the registry reads the caller's agent definition at search time and **enforces the allowlist server-side**: `search(query)` returns only entries in the accessible set (the agent can never even *see* out-of-allowlist tools); `load(entry_id)` refuses ids outside it. The **preloaded subset** is loaded into the system prompt by the harness. Workflows have **no** allowlist (they name tools deterministically in code; ADR-0008 §5).

### The two-tier session model (ADR-0007 §8, #18)

- **Native runs** (MAF) are **structured, replayable, inspectable**: run state lives in the service DB as a sequence of step events (each awaited primitive with inputs, outputs, action context); a run can be replayed, inspected, resumed, and its failure point identified — no black box.
- **Harness-image runs** are **opaque and snapshotted as-is**: the platform persists the **harness home** (e.g. `~/.hermes`, `~/.pi/agent`, opencode's config dir) in its native format — never parsed. Sessions are **two-tier**: structured DB for MAF; opaque harness home for images.
- **Workspaces / environments** are execution state/resources: an **agent workspace** is a persistent host directory (the durable state of a stateful agent: files, user-installed packages) that survives container destruction and is mountable into a session's container; it is shared with the Development service (VS Code, JupyterLab open the same directories). Workspaces are allocated by the platform core's `resources` capability, not discoverable capabilities (ADR-0008 §2). An **agent session** binds an agent + optional workspace: stateless sessions run the harness in-process; workspace sessions run in a disposable container.

### Memory substrate — this service is the loop-side home (ADR-0012 Part 1)

- **Working memory** — the agent loop's context window, held here on the agent loop, not stored in the profile KB (ADR-0012 §1).
- **Episodic memory (raw)** — backed by the **Document** service as document bundles: a **conversation-transcript bundle** per session, a **user-profile dossier bundle** (verbatim stated facts, deliberately not pre-summarized), a **task-history bundle**. Non-lossy, source of truth (ADR-0012 §1).
- **Semantic + procedural memory (derived)** — backed by the **Knowledge** service: a compact user-profile summary, the profile/graph KB, grounded skills — derived **lazily** over the bundles, each item tracing to its bundle IDs (ADR-0012 §1).
- **Memory retrieval** — a **callable capability owned by Document + Knowledge**, composing the `chunks` and `graph` data sources with an explicit precedence order and returning **cited, provenance-linked context**, plus a small **always-on preloaded surface** (compact profile summary + current-task notes). Retrieval routing is explicit — no hidden heuristics (ADR-0012 §1). The capture/graduation side (validated deltas from sessions → facts/entities, exact procedures → Workflow, reusable approaches → skills) routes through the Knowledge service's review queue (ADR-0012 Part 2; the destinations touch this service as the skills home).

### The continual learning assistant (ADR-0024 §2)

The platform's continual personal assistant is **literally Hermes Agent** (a vendored harness image) — deliberately **not** a MAF agent, because it is outside composition (the platform teaches the most popular assistant by using it, and inherits its continuous-learning features, skills, and tools). Hosted here (this service is also a harness-image session runner). **One workspace = one Hermes state per physical user** (not per role). On new-user creation the platform **automatically mounts** every installed service/implementation's learning-bar artifacts (docs + skills + MCP tools + diagnostics) via the registry. **Docs everywhere; tools by role**: documentation is mounted for all users (including admin-service docs for non-admins); admin/builder tools + skills are **not** mounted for users lacking that role. **One identity per session, chosen at launch** (User view → `user`, Builder view → `builder`, Administrator view → `admin`), governing tool mounting + action-context; no mid-session switching.

### Security of agent sessions (ADR-0017)

Agent-session containers (the workspace-session runners) are OS-isolated, not VMs, and get **default-allow-but-scoped-to-need** outbound (PyPI/GitHub/HuggingFace, the platform's own services/registry/connectors door) but **no unrestricted host or LAN access** — the container network policy is the backstop for harness tool calls, enforced even if the harness approves a call (ADR-0017, *host-filesystem isolation* and *container network policy*). The platform runs in a WSL VM with no access to host OS files by default (ADR-0017).

### ADR cross-references

ADR-0001 (family 9 authoring shape) · ADR-0002 (callable surfaces; the agent's accessible/preloaded tool lists in the definition) · ADR-0007 (agent primitive, MAF vs harness images, graduation path, session two-tier split, per-agent scoping, explicit model/implementation choice) · ADR-0008 (agent/skill entries, per-agent server-side scoping, authored namespace `chat.<name>`/`skill.<name>`, discoverable = launchable, models not entries) · ADR-0012 (memory substrate: working/episodic/semantic; the capture-to-destinations loop) · ADR-0017 (container network policy, host-filesystem isolation) · ADR-0024 (learning bar, continual learning assistant = Hermes Agent, guided AI-build skills live here as `skill` entries).
