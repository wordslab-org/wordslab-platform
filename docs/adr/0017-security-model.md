# ADR-0017 — The security model for the trusted home environment (threat model, TLS, isolation, guardrails, update authenticity)

**Status:** accepted (resolution of wayfinder ticket "Define the security model for the trusted home environment", #14); **amends none**; **shapes the `00-overview.md` Foundations chapter** (security = a cross-cutting principle, ADR-0013 §2 — chapter still deferred, this ADR is the source of truth until it is created); **feeds** "Design the backup & recovery story" (#22 — the at-rest key must survive leader rebuild), "Define how agents publish generated web apps & services" (#21 — the Connectors v1.1 gateway's TLS / edge-auth policy takes this ticket's stance).

## Context

The soul demands a **trusted environment, very small scale — but not naive**: cloud fallback means some outbound traffic, and services hold real data. The right answer is deliberately **lighter than the enterprise stack** (Keycloak, Vault, mTLS mesh, HSMs) while covering the real risks — and it must be **transparent, visible, no black box** (the user can always see and adjust what is guarded).

The trust model's *basics* are settled by prior tickets and this ADR takes them as given (not re-decided):

- **Machine identity keys** issued by the leader at join; core↔core auth via machine keys; revoking a machine = deleting its key (ADR-0003).
- **Overlay network** (WireGuard/Tailscale) for any internet crossing; rented cloud machines expose **no public ports**; home LAN stays **plain HTTP + Bearer** (trusted) (ADR-0003/0004).
- **Keys & secrets distribution**: `keys` = platform-internal credentials, `secrets` = outside-world credentials (master copy on leader, distributed to consuming services at install/rotation, no call-time round-trip) (ADR-0003).
- **Credential storage/distribution/rotation** is **#19's** (the shared `secrets` vault, push + pull-on-start, eventual consistency); **#14 owns protecting the copies at rest** (ADR-0006 §8).
- **Per-agent scoping** = the registry's discovery control boundary, enforced server-side (ADR-0008 §5).
- **Cloud action-context boundary**: the header is never sent to third-party providers (ADR-0004 §10).
- **The front-door reverse proxy + local CA + TLS cert distribution** mechanics are installer territory (ADR-0004 §2/§9, ADR-0014); #14 sets the **stance** they implement.
- **The supply-chain gate's 1-week wait** is a standing requirement; #14 owns its **mechanics** (ADR-0004 §12, slotted into ADR-0016's metadata/check step).

## Decision

### 1. Threat model — what #14 defends against

The honest home threat model, not nation-state: the primary defenses target a **compromised or malicious agent/harness** (the largest real attack surface, since sessions run containers, execute connectors, and run agent-generated code) and **accidental data leakage** (a mis-configured connector or a `cloud` implementation carrying data out). The explicit boundaries: **malware on a host with OS-level access** is *not* fully defended (no platform can protect a fully-owned host), and a **disk thief** is only lightly defended (see §4) — but a stolen *credential* is defended by its **short lifetime** (§4). **Trusted LAN peers; untrusted everything that crosses to the internet.**

Five surfaces frame the whole model:

1. **Compromised/malicious agent or harness** — primary defense target (container isolation + network policy + connector audit + registry scoping).
2. **Accidental data leakage** — mis-configured connector or `cloud` implementation carrying data out (guardrails at the outbound boundary, §8; visible privacy labels, ADR-0008).
3. **Malware on the user's host with OS-level access** — an explicit boundary: not fully defended; disk-level secrets protection is light (§4).
4. **Trusted LAN peers, untrusted everything crossing to the internet** — LAN plain HTTP+Bearer, internet/overlay TLS (§3).
5. **The platform must not reach into host OS files** — the WSL VM boundary closes host access by default; only **explicitly-shared directories** are mounted into the Linux side (and exposed as a Windows drive for easy access). A compromised agent inside the platform can only see the shared workspace, not the host's Documents/Desktop/etc. The mount *mechanics* are installer territory (#7 / ADR-0014); the **default-deny host-access stance** is this ADR's.

### 2. Isolation — the host boundary and the container boundary

- **Host-filesystem isolation (first-class):** the platform runs in a WSL VM; it gets **no access to host OS files by default**. File sharing is **explicit only** — a dedicated host directory is mounted into the Linux distro and mapped to a Windows drive on the host. This is the platform's outermost boundary.
- **Container isolation: OS-container isolation is enough** (containers, not VMs/microVMs) — matches the light stance, keeps disposable session startup fast. MAF runs in-process (no container); containerized harness images (Hermes Agent, OpenCode, Pi) run per-workspace-session.

### 3. TLS stance — browser-aware transport

The security reasoning (trusted LAN) and the browser's **secure-context** requirement (WebRTC/dictation, code-server, clipboard, service workers only under HTTPS) together give a **two-part rule**:

1. **Every browser-facing surface is HTTPS** — all service UIs, the dashboard, dictation, code-server — served with the **local CA** already established for the front door (ADR-0004 §9), certs distributed to client machines. Cheap (same machinery, extended to every UI origin), no enterprise weight, and it makes modern-browser features work.
2. **Plain HTTP + Bearer stays for trusted machine-to-machine API traffic** inside the trusted LAN (service↔service, core↔core) — no browser involved, so no secure-context requirement; trusted-LAN security reasoning holds.

**No mTLS, no full-internal-TLS** — that is enterprise weight and inverts the soul. TLS is required at the **front door** (the one mDNS address, local CA), over the **overlay**, and on **every outbound crossing to the internet** (connectors, cloud-gateway inference). Inside the trusted LAN, plain HTTP+Bearer.

### 4. Secrets at rest — deliberately light

Strong at-rest encryption is largely **theater**: harnesses and tools store their own keys anyway, often in plain `.env` files on disk. So:

- **Light obfuscation, not strong encryption:** what the platform itself stores is encrypted with a **static key in the platform source code**, so a random user browsing the disk does not read API keys in plaintext. No passphrase, no unlock ceremony, nothing that can break a rebuild.
- **The real defense is the credential's lifetime, not the disk:** prefer **short-lived credentials (ideally ~1 month validity) whenever the provider allows, rotated often** — the existing #19 rotation machinery (push + pull-on-start, eventual consistency, stale-until-next-boot) is the actual control. A stolen credential is useless within its short validity window, regardless of disk readability.
- Applies to the **master copy (leader)** and the **distributed copies (workers)** alike. At-rest must **survive leader rebuild** (interacts with #22 backup — not resolved here).

### 5. Container network policy — the backstop for harness tool calls

The container's network policy is the **last control** between a misbehaving harness and the world. **Default-allow-but-scoped-to-need:** the container gets outbound access to what its session's task needs (PyPI, GitHub, HuggingFace, the platform's own services / registry / connectors door), but **no unrestricted host or LAN access** — it cannot wander into other machines on the LAN or the host's network beyond its scoped need. Even if the harness's native accept/refuse approves a tool call, the container can only reach what the policy allows.

### 6. Harness accept/refuse — the harness is the execution authority

The **harness is the execution authority**: its own native accept/refuse (in its native opaque format, the UI the user already knows) decides "may this tool run". The platform does **not** intercept or override the harness's internal decisions (that would fight the opaque-harness-home principle, #18 / CONTEXT 'Harness home'). The platform's security lives in the **backstops around it**:

- what the container can reach → network policy (§5),
- what leaves the machine → connector audit/approval door (§7),
- what the agent can even see/discover → per-agent scoping (ADR-0008 §5),
- what filesystem it can touch → host-filesystem isolation + workspace mounts (§2).

Accepted cost: because the harness home is opaque, the platform shows **no unified accept/refuse trail** across harnesses; its own audit trail covers *what leaves the machine*.

### 7. Connectors security / audit / approval layer — the single door

Every outbound connector call (web / x / outlook / youtube / github / huggingface) passes through a service-level layer:

1. **Logging:** every connector call logged, attributable via action-context (what, who, which agent/service chain).
2. **Tiered by consequence:** read-only connectors (`web` search+fetch, `youtube` watch) are **logged-only**; **send/mutate** connectors (`x`, `github`, `outlook`, `huggingface`) require **human approval**. The line is "does data leave the machine / does it send or mutate".
3. **Approval is caller-identity-scoped, never platform-wide:** the grant rides the action-context (user + service chain) and is checked against **that caller** — approving GitHub for user A does not let agent B or another workflow under A post without its own approval. Per-config approval for send/mutate connectors; the highest-consequence sends can surface a per-call confirm in the dashboard as an **adjustable setting** (surfaced, not a hidden default).
4. **Harness-native outbound stays outside the Connectors door:** a harness's own package/network activity (PyPI install, git clone, raw API) is "the agent doing its job", bounded by the container network policy (§5), not funneled through the connector door. The audit trail covers **connector-mediated** outbound; the network policy covers everything else.
5. **Audit/approval trail view in the dashboard** (per #18) — the user sees what left the machine and who approved it (no black box).

### 8. Guardrails / moderation — data-safety, cheap by default

Guardrails are **data-safety at the two boundaries**, not primarily content censorship:

- **Outbound:** prevent private/personal-data leakage to external cloud services (a `cloud` implementation, a connector call, a harness tool carrying personal data out).
- **Inbound:** defend **prompt injection** from data coming in (retrieved documents, web content, ingested bundles) that tries to steer the agent.

The **default layer is cheap** and **on by default, visible** — and need not be exclusively deterministic: it may mix a **trained classifier / entity-extraction model, or a very small LLM**, whatever is light enough to run in-line (the *cost ceiling* is the constraint, not the technique). It is **visible, never silently filtered** — any interception is surfaced with its reason and is adjustable; **per-account, admin-configurable, default-on**.

The **heavy layer is optional, off by default**: the Shieldstral-class 3B LLM moderation filter may need a whole machine, so it is **not required/installed/enabled by default** — enabled only where the user wants stronger filtering and has the hardware (e.g. a child's account).

Placement (settled by #18): the moderation **model** in the Inference service's classic-AI capability; **builtin transforms** in the Media transformations service; **policy hooks in the agent service loop** + at the outbound door.

### 9. Update authenticity — two distinct supply chains

Two different code paths with **different trust models**, never conflated:

1. **The platform's own code** (maintainer-controlled, downloaded from the maintainer's repo): **signed packages + checksum verification against an embedded platform key**, verified before download/apply. The signature/checksum carries in the package metadata; the update flow verifies at the metadata/check step (ADR-0016).
2. **External open-source packages** (reused, downloaded by platform scripts at install from PyPI / Ollama / NVIDIA / any server — the platform **does not embed** these, e.g. no CUDA toolkit or Ollama binary in its own packages; it ships only **scripts that download them**): gated by the **audited supply-chain gate — vulnerability scan + 1-week wait** recorded at the metadata/check step, plus upstream checksums/signatures where available. This is where the standing requirement (ADR-0004 §12) executes its *mechanics*.

## Boundary / handoffs

- **Credential storage/distribution/rotation** → #19 (ADR-0006 §5); this ADR only protects the copies at rest (§4).
- **Mount mechanics / cert distribution / firewall ports / WSL→Windows bridging** → #7 (ADR-0014); this ADR sets the default-deny host-access stance and the browser-HTTPS stance.
- **Backup / leader-rebuild key recovery** → #22 (not resolved here); at-rest must survive rebuild.
- **Inbound gateway TLS / edge-auth policy** → #21 (the Connectors v1.1 gateway); this ADR's stance feeds it.
- **Spec home:** `00-overview.md` Foundations (security = a cross-cutting principle, ADR-0013 §2) — chapter still deferred; this ADR is the source of truth until it is created.

## Feeds

- **Feeds** the `00-overview.md` Foundations chapter (security principles), "Design the backup & recovery story" (#22), "Define how agents publish generated web apps & services" (#21).
- **CONTEXT.md** glossary additions: threat model, host-filesystem isolation, secrets at rest, container network policy, connector approval (caller-identity-scoped), guardrail (data-safety), update authenticity.
