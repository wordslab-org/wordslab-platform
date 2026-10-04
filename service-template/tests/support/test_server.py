"""The in-process test-server helper (spec #68, piece a).

Spins up the FULL template service in-process — base contract + the canary
capability + its three callable surfaces (`/openapi.json`, `/mcp`, `/echo`)
— and drives it over real HTTP (Starlette's ASGI transport — the full
middleware + routing stack, no port bound, no network, no real engine).
Every service's contract suite consumes this same seam, vendored with the
template (ADR-0002).

This is a TEST-SIDE artifact: production code never imports it (spec #68,
Implementation Decisions).
"""

from __future__ import annotations

from typing import Any

from starlette.testclient import TestClient

from app import create_app
from .stubs import stub_api_key  # the stub-factory is the single source (ticket #70)

# Paths the base contract leaves unauthenticated. `/health` must be
# readable without a key: it is the monitoring/dashboard surface
# (ADR-0001 item 6 — the dashboard reads /health for status colors).
UNAUTHENTICATED_PATHS = frozenset({"/health"})


class InProcessService:
    """The template service running in-process over real HTTP.

    Usage:

        svc = InProcessService()
        with svc.client as client:
            r = client.get("/health")
    """

    def __init__(
        self,
        *,
        service_name: str | None = None,
        version: str | None = None,
        api_keys: list[str] | None = None,
        **app_kwargs: Any,
    ) -> None:
        self.api_keys = api_keys if api_keys is not None else [stub_api_key()]
        self.app = create_app(
            api_keys=self.api_keys,
            service_name=service_name,
            version=version,
            **app_kwargs,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def authorized(self) -> TestClient:
        """The same client with the stub Bearer key applied to every request."""
        self.client.headers["Authorization"] = f"Bearer {self.api_keys[0]}"
        return self.client

    def close(self) -> None:
        self.client.close()
