# Learning and operability

> **Cross-cutting concern (ADR-0024).** The platform's educational goal made concrete across every service — **the per-service bar, the continual assistant, the guided build**. Organized build-view: cites the ADR and its support (service template ADR-0002, registry ADR-0008, dashboard ADR-0015, composition ADR-0007, Development, eval ADR-0020, publishing tiers ADR-0018, onboarding/backup ADR-0021); never restates them.

## The learning/operability bar on every service and implementation (ADR-0024 §1)

Every **service and implementation** carries a **required, auditable bar** of learning/operability artifacts, graded by depth (**how to use · how it works · study in depth · going further**), in three categories:

- **Documentation** — the four depth levels, written to be **readable and indexed for agents**: structured Markdown, canonical section schema + front-matter (title, capability/implementation, level, keywords, MCP tool refs). **One source, dual-consumed** — the human surface and the agent indexer read the same file; there is **no separate agent-authored set**.
- **Skills + MCPs** — MCP tools auto-generated from OpenAPI (with `@tool` overrides), plus a **how-an-agent-drives-me `skill`** (a registry `skill` entry). A genuinely-not-agent-drivable capability records an explicit **"not agent-operable"** note — no theater.
- **Diagnostics tools** — to fix and optimize.

The bar is **declared in the service template (ADR-0002)**, and its artifacts are indexed and mounted through the registry (ADR-0008). Publishing the bar is **mandatory to publish for `bundled`/`listed`, recommended-with-tracked-gaps for `third-party`** (ADR-0018's tiers); it applies to published things (ADR-0019).

## The continual learning assistant (ADR-0024 §2)

A personal assistant to learn and build — **literally Hermes Agent**, the vendored harness (the teaching vehicle for the most popular personal assistant; MAF unchanged as the composition primitive — MAF stays the platform-native loop, ADR-0007). **One workspace = one Hermes state per physical user.**

On **new-user creation**, the platform **auto-mounts every installed service/implementation's bar artifacts** (docs + skills + MCP tools + diagnostics) into the user's Hermes workspace via the registry.

**Docs everywhere; tools by role.** Documentation is mounted for all users (including admin docs for non-admins, for education); admin/builder tools and skills are **not** mounted for users who lack that role. **One acting identity per session, chosen at launch** — User view → `user`; Builder view → `builder`; Administrator view → `admin` — governing tool mounting + action-context for the whole session; no mid-session role switching. Role-scoped **tool access is consent content, designed in #31**.

## The guided build process (ADR-0024 §3)

A **versioned, first-class skill set** — the Matt Pocock engineering skills (wayfinder/grilling/tdd/code-review/…) **adapted/whitelabelled by the platform** to call the platform's own capabilities (Inference, Eval/ADR-0020, the agentic-development-workflow) — **extended with ML + evaluation best practices** from Shreya Shankar & Hamel Husain (evaluation designed into the build flow, steering to the eval capability). A **human-readable process documentation** teaches the process before the learner uses the skills. Surfaced through the **Development service's `agentic-development-workflow` capability**.

## Onboarding (ADR-0024 §4)

The first-run/initial journey (recap, front-door address, guided tour, datasets opt-in off) including the **backup-passphrase** step — the user is told explicitly to remember it; the hashed passphrase encrypts the per-service backup zips so only the user can decrypt them, and is re-entered on restore (ADR-0021). Lands in the dashboard first-run surface (ADR-0015).

## ADR cross-references

ADR-0002 (service template — the bar is declared there) · 0007 (composition — MAF stays the primitive; Hermes Agent the vendored assistant) · 0008 (registry — the bar's artifacts are indexed + mounted; the `skill` entry) · 0015 (dashboard — first-run surface, assistant access) · 0018 (publishing tiers — mandatory/recommended-with-gaps) · 0019 (applies to published things) · **0024 (this concern's governing ADR — bar, assistant, guided build, onboarding)** · 0021 (backup passphrase).
