"""The per-user export/restore template contract — ADR-0021 §3 as
template-level machinery (ticket #269): export one user+role's data as a
self-contained unit, apply true-incremental deltas, restore.

Because backup extracts data **per user** (per data sphere / role —
ADR-0021 §1), a database's builtin whole-DB backup is forbidden: it captures
every user at once and defeats per-user encryption and per-user restore
(ADR-0021 §3, which sharpens ADR-0002's service template). Every service's
storage must therefore support extracting a single user+role's data as a
**self-contained unit** and applying **true-incremental deltas** on top of a
full export (ADR-0021 §5's chain semantics). This module is the contract
SHAPE — the route pair, the closed unit shape, the loud rejections — not the
per-service storage design (each service realizes it in its own spec).

The surface (the shape the core's `backup` capability will call at the end —
ADR-0021 §8; the registry name `core.backup` is recorded as DATA where the
ADRs name it, never probed here):

- ``GET /v1/export?owner=<id>&role=<role>[&since=<seq>]`` — the export
  surface. ``owner`` + ``role`` are REQUIRED: a whole-DB export (no
  user+role context) is exactly the shape ADR-0021 §3 forbids, so the route
  cannot express it. ``since`` selects a true-incremental delta (the
  records with ``seq > since``); absent selects a full export.
- ``POST /v1/restore`` — the restore surface: applies one export unit
  (a full replaces the user+role's records; a delta must chain onto the
  current high-water seq, else 409 ``conflict``). The unit carries the
  service identity (ADR-0021 §7: each backup carries service metadata so
  the restore can verify the target accepts it — the service-name match is
  checked here; the version+capabilities acceptance judgment is #272's).

The export unit is ONE self-contained document (ADR-0021 §3) — deliberately
not item-5 paginated: a paginated export is not a self-contained unit, and
the backup machinery (#271) packages the whole unit.

The store protocol a service implements (the storage side stays the
service's; the contract module owns the payload rules):

- ``records(owner, role, after_seq=0) -> list[dict]`` — the user+role's
  records with ``seq > after_seq``, in seq order;
- ``high_water(owner, role) -> int`` — the highest seq stored for that
  user+role (0 when none);
- ``apply_full(owner, role, items) -> None`` — replace the user+role's
  records with the unit's items;
- ``apply_delta(owner, role, items) -> None`` — append the unit's items.

Closed shapes, loud rejections: an unknown role, a missing/empty owner, a
non-integer ``since``, a non-object restore body, or an export unit with an
unknown/missing key is a 400 ``invalid_request`` naming the offending entry
(base item 4); a unit whose service identity does not match this service, or
a delta that does not chain, is a 409 ``conflict`` with the reason.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .errors import conflict, invalid_request

# The three data-sphere roles (ADR-0021 §1): a physical user has three
# identities, one per sphere — user / builder / admin.
ROLES = ("user", "builder", "admin")

# The canary's default attribution (ticket #269): an input without an
# explicit owner/role belongs to the machine's local user identity.
DEFAULT_OWNER = "local"
DEFAULT_ROLE = "user"

# The two export kinds (ADR-0021 §5): a full export, or a true-incremental
# delta that applies ON TOP of a full export.
KIND_FULL = "full"
KIND_DELTA = "delta"
EXPORT_KINDS = (KIND_FULL, KIND_DELTA)

# The closed export-unit shape (ADR-0021 §3/§7): the unit is self-contained
# — it carries the service identity, the user+role context it belongs to,
# its kind, the seq it chains from, the seq it reaches, and the records.
UNIT_KEYS = frozenset(
    {"service", "version", "owner", "role", "kind", "since", "through", "items"}
)

EXPORT_PATH = "/v1/export"
RESTORE_PATH = "/v1/restore"


def resolve_owner_role(owner: object, role: object) -> tuple[str, str]:
    """Resolve the required user+role context of an extraction (ADR-0021
    §1/§3): both are required, the role is a closed vocabulary. Raises
    ``ValueError`` naming the offending entry; callers turn it into the
    contract's 400 ``invalid_request`` (base item 4)."""
    if not isinstance(owner, str) or not owner:
        raise ValueError(
            f"Invalid owner {owner!r}: the export is per user+role — a "
            "non-empty owner is required (ADR-0021 §3: whole-DB extraction "
            "is forbidden)."
        )
    if role not in ROLES:
        raise ValueError(
            f"Unknown role {role!r}: expected one of {list(ROLES)} "
            "(ADR-0021 §1 — the three data spheres)."
        )
    return owner, role


def build_export_unit(
    *,
    service: str,
    version: str,
    owner: str,
    role: str,
    kind: str,
    since: int | None,
    through: int,
    items: list[dict],
) -> dict:
    """One self-contained export unit (ADR-0021 §3) — the single encoding of
    the unit shape, shared by the export surface and by tests that need a
    specific unit. ``since`` is null for a full export, the seq the delta
    chains from for a true-incremental one."""
    if kind not in EXPORT_KINDS:
        raise ValueError(
            f"Unknown export kind {kind!r}: expected one of "
            f"{list(EXPORT_KINDS)} (ADR-0021 §5)."
        )
    return {
        "service": service,
        "version": version,
        "owner": owner,
        "role": role,
        "kind": kind,
        "since": since,
        "through": through,
        "items": [dict(item) for item in items],
    }


def validate_export_unit(unit: object) -> dict:
    """Validate one restore payload against the closed unit shape (ADR-0021
    §3): unknown keys, missing keys, wrong types, a kind or role outside the
    closed vocabularies — all raise ``ValueError`` naming the offending
    entry; callers turn it into 400 ``invalid_request``. The closed-shape
    scan runs BEFORE any presence-dependent rule."""
    if not isinstance(unit, dict):
        raise ValueError(
            "The restore body is one export unit — a JSON object (ADR-0021 §3)."
        )
    unknown = sorted(set(unit) - UNIT_KEYS)
    if unknown:
        raise ValueError(
            f"Unknown export-unit key(s) {unknown}: the unit shape is exactly "
            f"{sorted(UNIT_KEYS)} (ADR-0021 §3)."
        )
    missing = sorted(UNIT_KEYS - set(unit))
    if missing:
        raise ValueError(
            f"Export unit is missing key(s) {missing}: the unit is "
            "self-contained (ADR-0021 §3)."
        )
    owner, role = resolve_owner_role(unit["owner"], unit["role"])
    if unit["kind"] not in EXPORT_KINDS:
        raise ValueError(
            f"Unknown export kind {unit['kind']!r}: expected one of "
            f"{list(EXPORT_KINDS)} (ADR-0021 §5)."
        )
    since, through = unit["since"], unit["through"]
    if not isinstance(through, int) or isinstance(through, bool) or through < 0:
        raise ValueError(
            f"Invalid export-unit `through` {through!r}: a non-negative "
            "integer seq is required (ADR-0021 §3)."
        )
    if unit["kind"] == KIND_FULL:
        if since is not None:
            raise ValueError(
                "A full export unit carries `since = null` — a delta chains "
                "from a seq, a full does not (ADR-0021 §5)."
            )
    else:
        if not isinstance(since, int) or isinstance(since, bool) or since < 0:
            raise ValueError(
                f"A delta export unit requires a non-negative integer `since` "
                f"it chains from, got {since!r} (ADR-0021 §5)."
            )
    if not isinstance(unit["items"], list) or any(
        not isinstance(item, dict) for item in unit["items"]
    ):
        raise ValueError(
            "The export unit's `items` is a list of record objects (ADR-0021 §3)."
        )
    for key in ("service", "version"):
        if not isinstance(unit[key], str) or not unit[key]:
            raise ValueError(
                f"Invalid export-unit `{key}` {unit[key]!r}: the unit carries "
                "the service identity it was exported from (ADR-0021 §7)."
            )
    return {**unit, "owner": owner, "role": role}


def export_restore_routes(store, *, service_name: str, version: str) -> list[Route]:
    """The export/restore route pair, closed over the service's store (the
    store protocol is documented at the top of this module). A service wires
    these routes like any capability surface — the canary wires them against
    its interaction record as the template's demonstration (ticket #269)."""

    async def export(request: Request) -> JSONResponse:
        """GET /v1/export?owner=&role=[&since=] — one user+role's data as a
        self-contained unit (full), or the true-incremental delta since a
        seq (ADR-0021 §3/§5)."""
        params = request.query_params
        try:
            owner, role = resolve_owner_role(params.get("owner"), params.get("role"))
        except ValueError as error:
            raise invalid_request(str(error)) from None
        since: int | None = None
        raw_since = params.get("since")
        if raw_since is not None:
            try:
                since = int(raw_since)
            except ValueError:
                raise invalid_request(
                    f"Invalid `since` {raw_since!r}: a non-negative integer "
                    "seq (ADR-0021 §5)."
                ) from None
            if since < 0:
                raise invalid_request(
                    f"Invalid `since` {raw_since!r}: a non-negative integer "
                    "seq (ADR-0021 §5)."
                )
        kind = KIND_DELTA if since is not None else KIND_FULL
        items = store.records(owner, role, after_seq=since or 0)
        through = store.high_water(owner, role)
        return JSONResponse(
            build_export_unit(
                service=service_name,
                version=version,
                owner=owner,
                role=role,
                kind=kind,
                since=since,
                through=through,
                items=items,
            )
        )

    async def restore(request: Request) -> JSONResponse:
        """POST /v1/restore — apply one export unit to this service: a full
        replaces the user+role's records, a delta chains onto the current
        high-water seq (ADR-0021 §3/§5/§7)."""
        try:
            parsed = await request.json()
        except ValueError:  # malformed JSON is a CLIENT error (item 4)
            raise invalid_request("POST /v1/restore expects a JSON export unit.") from None
        try:
            unit = validate_export_unit(parsed)
        except ValueError as error:
            raise invalid_request(str(error)) from None
        if unit["service"] != service_name:
            raise conflict(
                f"This service is {service_name!r}; the export unit was "
                f"exported from {unit['service']!r} — the restore target must "
                "provide the same service (ADR-0021 §7)."
            )
        owner, role = unit["owner"], unit["role"]
        if unit["kind"] == KIND_DELTA:
            current = store.high_water(owner, role)
            if unit["since"] != current:
                raise conflict(
                    f"The delta chains from seq {unit['since']} but this "
                    f"service's {owner!r}/{role} data is at seq {current} — "
                    "apply the full export (and any earlier deltas) first "
                    "(ADR-0021 §5)."
                )
            store.apply_delta(owner, role, unit["items"])
        else:
            store.apply_full(owner, role, unit["items"])
        return JSONResponse(
            {
                "restored": True,
                "owner": owner,
                "role": role,
                "kind": unit["kind"],
                "items": len(unit["items"]),
            }
        )

    return [
        Route(EXPORT_PATH, export, methods=["GET"], name="export"),
        Route(RESTORE_PATH, restore, methods=["POST"], name="restore"),
    ]
