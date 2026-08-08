# ADR-0003 — Platform core, bootstrap layer & trust model

**Status:** accepted (resolution of wayfinder ticket "Scope the centralized platform services"); **amends ADR-0001** (base contract: key-management surface, action-context header, log surface)

## Context

The v1 service catalog (ADR-0001/0002 + "List and scope the v1 service catalog") is eleven fully independent services, each with its own DB, business logic, UI and API. Yet the platform still centralizes a small set of cross-cutting concerns (authentication, users, logs, stats, availability, updates, and more surfaced during grilling). The enterprise answer is a whole layer of products (identity provider, telemetry collector, SIEM, APM, secrets vault, config management…). This ADR is the deliberate home-scale inverse: **one** service centralizes *control* — never data, never execution, never storage, never the request path. It also settles the layer below the contract (the bootstrap) and the trust model between machines, cores and services. Simplicity is the main feature; the target audience is non-technical people who want to understand and stay in control (the soul of the project, map issue #1).

## Decision

### Two layers

- **Bootstrap layer** — native, platform-specific machinery *below* the service contract (not a service: no API, no DB, no keys). On Windows: installs/updates WSL + a Linux distro + virtual disks on user-chosen physical disks (wordslab-notebooks pattern); installs uv + Python; verifies network reachability (github/pypi); installs the first version of the platform core; then hands off. Persists only as a **re-runnable native updater** for its own layer (host updates); no resident daemon. Install experience is a familiar native installer (no command line), fully guided, transparent about every change, leaving decisions to the user, ending with a recap (installed/running + how updates/security/backup work) — designed in "Design the single-click installer".
- **Platform core** — one base-contract service per machine, with capabilities (ADR-0002 pattern): `fleet` (hardware detection, machine join, aggregate resources), `install` (installs/updates all services on this machine; cross-machine orchestration), `catalog` (inventory of installed + available services: placement, version, status), `resources` (allocates aggregate disk/RAM/VRAM between services and users; provisions storage dirs + quotas at install; async usage monitoring), `backup` (orchestrates per-service backup/restore — design in "Design the backup & recovery story"), `users` (few family members: name, permission level `admin`/`member`, per-user quota; admin-created; no orgs/RBAC/SSO/invites), `keys` (issuer + registry of per-service Bearer keys and human/tool keys; never validator), `secrets` (master copy + distribution of outside-world credentials; never a call-time round-trip), `monitoring` (health polls, continuous resource sampling, cloud provider status/limits; dashboard-only alerting in v1), `logs` (read-through aggregation + per-service search + action trails; no pipeline), `stats` (per-user + global; pull + hourly cached snapshots; no pipeline), `datasets` (scheduled batch extraction from service logs with declared anonymization → dataset files in workspaces; opt-in per user, default off). Human surface = the dashboard. The core is the platform's eyes, hands and ledger — it never routes user traffic (except dashboard login), never proxies model calls, never enforces quotas in the request path; a service runs fine with the core down.

### Role split

Every machine runs one core. The first machine's core is the **leader core** (runs the authority capabilities: users, keys, secrets, resources, catalog, aggregation, updates). Other machines run **worker cores** (local capabilities only: fleet/install/monitoring) and hold no users/keys. Same service, same code — capabilities enabled per role. Discovery/placement mechanics are designed in "Design the multi-machine topology".

### Trust model

- **Machine identity keys**: every machine's core authenticates to the leader and other cores with a long random key issued by the leader at join (short-lived **join code** shown in the leader's dashboard, typed or scanned by the user). Revoking a machine = deleting its key. The join code is the only shared secret; afterwards every machine has its own key.
- **Services**: per-service Bearer keys, generated at install, stored and validated by the service itself (ADR-0001 base item 2) — no central round-trip, a service works standalone, cross-machine, or in the cloud.
- **Networks**: home LAN = plain HTTP + Bearer (trusted environment). Any internet crossing (rented cloud hosts) = the machine joins an **overlay network** (WireGuard-based; Tailscale as the friendly default, self-hosted WireGuard as the no-third-party option) and exposes **no public ports**. The rented machine is never opened to the internet.
- **Action context**: every user-initiated action gets an action id stamped with the user; an action-context header propagates through chained service calls (each service appends itself to the chain). Every action is logged per-service with user + chain; the dashboard renders any action's chronological + hierarchical trail on demand (no black box); connectors inherit the context so outbound calls are attributable (feeds the connector audit/approval layer).

### Keys & secrets (two distinct capabilities)

- **`keys`** = platform-internal credentials (per-service Bearer keys, machine identity keys, human/tool keys). Core = issuer + registry (id, scope, purpose, created, last used, revoked); service = validator. Rotation/revocation = dashboard one-click; the base contract gains an admin-scoped key-management surface on every service (`GET/POST /v1/keys`, `DELETE /v1/keys/{id}`) so the core has a remote handle while services stay autonomous. No key expiry in v1.
- **`secrets`** = outside-world credentials (BYOK provider keys, connector tokens). The core holds the **master copy** and **distributes** it to each consuming service at install and on rotation; services use it locally with no call-time round-trip. Management is single-point (one dashboard page to add/rotate/revoke); copies on machines are protected per the security model. Provider-side machinery (config shapes, quotas, cost) is designed in "Design the inference provider model"; at-rest protection in "Define the security model for the trusted home environment".

### Logs — two surfaces

- **Raw technical logs** (auditing/understanding/diagnostics): per-service DBs, action-context stamped. Read via base-contract `GET /v1/logs` (common filters: action_id, time, level + a `q` search parameter interpreted by each service against its own schema, searchable fields self-declared). Scoped by key scope + user: members see their own actions, admin sees all, machine/bootstrap logs admin-only.
- **Anonymized datasets** (study/trends/improvement/training): the core's `datasets` capability runs family-5 batch jobs — pull logs → declared per-service anonymization pipeline (user ids → opaque hashes, PII stripped, policy visible) → dataset files in a workspace → consumed by Training and Evaluation. Scheduled runs supported. **Opt-in per user, default off**, explained in the first-run wizard.

### Stats & monitoring

- **Stats**: per-user + global: action type counts/duration, per-service usage in native units (tokens, pages, audio seconds…), machine resource usage, cloud units + spend. Some metrics global-only. Pull + hourly cached snapshots in the leader; no pipeline.
- **Monitoring**: worker cores poll local services' `/health` every ~30–60 s; continuous machine resource sampling every ~5–10 s (disk/RAM/VRAM/CPU/GPU) — **always visible on the dashboard** (the critical home-scale limiting factor); cloud provider status/limits reflected alongside local gauges. Bounded history (~24 h fine, ~7 d coarse). Alerting = dashboard-only in v1.

### Deliberately NOT centralized

Service business logic, DBs, UIs and APIs (full independence — no central round-trip, ever); model lifecycle & model management (per-service, per-machine); machine resources themselves (machines own them; the core allocates and views); raw log storage & usage recording (per-service; the core reads and derives, never collects); backup **data** storage (per-service; orchestration is core); storage **content** (services own it; allocation + quotas are core); evaluation (its own ticket); security boundary mechanics (TLS, container network policy, harness accept/refuse, connector approval); the service catalog's content & governance; inbound exposure / publishing (v1.1); data residency (data lives where its service lives).

### Support matrix (v1)

One runtime (Linux); hosts = Windows 10/11 via WSL2 (primary) + native Linux + rented cloud hosts (native-Linux install path); one GPU stack (CUDA; ROCm and MLX deferred, kept possible by the per-OS bootstrap, engine variants, and hardware-spanning models.toml). Configurations: **no-GPU cheap** (all model calls via cloud providers — per-service `cloud-only` inference policy) and **GPU small/middle/big** (local, private).

## Considered options

- **One core service vs several centralized services** — one: single install/DB/update, one dashboard entry; the capability pattern carries the six+ concerns in-process. Several would recreate the enterprise layer we invert.
- **Trust: join code + per-machine keys (chosen) vs one shared cluster secret vs certificates/PKI** — per-machine keys make revocation per-machine and avoid a single master secret; PKI is enterprise weight.
- **Internet crossing: overlay network (chosen) vs public TLS + IP allowlist** — the overlay removes the exposed surface entirely; public TLS is the later "expert mode".
- **Secrets: core master + distribution (chosen) vs central vault API per call vs vault in the Connectors service vs separate vault service** — per-call round-trips weaken standalone services; Connectors placement couples Inference→Connectors; a separate service adds install/update weight.
- **Logs: read-through + per-service search (chosen) vs central log pipeline** — the pipeline breaks independence and is the enterprise shape.
- **Datasets: core extraction (chosen) vs Training-owned extraction** — Training reaching into every service's logs fights independence; the core is the cross-service gatherer.
- **Alerting: dashboard-only v1 (chosen) vs active notifications** — notifications deferred; the data contract is the same either way.

## Consequences

- **Amends ADR-0001**: base item 2 gains the admin-scoped key-management surface; the base contract gains the action-context header and the log surface (`GET /v1/logs`, per-service `q` search).
- **Created**: "Design the backup & recovery story" — backup/restore orchestration is a core capability; the ticket designs what/where/how/restore.
- **Expanded**: "Design the single-click installer" (two-layer installer + install-experience requirements + support matrix), "Design the update & versioning flow" (host-vs-service update lanes + core self-update), "Define the security model for the trusted home environment" (trust-model basics as given; #14 sharpens TLS, secrets at rest, network policy, harness accept/refuse).
- **Feeds**: the dashboard (#8 — core surfaces: status, gauges, cloud provider cards, action trails, users/keys/secrets/catalog pages), multi-machine topology (#6 — leader/worker mechanics, discovery, overlay), update flow (#10), provider model (#19 — vault machinery home), capability registry (#20 — the core registers nothing; services register), evaluation (#16 — deliberately out of scope here), publishing (#21).
- **No separate "platform core design" ticket** — the core's API detail lands in the spec (spec anatomy, #12); its surfaces are owned by #4/#6/#7/#8/#10/#14.
- **Terminology** (CONTEXT.md): platform core, bootstrap layer, leader core / worker core, machine identity key, join code, action context.
