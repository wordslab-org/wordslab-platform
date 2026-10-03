"""Base contract item 4 — Errors (ADR-0001 §Base contract.4).

Fixed 11-code taxonomy. Error bodies are
`{"error": {"type", "message", "resource"?}, "request_id"}` and every
response carries `X-Request-Id`. No rate limiting in v1 (429 means resource
exhaustion, nothing else), no 422, no per-endpoint error enums.
"""

from __future__ import annotations

# The 11 codes, verbatim from ADR-0001 item 4. 503 deliberately carries two
# types (`busy` and `unavailable`), so the taxonomy maps type → status, not
# the other way round.
ERROR_TAXONOMY: dict[str, int] = {
    "invalid_request": 400,
    "authentication_failed": 401,
    "permission_denied": 403,
    "not_found": 404,
    "conflict": 409,
    "request_too_large": 413,
    "resource_exhausted": 429,
    "internal_error": 500,
    "busy": 503,
    "unavailable": 503,
    "timeout": 504,
}

# Resource names for 429 `resource_exhausted` (ADR-0001 item 4; the
# `cloud-spend` name comes from ADR-0005).
RESOURCE_EXHAUSTED_RESOURCES = ("vram", "ram", "disk", "gpu", "cloud-spend")


class ApiError(Exception):
    """One error type from the ADR-0001 item-4 taxonomy.

    Raise this anywhere in a capability; the app's exception handler turns it
    into the contract error body with the request's `X-Request-Id`.
    """

    def __init__(
        self,
        type_: str,
        message: str,
        *,
        resource: str | None = None,
        status: int | None = None,
    ) -> None:
        if type_ not in ERROR_TAXONOMY:
            raise ValueError(f"unknown error type {type_!r} (not in the 11-code taxonomy)")
        if status is None:
            status = ERROR_TAXONOMY[type_]
        if type_ == "resource_exhausted" and resource is None:
            raise ValueError("resource_exhausted requires a `resource` name (vram/ram/disk/gpu/cloud-spend)")
        super().__init__(message)
        self.type = type_
        self.message = message
        self.resource = resource
        self.status = status

    def body(self, request_id: str) -> dict:
        error: dict = {"type": self.type, "message": self.message}
        if self.resource is not None:
            error["resource"] = self.resource
        return {"error": error, "request_id": request_id}


# Convenience constructors — one per taxonomy code, so call sites read as the
# contract reads.
def invalid_request(message: str) -> ApiError:
    return ApiError("invalid_request", message)


def authentication_failed(message: str = "Missing or invalid API key.") -> ApiError:
    return ApiError("authentication_failed", message)


def permission_denied(message: str = "This key is not allowed to perform this operation.") -> ApiError:
    return ApiError("permission_denied", message)


def not_found(message: str = "Resource not found.") -> ApiError:
    return ApiError("not_found", message)


def conflict(message: str) -> ApiError:
    return ApiError("conflict", message)


def request_too_large(message: str = "Request body too large.") -> ApiError:
    return ApiError("request_too_large", message)


def resource_exhausted(resource: str, message: str) -> ApiError:
    return ApiError("resource_exhausted", message, resource=resource)


def internal_error(message: str = "Internal error.") -> ApiError:
    return ApiError("internal_error", message)


def busy(message: str = "The service is busy; retry later.") -> ApiError:
    return ApiError("busy", message)


def unavailable(message: str = "The service is unavailable; retry later.") -> ApiError:
    return ApiError("unavailable", message)


def timeout(message: str = "The operation timed out.") -> ApiError:
    return ApiError("timeout", message)
