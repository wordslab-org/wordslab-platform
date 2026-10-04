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
  collaborator; the composition-specific resolution patterns remain #73).

Test-side only: production code never imports this module (spec #68). The
response-shape checking is NOT duplicated here: the matchers reuse the
suite's canonical checker (`tests.contract.runner.failures`), so stub-factory
drift-detection and the family red gate share one implementation.
"""

from __future__ import annotations

import secrets
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from contract.base.health import CANNOT_SERVE_STATUSES, HEALTH_STATUSES
from contract.base.health import resources as build_resources
from tests.contract.runner import failures

__all__ = [
    "StubCollaborator",
    "stub_api_key",
    "stub_health_payload",
    "stub_health_violations",
    "stub_401_violations",
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

