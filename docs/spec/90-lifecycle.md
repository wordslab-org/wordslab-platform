# 90 — Lifecycle: installer, updates, backup

> **Status:** drafted at the resolution of wayfinder ticket "Design the backup & recovery story" (#22) — the third and final tri-section piece (installer + updates + backup). Prior sessions deferred the chapter until all three sections had content; with installer (ADR-0014), updates (ADR-0016) and backup (ADR-0021) all settled, the chapter is created now. **Source of truth:** ADR-0014 (installer), ADR-0016 (updates), ADR-0021 (backup), plus the ADRs they realize (0003 core/install, 0004 topology/data locations, 0005 resources/quotas, 0017 security/update-authenticity). This chapter is the **organized build-view** — it cites, never restates.
>
> **Conventions:** Part 1 is the user guide (use cases); Part 2 is the organized build reference (citations). Terms are CONTEXT.md's (data location, data sphere, backup policy, resident launcher, update lane, version).

## Identity

`90-lifecycle.md` is the platform-lifecycle chapter: how a machine is **installed**, how it is **kept up to date**, and how its data is **backed up and restored**. These three describe the ongoing operation of the platform on user machines and share the same maintenance loop (ADR-0013 §2). The chapter's three sections correspond to the three settled tickets: installer (#7 / ADR-0014), updates (#10 / ADR-0016), backup (#22 / ADR-0021).

---

# Part 1 — Use cases (user guide)

## Section A — Installing the platform (from ADR-0014)

### What the user sees and does

- **Windows:** a download button on wordslab.org → a native `.exe`, no command line. **Linux:** `curl https://wordslab.org/install.sh | bash`. Both open the same guided journey; nothing is installed silently.
- The install is **phased**: a native C# console → a Python TUI (streaming installer API) → a **web UI** (the dashboard's S0 install phase) once the core + dashboard are up. On completion the dashboard hosts the rest of the install (the core's `install` capability).
- A **recap** ends the install: everything installed and running, the front-door address (`wordslab.local`), and a short guided tour deferring to its chapters — how updates work, how data is secured, **how backups run**. Anonymous datasets are opt-in, off by default. (This is where the backup story is first explained to a non-technical user.)
- **Data locations:** the wizard lists each physical disk (name, free space, measured speed) and defaults to one recommended location, with an explicit "add another disk" creating a **data volume named after the disk**. Roles are folders inside volumes (`models/`, `workspace/`, per-service data); software lives in the distro filesystem. Adding a disk remains possible anytime from the launcher/dashboard.
- **Update/Repair re-run:** a machine that already has the platform presents two clear, non-destructive paths — **Update** (default; updates bootstrap + core in place, data volumes untouched) vs **Repair / clean reinstall** (separate, guarded; recreates software, explicitly keeps the data volumes). **Invariant: an update never touches the data volumes.**
- **Join:** to make this machine a worker, install-then-join — the leader dashboard "Add a machine" finds LAN candidates (mDNS, manual fallback), the worker installs the platform on itself first, then a short type-in **join code** (e.g. `AKR67`) issues its machine identity key. Workers are lean (only the non-core services their chosen activities need).

### Representative use cases

1. **"Install Wordslab on my computer"** (new user) — download → guided install → data location chosen → recap (address, updates, security, backup) → first-run welcome. Supporting: installer (ADR-0014), core `install` (0003), data locations (0004).
2. **"Add a second machine / disk"** — install a worker and join it to the leader, or add another data location anytime. Supporting: ADR-0014 §5/§9.
3. **"Repair my platform without losing data"** — run the guarded Repair path; data volumes are preserved. Supporting: ADR-0014 §7.

## Section B — Keeping the platform up to date (from ADR-0016)

### What the user sees and does

- **Two update lanes**, presented at first-run and in the dashboard's **Install & Updates** surface (leader-only):
  - **Tier 1 — frequent & automatic:** implementations (new models, harness images) — additive, side-effect-free. (Automatic here means *delivered to the list*, not auto-applied.)
  - **Tier 2 + 3 — infrequent & user-chosen:** services + core + bootstrap, updated as one consistent **platform bundle**.
- **No automatic update in any tier.** Both behaviors are **user-triggered and one-click** — they differ in cadence and coordination, not autonomy (the "no automatic anything" rule, ADR-0016 §0).
- A **centralized updates list** (leader-stored, persistent) shows installed-vs-available with a **dependency-satisfaction verdict**; an item is removed when acted on or superseded. Updates are applied **individually, at the user's own pace**.

### Representative use cases

1. **"Check what's new and update"** — browse the centralized list, see the verdict, apply one-click. Supporting: update flow (ADR-0016), catalog + Install & Updates (0003/0014).
2. **"Roll back a bad update"** — the previous consistency unit (implementation version / whole bundle) is restored. Supporting: ADR-0016 §(rollback), retention = current + one-previous.
3. **"Update at my own pace"** — Tier 1 items sit in the list until the user acts; no silent change. Supporting: ADR-0016.

## Section C — Backing up & restoring data (from ADR-0021)

### What the user sees and does

- **Backup is per data sphere** (user / builder / admin — the three identities of a physical user). The **admin is compelled to configure a backup policy + target for each sphere at install**, then backups run **automatically**:
  - **Full** every ~20h of cumulative uptime, **incremental** every ~1h, **keep 5 fulls** → you can restore to any point within the last ~100h of uptime (≈ up to a month at home). Cadence is by **uptime**, not wall-clock, so an often-off home machine still loses at most a few hours of work.
  - A **same-disk target is allowed to start** (guards against mistakes/deletions), but a reminder shows at every platform start until an off-disk target is configured.
- **Every service UI** shows an easy **"back up my data now"** and **"restore to an earlier point"** for the current user — where the user works, not hidden in an admin dashboard.
- **What's backed up:** all user-generated + authoritative data (workspaces, session history, documents, knowledge, agent memory, admin config + change history + metrics). **Not backed up:** model weights and reinstallable software (re-download/reinstall).
- **Builder data** backs up primarily by **pushing to GitHub + HuggingFace** (with a local-directory mirror for unpublished work). **User data** backs up as **per-service encrypted zips** (encrypted with the user's backup passphrase). **Admin data** is encrypted with a strong admin passphrase (it holds API keys).

### Representative use cases

1. **"Make sure I never lose my data"** (first-run) — the recap explains the backup story; the admin sets the per-sphere policy + target. Supporting: backup (ADR-0021), installer recap (0014).
2. **"Get my work back after a mistake"** — from a service's UI, restore the current user's data to a previous point in time (hourly recovery points). Supporting: ADR-0021 §7/§9.
3. **"Move my data to a new install"** — back up from one installation and restore to another that provides the same services; enter the same backup passphrase, point at the target, restore. Supporting: ADR-0021 §7 (portability, service metadata in each zip).
4. **"Recover after the leader dies"** — restore the admin sphere → the new leader returns as the **same** platform in minutes (vs the hour-scale guided rebuild). Supporting: ADR-0004 §1, ADR-0021 §7.

---

# Part 2 — Build spec (organized reference + citations)

## Section A — Installer (ADR-0014)

- **Two Windows executables:** installer (download-button `.exe`, webview, opens dashboard, leaves a **resident launcher**) + resident launcher (on every machine; start/stop/update/monitor/**backup** locally or remotely; machine registry seeded from leader catalog; front door owns the one address). (ADR-0014 §3/§4.)
- **Phased install:** native C# console → Python TUI (streaming installer API over stdout/stderr) → web UI once core + dashboard up (dashboard = rest-of-install, the core `install` capability). (ADR-0014 §3.)
- **Three machine roles:** client command center / leader / worker (leader or worker, never both; client = extra role). (ADR-0014 §2.)
- **Data locations:** default one disk + "add another disk" per-disk volume; **roles are folders not volumes**; add-later live from launcher. (ADR-0014 §5; ADR-0004 §8.)
- **Update/backup-savvy install:** two update lanes (frequent-automatic models/harnesses vs user-chosen consistent bundles); **Update vs Repair** (data-preserving). (ADR-0014 §6/§7.)
- **Join:** install-then-join + short type-in code (e.g. `AKR67`). (ADR-0014 §9.)
- **First-run recap:** installed/running + front-door address + guided tour deferring to chapters (updates, security, backup; datasets opt-in off). (ADR-0014 §8.)

## Section B — Updates (ADR-0016)

- **Three version tiers, each versioned by what it is:** date-based platform bundle `2026-07` / semver services / artifact-own-version implementations, on a **capability-API-version** substrate (required + optional features; major = required-set change). (ADR-0016 §1.)
- **Compatibility = declared dependencies** (per-capability minimum version + required optional features, checked as a satisfy relation across the graph); seamless update iff it preserves its target; target change = bundled. (ADR-0016 §2.)
- **No automatic anything — both behaviors one-click** (Tier 1 frequent/safe, Tier 2+3 bundled). (ADR-0016 §0.)
- **Two-part package** (metadata → checks → implementation, no GB for nothing). (ADR-0016.)
- **Centralized updates list** (persistent, leader-stored, removed on act/supersede); catalog + Install & Updates leader-only, showing installed-vs-available + dependency-satisfaction verdict. (ADR-0016.)
- **Rollback** = previous consistency unit (impl version / whole bundle); core self-updates only in the bundle, auto-reverts on failed restart; retention = current + one-previous, automatic-on-verified-replace. (ADR-0016.)
- **Update authenticity** per ADR-0017 (own code signed+checksummed; third-party audited scan + 1-week gate) — consumed, not re-decided. (ADR-0016, ADR-0017.)

## Section C — Backup & recovery (ADR-0021)

- **Organizing principle — data spheres:** backup is **per sphere** (user / builder / admin); a physical user has **three identities** (`laurent` / `laurent-builder` / `laurent-admin`). Every datum is linked to an identity + role (attribution model — folded into #31). (ADR-0021 §1.)
- **What's backed up:** all user-generated + authoritative data across services; **excluded** are model weights and reinstallable software (re-download/reinstall). (ADR-0021 §2.)
- **Per-user extraction:** service storage must be **designed for per-user export + true incremental from the start** (DB builtins can't be used — they'd capture every user and defeat per-user encryption/restore). A **service-template constraint** (amends ADR-0002). (ADR-0021 §3.)
- **Where (per sphere):**
  - **User sphere:** per-service encrypted zips; target chosen by that user (external disk / another machine's `workspace/` / cloud = a data location; no shared storage). (ADR-0021 §4.)
  - **Builder sphere:** GitHub + HuggingFace push (primary) + local-directory mirror (unpublished work, GitHub-down days); **not encrypted** (auditability, LAN-open). (ADR-0021 §4.)
  - **Admin sphere:** config + change history + metrics/errors; target chosen by the admin. (ADR-0021 §4.)
- **How/when:** admin **compelled to configure policy + target per sphere at install** (same-disk allowed to start + persistent UI reminder until off-disk); then **automatic** by **cumulative uptime** — full every 20h, true-incremental every 1h, keep 5 fulls ⇒ hourly recovery points over the last ~100h of uptime. Fulls exist for restore performance/robustness (cap the incremental chain at 19 files), not data safety. (ADR-0021 §5.)
- **Encryption:** user zips keyed by a **user-chosen backup passphrase** (entered at onboarding — see #29; hashed, hash stored = the key; independent of login; portable to a new install). Builder backups **not encrypted**. Admin backups **encrypted with a strong admin passphrase** (hold API keys). We don't defend against a skilled malicious admin at home (ADR-0017 threat model). (ADR-0021 §6.)
- **Restore:** per-service or as a whole, in the context of a **user+role**, for every sphere; **the backup/restore story IS the disaster-recovery story** (no separate flow). **Portable** to another installation providing the same services; each zip carries **service metadata (version + capabilities)** for verification. Admin-sphere restore returns a new leader to the same platform in **minutes**. (ADR-0021 §7.)
- **Core `backup` capability** (sharpens ADR-0003): orchestrates per-service backup/restore through each service's per-user export/restore surface; owns the platform-wide per-sphere policy + cumulative-uptime cadence + dashboard surfaces; backup data storage stays per-service (not centralized). The **resident launcher's Backup trigger** routes to the same policy. (ADR-0021 §8.)
- **Every service UI** exposes **on-demand backup + point-in-time restore** for the current user (near-free — same capability the orchestration calls). (ADR-0021 §9.)
- **Relation to #31:** backup copies each sphere as-is; #31 governs how data moves between spheres (filter+anonymize boundary). User backups encrypted → never cross spheres; builder backups non-personal → no GDPR obligation. (ADR-0021 §10.)
