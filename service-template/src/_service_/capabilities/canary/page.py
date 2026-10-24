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
    H3,
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

# The backup trigger rides the same surface the orchestration calls
# (ADR-0021 §9, ticket #269): "back up my data now" exports the CURRENT
# user's data as one self-contained unit (GET /v1/export) and downloads it;
# "restore" applies a saved unit back (POST /v1/restore). Near-free given
# the design — the same capability the core's backup orchestration drives.
_BACKUP_ALPINE = (
    "{backupBusy: false, backupNote: '', "
    "async backupNow() {"
    "this.backupBusy = true; this.backupNote = '';"
    "try {"
    "const r = await fetch('/v1/export?owner=local&role=user');"
    "if (!r.ok) { this.backupNote = 'Backup failed: ' + r.status; return; }"
    "const unit = await r.json();"
    "const a = document.createElement('a');"
    "a.href = URL.createObjectURL(new Blob([JSON.stringify(unit, null, 2)], "
    "{type: 'application/json'}));"
    "a.download = unit.service + '-' + unit.owner + '-' + unit.role + '.json';"
    "a.click();"
    "this.backupNote = 'Exported ' + unit.items.length + ' record(s) as one unit.';"
    "} catch (e) { this.backupNote = 'Backup failed: ' + e; }"
    "finally { this.backupBusy = false; }"
    "}, "
    "async restoreFile(input) {"
    "this.backupNote = '';"
    "try {"
    "const unit = JSON.parse(await input.files[0].text());"
    "const r = await fetch('/v1/restore', {method: 'POST',"
    "headers: {'Content-Type': 'application/json'},"
    "body: JSON.stringify(unit)});"
    "const body = await r.json();"
    "this.backupNote = r.ok ? ('Restored ' + body.items + ' record(s).') "
    ": ('Restore refused: ' + body.error.message);"
    "} catch (e) { this.backupNote = 'Restore failed: ' + e; }"
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
                # The backup trigger (ADR-0021 §9, ticket #269): "back up my
                # data now" + restore, riding the same per-user export/restore
                # surface the core's backup orchestration drives.
                Div(
                    H3("Backup"),
                    Small(
                        "Your data, one self-contained unit per user — the same "
                        "export/restore surface the platform's backup cadence "
                        "drives (ADR-0021). Export downloads your unit; restore "
                        "applies a saved unit back.",
                        cls="muted",
                    ),
                    Button("Back up my data now", type="button",
                           **{"@click": "backupNow()", ":disabled": "backupBusy"}),
                    Label(
                        Input(type="file", accept="application/json",
                              **{"@change": "restoreFile($event.target)"}),
                        "Restore from a saved unit",
                        cls="restore-label",
                    ),
                    Div(
                        "",
                        cls="backup-note",
                        **{"x-show": "backupNote !== ''", "x-text": "backupNote"},
                    ),
                    cls="backup",
                    **{"x-data": _BACKUP_ALPINE},
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
