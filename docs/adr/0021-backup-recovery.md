# ADR-0021 — The backup & recovery story (spheres, cadence, encryption, restore)

**Status:** accepted (resolution of wayfinder ticket "Design the backup & recovery story", #22); **amends none**; **sharpens** ADR-0002 (service template gains a per-user export + incremental storage requirement) and ADR-0003 (the core `backup` capability's orchestration contract); **creates** the `docs/spec/90-lifecycle.md` spec chapter (with ADR-0014 installer and ADR-0016 updates); **feeds** "Design the data consent & handling / GDPR-aware usage-data model" (#31, open — the three-identities attribution model is folded into that ticket as its foundation) and "Design the learning experience" (#29, open — the onboarding experience, including the backup-passphrase step). **Does NOT resolve** #31 or #29.

## Context

The core has a `backup` capability that **orchestrates per-service backup/restore**; backup **data** storage is deliberately **not centralized** (ADR-0003). Recovery is a **guided rebuild** (bootstrap a new leader → workers re-join → services re-register → re-enter users/secrets), hour-scale and acceptable for authority surfaces; **backing up the leader's authority state makes recovery minutes** (ADR-0004 §1). Backup **targets = data locations** (another machine's `workspace/` or an external drive); **no shared/networked storage in v1**; **`workspace/` is the backup-isolation folder** (software reinstallable, models re-downloadable — ADR-0004 §8). **Models are NOT backed up.** The per-user quota model **bounds how much data can be backed up** (ADR-0005). The **resident launcher has a Backup trigger** (start/stop/update/monitor/backup, locally or remotely) and the first-run recap must explain "how backups run" (ADR-0014 §4/§8). **Backup of published apps** is a handoff to this ticket (ADR-0019). The spec chapter is the tri-section **`90-lifecycle.md`** (installer + updates + backup; installer and updates are settled but the chapter file does not yet exist — ADR-0013 §2, ADR-0016 §"Shapes").

Grilling with Laurent reframed the entire ticket around **data spheres** (user / builder / admin) and a **three-identities attribution model** — every datum is linked to an identity and its role. That attribution model is a prerequisite for the data-consent model (#31), so it was **folded into #31 as its foundation** rather than designed here; backup is a clean consumer of it (it backs up each sphere as it exists).

The soul shapes every decision: **no magic, no black box** — backup must be understandable and controllable by a non-technical user. The "no automatic anything" stance (ADR-0016) is reconciled here by making the automation **chosen and configured up front** (compelled policy at install) rather than hidden: it is *chosen* automation, visible and explained, never a silent background process.

## Decision

### 1. Organizing principle — backup per data sphere, not per service

Data is backed up **per sphere**. A physical user has **three identities, one per sphere**: `laurent` (user), `laurent-builder` (builder), `laurent-admin` (admin). Every datum is linked to an identity **and** its role. (This attribution model is folded into #31 as its foundation; backup consumes it.)

- **User sphere** (`laurent`) — the user's own interaction traces with platform services, and documents/images they uploaded. **Private by default**; no other user sees them.
- **Builder sphere** (`laurent-builder`) — everything a user produces *as a builder*: authored workflows/agents/skills, published things, eval datasets/runs, trained models. **Contains no personal/secret data** (the core mediates the user→builder transition, #31). Simulated interactions run **as the builder identity**, so builder traces need **no filter/anonymize** (they are synthetic, never personal).
- **Admin sphere** (`laurent-admin`) — **single**, even if several physical users have admin rights: all configuration for the installed platform core and services, the **history of changes**, performance metrics and errors. **No user data appears in it.**

### 2. What is backed up (and what is not)

**Backed up:** everything **user-generated and authoritative** across services — service databases and data folders (workspaces, session history, document collections, knowledge bases, agent memory), the **admin sphere** (config + change history + metrics/errors), and the **builder sphere** (authored artifacts, eval datasets/runs, trained models). The per-user quota model bounds these volumes (ADR-0005).

**NOT backed up:** **model weights** and **reinstallable software** (the distro, services). Everything that can be downloaded/reinstalled is excluded — re-download/reinstall instead of burning disk on a copy. This matches the backup-isolation folder (`workspace/`) and the ADR-0004 §8 exclusion of reinstallable software.

### 3. Per-user extraction — storage is designed for it

Because backup extracts data **per user** (and per sphere/role), the platform **cannot use a database's builtin whole-DB backup/restore** — that would capture every user at once and defeat the per-user encryption and per-user restore. Service storage must be **designed for per-user export + true incremental from the start**. This is a **service-template constraint** (ADR-0002): every service's data model and storage must support extracting a single user+role's data as a self-contained unit and applying incremental deltas to it.

### 4. Where backups live (per sphere)

- **User sphere:** each user's per-service encrypted zip files; **target chosen by that user** — any data location (external disk / another machine's `workspace/` / cloud). A backup target is a data location (ADR-0004 §8); no shared storage.
- **Builder sphere:** **GitHub + HuggingFace push** is the **primary, natural** regular backup for builder artifacts (code, agent definitions, catalog entries, trained/fine-tuned models) — combined with a **local-directory mirror** as the gap-fill (unpublished work, convenience, GitHub-down days). **Not encrypted** — at home and in the open-source context we must be able to **audit how a solution was built**. Not public, but open to anyone on the LAN.
- **Admin sphere:** the admin-sphere backup (config + change history + metrics/errors). Target chosen by the admin.

### 5. How / when — compelled policy, then automatic, by cumulative uptime

**An admin is compelled to configure a backup policy + target for each sphere at install time** (this is what reconciles "no automatic anything" with the backup need: the automation is *chosen and configured up front*, visible, explained in the installer recap). Once configured, backups run **automatically**.

- **Same-disk backup is allowed as a starting policy** (it protects against user mistakes and deletions, not disk loss), but a **reminder is displayed in the platform UI at every platform start** until a proper off-disk policy (a distinct target) is in place.
- **Cadence is by cumulative uptime, not wall-clock** — a home machine is often off, so a scheduled backup would silently miss; a cumulative-uptime schedule guarantees the user loses **at most X hours of work**. Policy:
  - **Full** every **20 hours of cumulative uptime** (≈ ≤1 week at home),
  - **True incremental** (since the last backup) every **1 hour of cumulative uptime**,
  - **Keep 5 full backups** ⇒ recovery points to the state **every hour across the last 100 hours of uptime** (≈ ≤1 month).
- **The full every 20h is kept for restore performance and chain robustness, not data safety** (the hourlies provide the data-safety recovery points). It caps the incremental chain at 19 files to restore (1 full + up to 19 hourlies) — fast and robust. A coarser full cadence would mean many more files to apply and a single corrupt incremental would kill everything after it; a finer one costs more storage for no home-scale benefit.

### 6. Encryption, per sphere

- **User sphere:** each user's backups are encrypted with a key derived from a **user-chosen backup passphrase**. The passphrase is **entered at onboarding** (see #29), the user is told they must remember it — it encrypts their backups so only they can decrypt them. The passphrase is **hashed**; the **hash is stored and used as the key** to encrypt the per-service zip files. It is **independent of the login passphrase** (a login change never orphans backups). Because it is passphrase-derived, it is **portable and disaster-recoverable**: on a new platform the user enters the same passphrase, points at their chosen backup target, and restores from another install — no hidden platform state is needed. The admin cannot easily open a user's backups; we do **not** defend against a skilled malicious admin inside the home (consistent with ADR-0017's anti-theater threat model).
- **Builder sphere:** **not encrypted** (auditability — see §4).
- **Admin sphere:** if it holds the **API keys** used to access external services (it does — the secrets master + service config), it is **encrypted with a strong passphrase known by the admin**.

### 7. Restore — per-service or whole, per user+role; = disaster recovery

Restore granularity is **per-service or as a whole, in the context of a user+role**, for every sphere:

- **User sphere:** restore one service's data (one zip) OR everything for that user across services; point-in-time (hourly recovery points).
- **Builder sphere:** restore from the local mirror at a point-in-time, or re-clone from GitHub/HF.
- **Admin sphere:** restore the platform's configuration + change history + metrics — this is what makes a new leader / recovered machine return as the **same** platform in **minutes** (vs the hour-scale guided rebuild baseline of ADR-0004 §1).

**The backup/restore story IS the disaster-recovery story** — no separate flow. **Portability:** a user can back up from one installation and restore to another **if it provides the same services** (this is why backup is per-service). Each backup zip carries **service metadata (version + capabilities)** so the restore can verify the target service accepts it.

### 8. The core `backup` capability (sharpening ADR-0003)

The core's `backup` capability **orchestrates** per-service backup/restore through each service's per-user export/restore surface (services stay standalone; the core never stores backup data). It owns the **platform-wide policy** (the per-sphere policy + targets configured at install), the **automatic cadence** (cumulative-uptime scheduling), and the **dashboard surfaces** (per-sphere policy view + admin-sphere restore). The **resident launcher's Backup trigger** (ADR-0014) is the machine-lifecycle entry point that routes to the same policy.

### 9. Every service UI exposes backup + restore for the current user

Each service's UI is **mandated to expose an easy way to trigger a backup on demand for the current user, and to restore their data to a previous point in time**. This is **near-free given the design**: per-user export + point-in-time restore is already a required capability every service must expose (the orchestration calls it), so the on-demand trigger and restore are just **surfacing that same capability in the service's own UI**. It also serves the soul — the non-technical user sees "back up my data now" / "restore to an earlier point" where they actually work, not buried in an admin dashboard. The dashboard/core exposes the platform-wide per-sphere policy.

### 10. Relation to #31 (data consent & handling)

#22 backs up each sphere **as it exists**; #31 governs how data **moves between spheres** (the core-mediated filter+anonymize boundary). The two do not conflict:

- **User-sphere backups** hold personal data but are **encrypted with the user's passphrase** — they never cross into a builder's/admin's sphere. No consent/filter/anonymize obligation is created by backup itself.
- **Builder-sphere backups** are **non-personal by construction** (builder identity, synthetic traces), so they carry **no GDPR obligation** and are freely auditable.

The **three-identities attribution model** underpinning all of this is the missing foundation of #31 and is **folded into that ticket** (not resolved here).

## Deferred / folded out

- **`90-lifecycle.md` spec chapter** — created with this ADR (installer + updates + backup tri-section; installer from ADR-0014, updates from ADR-0016, backup from this ADR).
- **Onboarding experience** (where the backup passphrase is entered) → **#29** "Design the learning experience" (expanded to own it).
- **Three-identities attribution model** → **#31** "Design the data consent & handling model" (expanded to own it as its foundation).

## Consequences

- **Sharpens ADR-0002** — the service template must design storage for **per-user export + true incremental**, a first-class constraint (backup cannot use DB builtins).
- **Sharpens ADR-0003** — the core `backup` capability's orchestration contract: policy + cadence + dashboard surfaces; backup data storage remains per-service (not centralized).
- **Realizes** ADR-0004's leader-state restore (admin-sphere backup makes recovery minutes) and the data-location backup-target model; confirms ADR-0004 §8 (models/software not backed up, `workspace/` is the isolation folder).
- **Creates** `docs/spec/90-lifecycle.md` (backup section; installer + updates filled).
- **Feeds** #31 (attribution model as its foundation) and #29 (onboarding experience). Does **NOT** resolve them.
- **Glossary (CONTEXT.md):** add "data sphere" (user / builder / admin), "backup policy", "cumulative-uptime backup cadence". (Terms "data location", "leader core / worker core", "privacy tier", "Data consent & handling model" already exist.)
