"""Base contract item 6 — Health (ADR-0001 §Base contract.6).

`GET /health` → `{"status", "service", "version", "resources", "models"?}`.
Status enum and the 200/503 split are the ADR's, not ours.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

# The status enum, verbatim from ADR-0001 item 6.
HEALTH_STATUSES = (
    "starting",      # alive/progressing
    "installing",
    "downloading",
    "backing_up",
    "ready",
    "busy",
    "degraded",      # needs human maintenance, still serving
    "full",          # cannot serve
    "stopping",      # cannot serve
    "down",          # cannot serve
)
CANNOT_SERVE_STATUSES = frozenset({"full", "stopping", "down"})


def health_endpoint(service_name: str, version: str, *, get_status=None, get_resources=None, get_models=None):
    """Build the `/health` route. `get_status`/`get_resources`/`get_models`
    are zero-arg callables the service supplies so /health reports live state
    rather than constants; the resources/models payload shape is the ADR's:
    used/total per host (cpu/gpu percent, ram/vram/disk GB; gpu/vram omitted
    when no GPU), `models` = per-model status dict for model-backed services.
    """

    async def health(request: Request) -> JSONResponse:
        status = get_status() if get_status else "ready"
        if status not in HEALTH_STATUSES:
            raise ValueError(f"unknown /health status {status!r} (not in the ADR-0001 item-6 enum)")
        body: dict = {
            "status": status,
            "service": service_name,
            "version": version,
            "resources": get_resources() if get_resources else {},
        }
        models = get_models() if get_models else None
        if models is not None:
            body["models"] = models
        code = 503 if status in CANNOT_SERVE_STATUSES else 200
        return JSONResponse(body, status_code=code)

    return health
