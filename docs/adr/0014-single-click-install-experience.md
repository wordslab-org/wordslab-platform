# ADR-0014 — The single-click install experience (installer, resident launcher, machine roles)

**Status:** accepted (resolution of wayfinder ticket "Design the single-click installer", #7); **amends none**; **shapes the `90-lifecycle.md` spec chapter (now `20-concerns/25-lifecycle-and-updates.md` in the architecture doc)** (installer section; ADR-0013 §2); **expands ticket "Design the update & versioning flow" (#10)** with the frequency-driven version taxonomy.

## Context

The map's soul demands the product's first experience be **familiar, guided, transparent and fully-decisioned** — no command line, no black box, every change explained and reversible. ADRs 0003/0004/0005 settled the two-layer mechanics the install *presents* (bootstrap + core `install` capability, two-layer installation, data locations, front door, join flow, resource fit-gating). This ADR decides the **user-facing install experience** on top of them — the entry points, the phased wizard, the machine roles, the two Windows executables, and the resident launcher that becomes the user's command center. It deliberately does **not** re-decide the layers, topology, or resource model.

## Decision

### 1. Machine roles (three, two orthogonal axes)

- **Client machine** — the user's remote **command center**: where the install is launched and from where the user **starts / uses / stops / updates / monitors / backs up** the leader and worker machines. Runs the **resident launcher** (below). v1: **Windows desktop only** (macOS, Linux desktop later).
- **Leader machine** — hosts the platform core + dashboard + front door.
- **Worker machine** — joins the platform; hosts the services/implementations its activities need.

**A machine is either leader or worker — never both** (one core per machine, role at install/join, ADR-0003). *Client* is an **additional role any machine can play**, orthogonal to leader/worker: a machine is (leader **or** worker) **and optionally** client. Common cases: one Windows PC as all three; a gamer PC (leader) + light laptop (client); a laptop (client) + rented cloud VM (leader).

### 2. The two Windows executables

The install produces **two distinct executables** — the familiar "installer leaves an app you pin to the taskbar":

1. **The installer** (downloaded `.exe`): self-contained; runs the guided install; **renders the web-UI phase in an embedded webview**; on completion **opens the dashboard in the browser itself** (no copy/paste) and **leaves the resident launcher behind**.
2. **The resident launcher** — see §4.

### 3. The guided install — a phased progression (one journey, three UIs in sequence)

The install **hands off three times**, everything visible at each stage; the wizard carries exactly the **bootstrap** (WSL → uv/Python → network reachability → data volumes → first platform core → front door), then hands the rest to the web:

1. **Phase 1 — native, before Python** (Windows `.exe`/`.bat` + PowerShell; Linux `bash`). On Windows a thin **C# console wizard** collects the initial parameters, then runs the first native scripts and **mirrors their text output** until Python is installed.
2. **Phase 2 — Python TUI, once Python (via `uv`) exists:** all install scripts become **Python**. A small, solid **installer API** wraps every command-line install (run, **stream stdout/stderr**, interpret the logs, render progress as lines are found). The **Python TUI renders the install wizard** on top, with **careful inline guidance for how to use the text UI** at each step (essential when SSH'd into a VM). The numbered bootstrap scripts remain visible/runnable beneath (transparency, no magic).
3. **Phase 3 — web UI, as soon as the platform core + dashboard are up:** the web UI takes over for the **rest of the install** (installing/updating services, capabilities, activities is a **dashboard function** — the core's `install` capability — not the wizard's). **Windows:** installer webview, then opens the browser to the dashboard URL. **Remote/SSH (no local browser):** the TUI's final act prints the reachable URL for the user to open elsewhere. The handoff is **an address, not a process switch** — the web UI is served by the core and reached by an address.

### 4. The resident launcher — the client's command center

**Installed on every machine** — client-only, and leader/worker machines too — with a **UI only on Windows** (headless/remote on Linux). It is the single surface to **start / stop / update / monitor / backup** the platform, either **locally** (on a leader/worker box, controlling this machine's platform) or **remotely** (any other machine). On **Start** it opens the **web dashboard in the browser**; the launcher is the machine-lifecycle + connect surface, all deep management lives in the dashboard.

- **Start**, by where the leader lives: **this machine** (run WSL + platform, open `wordslab.local`/localhost) · **cloud VM** (launch via provider API → SSH → start → open remote URL) · **separate Windows machine on the LAN** (its own launcher starts WSL + platform; this launcher detects it on the LAN and opens its dashboard).
- **Wake (remote):** a **Wake-on-LAN** wake packet brings a sleeping/off LAN machine back up into a state where its **auto-starting launcher boots the platform** — the client does the *waking*, no user needed at the target. **Physical power** for local machines stays manual (the user presses the button in the physical world); **cloud VMs are controlled via provider APIs**. WoL is a remote-wake extra, not a substitute for physical power.
- **Stop / Restart / Update / Monitor / Backup** the leader and worker machines (backup trigger → #22).
- **Manage data locations** — add a disk / data volume anytime (physical disk added, or a rented cloud disk when out of space); the core's `resources` capability provisions it.

**Machine registry** — the launcher's "where is everything": a small config with three entry kinds — **this machine** / **LAN machine** (mDNS-detected, WoL) / **cloud machine** (holds **provider API credentials** in the client's secure store + instance id). The **front door** still provides the one address + one cert once reachable; the **launcher owns reachability & power, the front door owns the single address**. The registry **follows the platform**: it is **seeded from the leader's catalog** (every machine the leader tracks is importable into any client launcher), the local install adds "this machine" automatically, and a **manual add** is needed only for the very first connection before any platform is reachable.

### 5. Data locations — a live surface, not an install-time step

At install the wizard lists each physical disk (name, free space, measured speed) and **defaults to one recommended location**, with an explicit "add another disk" that creates a **data volume named after the disk**. **Roles are folders inside volumes, never separate volumes per function** — `models/`, `workspace/`, per-service data are directories within a data location; software lives in the distro filesystem (ADR-0004 §8, no specialization). Adding a disk/data volume **remains possible later, anytime, from the launcher/dashboard** (e.g. after adding a physical disk, or renting a cloud disk when out of space).

### 6. Install principles (bake update/backup in)

The install is designed from the start for the update/repair and backup/restore story: **installed-to-be-updatable** (layout leaves clean update paths), **no endless version accumulation** (old versions pruned), **backward compatibility** (apps built on the platform keep running across updates). The first-run presents **two update lanes** — **frequent & automatic** (implementations: new models, harness images — additive, side-effect-free) vs **infrequent & user-chosen** (services + core + bootstrap, updated as one consistent bundle). *(The taxonomy and policy detail belong to #10; the install presents the lanes.)*

### 7. Entry & re-run

- **Windows:** a download button on wordslab.org → native `.exe`, no command line. **Linux:** `curl https://wordslab.org/install.sh | bash`. Both open the same guided journey. Nothing installed silently.
- **Re-run (machine already has the platform):** two clear, non-destructive paths — **Update** (default; updates bootstrap + core in place, data volumes untouched) vs **Repair / clean reinstall** (separate, clearly-labelled, guarded; recreates software and explicitly states it **keeps the data volumes**). **Invariant: an update never touches the data volumes.**

### 8. First-run experience ("Welcome to Wordslab Platform")

After install: a **recap of everything installed and running**; the **front-door address** (`wordslab.local`); a **short guided tour** that *defers* to its chapter — one-line pointers to how updates work (two lanes), how data is secured (#14), how backups run (#22); **anonymous datasets opt-in, off by default** (ADR-0003 `datasets`). First-run promises and locates the transparency; the depth lives in each chapter.

### 9. Join (install-then-join)

**B1** Leader dashboard → **"Add a machine"** → finds LAN candidates by mDNS (manual fallback). **B2** The worker **installs the platform on itself first** (same entry point; its own core + front door) **before it can join**. **B3** A **short, short-lived, type-in join code** (e.g. `AKR67`) shown on the **leader dashboard**, typed into the candidate. **B4** The leader issues a **machine identity key** → the machine is part of the platform (ADR-0003). **B5** **Lean worker:** only the non-core services its chosen **activities** need, gated by **fit** (local implementation only if the smallest supported one fits; else cloud-only there); the rest of the journey continues on the **leader dashboard**, which walks the user into choosing activities.

### 10. Cloud path (fully designed in v1)

The rented-VM journey is driven from the Windows client (works for a cloud leader or worker; a single-node cloud platform's core is the leader): **C0** provider + instance selection (Runpod/JarvisLabs/Vast.ai/generic VPS) sized to the v1 configuration; launcher holds the **provider API key**. **C1** VM creation **automated where the provider's API allows** (SSH access), guided manual steps with illustrations otherwise. **C2** **Overlay first — no public ports, ever** (Tailscale default / self-hosted WireGuard choice); install/join complete over the overlay so no join code or key is exposed to the internet. **C3** Install over SSH in the **TUI** (`curl | bash` → the same guided journey). **C4** Role: first machine → leader (completes Path A); joining → worker via join code. **C5** The VM reports its reachable address; the launcher gets the **remote URL** and adds it to its registry; **Start** = launch VM → SSH → start → open remote dashboard. **C6** **Privacy surfaced**: the wizard warns on a `local` implementation placed on a cloud node; a cloud leader means users/secrets/logs live on the rented box (ADR-0004 §7). **C7** Updates follow the same two lanes; a rented cloud disk can be added later.

## Considered options

- **Single silent `.bat` that does everything vs a launcher → guided wizard** — a silent everything-in-one install is a black box; the soul wants no command line and every decision surfaced. Chose the launcher → guided wizard.
- **Two parallel renderers (GUI + TUI from one wizard model) vs a phased progression** — a shared declarative step model with two renderers duplicates complexity; the install *naturally* moves from native → Python → web as components become available. Chose the **phased progression**.
- **Download-button native installer on Windows (chosen) vs a command-line `.bat`** — the soul is a non-technical audience; the `.bat`-only entry is the notebooks pattern and is not familiar enough.
- **Data locations: per-disk volumes with roles-as-folders, defaulted + add-later (chosen) vs forced multi-disk choice vs specialized per-role volumes** — forced choice burdens the beginner; specialized volumes are inflexible and break uv sharing (already rejected by ADR-0004 §8). Default + add-later keeps it decisioned-but-not-forced and live.
- **Launcher on every machine, UI only on Windows (chosen) vs launcher only on client machines** — a single launcher everywhere (headless on Linux) gives one consistent command-center surface and lets a leader/worker box control itself or be controlled remotely; a client-only launcher leaves leader/worker boxes with no local control surface.
- **WoL wake as a remote extra, physical power stays manual, cloud via provider APIs (chosen) vs full remote power control everywhere** — physical power can't be automated on local machines; honesty about that boundary (the soul) beats pretending the launcher controls the power button.

## Consequences

- **Shapes the `90-lifecycle.md` spec chapter (now `20-concerns/25-lifecycle-and-updates.md`)** (installer section) — to be filled when the spec chapter is created (ADR-0013 maintenance loop; deferred this session per Laurent).
- **Expands "Design the update & versioning flow" (#10)** — the frequency-driven version taxonomy (three tiers: implementations / services / core+bootstrap; two behaviors: frequent-automatic vs infrequent-user-chosen-consistent-bundle; no-accumulation + backward-compat) is recorded in #10's body.
- **Feeds** "Design the integrated UI (dashboard)" (#8 — the web install UI, the dashboard as the rest-of-install surface, storage view), "Define the security model for the trusted home environment" (#14 — client-machine firewall/WSL-bridging mechanics, provider credential storage on the client, local CA on clients), "Design the backup & recovery story" (#22 — launcher backup trigger, backup isolation of `workspace/`), the update flow (#10 — the two-lane presentation), "Design the inference provider model" (#19 — provider APIs for cloud VM automation + credentials).
- **Reference prototype:** `docs/prototypes/installer-flow.md` (markdown screen-by-screen outline; the artifact this resolution reacts to).
- **Glossary (CONTEXT.md):** "client machine" (additional role any machine can play), "resident launcher", "installer (two Windows executables)". Machine, leader/worker core, front door, data location, bootstrap layer, join code, machine identity key already exist.
