# ADR-0005 — Resource management layer (reservation ledger, load/unload policy, quotas)

**Status:** accepted (resolution of wayfinder ticket "Design the resource management layer (disk, RAM, VRAM across machines)"); **amends ADR-0001** (base contract 429 taxonomy: `cloud-spend` resource name)

## Context

ADR-0004 settled the topology — machine roles, join, two-layer install, activities → graph → placement, routing, cloud nodes, data locations, front door. This ADR is the "how much" side that sits on top of it (ADR-0004 §11: **#6 = where, #4 = how much**): how the platform manages disk, RAM and VRAM across all machines and all resource consumers — models (weights, RAM cache, VRAM), file uploads, document indexes, agent environments, and non-model service data — from a single dashboard. It is a **coordination layer, not a scheduler** (ADR-0004 §5): services stay fully independent; the resource layer reports, places, and budgets. Everything is cut to the soul of the project — non-technical users who want to understand and stay in control: **no magic, no black box, every decision visible and theirs.**

The research ("Research model serving & fast swap for home GPUs") is canonical on the engine side: Ollama is already a model manager (keep_alive, concurrency, multi-GPU); llama.cpp mmap makes the OS page cache the weight cache (weights "in RAM" cost nothing until touched); load/unload is dominated by VRAM contention, not disk reads (a second load of the same model is ~1 s from RAM). The platform's model layer is a **thin orchestration layer** — it adds policy, not engines.

## Decision

### 1. Resource requirements — uniform declarations

Every resource consumer — **service, capability, implementation** — declares the same **resource requirements** in two states:

- **At install:** disk GB (weights + execution code) + required **technologies** (yes/no per hardware capacity — AVX2/AVX512, tensor-core generation, FP8/NVFP4, etc.).
- **When running:** RAM/VRAM GB as a **running formula** — the declared configurable variables (batch/concurrency, context length, document/media length, with min/max ranges) and the formula estimating RAM/VRAM/disk from them. Resident weights are part of the running estimate; there is **no separate "loaded" number**.

Models are implementations of the llm/vlm capability; the same declaration shape covers services and capabilities (ADR-0002 declaration fields extended).

### 2. Hardware capacity — measured facts

Each machine's resources are facts, never config:

- **Capacities:** supported technologies (yes/no per feature).
- **Quantities:** measured free RAM/VRAM/disk GB, kept current by monitoring (ADR-0003 `monitoring`).
- **Speed rank per resource** (fast/medium/slow): from lightweight benchmarks run by the core's `fleet` capability at join and on demand — disk sequential/random read/write, CPU single/multi-core, RAM bandwidth/latency, GPU compute/latency. A slow NVMe or network disk is not mistaken for fast by its label.

### 3. The reservation ledger

The platform's view of "free" is **measured free minus active reservations**. Loading an implementation **books** its install disk + running formula at the configured parameters; unloading **releases**. Disk is **booked at install time** (the install-disk requirement is booked on the `models/` folder before the download starts, so concurrent installs can't both assume the same free space; realized as the download lands, released on delete). **User reservations** book capacity without declarations — the admin sets a per-user quota limit (disk/RAM/VRAM), the user books within it and releases manually; the platform never auto-releases them. The ledger feeds the fit test, dashboard gauges, and eviction decisions.

### 4. Fit test (install) vs load/unload (runtime) — two different logics

The install-time **fit test** and the runtime **load/unload** logic are deliberately separate:

- **Install fit test** (ADR-0004 §3 gate + simulation): technology match ∧ remaining-disk fit (ledger) ∧ memory fit **when running alone at minimum parameters**. Uses the sum/max rule via the concurrency levels (below). Quantity fit is the **hard gate**.
- **Runtime load/unload:** swappable/sequential members are treated as **plain independent implementations** — no special swap machinery. They load simultaneously when free capacity permits; load on demand when it doesn't, with the same logic as any other working-set member.

### 5. Three concurrency levels (replaces co-resident vs sequential)

The dependency graph declares concurrency per edge in three explicit levels, feeding the **install-time fit test** (only; runtime treats all members alike):

- **`always load jointly`** — atomic residency: the group loads/unloads together, a member is never alone resident. Install fit = **sum**, hard.
- **`load jointly if possible`** — preferred joint residency: calling one member tries to bring the group, falling back to alone when space is tight. Install fit = **sum** (preferred), with individual fallback.
- **`load on demand`** — fully independent: each member loads on its own call when space permits. Install fit = **largest** only.

### 6. Runtime residency: working set, idle sweep, pressure unloads

- **Working set = the demand surface** (what the user's current activities *want*), not the resident set. **Resident** = the loaded subset, booked in the ledger. Members load when free capacity permits, load **on demand** when it doesn't.
- **Unloads are deterministic for the already-done, asked for the genuinely ambiguous.**
  - **Idle sweep:** members past their idle timeout (default ~30 min, per-capability adjustable; **pin** keeps resident) are unloaded on the next sweep — their own inactivity, not a choice.
  - **Pressure unload:** when a load doesn't fit, first free what's already idle; then **ask the user** when there is genuine ambiguity — if exactly one way frees the needed amount (one candidate alone, or one viable combination), do it silently; if several distinct ways exist, ask the user to choose, showing each option and what it frees. **Remembered decisions** are explicit per-load rules ("to load X, when ambiguous between A and B, choose A") — stored visibly, editable, and applied without asking when they resolve the ambiguity. **Never** pinned implementations, **never** auto-evicting user reservations.
- **The fit lever:** before unloading anything, the platform proposes **lower parameters** for the incoming implementation (within the hardware-capped ranges — max context / image size / sound length) to fit, then lower parameters of a resident implementation (user asked — it affects running work).
- **Refusal:** if nothing frees enough or the user declines, the load is refused with `429 resource_exhausted` (binding resource: `ram`/`vram`/`disk`, shortfall in GB on the dashboard), **no queue in v1**, and the service's inference policy decides cloud fallback.

### 7. Performance dimension — placement clues

- Implementations declare a **performance class** per resource used (fast/medium/slow/any) and **transfer-speed needs** between resources (e.g. high disk→VRAM for fast loads; low-latency RAM↔GPU for realtime).
- Speed ranks are **soft placement clues** for the topology's simulation (quantity fit stays the hard gate): place fast-disk/GPU-needing implementations on the fastest matching resources, respect transfer needs, co-locate realtime (proximity edges are the hard same-machine constraint). The simulation shows the reason (fast NVMe vs HDD).
- Speed rank also feeds the `speed` model-selection goal: a fast GPU can afford a larger `recommended` model; a slow one prefers the smaller/faster.

### 8. Disk quotas — measured caps + two-tier enforcement

- **Models quota per data location** (each disk's `models/` folder; default generous, admin-editable), with an aggregate view across machines. Implementation installs book against it (install fit consults the ledger).
- **Three layers of caps, enforced at the tightest:** per data location (the disk's table), per service folder (default provisioned at install from the service's declaration, admin-editable), per user (workspace disk within the admin-set user quota limit). The user's workspace booking sits in the ledger; measured usage is shown against it.
- **Two-tier enforcement:** platform-mediated writes (uploads — pre-checked + booked during resumable uploads; implementation downloads/installs) are **blocked at quota** (`429 resource_exhausted`, `disk`). Everything else (service-internal DBs/indexes, agent/user programs) **can't be blocked** — enforcement is **monitor + warn + a strong storage UI**: continuous usage measurement, presented per data location / folder / service / **user**, **green / orange / red** with clear attribution of **who oversteps** (warn ~80%, red at 100%). The human acts (clean up, release, raise the quota).

### 9. Cloud spend quotas — two parallel local dimensions

Machinery (providers, credentials, billing, LiteLLM gateway, per-key budgets) is #19's; the local quota rules are #4's. Constraint: the core never sits in the request path, so caps are **distributed, enforced locally, accounted by pull** (the ADR-0003 secrets pattern — master + distribution at install/rotation, no call-time round-trip).

- **Pay-per-token spend:** per-service **monthly cap**, set on the dashboard (cloud-enablement proposes a visible default, e.g. €10/month), distributed to the consuming service, which enforces it locally at call time (it knows each call's `usage.cost`). LiteLLM per-service virtual keys are a backstop.
- **Fixed-price subscriptions with opaque usage limits:** the provider owns the limit and exposes a **"% usage remaining per unit of time" API** (e.g. pooled caps like "5 hours / week" or rolling windows). Provider adapters (machinery #19) **plug into that remaining-% API**; the platform caches remaining-% (refresh on a cadence + opportunistically on proxy usage/limit headers or 429s — no per-call round-trip) and shows each plan as a measured gauge with thresholds (orange below ~30%, red below ~10%) and optional per-service shares/priority. A service refuses cloud routing at/below the red line, falling back local or refusing.
- **"Can I route to cloud?"** respects whichever local limit is tighter: the money cap or the remaining-% red line. At the cap, cloud-routed calls return `429 resource_exhausted` with resource **`cloud-spend`** (amends ADR-0001's taxonomy); local-only traffic is unaffected; the dashboard explains how to raise/reset. Monthly period auto-renews.

### 10. Boundary with the topology (#6) and the provider model (#19); monitoring

- **#6 = where; #4 = how much; #19 = cloud machinery.** #6: machine roles, join, two-layer install, activities → graph → placement, routing, cloud nodes, data locations, front door. #4: resource requirements declarations, the reservation ledger, load/unload policy, quotas (RAM/VRAM/disk/cloud-spend local rules). #19: providers, credentials, billing, LiteLLM gateway, per-key budgets, opaque remaining-% adapters. #4 never re-places; #6 never budgets.
- **The fit test is shared:** #4 owns its inputs and numbers (requirements, max-capacity caps, current reservations, models/disk quotas, performance ranks); #6's simulation owns where it is applied. Placement feeds #4; #4 never re-places.
- **Monitoring:** sampling/health polling mechanics are ADR-0003's `monitoring` capability (poll `/health` ~30–60 s, continuous resource sampling ~5–10 s). #4 **consumes those measurements** — the ledger's free-capacity view, the gauges, and the spend/remaining-% figures are built on them; #4 defines what numbers are needed.

## Considered options

- **Reservation ledger (chosen) vs pure measured reporting vs per-service hard budgets** — a ledger makes "will it fit?" computable and honest (concurrent installs, load booking) while staying visible; per-service RAM/VRAM caps would fight the working set's actual demand at home scale.
- **Two requirement states + running formula (chosen) vs three states (install/loaded/running) vs fixed resource profile** — folding "loaded" into the running formula removes a redundant number; a formula makes the configurable variables (batch/context/media length) the fit lever.
- **Three concurrency levels (chosen) vs two (co-resident/swappable)** — "load jointly if possible" names the common middle case; explicit names beat implicit "swappable" semantics.
- **Runtime treats all members alike (chosen) vs special swap machinery for swappable** — no hidden engine; sum/max is an install-time fit rule only.
- **Ask-on-ambiguity + remembered rules (chosen) vs automatic LRU eviction** — an LRU is the black box the soul forbids; deterministic when forced, user-chosen when not.
- **Parameter-lowering as the primary fit lever (chosen) vs immediate unload** — least disruptive; keeps running work untouched.
- **Disk: measured caps + two-tier enforcement (chosen) vs booking everything** — most writes aren't platform code; block what we mediate, warn + UI for the rest.
- **Cloud: distributed local enforcement + pull accounting (chosen) vs central call-time check** — preserves service independence; the core never proxies calls.

## Consequences

- **Amends ADR-0001** — base contract 429 taxonomy gains resource name `cloud-spend` (fixed-price subscription quotas as well as money caps).
- **Expands** "Design the inference provider model" (#19 — provider adapters must plug into opaque "% usage remaining per unit of time" APIs; the two-dimension money/subscription quota model), "Design the integrated UI (dashboard)" (#8 — storage view with green/orange/red + who-oversteps attribution, working-set UI with resident status / pin / drag / delete, the ask-user-to-unload and parameter-lowering dialogues, spend and remaining-% gauges), "Design the single-click installer" (#7 — storage-dir + quota provisioning at install by the `resources` capability).
- **Feeds** "Design the backup & recovery story" (#22 — quotas constrain backup volumes), the spec anatomy (#12 — this chapter lands in the spec), "Design the multi-machine topology" (#6, resolved — placement consumes these declarations and numbers).
- **Glossary (CONTEXT.md):** hardware capacity (+ speed rank), resource requirements (install + running formula, performance class, transfer needs), fit check, reservation ledger, user reservation, three concurrency levels, working set (desired) vs resident, fit lever, models quota, two-dimension cloud quota.
