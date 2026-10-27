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
`structured_outputs`, `citations`, `reasoning`, `refusals`, `streaming`) plus
its documented deviations from the upstream shapes ("follow upstream OpenAI
shapes; document deviations, pinned to a reference date"). Passing that matrix
to `responses_routes()` turns it into a **gate**: a request needing a feature the
selected implementation lacks is refused with a 400 that names the feature and
the implementation, before the engine is called — no silent substitution
(ADR-0007 §10's explicit-implementation rule). Without a matrix the route does
not gate; the implementation then owns the refusal itself.

The matrix is **feature support, not a ranking**. Rankings (quality, speed,
cost) are dynamic — artificialanalysis at selection time — and must never be
stored in a declaration (ADR-0031 §5). This is the opposite kind of fact, and
the two never mix.

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
   `fragments=[..., family_1.openapi_fragment]`.
3. **Declare the family in the test suite** — `tests/contract/families/
   manifest.toml` → `families = ["1"]` — and keep the block. The block is the
   vendored conformance gate: it drives the module against the deterministic
   `StubEngine`, never a real model.
4. **Deviation**: if an implementation cannot follow an upstream shape, record
   it in its `SUPPORT.deviations` and in its docs — a deviation that is only in
   code is a divergence nobody can audit.
