"""The canary's human surface — the Echo page (ADR-0002 §4).

FastHTML components rendered to one HTML page, served from a plain Starlette
route so the capability coexists with the base-contract app in one process.
Client-side interactivity is **vendored Alpine.js** (FastHTML's Surreal is not
loaded — never vendored, never a CDN); base styles are vendored Pico.

The page calls the SAME API a client would (`POST /v1/echo`) — the human
surface drives the deterministic surface, it does not duplicate it.

Auth note: the template's Bearer gate applies to the page itself (everything
but `/health` requires the key, `contract/base/auth.py`). In the platform,
capability UIs are embedded by the dashboard, which mediates the user
session; direct browser access carries the Bearer story of the dashboard
integration (#62), not a per-page one.
"""

from __future__ import annotations

from pathlib import Path

from fasthtml.common import (
    Body,
    Button,
    Div,
    Form,
    H1,
    Head,
    Html,
    Input,
    Label,
    Link,
    Main,
    P,
    Pre,
    Script,
    Small,
    Title,
)
from starlette.responses import HTMLResponse
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

# All JS/CSS vendored in `ui/static/` — no CDN (ADR-0002 §4: a home LAN may
# be offline). The shared UI kit (design tokens + nav shell, ADR-0002 §4)
# arrives as its own template ticket; `service.css` is the minimal token set
# the kit will replace.
STATIC_DIR = Path(__file__).resolve().parents[2] / "ui" / "static"

_ECHO_FORM_ALPINE = (
    "{text: '', private: false, busy: false, result: null, error: null, "
    "async submit() {"
    "this.busy = true; this.error = null;"
    "try {"
    "const r = await fetch('/v1/echo', {method: 'POST',"
    "headers: {'Content-Type': 'application/json'},"
    "body: JSON.stringify({text: this.text, "
    "consent: this.private ? 'private_secret' : 'may_use'})});"
    "this.result = await r.json();"
    "} catch (e) { this.error = e; }"
    "finally { this.busy = false; }"
    "}}"
)


def echo_page(service_name: str, version: str) -> HTMLResponse:
    page = Html(
        Head(
            Title(f"{service_name} — Echo"),
            Link(rel="stylesheet", href="/static/pico.min.css"),
            Link(rel="stylesheet", href="/static/service.css"),
            Script(src="/static/alpine.min.js", defer=True),
        ),
        Body(
            Main(
                H1("Echo", Small(f" · {service_name} {version} · canary capability", cls="muted")),
                P(
                    "The template's proof capability. This page drives the same "
                    "API every client drives — POST /v1/echo, echoed back "
                    "unchanged. It also answers on the agent surface "
                    "(MCP tools auto-generated from /openapi.json).",
                    cls="lead",
                ),
                Form(
                    Input(
                        name="text",
                        placeholder="Type something…",
                        required=True,
                        x_model="text",
                    ),
                    Button("Echo", type="submit", **{":disabled": "busy"}),
                    cls="echo-form",
                    **{"x-data": _ECHO_FORM_ALPINE, "@submit.prevent": "submit()"},
                ),
                # The consent toggle rides every user input (ADR-0026 §1,
                # ticket #72): per-interaction consent defaults to "may use
                # for improvement"; the private/secret state is the very
                # visible, one-gesture-away opt-out — never a hidden
                # heuristic, never bypassable in the extraction surface.
                Div(
                    Label(
                        Input(type="checkbox", x_model="private"),
                        "private/secret — do not use",
                        cls="consent-toggle",
                    ),
                    Small(
                        "Unchecked (the default): this input may use for improvement — "
                        "it stays eligible for the service's extraction, which always "
                        "applies the consent gate (private/secret excluded, never "
                        "bypassed); anonymization happens later, at the core's "
                        "datasets boundary. Checked: never used, never extractable.",
                        cls="muted consent-hint",
                    ),
                    cls="consent",
                ),
                Div(
                    Pre(
                        "",
                        cls="echo-result",
                        **{"x-show": "result !== null", "x-text": "JSON.stringify(result, null, 2)"},
                    ),
                    Div(
                        "",
                        cls="echo-error",
                        **{"x-show": "error !== null", "x-text": "error"},
                    ),
                ),
                role="main",
            )
        ),
    )
    return HTMLResponse(str(page))


def ui_routes(service_name: str, version: str) -> list:
    """The capability's human-surface routes: the static assets (vendored)
    and the page itself."""
    from starlette.routing import Route

    return [
        Mount("/static", StaticFiles(directory=STATIC_DIR), name="canary-static"),
        Route("/echo", lambda request: echo_page(service_name, version), methods=["GET"]),
    ]
