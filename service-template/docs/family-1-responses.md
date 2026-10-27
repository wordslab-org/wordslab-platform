# Family 1 — the Responses API module and its support matrix

The template ships family 1 of the service contract (ADR-0001 §Families.1) as
one self-contained module: the **OpenAI Responses API by reference** at
`POST /v1/responses`. A model-backed capability keeps the module and mounts its
route; a service that does not do inference deletes the directory whole
(CONTRIBUTING.md step 5).

## What it is

`src/_service_/contract/families/family_1_responses/` — four pieces, one per
concern:

- **`shapes.py`** — the vocabulary and the two shapes. `parse_request()` turns a
  request body into what the engine seam receives (a bare string `input` becomes
  one `input_text` part; function tools and MCP servers are the two tool kinds);
  `normalize_response()` turns an engine reply into the contract body — the
  `resp_` id, `object: "response"`, the item/part vocabulary, and `usage` in
  tokens. A malformed REQUEST is 400 `invalid_request`; a malformed ENGINE REPLY
  is 500 `internal_error`, because the implementation, not the caller, is wrong.
- **`events.py`** — the typed streaming vocabulary (`response.created` …
  `response.completed`) and `events_for()` / `sse_frames()`. The contract fixes
  the event ORDER and the frame format (`event: <type>` + `data: <json>`), not
  the pacing: the module derives the sequence from the completed body, and an
  adapter that streams natively emits the same frames earlier. There is no
  `[DONE]` sentinel in the Responses API — the terminal event closes the stream.
- **`support.py`** — the per-implementation `SupportMatrix` (see below).
- **`api.py`** — the OpenAPI fragment a capability merges into the service
  document; the `/mcp` tools are auto-generated from that document, so merging
  the fragment is what makes inference agent-callable (base item 9).

`routes.py` is the seam: `responses_routes(engine, support=…, implementation=…)`
mounts the route for one engine. The module owns the contract; the engine owns
the model.

## The support matrix (why it exists)

ADR-0004 makes a capability's API the **union of its implementation
variants**: a local GGUF engine may not take audio input, a cloud provider may
not return reasoning items. The contract does not force-fit them — it requires
the difference to be **declared and documented** rather than discovered by a
failed request.

Each implementation's adapter module exports `SUPPORT: SupportMatrix` — the
features it supports (`vision`, `audio`, `function_tools`, `mcp_tools`,
`structured_outputs`, `citations`, `reasoning`, `refusals`) plus its documented
deviations from the upstream shapes and the `reference_date` they were checked
against ("follow upstream OpenAI shapes; document deviations, pinned to a
reference date"). Passing that matrix to `responses_routes()` turns it into a
**gate**: a request needing a feature the selected implementation lacks is
refused with a 400 that names the feature and the implementation, before the
engine is called — no silent substitution (ADR-0007 §10's explicit-implementation
rule). Without a matrix the route does not gate; the implementation then owns the
refusal itself.

`streaming` is deliberately **not** a feature: the typed event sequence is the
module's own (`events.py`), so every implementation that serves this route
streams. Output-side features (citations, reasoning, refusals) cannot be
requested either — they are discovered from the response — so for those the
matrix is documentation. An **empty** `supported` set is legal and meaningful:
plain text in, plain text out is family 1's always-supported base, so a small
local model with no vision, no tools and no structured outputs declares exactly
that and is a legitimate variant (ADR-0004: the API is the union of its
variants, not their intersection).

The matrix is **feature support, not a ranking**. Rankings (quality, speed,
cost) are dynamic — artificialanalysis at selection time — and must never be
stored in a declaration (ADR-0031 §5). This is the opposite kind of fact, and
the two never mix.

## Deviations from the upstream reference

Pinned to the upstream Responses API shapes as of **2026-10-27**. The module
carries the surface ADR-0001 §Families.1 fixes; what it does not carry is
listed here rather than left to be discovered (ADR-0001: "document deviations"):

- **Request fields read**: `model`, `input`, `instructions`, `tools`, `text`,
  `stream`, `max_output_tokens`, `background` (`false` is the synchronous
  default and is dropped; `true` — or any non-boolean — is 400).
- **Request fields forwarded, not interpreted**: every OTHER top-level key is
  passed to the engine untouched (base item 3: additive changes stay
  backward-compatible within a major) — an adapter that understands
  `temperature`, `top_p`, `tool_choice`, `metadata` or `truncation` receives it
  as-is, and one that does not is documented in its own `SUPPORT.deviations`.
  **Forwarded is not honored**: `previous_response_id`, `store` and `include`
  reach the engine, but this module keeps no response store and rebuilds the
  body from a fixed key set (and re-prefixes the engine's id to `resp_…`), so
  continuation and expansion cannot work here — a capability that needs them
  says so in its own docs.
- **Forwarded keys are engine-visible, not interpreted.** In particular the
  ADR-0026 consent flag and the user/role attribution are NOT contract fields of
  family 1: a capability that accepts them must enforce the consent/sphere rule
  BEFORE the engine call — forwarding is not honoring.
- **`text.format.type`**: only `text` and `json_schema` are accepted.
  Upstream's `json_object` is refused (400) rather than silently treated as
  text — ask for `json_schema` instead.
- **`file_id` inputs**: family 7's file references (`input_file`, `file_id` on
  an image) are not part types here — an image arrives by URL. ADR-0001
  §Families.7 makes `file_id` a cross-family input; wiring it is that family's
  ticket, and until then this module refuses rather than guesses.
- **Response-body fields not emitted**: the body carries `id`, `object`,
  `created_at`, `status`, `model`, `output`, `usage` (plus `instructions` when the
  request carried it). Upstream's `error`, `incomplete_details`,
  `background`, `service_tier`, `user`, `prompt_cache_key`, `max_output_tokens`,
  `store`, `previous_response_id`, `tools`, `text`, `tool_choice`,
  `temperature`, `top_p`, `truncation`, `metadata` and `parallel_tool_calls` are
  absent — so an `incomplete` response reports its status without a reason.
- **`usage` carries the three counts only** (`input_tokens`, `output_tokens`,
  `total_tokens`): upstream's `input_tokens_details` / `output_tokens_details`
  (cached-token counts) are dropped, so a service that reports on base item 8
  cannot see its cache hit rate from this surface.
- **`background: true`** is refused (400) with a message pointing at family 5
  (async jobs), rather than silently serving a synchronous turn.
- **Tool loop**: a previous turn's `function_call` and its
  `function_call_output` are accepted as input ITEMS (never inside a message's
  `content`, where upstream has none) — that pair is what makes a loop closable.
  `mcp_approval_response` is NOT accepted — the MCP approval flow is the
  Connectors service's, and a service that needs it declares the deviation.
- **Event types**: the module emits `response.created`, `response.in_progress`,
  `output_item.added/done`, `content_part.added/done`, `output_text.*`,
  `refusal.*`, `function_call_arguments.*`, `reasoning_summary_text.*` and a
  terminal `response.completed/incomplete/failed`. Upstream's
  `response.output_text.annotation.added` is **not** emitted: annotations are not
  streamed as a separate event — they are already populated on the
  `content_part.added` / closed part that carries them.


## What is deliberately NOT here

- **Engine adapters** — Ollama, vLLM, sglang, the cloud gateway: the Inference
  service's implementation tickets (#119, #120). They implement
  `ResponsesEngine.responses()` and declare `SUPPORT`.
- **The model catalog and the download/load lifecycle** — family 5, ticket #80.
- **Background responses** (`"background": true`) — family 5's async surface
  too, so the module refuses them with a message saying so, instead of
  pretending they work.
- **Schema validation of structured outputs** — the module enforces that a turn
  declaring `json_schema` returns parseable JSON (an unparseable reply is a
  500); honoring the *schema* is the engine's job, and the adapter's
  conformance is where that is tested.

## How to use it

1. **Mount it** in the capability that implements inference:

   ```python
   from contract.families import family_1_responses as family_1

   routes = family_1.responses_routes(
       engine, support=adapter.SUPPORT, implementation="ollama"
   )
   ```

2. **Merge the fragment** into the service document:
   `fragments=[..., family_1.openapi_fragment]`. The fragment is written inline
   (no `$ref` in the request body) so the auto-generated MCP tool carries real
   parameters, and it does NOT define the item-4 `error` schema — the base
   document supplies that once for every service.
3. **Declare the family in the test suite** — `tests/contract/families/
   manifest.toml` → `families = ["1"]` — and keep the block. The block is the
   vendored conformance gate: it drives the module against the deterministic
   `StubEngine`, never a real model.
4. **Deviation**: if an implementation cannot follow an upstream shape, record
   it in its `SUPPORT.deviations` and in its docs — a deviation that is only in
   code is a divergence nobody can audit.
