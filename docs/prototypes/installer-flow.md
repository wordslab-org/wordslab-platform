# Prototype — the single-click installer flow (issue #7)

> **PROTOTYPE — throwaway, for reaction only.** A rough screen-by-screen outline of the *install experience* for `wordslab-platform`. It reworks the proven `wordslab-notebooks` installer pattern into the guided, transparent experience the soul demands. It **incorporates** the settled mechanics from the closed tickets (#9/#6/#4 — ADRs 0003/0004/0005); it does **not** re-decide them. Nothing here is authoritative until Laurent confirms shared understanding.

## Machine roles (settled here, #7)

Three kinds of machine, each a *role in a given interaction* — **one physical machine can play several**:

- **Client machine** — the user's remote **command center**: where the user launches the install, and from where they **start / use / stop / update / monitor** the leader and worker machines. Runs the **resident launcher** (below). v1: **Windows desktop only** (future: macOS, Linux desktop).
- **Leader machine** — hosts the platform core + dashboard + front door. v1: **Linux & NVIDIA stack only** (incl. Linux in WSL) (future: macOS & MLX).
- **Worker machine** — joins the platform, hosts the services/implementations its activities need. Same v1 stack as leader.

**A machine is either leader or worker — never both.** *Client* is an **additional role any machine can play** (its user-side command-center face), orthogonal to leader/worker: a machine is (leader **or** worker) **and optionally** client.

Common cases:
- **All one machine** — the user's Windows PC is simultaneously client, leader, and (alone) the whole platform.
- **Windows gamer PC = leader; light laptop = client** — the laptop's launcher starts/stops the gamer PC (power on, launch the resident there → WSL + platform), then the laptop detects the leader on the LAN and opens its dashboard.
- **Client laptop + rented cloud VM = leader** — the launcher starts the VM via the provider API, SSHes in, launches the platform there, and opens the remote dashboard.

## The two Windows executables

The install on Windows produces **two distinct executables** — the familiar "installer leaves an app you can pin to the taskbar":

1. **The installer** (downloaded `.exe`, e.g. from wordslab.org): self-contained; runs the guided install; **displays the web-UI phase of the install in an embedded webview**; on completion **leaves the resident launcher behind**.
2. **The resident launcher** (installed by the installer; also on leader/worker machines when they're Windows): a friendly GUI to **start / stop / connect / update / monitor** the leader and worker machines. On **Start** it opens the **web dashboard in the user's browser** — the launcher is the machine-lifecycle + connect surface only; all deep management happens in the dashboard.

---

## Entry points

The user's journey starts on the **client machine**. From there the install branches depending on what this machine is and where the leader will live:

- **Client-only command center** (laptop against a remote/cloud leader): install the launcher, configure it with the leader (LAN or cloud API), done.
- **Client that is also the leader** (common Windows case): install the launcher, then continue into the platform bootstrap on this machine (Path A below).
- **Standalone worker / rented VM**: the platform install (Path A/B), reached via the leader dashboard.

---

## Install principles (bake the future in)

The install is designed **from the start for the update/repair and backup/restore story**, so it never paints us into a corner:

- **Installed to be updatable** — layout/versioning leaves clean update paths (bootstrap/core vs services vs implementations).
- **No endless version accumulation** — updates don't pile up disk; old versions are pruned (mechanics → #10).
- **Backward compatibility** — applications already built on the platform keep running across updates (→ #10's backward-compat story).
- **Frequency-driven update UX** — the install/first-run present **two update lanes**: **frequent & automatic** (implementations: new models, harness images — additive, side-effect-free, seamless) vs **infrequent & user-chosen** (services + core + bootstrap, updated as one consistent dependency bundle). *(Mechanics of the taxonomy and the policy belong to #10; the install presents the lanes.)*

---

## Path A — install the platform on a leader (local, or as the client's target)

### A0. The entry
- **Windows:** download button on wordslab.org → native `.exe` → the installer. No command line.
- **Native Linux:** `curl https://wordslab.org/install.sh | bash` → same journey in a Terminal UI (essential when SSH'd into a rented VM).
- The entry checks OS/prereqs (WSL2 on Windows, GPU), installs WSL + deps if needed, and opens the wizard. **Nothing installed silently.**
- **When the machine already has the platform** (re-run): the entry offers two clear, non-destructive paths —
  - **Update the platform** (default): detects the existing install, updates the bootstrap + core in place, **data volumes untouched**.
  - **Repair / clean reinstall** (separate, clearly-labelled, guarded): recreates the distro/software, and explicitly states it **keeps your data volumes** (`models/`, `workspace/` untouched) — it never conflates "update" with "wipe."
  - **Invariant: an update never touches the data volumes.** (The update *mechanics* — bootstrap vs core/service update lanes — are ADR-0003's, designed in #10; here we shape the experience.)

### A1. Welcome
- The transparency promise: *nothing happens without your approval; every change is shown and reversible.*

### A2. Machine role & hardware
- The wizard detects CPU/RAM/GPU/disks and maps to the **v1 configuration** (no-GPU cloud-only vs GPU small/middle/big), recommending the fit in plain words.
- Confirms this machine's role(s): is it the **leader**, a **client command center**, both, or a **worker** joining an existing platform?

### A3. Where your data lives (multi-disk / data locations)
- Lists each physical disk (name, free space, measured speed). **Default: one recommended location**; "add another disk" adds a **data volume named after the disk**. **Roles are folders inside volumes, not separate volumes per function** — `models/`, `workspace/`, per-service data are directories within a data location (software lives in the distro filesystem) — flexible and never specialized (ADR-0004).
- **Not just at install:** adding a disk / data volume stays possible **later, anytime, from the resident launcher / dashboard** — e.g. a month in, after adding a physical disk, or when out of space on the current volume and renting a cloud disk. The data-location story is a live management surface, not a one-time install step.

### A4. Full transparency recap
- Every machine change listed *before* it happens (WSL, uv/Python, network checks, platform core, front door, data volumes). **Continue / Back.**

### A5. Guided install — a phased progression (one journey, three UIs in sequence)
The install **hands off three times**, everything visible at each stage:

1. **Phase 1 — native, before Python** (Windows `.exe`/`.bat` + PowerShell; Linux `bash`):
   - Windows: a thin **C# console wizard** collects the initial install parameters, then runs the first native scripts and **mirrors their text output** until Python is installed.
2. **Phase 2 — Python TUI, once Python (via `uv`) exists:** all install scripts become **Python**. A small, solid **installer API** wraps every command-line install (run, stream stdout/stderr, interpret the logs, render progress as lines are found). The **Python TUI renders the install wizard** on top. On Windows the installer keeps showing this window — now rendering the Python TUI, with **careful inline guidance for how to use the text UI** at each step.
3. **Phase 3 — web UI, as soon as the platform core + dashboard are up:** the web UI takes over for **the rest of the install**. From here on, installing/updating services, capabilities, and activities is a **dashboard function** (the core's `install` capability, ADR-0003), not the wizard's job.
   - **Windows:** the installer executable renders this phase in an **embedded webview**, then **opens the browser to the dashboard URL itself** — no copy/paste.
   - **Remote/SSH (no local browser):** the TUI's final act prints the reachable URL and tells the user to open it from their own machine. The web install UI is **served by the core and reached by an address**; the handoff is an address, not a process switch.

The wizard therefore carries exactly the **bootstrap** (WSL → uv/Python → network reachability → data volumes → first platform core → front door), then hands the rest to the web. The numbered bootstrap scripts remain visible/runnable beneath both text phases (transparency, no magic).

### A6. First leader account
- Create the **first admin account**. This machine is the **leader**.

### A7. Provisioning (ADR-0005)
- The core's `resources` capability seeds the reservation ledger and provisions standard folders + default quotas (models quota per data location, per-service folder default, user workspace quota).

### A8. First-run — "Welcome to Wordslab Platform"
- **Recap of everything installed and running.** **Your address** — the front door (`wordslab.local`). A **short guided tour** that *defer*s to its chapter:
  - **How you're kept up to date** — a one-liner: *new models and harnesses update themselves automatically; services and the platform update together only when you choose.* (Mechanics → #10.)
  - **How your data is secured** → the security chapter (#14).
  - **How backups run** → the backup chapter (#22).
  - Datasets **opt-in, off by default** (ADR-0003 `datasets`).
- The depth of each lives in its chapter; first-run only promises and locates them.

### A9. Hand over to the resident launcher + dashboard
- The installer installs the **resident launcher**, then opens the dashboard (below).

---

## The resident launcher — the client's command center

**The client launcher is installed on every machine** — client-only machines, and leader/worker machines too — with a **UI only on Windows** (on Linux it's headless/remote). It is the single surface to **start / stop / update / monitor / backup** the platform, either:
- **Locally** on the current machine (on a leader/worker box, it controls this machine's platform), or
- **Remotely** for any other machine.

Actions, dispatching by target:
- **Start** — opens the dashboard in the browser, by where the leader lives:
  - **This machine:** start WSL → start the platform → open `http://wordslab.local` (or localhost).
  - **Cloud VM:** launch the VM via the provider API → SSH in → start the platform there → open the remote dashboard URL.
  - **Separate Windows machine on the LAN:** the leader's own launcher starts WSL + the platform; this client's launcher **detects it on the LAN** and opens its dashboard.
- **Wake (remote machines):** a **Wake-on-LAN** wake packet brings a sleeping/off LAN machine back up into a state where its auto-starting launcher boots the platform — the client does the *waking*; the leader/worker's launcher then just comes up and runs the platform, no user needed there.
- **Physical power:** local machines still need **electrical start/stop by the user in the physical world** (press the button); **cloud VMs are controlled via the provider APIs**. WoL is a cool remote-wake extra, not a substitute for physical power.
- **Stop / Restart / Update / Monitor / Backup** the leader and worker machines (backup trigger → #22).
- **Manage data locations** — add a disk / data volume anytime (physical disk added, or a rented cloud disk when out of space); the core's `resources` capability provisions it. The ongoing face of the A3 decision.

**Machine registry (the launcher's "where is everything"):** a small config the launcher manages, with three entry kinds —
- **This machine** (leader is local): Start = run WSL + platform, open `wordslab.local`/localhost.
- **LAN machine** (leader is a `wordslab.local` peer): detected via mDNS; Start = Wake-on-LAN power-on, open the front door.
- **Cloud machine** (leader is a rented VM): the launcher holds the **provider API credentials** (in the client's secure store) + instance id; Start = launch VM via API → SSH → start platform → open the remote URL.
- The **front door still provides the one address + one cert** once reachable; the launcher owns *reachability & power*, the front door owns *the single address*.
- **The registry follows the platform:** it's **seeded from the leader's catalog** (every machine the leader tracks is importable into any client launcher — the laptop sees the cloud VM and LAN worker automatically once it knows the leader). The local install adds **"this machine"** automatically; a **manual add** is only needed for the very first connection, before any platform is reachable.

---

## Path B — add a machine / worker (ADR-0004 join)

- **B1** Leader dashboard → **"Add a machine"** → finds LAN candidates by mDNS (manual entry fallback).
- **B2** **The worker installs the platform on itself first** — download the installer/entry (same A0 entry point) and complete the bootstrap install (its own platform core + front door) **before it can join**. On a cloud VM that's the same native-Linux install. *(Join is install-then-join, not just "open a page.")*
- **B3** **Join code** — a **short, short-lived, type-in code** (e.g. `AKR67`) shown on the **leader dashboard**, typed into the candidate to request the join.
- **B4** The leader issues a **machine identity key** → the machine is part of the platform (ADR-0003 trust model).
- **B5** **Lean worker:** the joined machine gets only the non-core services its chosen **activities** need, gated by **fit** (a local implementation only if the smallest supported one fits; else cloud-only there). The rest of the journey continues on the **leader dashboard**, which walks the user into choosing the worker's activities.
- **B6** **Client machines** reach the dashboard + service UIs through the front door (one hostname, one TLS cert from the local CA, firewall/WSL-bridging mechanics → #14).
- **B7** **Cloud machine** — see **Path C** below (fully prototyped).

---

## Path C — install the platform on a cloud VM (driven from the client command center)

The rented-VM journey, driven from the Windows client (works the same for a cloud **leader** or a cloud **worker**; single-node cloud is the leader, ADR-0004 §1).

- **C0. Provider & machine selection.** From the launcher (or the installer entry): choose a cloud provider (Runpod / JarvisLabs / Vast.ai, or a generic Linux VPS) and an instance type sized to the **v1 configuration** (no-GPU cheap vs GPU small/middle/big). The launcher holds the **provider API key** (client's secure store; also mirrored into the core's `secrets` once a leader exists).
- **C1. VM creation.** **Automated where the provider's API allows** — the launcher's cloud entry calls the provider API (create instance, obtain SSH access). Where the provider has no API, the wizard **guides the manual steps with illustrations** (rework of notebooks' SSH-key registration flow). The user's SSH key is registered with the provider (notebooks' `prepare-client-machine.bat` pattern).
- **C2. Overlay first — before anything else.** The VM joins the **overlay network** (Tailscale default / self-hosted WireGuard option — one guided screen, choice remembered). **No public ports, ever.** The rest of the join/install completes **over the overlay**, so no join code or key is ever exposed to the internet (ADR-0003/0004).
- **C3. Install over SSH in the TUI.** The launcher (or the user directly) SSHes into the VM and runs the **native-Linux install** — `curl https://wordslab.org/install.sh | bash` → the same guided journey in the **Terminal UI**. The TUI is essential here: SSH'd into a VM with no browser, the text wizard is the whole experience. (The wizard's inline "how to use the text UI" guidance matters most on this path.)
- **C4. Role: leader or worker.**
  - **First machine → leader:** single-node platform; a rented no-GPU VPS *is* a whole platform (ADR-0004 §1). Completes Path A.
  - **Joining an existing platform → worker:** complete the join via **join code** (Path B) over the overlay.
- **C5. Front door on the cloud leader.** The VM reports its **reachable address** (the front-door/overlay name). The client's launcher gets the **remote URL**, adds the machine to its **registry** (seeded from the leader's catalog, or manual for the very first connection), and the **Start** button for this machine = launch VM via API → SSH in → start the platform → open the remote dashboard.
- **C6. Privacy surfaced.** If a `local` implementation would be placed on the cloud node, the wizard **warns** ("data leaves your home"); a **cloud leader** means users/secrets/logs live on the rented box — surfaced, never silent (ADR-0004 §7).
- **C7. Updates on the cloud path.** Same two update lanes as anywhere; the overlay makes remote update/repair as smooth as local. A rented cloud **disk can be added later** when out of space (the Q5 live data-location surface).

---

## Artifact & scope
- **Form:** the markdown screen-by-screen outline is the prototype artifact (kept, per the grilling — no HTML click-through). Screen-level mockups of the wizard/TUI/dashboard belong to #8 (dashboard), not here.
- The layers/topology/resource model are settled (ADRs 0003/0004/0005). This is the user-facing **experience** of presenting them.