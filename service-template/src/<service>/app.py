"""The service's own assembly — the stable shell (ADR-0029 §4, amended by
ADR-0031 §1: a service is a set of capabilities).

This is the ONE file a service edits to compose itself: it loads the
declaration (`service.toml` — identity is data, not code), assembles the
OpenAPI document from the capabilities' fragments, and hands everything to
the base factory (`contract/base/app.py` — vendored, never edited). The
canary capability ships with the template and is always mounted: it proves
the template out of the box (copy → run the suite → green, ticket #71).
"""

from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette

from contract.base.app import create_service_app
from contract.base.openapi import openapi_document
from contract.declaration.service_toml import load_service_toml

try:  # installed-package mode (`<service-name>.app`)
    from .capabilities import canary
except ImportError:  # the template's own suite (conftest seeds src/<service>)
    from capabilities import canary

# The declaration lives at the service root — this file is
# `src/<service-name>/app.py`, so two parents up. The copy-to-start ritual
# renames `src/<service>/` (CONTRIBUTING.md step 2); the relative shape —
# and this path — survive the rename unchanged.
DECLARATION_PATH = Path(__file__).resolve().parents[2] / "service.toml"


def create_app(
    *,
    api_keys: list[str],
    service_name: str | None = None,
    version: str | None = None,
    extra_routes=None,
    idempotency_store=None,
    resources: dict | None = None,
    models: dict | None = None,
    health_status: str = "ready",
) -> Starlette:
    """Assemble the full service app: base contract + capabilities + surfaces.

    `service_name`/`version` default to the declaration's identity; test
    fixtures may override them (the vendored suite does). `extra_routes` are
    additional capability routes under `/v1` (the base factory mounts them).
    """
    declaration = load_service_toml(DECLARATION_PATH)
    name = service_name or declaration.name
    version_ = version or declaration.version

    openapi_doc = openapi_document(
        title=name,
        version=version_,
        description=declaration.description,
        fragments=[canary.openapi_fragment],
    )

    return create_service_app(
        service_name=name,
        version=version_,
        api_keys=api_keys,
        resources=resources,
        models=models,
        health_status=health_status,
        extra_routes=[*canary.routes, *(extra_routes or [])],
        ui_routes=canary.ui_routes(name, version_),
        openapi_doc=openapi_doc,
        idempotency_store=idempotency_store,
    )
