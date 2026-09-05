# Security — the trusted home environment

**Source of truth: ADR-0017.**

The security stance is **honest and light**, sized to a trusted home/small-business environment at very small scale — deliberately lighter than the enterprise stack (no Keycloak, Vault, mTLS mesh, or HSMs). The soul governs: **transparent, visible, no black box** — the user can always see and adjust what is guarded. The platform is trusted but not naive: cloud fallback means some outbound traffic, and services hold real data.

## Honest threat model

The primary defenses target a **compromised or malicious agent/harness** (the largest real attack surface, since sessions run containers, execute connectors, and run agent-generated code) and **accidental data leakage** (a mis-configured connector or a `cloud` implementation carrying data out). Trusted LAN peers; untrusted everything that crosses to the internet.

The explicit boundaries — what is **not** fully defended:

- **Malware on the user's host with OS-level access** is an explicit boundary, not fully defended (no platform can protect a fully-owned host).
- A **skilled malicious admin** is not fully defended.
- A **disk thief** is only lightly defended; but a stolen *credential* is defended by its **short lifetime** (see Secrets at rest).

## Host-filesystem isolation

The platform runs in a **WSL VM** with **no access to host OS files by default** — this is the platform's outermost boundary. File sharing is **explicit only**: a dedicated host directory is mounted into the Linux distro and mapped to a Windows drive on the host. A compromised agent inside the platform can only see the shared workspace, not the host's Documents/Desktop/etc. The mount mechanics are installer territory (ADR-0014); the **default-deny host-access stance** is this ADR's (ADR-0017).

## Browser-aware TLS

Every **browser-facing surface is HTTPS** — all service UIs, the dashboard, dictation, code-server — served with the **local CA** already established for the front door (ADR-0004 §9), certs distributed to client machines. Cheap (the same machinery, extended to every UI origin), no enterprise weight, and it satisfies the browser's **secure-context** requirement (WebRTC/dictation, code-server, clipboard, service workers only under HTTPS).

**Plain HTTP + Bearer stays for trusted machine-to-machine API traffic** inside the trusted LAN (service↔service, core↔core) — no browser involved, so no secure-context requirement; the trusted-LAN security reasoning holds.

**No mTLS, no full-internal-TLS** — that is enterprise weight and inverts the soul. TLS is required at the **front door** (the one mDNS address, local CA), over the **overlay**, and on **every outbound crossing to the internet** (connectors, cloud-gateway inference). Inside the trusted LAN, plain HTTP+Bearer.

## Secrets at rest — deliberately light

Strong at-rest encryption is largely **theater**: harnesses and tools store their own keys anyway, often in plain `.env` files on disk. So the platform uses **light static-key obfuscation, not theater-strength encryption**: what the platform itself stores is encrypted with a **static key in the platform source code**, so a random user browsing the disk does not read API keys in plaintext. No passphrase, no unlock ceremony, nothing that can break a rebuild.

The **real defense is the credential's lifetime, not the disk**: prefer **short-lived credentials (ideally ~1 month validity) whenever the provider allows, rotated often** — the existing rotation machinery (push + pull-on-start, eventual consistency, stale-until-next-boot; ADR-0006 §5) is the actual control. A stolen credential is useless within its short validity window, regardless of disk readability. Applies to the master copy (leader) and distributed copies (workers) alike; at rest must survive leader rebuild (interacts with the backup story).

## Container isolation

**OS-container isolation (not VMs/microVMs) is enough** — matches the light stance and keeps disposable session startup fast. MAF runs in-process (no container); containerized harness images (Hermes Agent, OpenCode, Pi) run per-workspace-session.

## The harness is the execution authority; the platform provides backstops

The **harness is the execution authority**: its own native accept/refuse (in its native opaque format, the UI the user already knows) decides "may this tool run". The platform does **not** intercept or override the harness's internal decisions (that would fight the opaque-harness-home principle). The platform's security lives in the **backstops around it**:

- **Container network policy** — the last control between a misbehaving harness and the world: **default-allow-but-scoped-to-need**. The container gets outbound access to what its session's task needs (PyPI, GitHub, HuggingFace, the platform's own services / registry / connectors door), but **no unrestricted host or LAN access** — it cannot wander into other machines on the LAN or the host's network beyond its scoped need. Even if the harness's native accept/refuse approves a tool call, the container can only reach what the policy allows.
- **The single audited connectors door** — what leaves the machine.
- **Per-agent scoping** — what the agent can even see/discover (ADR-0008 §5).
- **Host-filesystem isolation + workspace mounts** — what filesystem it can touch.

Accepted cost: because the harness home is opaque, the platform shows **no unified accept/refuse trail** across harnesses; its own audit trail covers *what leaves the machine*.

## Guardrails = cheap, on-by-default, visible data-safety

Guardrails are **data-safety at the two boundaries**, not primarily content censorship:

- **Outbound:** prevent private/personal-data leakage to external cloud services (a `cloud` implementation, a connector call, a harness tool carrying personal data out).
- **Inbound:** defend **prompt injection** from data coming in (retrieved documents, web content, ingested bundles) that tries to steer the agent.

The **default layer is cheap**, **on by default, and visible** — it need not be exclusively deterministic: it may mix a trained classifier / entity-extraction model, or a very small LLM, whatever is light enough to run in-line (the *cost ceiling* is the constraint, not the technique). It is **visible, never silently filtered** — any interception is surfaced with its reason and is adjustable; **per-account, admin-configurable, default-on**.

The **heavy moderation tier is optional and off by default**: the Shieldstral-class 3B LLM moderation filter may need a whole machine, so it is **not required/installed/enabled by default** — enabled only where the user wants stronger filtering and has the hardware (e.g. a child's account).

## Update authenticity — two distinct supply chains

Two different code paths with **different trust models**, never conflated:

1. **The platform's own code** (maintainer-controlled, downloaded from the maintainer's repo): **signed packages + checksum verification against an embedded platform key**, verified before download/apply. The signature/checksum carries in the package metadata; the update flow verifies at the metadata/check step (ADR-0016).
2. **External open-source packages** (reused, downloaded by platform scripts at install from PyPI / Ollama / NVIDIA / any server — the platform **does not embed** these, e.g. no CUDA toolkit or Ollama binary in its own packages; it ships only **scripts that download them**): gated by the **audited supply-chain gate — vulnerability scan + 1-week wait** recorded at the metadata/check step, plus upstream checksums/signatures where available (ADR-0004 §12).

## Connectors — a single audited door

Every outbound connector call (web / x / outlook / youtube / github / huggingface) passes through a service-level layer:

1. **Logging:** every connector call logged, attributable via action-context (what, who, which agent/service chain).
2. **Tiered by consequence:** read-only connectors (`web` search+fetch, `youtube` watch) are **logged-only**; **send/mutate** connectors (`x`, `github`, `outlook`, `huggingface`) require **human approval**. The line is "does data leave the machine / does it send or mutate".
3. **Approval is caller-identity-scoped, never platform-wide:** the grant rides the action-context (user + service chain) and is checked against **that caller** — approving GitHub for user A does not let agent B or another workflow under A post without its own approval. Per-config approval for send/mutate connectors; the highest-consequence sends can surface a per-call confirm in the dashboard as an **adjustable setting** (surfaced, not a hidden default).
4. **Harness-native outbound stays outside the Connectors door:** a harness's own package/network activity (PyPI install, git clone, raw API) is "the agent doing its job", bounded by the container network policy, not funneled through the connector door. The audit trail covers **connector-mediated** outbound; the network policy covers everything else.
5. **Audit/approval trail view in the dashboard** — the user sees what left the machine and who approved it (no black box).

The connector/audit and inbound-exposure half is detailed in the Connectors chapter (30-services/38) and Publishing (30-services/39).
