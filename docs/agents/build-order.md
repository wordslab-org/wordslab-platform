# Build order — how to implement the spec tickets

The implementation order for the `ready-for-agent` spec issues. It is **dependency-driven**, not the architecture's *service* build order (which assumed the substrate exists): the substrate must be built first or nothing runs. Each stage is independently testable — the **feedback loop is continuous**: after every stage, run the test-harness sweeper (issue #68) — `GET /health` + the vendored conformance suite on every installed service.

> Sources: the v1 catalog build order (ADR-0009 §8), the topology (ADR-0004), the specs #46–#67. The cross-cutting concerns (#65, #66, #67) are **started at stage 0 as base/template contracts** and **verified standalone at the end** — not deferred entirely to the end.

| Stage | Issue(s) | What exists / what's testable now |
|---|---|---|
| **0** | **#68 test harness** + **#46 foundation** | A copy of `service-template/` boots, the canary capability passes the vendored suite, the sweeper reports green. **First feedback loop.** The consent-flag + never-bypassable private/secret exclusion are template contracts from here on (ADR-0026). |
| **1** | **#63 Installer/bootstrap** | WSL/distro/uv/Python, data volumes, first core, front door — the guided journey runs on a real machine (the installer's runbook). |
| **2** | **#62 Platform core** + **#64 dashboard** (thin: first-run + `/health` rail) | Leader up; dashboard shows `/health` + metrics; the standing sweeper (#68) can poll the fleet. The **#65 update/backup machinery** builds into the core here (its `install`/`catalog`/`backup` capabilities). |
| **3** | **#47 Inference** | The first real capability on the contract-tested base; its suite exercises #46; cloud egress will go through #50. |
| **4** | **#50 Connectors (web)** | The audited door is real; agents get web; Inference's cloud calls get their audited path. |
| **5** | **#48 Chat + Agents** | The first agent loop calling Inference (#47); the learning assistant's host. |
| **6** | **#49 Document (parse)** | A corpus exists — the raw layer for memory + Knowledge. |
| **7** | **#51 Development** | The build surface (code-server/JupyterLab/the agentic-dev-workflow) — the platform becomes self-hosting for its own builders. |
| **8** | **#52 Document (rest)** | The Knowledge-dependent surface (bidirectional index, storage delegation, facets, materialization) ready before Knowledge. |
| **9** | **#53 Workflow** | The orchestrator — before Knowledge's pipelines (ADR-0009 §8). |
| **10** | **#54 Knowledge** | Reasoning on the corpus; the semantic authority; the review queue. |
| **11** | **#55 Connectors (rest)** | The remaining tool families (code/social/email/video/modelhub). |
| **12** | **#56 Audio · #57 Image · #58 Media transformations · #59 Generation** (any order) | The four light content services. |
| **13** | **#60 Publishing & Governance** | Ship what you built (deploy/expose + the compliance gate). |
| **14** | **#61 Training & Evaluation** | Produce + measure models (full job-runner form is v1.1). |
| **end** | **#65 Lifecycle · #66 Security · #67 Data consent** — final standalone verification | Their contract parts shipped incrementally (stage 0 onward); here the full boundary + invariants get their standalone pass. |

## The testability rule

**Nothing ships without its contract suite green, and the sweeper re-runs after every stage.** Three things are present *from stage 0* (base/template contracts, not end-stage bolt-ons):

- the **canary capability + the shared test harness** (#46 + #68) — every service's suite consumes the same seam;
- the **consent flag on every user input** + the never-bypassable private/secret exclusion (#46, per ADR-0026) — present in every service's extraction surface from the first service;
- the **security control placement** (#66) checked continuously — a control named in the model has a home from the first service that carries it.

The heavy end-stage pieces of #65/#66/#67 (the anonymizer's quality bar, the update/backup machinery's full mechanics, the security invariants' final verification) land last, but their *contracts* are live from stage 0.
