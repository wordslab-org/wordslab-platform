"""The canary capability (ticket #71) — the template's proof capability.

A minimal skeleton capability wired to the three callable surfaces the base
contract mandates (ADR-0001 item 9, ADR-0002 §3/§4):

- **deterministic**: `POST /v1/echo` (returns the request body) and
  `GET /v1/echo/ping` (returns pong) — routes in `routes.py`, OpenAPI
  fragment in `api.py`;
- **agent**: its tools are auto-generated from the OpenAPI fragment by the
  base machinery (`contract/base/mcp.py`) — the canary ships no MCP code;
- **human**: the Echo page (`page.py`) at `/echo` — FastHTML + vendored
  Alpine.js, calling the same `/v1/echo` API.

This capability is the pattern a real capability copies: own business logic
(routes), own OpenAPI fragment, own UI pages — sharing the service's
contract surfaces. Delete it along with its `tests/contract/test_canary.py`
slices when you replace it with real capabilities.
"""

from .api import openapi_fragment
from .routes import routes
from .page import ui_routes

__all__ = ["openapi_fragment", "routes", "ui_routes"]
