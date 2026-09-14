# Family-contract verification postures

**Source of truth: ADR-0001** (the families referenced below) and the back-pointers per risk. This chapter records the **verification posture** for the three build-time risks that threaten whole contract families — how each is handled (verify-early prototype, documented fallback, or accept-and-learn), when it is checked, and what the fallback shape is. It decides the *posture*, not the family contracts' content (that stays in ADR-0001). Settled by ticket #40.

The three risks were flagged in ADR-0001's "Open risks for the service template" as build-time risks. Each threatens a whole contract family, and **each family fails differently** — so each gets its own posture rather than one shared answer:

| Family / risk | Posture | When checked | Fallback shape |
|---|---|---|---|
| Family 1 — Ollama vision-through-Responses | **Accept-and-learn** | At template build-time gate (ADR-0001's existing "verify at template build time") | Service adapter already absorbs the engine gap — not a contract deviation |
| Families 3 + base 9 — stateless MCP transport | **Documented fallback (pin + verify)** | At template build (pinned reference SDK verified against the stateless spec) | **Traditional stateful MCP** (contract amendment if the pinned FastMCP reference SDK does not honor the stateless transport) |
| Family 4 — WebRTC on LAN | **Accept-and-learn** | During the dashboard build, on a real home LAN | WebSocket (already a defined path in family 4) |

## Ollama vision-through-Responses (family 1) — accept-and-learn

The family-1 contract surface is the OpenAI Responses API, with Ollama as the local engine. Local engines can lag on vision-through-Responses. ADR-0001 already settles the **shape**: the service adapter absorbs the engine gap, so it is **not a contract deviation**. Because the adapter is whatever bridges Ollama's surface to the Responses shape, it *is* the documented fallback — there is no separate open design question, only when to confirm it works.

**Posture: accept-and-learn.** No dedicated early spike. The check happens naturally at the template build-time gate (ADR-0001's existing "verify Responses+vision on Ollama at template build time"), when the adapter is actually built and exercised. If the bridge proves impossible, that would surface a family-1 contract amendment — a genuinely separate decision raised as a new ticket then, not pre-empted here.

## Stateless MCP transport (families 3 + base 9) — documented fallback, verify at build

Both the base contract's callable surfaces (base item 9: stateless MCP at `/mcp`, tools auto-generated from OpenAPI) and the tool-services family (family 3) rest on the reference SDK supporting the spec's **stateless** transport (spec 2026-07-28; per-request headers, no sessions). Every service exposes `/mcp`, so this is the widest blast radius of the three.

**Posture: documented fallback (pin + verify).** Pin the FastMCP reference SDK at template build and verify it honors the stateless transport. **If the pinned reference SDK does not support stateless MCP, fall back to traditional stateful MCP** — a contract amendment (ADR-0001 family 3 / base item 9 are amended to the session-based transport), the fallback shape from #40's Context. No sanity-shim emulating stateless is added; the honest amendment is preferred over a shim. Raised as a new ticket if that fallback ever triggers.

## WebRTC on LAN (family 4) — accept-and-learn

Family 4 (realtime voice) defines **WebRTC primary** — what the browser dashboard needs for live voice — and **WebSocket for server-side agents**. Two already-settled decisions thin this risk: ADR-0017 grounds browser WebRTC in the HTTPS secure-context posture (browsers require it; WebRTC rides the trusted-LAN/HTTPS posture, not standalone), and ADR-0001's considered options note that **on a home LAN no STUN/TURN is required**. The only genuinely untested bit is WebRTC peer-connection working reliably on a real home LAN.

**Posture: accept-and-learn.** **WebSocket is the documented fallback** — it is already a defined path in family 4, so the family still works if WebRTC misbehaves on some browser or router. Verify WebRTC on an actual home LAN during the dashboard build (the dashboard is family 4's primary consumer). No dedicated early spike; no STUN/TURN machinery is added.