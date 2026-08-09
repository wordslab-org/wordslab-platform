# ADR-0004 — Multi-machine topology (discovery, placement, routing, cloud, storage)

**Status:** accepted (resolution of wayfinder ticket "Design the multi-machine topology"); **amends ADR-0001** (family-contract conformance: capability API = union of implementation variants) and **ADR-0002** (implementations layer; heavy-dependency coordination)

## Context

ADR-0003 settled the platform core, the leader/worker role split and the trust model: one core per machine, authority capabilities on the leader, machine identity keys issued at join, an overlay network (WireGuard-based, Tailscale default) for any internet crossing, services fully standalone with the core down. This ADR designs the mechanics on top: how a machine finds and joins the platform, where the leader lives and what happens when it fails, how services and their implementations are installed and placed on machines, how model-backed calls are routed, the cloud as a node, multi-disk storage, cross-boundary access from client machines, and action context across machine boundaries.

Home scenario: 3 gaming PCs — RTX 3070 8 GB / 32 GB RAM, RTX 4090 24 GB / 32 GB RAM, RTX 5090 32 GB / 64 GB RAM — services and implementations distributed across all three. Enterprise scenario: two RTX 6000 Pro 96 GB machines hosting all services "for high availability" — v1 deliberately does **no HA** (simplicity beats correctness-by-the-book). Everything here is cut to the soul of the project: non-technical users who want to understand and stay in control — no magic, no black box, every decision visible and theirs.

## Decision

### 1. Leader placement & failure

- **The first machine's core is the leader** — wherever it is, including a rented cloud machine (a single rented no-GPU VPS *is* a whole single-node platform; its core is the leader). No re-election, no leader migration in v1. The dashboard gently suggests picking the machine you'll leave on most (the leader hosts the dashboard, catalog, secrets, and the front door), but any machine works: the core is control-plane only, never the request path.
- **v1 = single leader, no HA.** No failover, no election, no replica. If the leader machine dies, everything keeps working (services are standalone; worker cores keep monitoring their own machines); only the **authority surfaces** go dark: dashboard login, users/keys/secrets management, new installs, updates, catalog/aggregation views.
- **Recovery = guided rebuild.** Re-run bootstrap on a new leader machine → workers re-join with fresh join codes → services re-register in the catalog → re-create users and re-enter outside-world secrets. Services' own per-service Bearer keys survive untouched (stored/validated by the service itself). Acceptable downtime for authority surfaces: **hours**. "Design the backup & recovery story" (#22) should shorten this via leader-state backup/restore.
- **Enterprise "high availability"** resolves to a normal leader+worker pair: services placed across both machines manually (redundant copies if wanted, switched by hand). Automatic HA/failover is out of v1 scope.

### 2. Discovery & join — leader-dashboard-initiated, guided end to end

Nothing starts standalone on the joining machine; the leader dashboard is the entry point.

- **Onboarding:** website → "Download wordslab platform for Windows" → native graphical installer (bootstrap + core) → dashboard appears showing the rest of the journey. The dashboard first explains multi-machine (what dispatching service instances across machines gives you, local vs cloud tradeoffs, costs), then the user decides.
- **LAN candidate:** the leader's "Add a machine" page (found by mDNS name; typing the leader's name is the manual fallback when discovery is blocked) is opened on the candidate, **auto-collects its hardware** and sends it to the leader; the user confirms on the candidate → guided bootstrap install → join code from the leader dashboard → machine identity key issued.
- **Cloud machine:** join the **overlay first**, then complete the join over it — the public internet never sees a join code or a key. VM creation is automated where the provider's API allows (provider API key in the core's `secrets`); otherwise the dashboard guides the manual steps with illustrations.
- **Client machines** (non-node machines on the LAN) are first-class consumers: they reach the dashboard and service UIs/APIs through the front door (below) — mechanics (firewall ports, WSL→Windows port bridging, HTTPS certs on clients) belong to "Design the single-click installer" (#7) and the security model (#14).

### 3. Two-layer installation

- **Layer 1 — services/capabilities (software):** the **leader gets all services and all capabilities, no questions**. Worker machines get only the non-core services their activities need, installed *as part of the activity installation* — lean workers, disk saved.
- **Layer 2 — implementations:** installed per activity need, gated by fit — a machine gets a capability's local implementation only if **at least the smallest supported local implementation fits** (disk/RAM/VRAM/compute); otherwise that capability is cloud-only on that machine. (A no-GPU machine therefore has every model-backed capability cloud-only — the "no-GPU cheap" configuration, naturally.)
- All services and capabilities software lives in the distro's filesystem (one filesystem → uv package dedup and docker layer sharing work).

### 4. Capabilities, implementations, dependency graph, activities

- **Capability** — what the platform can do (stt, tts, chat, llm inference, document parse, index, search, image generation…), defined by its family contract. **Implementation** — a concrete way to deliver a capability: same problem, different tradeoffs (size/speed/performance, specific data domains or use cases); very similar API, not necessarily identical. **Models are implementations of the llm/vlm capability.** What is downloaded, loaded, unloaded, deleted is always an implementation. Services are autonomous to install an implementation on demand.
- **Implementation resource profile:** disk (install + execution), RAM and/or VRAM (loaded), compute (CPU/GPU) for execution; some requirements scale with a **max capacity** (context length in tokens, batch/concurrency, max document size) which is **capped by machine hardware** at load and can be lowered by user config.
- **Dependency graph:** implementations depend on a general capability (the user picks the implementation) or on a specific implementation; dependencies can be **optional** (e.g. stt for chat); **model-backed capabilities are the special case** of a dependency on an llm/vlm implementation. The graph declares **concurrency** (what must run together vs one-after-another) and **proximity** on edges ("same machine" for realtime/low-latency chains, "LAN-ok" for everything else).
- **Activity** — a pre-configured set of capabilities in a dependency + concurrency graph: the **user-facing install unit** (more than a profile — a real graph). The user selects activities, configures (optional deps, max capacity), and chooses implementations (recommended per hardware + model selection goal); several implementations of a capability can be installed and switched at runtime in the UI.
- **Capability API = the union of its implementation variants** (amends ADR-0001's conformance stance): the family contract documents which implementation supports what; variants are documented, not force-fitted into one identical shape.

### 5. Placement = simulation, user-confirmed, no scheduler

- The **simulation** resolves an activity's graph: pick implementations (recommended per hardware + model selection goal), check fit (per-implementation resource profile, hardware-capped capacity, disk via the storage view), enforce privacy tiers as a hard constraint (`local-only` never lands on cloud nodes), **spread concurrent capabilities across machines** (fleet capacity is the point; proximity edges respected), and offer cloud when nothing local fits — with cost shown.
- **Co-resident = sum, swappable = max:** co-resident capabilities' RAM/VRAM add up on their machine; swappable ones count only as the largest (they share VRAM by load/unload). The one rule that makes "will it fit?" computable and explainable.
- One-click confirm → implementations download/load → the **working set** populates. The working set is the set of loaded implementations of the user's current activities: a live dashboard surface (rendering is #8's, semantics ours), auto-populated by activity launches, auto-cleared by an idle timeout (default ~30 min, per-capability adjustable; **pin** keeps resident), and **manually drivable** — drag an implementation to another machine = move its execution + model load there (download/load on target, unload on source; constraints enforced, refusals explained); delete = unload + free disk.
- The simulation is **re-runnable on demand** as needs or the fleet evolve; it starts from current state and proposes deltas.
- No scheduler, no automatic migration in v1 — moving a service later is reinstall + restore (#22). The recommendation engine is the product's value (managing resource scarcity at home), but it stays greedy and legible: every choice displayable, no hidden solver.

### 6. Model routing

A model-backed call = a dependency on an llm/vlm implementation. **Routing is which loaded implementation serves the call**, chosen by the graph's placement: same machine as the caller first (localhost), else the machine where the working set placed the implementation, least-loaded tiebreak, cloud per the inference policy when nothing local fits. No per-call knob, no hidden load balancer; the routing table is the working set's placement. Every call records "served by: machine · implementation · model" in the action trail. Runtime switching between installed implementations is a per-capability UI choice.

### 7. Cloud as a node

- **Two cloud modes, cleanly split.** A **provider subscription** (inference/tools on provider machines) is *not* a node — it is the cloud-routing leg of the inference policy, machinery in "Design the inference provider model" (#19). A **rented machine** is a first-class node: joins over the overlay like any worker, activities can place implementations on it, it can be the leader in single-node configs. Guidance ladder: cloud-first (provider subscriptions) when no powerful machine; rent a machine as the next step for self-hosting, sensitive data, large-scale processing, or training classic models.
- **Join:** overlay first (Tailscale default, self-hosted WireGuard alternative — one guided screen explaining the tradeoff, choice remembered), then the join code over it. **No public ports, ever.** Any Linux VPS can join (native-Linux path). VM creation automation (provider API key in `secrets`) is a convenience layer for the common providers; guided manual steps otherwise. Provider credentials/billing/quotas = #19.
- **Privacy on cloud nodes:** the simulation **warns on every `local-only` placement on a cloud node** ("data leaves your home"); a cloud leader means users/secrets/logs live on the rented box. Surfaced, never silent.

### 8. Multi-disk = data locations

- **Data locations, named after their disk.** Each machine reports its physical disks; the bootstrap creates one **platform data volume per user-chosen physical disk**, named after that disk (visible — "D:", or the disk's real name; no "volume #2" abstraction). Standard folders inside: `models/`, `workspace/`, plus per-service data folders. **Roles are folders, not disks** — a big HDD can hold models while an NVMe holds workspace.
- **Software lives in the distro only** (one filesystem → uv hardlink dedup, docker layer sharing, models shared by path across services). Service data, DBs and agent workspaces live on data volumes. The dashboard's storage view aggregates machines × data locations; the simulation's disk-fit checks use the same numbers.
- **No shared/networked storage in v1** — each machine's disks are local to it; data lives where its service lives (ADR-0003). Cross-machine movement = backup/restore (#22) or reinstall. Backup isolation: `workspace/` is the folder that needs backup (software reinstallable, models re-downloadable).
- **Workspace environments** (JupyterLab / agent workspaces) install their own Python libraries on their data volume — a second copy, decoupled from the platform version (accepted: more disk, but sandboxed and version-independent).

### 9. Front door — cross-boundary access

- The leader machine hosts the **front door**: a tiny static-config reverse proxy (Caddy/nginx class — no logic, no DB, no keys; bootstrap-installed, **not** the core). It is the one stable address clients use — an mDNS name like `wordslab.local` → the dashboard and every service UI/API, wherever the instance lives (LAN or overlay). The catalog regenerates its config when placement changes.
- One port, one TLS certificate (local CA, distributed to client machines — mechanics #7/#14). Clients only ever need one hostname (DHCP-proof), and the core still never routes user traffic (the proxy is config, not logic).
- **Identity ≠ IP:** machine identity keys are the identity; IP addresses are transient locators, reported by each machine to the leader, kept current in the catalog, reflected on the dashboard. Stable names everywhere.

### 10. Action context across machines

The action-context header (action id + user + service chain) **crosses machine boundaries unchanged**: same action id, each hop appends itself; no re-stamping, no truncation. Auth stays per-hop (each callee validates the caller's own per-service Bearer key; keys never travel along the chain). The front-door proxy passes the header through. **Cloud boundary rule:** the header is never sent to third-party providers — a provider sees only the inference payload; the local trail records "routed to provider P" with the action id. The leader's logs aggregation + the dashboard's action trail reconstruct the full cross-machine, cross-cloud path on demand.

### 11. Boundary with "Design the resource management layer" (#4)

- **#6 = where; #4 = how much.** #6: machine roles, join, two-layer install, activities → graph → placement, routing, cloud nodes, data locations, front door, action context. #4: budgets and quotas (disk/RAM/VRAM per service and user), storage-dir provisioning, RAM-cache/load-unload **mechanics** (the swap that makes "swappable = max" true in practice), GPU budgets, cloud spend quotas.
- The hand-off: #6's placement produces "this working set runs on machines B+C, these implementations resident"; #4 sits on top with how much each may use and when idle things unload. #6 declares the co-resident/swappable classification (dependency graph); #4 implements load/unload. Placement feeds #4; #4 never re-places.

### 12. Standing requirements registered here (platform-wide)

- **Heavy-dependency coordination:** services are designed and evolve together on shared versions of the heavy dependencies (PyTorch/CUDA class) so uv's dedup saves disk; workspace environments are decoupled by design.
- **License policy:** every library and model must have a clear open-source license (revenue-threshold restrictions acceptable, e.g. "< $10M/month"); nothing without a clear license or with commercial use forbidden. → new ticket "Define the platform's component license policy".
- **Supply-chain audit:** every library checked and monitored for known vulnerabilities with an audit trail before inclusion; **always wait at least a week** before including the latest version of a tool or library. → "Define the security model for the trusted home environment" (#14).

## Considered options

- **Discovery: dashboard-initiated with mDNS + manual fallback (chosen) vs manual-only vs overlay-only** — the dashboard is the entry point; mDNS makes candidates appear without typing; typing is the fallback; cloud joins over the overlay first.
- **Leader: single leader, no HA, rebuild recovery (chosen) vs HA/failover vs peer-to-peer** — HA is enterprise weight; services keep working with the leader down; the rebuild path is a guided hour-scale repair.
- **Placement: activity-driven simulation, user-confirmed (chosen) vs install-time planning/profiles vs auto-scheduler** — profiles demand foreknowledge a discovering user lacks; an auto-scheduler is the black box the soul forbids. The activity is the moment the user knows what they need.
- **Install: two layers, leader full + workers lean (chosen) vs all services everywhere** — saves worker disk; the leader remains the reference installation.
- **Concurrency: spread across machines with proximity edges (chosen) vs cram onto one machine** — the fleet's aggregate capacity is the point of multiple machines; realtime edges stay co-located.
- **Disks: data locations per physical disk, roles as folders (chosen) vs per-role virtual disks (wordslab-notebooks pattern)** — roles-as-disks is inflexible and breaks uv across vhdx boundaries; folders keep the four original goals (multi-disk space, reinstall without data loss, backup isolation, reuse) with far less machinery.
- **Access: front-door proxy (chosen) vs direct addressing vs core in the request path** — a static proxy is one stable name, DHCP-proof, TLS in one place, and keeps the core out of user traffic; the core-in-path option was rejected at #9.
- **Cloud: overlay join, no public ports (chosen, ADR-0003) vs public TLS + allowlist** — the overlay removes the exposed surface entirely.

## Consequences

- **Amends ADR-0001** — family-contract conformance: capability API = union of implementation variants, documented per-implementation support (the "engine gap absorbed by adapter" stance generalizes into this).
- **Amends ADR-0002** — capabilities carry implementations (models = one kind); per-capability model declarations generalize to implementation declarations (resource profiles, max capacity, license); heavy-dependency coordination policy.
- **Expands** "Design the single-click installer" (#7 — two-layer install, leader full/workers lean, data locations, front door bootstrap install, client-machine mechanics), "Design the integrated UI (dashboard)" (#8 — working-set view, storage view, topology view, front-door entry), "Design the update & versioning flow" (#10 — implementation-level updates across machines, workers lean), "Define the security model for the trusted home environment" (#14 — supply-chain audit policy, cloud action-context boundary), "Design the backup & recovery story" (#22 — leader-state restore shortens recovery; backup targets = data locations on other machines/external drives).
- **Creates** "Define the platform's component license policy" (license requirements registered above).
- **Feeds** #4 (placement as input, budgets on top), #19 (provider machinery; cloud-node VM automation), #8 (the views), #12 (spec anatomy), #20 (unchanged — capabilities, not implementations, register).
- **Glossary (CONTEXT.md):** implementation, activity, dependency graph (proximity edges), working set, two-layer installation, data location, front door.
