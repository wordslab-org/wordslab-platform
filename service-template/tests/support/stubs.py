"""The stub-factory for base-contract fixtures (ticket #70, piece b; spec
#68 story 2).

Produces the documented stub shapes every service's contract suite consumes,
all deterministic and offline (no real engine, no network, no real external
system — spec #68 Implementation Decisions):

- `stub_api_key()` — a stub Bearer key (base item 2);
- `stub_401_violations(response)` — the expected-401-body matcher (base
  items 2 + 4);
- `stub_health_payload(...)` + `stub_health_violations(response, payload)` —
  a stub `/health` payload in the documented shape and its matcher (base
  item 6);
- `StubCollaborator` — a stub collaborator endpoint following the base
  contract, wired via `create_service_app(extra_routes=...)`, recording
  every request it serves (dispatch assertions without the real
  collaborator);
- `StubEngine` — a fake engine behind the family-1/2/5 seam returning
  deterministic canned model output (family-1/2 inference, the family-5 model
  catalog and its lifecycle operations), with a family-shaped HTTP surface
  (`/v1/responses`, `/v1/embeddings`, `/v1/models`) so a model-backed
  service's contract behavior is assertable without a real engine;
- `StubRegistry` + `ResolvedReference` — the fake capability registry (the
  name→URL resolver, ADR-0008 §7) that `call`/`model`/`agent` composition
  references resolve against, each to the fake endpoint registered under its
  stable name (typically a `StubCollaborator`'s path).

Test-side only: production code never imports this module (spec #68). The
response-shape checking is NOT duplicated here: the matchers reuse the
suite's canonical checker (`tests.contract.runner.failures`), so stub-factory
drift-detection and the family red gate share one implementation.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from contract.base.consent import MAY_USE, PRIVATE_SECRET
from contract.base.errors import invalid_request
from contract.base.health import CANNOT_SERVE_STATUSES, HEALTH_STATUSES
from contract.base.health import resources as build_resources
from contract.base.pagination import paginate
from tests.contract.runner import failures

__all__ = [
    "COMPOSITION_PRIMITIVES",
    "ResolvedReference",
    "StubCollaborator",
    "StubEngine",
    "StubRegistry",
    "stub_api_key",
    "stub_health_payload",
    "stub_health_violations",
    "stub_401_violations",
    "stub_consent_interaction",
    "stub_consent_gate_violations",
]


# --- stub Bearer key (base item 2) ------------------------------------------

def stub_api_key() -> str:
    """A stub Bearer key for base-contract tests. Unique per call, so a
    service's tests never collide with another key in the same process."""
    return "sk-stub-" + secrets.token_hex(16)


# --- expected 401 body (base items 2 + 4) -----------------------------------

def stub_401_violations(response) -> list[str]:
    """Violations against the documented 401 `authentication_failed` body:
    status 401 (base item 2) plus the canonical error-body checks — the
    shape `{"error": {"type", "message"}, "request_id"}`, the taxonomy type,
    and the `request_id`/`X-Request-Id` pairing (base item 4)."""
    problems: list[str] = []
    if response.status_code != 401:
        problems.append(f"status {response.status_code} != 401 (base item 2)")
    problems += failures(response, "authentication_failed")
    return problems


# --- stub /health payload (base item 6) -------------------------------------

def stub_health_payload(
    *,
    status: str = "ready",
    service: str = "template-service",
    version: str = "0.1.0",
    resources: dict | None = None,
) -> dict:
    """A `/health` payload in the documented item-6 shape:
    `{"status", "service", "version", "resources", "models"?}`. The
    `resources` payload defaults to a zeroed no-GPU machine."""
    if status not in HEALTH_STATUSES:
        raise ValueError(
            f"unknown /health status {status!r} (not in the ADR-0001 item-6 enum)"
        )
    payload: dict = {
        "status": status,
        "service": service,
        "version": version,
        "resources": resources
        if resources is not None
        else dict(
            build_resources(cpu_percent=0.0, ram_gb=(0.0, 0.0), disk_gb=(0.0, 0.0))
        ),
    }
    return payload


def stub_health_violations(response, payload: dict) -> list[str]:
    """Violations of one response against the expected `/health` payload:
    HTTP 200 for alive/progressing states, 503 for cannot-serve states, and
    the body equal to the payload (item 6 fixes the whole shape)."""
    problems: list[str] = []
    expected_code = 503 if payload["status"] in CANNOT_SERVE_STATUSES else 200
    if response.status_code != expected_code:
        problems.append(
            f"status {response.status_code} != {expected_code} for health "
            f"status {payload['status']!r} (base item 6)"
        )
    try:
        body = response.json()
    except ValueError:
        return problems + ["response body is not JSON (base item 1)"]
    if body != payload:
        drifted = {
            key: (body.get(key), payload.get(key))
            for key in set(body) | set(payload)
            if body.get(key) != payload.get(key)
        }
        problems.append(f"health payload drifted: {drifted} (base item 6)")
    return problems


# --- stub collaborator endpoint (spec #68 story 4, base fixtures) ------------


class StubCollaborator:
    """A fake capability endpoint following the base contract: deterministic
    configured body, records every request it serves — dispatch assertions
    without the real collaborator. Offline: no network, no real system.

    Wire it through the service factory's `extra_routes` (full `/v1/...`
    path, base item 3):

        collab = StubCollaborator()
        svc = InProcessService(api_keys=[key], extra_routes=[collab.route])
    """

    def __init__(
        self,
        *,
        path: str = "/v1/collaborator",
        methods: tuple[str, ...] = ("GET", "POST"),
        body: dict[str, Any] | None = None,
        status: int = 200,
    ) -> None:
        if not path.startswith("/v1/"):
            raise ValueError("the collaborator path is a full contract path under /v1 (base item 3)")
        self.path = path
        self.methods = tuple(methods)
        self.body = body if body is not None else {"collaborator": path, "result": "stub-ok"}
        self.status = status
        self.requests: list[dict] = []
        # extra_routes are declared with their full /v1 path (base item 3);
        # the app factory strips the prefix it mounts.
        self.route = Route(path, self._serve, methods=list(self.methods), name="stub-collaborator")

    async def _serve(self, request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:
            payload = None
        self.requests.append(
            {
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.query_params),
                "payload": payload,
            }
        )
        return JSONResponse(self.body, status_code=self.status)


# --- consent-flagged stub interaction + the exclusion-assertion helper
# --- (spec #68 story 9, ticket #72: the ADR-0026 gate as a base-contract-
# --- level assertion, testable at every service's seam from the first
# --- service).

def stub_consent_interaction(
    *,
    text: Any = "hello",
    consent: str = MAY_USE,
    **fields: Any,
) -> dict:
    """A consent-flagged stub interaction in the template's recorded shape
    (`{text, consent}` — the canary's record; `**fields` extends it with a
    service's own keys). The consent flag defaults to the ADR-0026 §1
    default ("may use for improvement"); pass `consent=PRIVATE_SECRET` for
    the "private/secret — do not use" state."""
    if consent not in (MAY_USE, PRIVATE_SECRET):
        raise ValueError(
            f"unknown consent state {consent!r}: expected 'may_use' or "
            "'private_secret' (ADR-0026 §1)"
        )
    interaction: dict[str, Any] = {"text": text, "consent": consent}
    interaction.update(fields)
    return interaction


def stub_consent_gate_violations(extracted: list, recorded: list) -> list[str]:
    """Violations of an extraction surface against the never-bypassable
    private/secret exclusion (ADR-0026 §2 pass 1, filter = the consent
    gate): given the RECORDED interactions (pre-extraction) and the
    EXTRACTION's output (the list of interactions it returned), report

    - a private/secret (or state-less) recorded interaction appearing
      VERBATIM in the output — the exclusion bypassed;
    - an output item whose consent state is not `may_use` — an eligible
      interaction must carry the flag, fail-closed.

    Content-level leak detection (a re-marked copy of a private interaction)
    needs interaction identity — the consent lanes' substrate (ticket #286)
    owns it; at the template level this is the canary-proven assertion
    shape."""
    problems: list[str] = []
    private_records = [i for i in recorded if i.get("consent") != MAY_USE]
    for item in extracted:
        if any(item == record for record in private_records):
            problems.append(
                "a private/secret interaction leaked through the extraction "
                "verbatim (ADR-0026 §2: the exclusion is never bypassable)"
            )
        state = item.get("consent")
        if state != MAY_USE:
            problems.append(
                f"an extracted interaction carries consent state {state!r}, "
                f"not 'may_use' (ADR-0026 §2: only may-use interactions are "
                "eligible to pass)"
            )
    return problems


# --- stub engine (spec #68 story 3; the family-1/2/5 seam) ------------------
# A fake model-serving engine behind the family-1/2/5 seam (ADR-0001
# §Families.1/2/5): deterministic canned model output, offline — no engine, no
# network, no randomness the tests cannot reproduce (spec #68 Implementation
# Decisions). A model-backed capability calls the engine's operations;
# `routes()` exposes the same output as a family-shaped HTTP surface so the
# engine is assertable over the one seam — and so a family conformance block
# (#76–#84) can satisfy its stub-backed cases without a real engine. The stub
# serves the family modules; it never implements them.

# The composition primitive kinds a reference can carry (ADR-0007 §3): `call`
# = a service capability, `model` = a raw model call, `agent` = run a native
# agent to completion. The other primitives (`subworkflow`/`delay`/`event`/
# `user_input`) are not service references, so they never reach the resolver.
#
# Of the three, `call` (a service capability) and `agent` (an agent entry) are
# registry entries the name→URL resolver serves (ADR-0008 §2/§7); `model` is
# NOT a registry entry — ADR-0008 §2 keeps models out ("models are never
# entries"); a `model(...)` reference names an explicit implementation choice
# (ADR-0007 §10) whose surface is the Responses API (ADR-0007 §5). The stub
# resolves all three kinds uniformly so a composition test can assert dispatch
# without the real collaborator (spec #68 story 4); the `model` primitive's
# exact resolution path is an open question flagged on ticket #73.
COMPOSITION_PRIMITIVES = ("call", "model", "agent")


def _stable_token(value: object) -> str:
    """A deterministic token derived from a value — the stub engine's ids are
    reproducible, never random (spec #68 Implementation Decisions)."""
    payload = json.dumps(
        value, sort_keys=True, default=str, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:24]


def _count_tokens(value: object) -> int:
    """A deterministic token count (whitespace words). The family-1/2 `usage`
    unit is the reference API's (tokens); the stub does not ship a tokenizer."""
    return len(str(value).split())


def _stub_vector(text: str, dim: int) -> list[float]:
    """A deterministic pseudo-embedding for `text` — reproducible floats, no
    model, no randomness."""
    seed = int(_stable_token(text), 16)
    return [round(((seed >> (i * 4)) & 0xF) / 15.0, 4) for i in range(dim)]


async def _json_object(request: Request) -> dict:
    """The request body as a JSON object; a malformed or non-object body is
    the contract's 400 `invalid_request` (base item 4), never a 500."""
    try:
        parsed = await request.json()
    except ValueError:
        raise invalid_request("Expected a JSON object request body.") from None
    if not isinstance(parsed, dict):
        raise invalid_request("Expected a JSON object request body.")
    return parsed


class StubEngine:
    """A fake engine behind the family-1/2/5 seam (spec #68 story 3).

    Deterministic and offline: every output is derived purely from the request
    (a stable hash for ids, whitespace for token counts, a hashed vector for
    embeddings) — no engine, no network, no randomness. The family-5 lifecycle
    operations (`download`/`load`/`unload`/`prepare`) are the in-process engine
    seam a family-5 module calls — deterministic status transitions, no HTTP
    routes (the lifecycle surface is that module's, #80). Wire the
    family-shaped surface through the factory's `extra_routes`:

        engine = StubEngine()
        svc = InProcessService(extra_routes=engine.routes())
    """

    def __init__(
        self,
        *,
        model_name: str = "stub-model",
        models: list[dict] | None = None,
        embedding_dim: int = 8,
    ) -> None:
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self.models = (
            list(models)
            if models is not None
            else [
                {
                    "id": model_name,
                    "supported": True,
                    "recommended": True,
                    "downloaded": True,
                    "size_gb": 1.0,
                    "status": "ready",
                }
            ]
        )
        self.calls: list[dict] = []

    # --- the engine operations a model-backed capability calls ---------------

    def responses(self, request: dict) -> dict:
        """A family-1 Responses-API body (ADR-0001 §Families.1) — the canned
        model output for `request`, deterministic in the request."""
        self.calls.append({"operation": "responses", "request": request})
        text = "stub-response:" + str(request.get("input", ""))
        usage = {
            "input_tokens": _count_tokens(request.get("input", "")),
            "output_tokens": _count_tokens(text),
        }
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
        return {
            "id": "resp_" + _stable_token(request),
            "object": "response",
            "model": request.get("model", self.model_name),
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                }
            ],
            "usage": usage,
        }

    def embeddings(self, request: dict) -> dict:
        """A family-2 embeddings body (ADR-0001 §Families.2) — deterministic
        pseudo-embeddings, one per input."""
        self.calls.append({"operation": "embeddings", "request": request})
        inputs = request.get("input")
        if isinstance(inputs, str):
            inputs = [inputs]
        inputs = inputs if isinstance(inputs, list) else []
        return {
            "object": "list",
            "model": request.get("model", self.model_name),
            "data": [
                {
                    "object": "embedding",
                    "index": index,
                    "embedding": _stub_vector(str(text), self.embedding_dim),
                }
                for index, text in enumerate(inputs)
            ],
            "usage": {"prompt_tokens": sum(_count_tokens(text) for text in inputs)},
        }

    def model_catalog(self) -> list[dict]:
        """A family-5 model catalog (ADR-0001 §Families.5) — copies, so a
        caller cannot mutate the stub's state."""
        return [dict(model) for model in self.models]

    # --- the family-5 model-lifecycle seam (ADR-0001 §Families.5) -----------
    # The in-process lifecycle operations a family-5 module calls (the HTTP
    # lifecycle surface — /v1/models/{id}/load, the job object — is that
    # module's, #80). Each applies a deterministic status transition to the
    # stub's catalog; an unknown model is a loud rejection.

    def download(self, model_id: str) -> dict:
        """`absent` → `available` (the download step; synchronous in the stub
        — the job object is the family module's surface, not the engine's)."""
        self.calls.append({"operation": "download", "model": model_id})
        model = self._model(model_id)
        if model["status"] == "absent":
            model["downloaded"] = True
            model["status"] = "available"
        return dict(model)

    def load(self, model_id: str) -> dict:
        """`available`/`error` → `ready`."""
        self.calls.append({"operation": "load", "model": model_id})
        model = self._model(model_id)
        if model["status"] in ("available", "error"):
            model["status"] = "ready"
        return dict(model)

    def unload(self, model_id: str) -> dict:
        """`ready` → `available`."""
        self.calls.append({"operation": "unload", "model": model_id})
        model = self._model(model_id)
        if model["status"] == "ready":
            model["status"] = "available"
        return dict(model)

    def prepare(self, model_id: str) -> dict:
        """The full prepare sequence (ADR-0001 §Families.5): download when
        absent, unload the other resident model, then load the target to
        `ready`."""
        self.calls.append({"operation": "prepare", "model": model_id})
        target = self._model(model_id)
        for model in self.models:
            if model is not target and model["status"] == "ready":
                model["status"] = "available"
        if target["status"] == "absent":
            target["downloaded"] = True
        target["status"] = "ready"
        return dict(target)

    def _model(self, model_id: str) -> dict:
        """The stub's live record for `model_id` (mutated in place by the
        lifecycle operations); an unknown model is a loud rejection."""
        for model in self.models:
            if model["id"] == model_id:
                return model
        raise ValueError(
            f"no such model {model_id!r} — not a lifecycle target "
            "(ADR-0001 §Families.5)"
        )

    # --- the family-shaped HTTP surface -------------------------------------

    def routes(self) -> list[Route]:
        """The engine's output as a family-shaped HTTP surface
        (`/v1/responses`, `/v1/embeddings`, `/v1/models`) — wire via
        `extra_routes`. This is the TEST-SIDE stand-in for a family module's
        surface: a real service's family module (#76–#84) owns its own
        surface and calls the engine's operations, so a service never wires
        these routes alongside its own module."""

        async def responses_endpoint(request: Request) -> JSONResponse:
            return JSONResponse(self.responses(await _json_object(request)))

        async def embeddings_endpoint(request: Request) -> JSONResponse:
            return JSONResponse(self.embeddings(await _json_object(request)))

        async def models_endpoint(request: Request) -> JSONResponse:
            return paginate(request, self.model_catalog(), key_fn=lambda m: m["id"])

        return [
            Route("/v1/responses", responses_endpoint, methods=["POST"]),
            Route("/v1/embeddings", embeddings_endpoint, methods=["POST"]),
            Route("/v1/models", models_endpoint, methods=["GET"]),
        ]


# --- stub-collaborator resolution (spec #68 story 4; ADR-0008 §7/§8) --------
# The fake capability registry: the name→URL resolver composition references
# resolve against (ADR-0008 §7) — standing in for the leader core's registry in
# tests. Names are reserved explicitly (no probing, no magic); a reference of
# any composition-primitive kind resolves by stable name to a fake endpoint (a
# `StubCollaborator`), which records the dispatched request. Deterministic and
# offline: no core, no network.


@dataclass(frozen=True)
class ResolvedReference:
    """One resolved composition reference: the primitive that made it, the
    stable name it named, and the endpoint it resolves to (ADR-0008 §7)."""

    primitive: str
    name: str
    endpoint: str


def _validate_stable_name(name: str) -> None:
    """A stable name is `<service>.<capability>` (or `<service>.<kind>.<name>`
    for authored entries) — dot-separated, non-empty parts (ADR-0008 §8)."""
    parts = name.split(".")
    if len(parts) < 2 or any(not part for part in parts):
        raise ValueError(
            f"Invalid stable name {name!r}: expected <service>.<capability> "
            "(ADR-0008 §8)."
        )


class StubRegistry:
    """The fake capability registry — the name→URL resolver (ADR-0008 §7) that
    `call`/`model`/`agent` composition references resolve against in tests.

    Register a fake endpoint under a stable name, then resolve a reference of
    any composition-primitive kind:

        collab = StubCollaborator()
        registry = StubRegistry()
        registry.register("document.parse", collab.path)
        reference = registry.resolve("call", "document.parse")
        svc = InProcessService(extra_routes=[collab.route])
        # ... dispatch `reference.endpoint` through the seam

    Resolution is kind-agnostic (ADR-0008 §7: one registry, one name→URL
    role) — the primitive is recorded on the reference, not used to select the
    endpoint.
    """

    def __init__(self) -> None:
        self._endpoints: dict[str, str] = {}

    def register(self, name: str, endpoint: str) -> None:
        """Reserve a stable name → endpoint. The endpoint is the entry's
        resolving reference — opaque to the registry (ADR-0008 §1: "a
        reference to the owning service"), so no path shape is imposed here;
        in a test it is typically a `StubCollaborator`'s `/v1/...` route path.
        A second claimant is refused: a name is reserved once (ADR-0008 §8)."""
        _validate_stable_name(name)
        if not isinstance(endpoint, str) or not endpoint:
            raise ValueError(
                "The endpoint is the entry's resolving reference (ADR-0008 §1)."
            )
        if name in self._endpoints:
            raise ValueError(
                f"The stable name {name!r} is already reserved — a second "
                "claimant can never shadow it (ADR-0008 §8)."
            )
        self._endpoints[name] = endpoint

    def resolve(self, primitive: str, name: str) -> ResolvedReference:
        """Resolve a composition reference: validate the primitive kind
        (ADR-0007 §3) and the stable name → its endpoint (ADR-0008 §7)."""
        if primitive not in COMPOSITION_PRIMITIVES:
            raise ValueError(
                f"Unknown composition primitive {primitive!r}: expected one of "
                f"{COMPOSITION_PRIMITIVES!r} (ADR-0007 §3)."
            )
        endpoint = self._endpoints.get(name)
        if endpoint is None:
            raise ValueError(
                f"No capability is registered under the stable name {name!r} — "
                "the reference does not resolve (ADR-0008 §7)."
            )
        return ResolvedReference(primitive, name, endpoint)
