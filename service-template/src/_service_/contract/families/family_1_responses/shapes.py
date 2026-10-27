"""Family 1 — LLM & agents inference: the Responses API shapes.

ADR-0001 §Families.1: `POST /v1/responses` is the **OpenAI Responses API by
reference** — request, typed streaming events, tool calling (function tools +
MCP servers), structured outputs, citations, reasoning items, refusals, and
`usage` in tokens. Multimodal **input** is in (`input_text` / `input_image` /
`input_audio`); generation output is text/structured. The rule is *follow
upstream shapes, document deviations* — so this module fixes the **vocabulary**
(the item / part / tool / annotation type names) and the **two shapes**
(`parse_request` on the way in, `normalize_response` on the way out). Every
model-backed service and every engine adapter speaks them, which is what makes
one family contract hold across implementations (ADR-0004: a capability's API
is the union of its implementation variants).

Cite, don't restate: the family's wording is ADR-0001's. Deliberately NOT
here — the engine adapters themselves (Ollama / vLLM / sglang, the cloud
gateway: the Inference service's implementation tickets), the model catalog and
its download/load lifecycle (family 5, ticket #80), and background/async jobs —
`"background": true` is family 5's surface, so it is rejected here with a
precise message instead of being silently ignored. The documented deviations
from the upstream reference (the request fields and event types this module does
not carry, and why) live in `docs/family-1-responses.md` — ADR-0001's rule is
"document deviations, pinned to a reference date".

Errors follow base item 4's taxonomy: a malformed REQUEST is 400
`invalid_request`; a malformed ENGINE REPLY is 500 `internal_error` (the
implementation broke this seam — it is never the client's fault). What "malformed
request" means here is precise: an unknown input PART type or TOOL type, a missing
required field, a wrong type on a field this module reads. Unknown TOP-LEVEL keys
are accepted and forwarded (base item 3: additive changes stay backward-compatible
within a major) — a service's engine may understand a field this module does not,
so dropping the request would be the worse failure.
"""

from __future__ import annotations

import json
import time
import uuid

from ...base.errors import internal_error, invalid_request

# --- the vocabulary (upstream type names, pinned by ADR-0001 §Families.1) ----

# What may sit INSIDE a message's `content` — the multimodal content parts. A
# tool call and its result are ITEMS, not content parts (upstream has no tool
# item inside a message), so they are not here.
MESSAGE_CONTENT_PART_TYPES = frozenset({"input_text", "input_image", "input_audio"})

# What may appear in `input` beside the role-tagged messages: the content parts
# standing alone, plus the two items that make a tool loop closable — the
# assistant's `function_call` and the caller's `function_call_output`. Without
# both, a model could emit a call that can never be answered.
INPUT_ITEM_TYPES = MESSAGE_CONTENT_PART_TYPES | frozenset(
    {"function_call", "function_call_output"}
)

# OUTPUT item types this family fixes. Upstream carries more (file_search_call,
# web_search_call, image_generation_call, …) — those belong to the service that
# produces them; a service implementing this module must not invent new ones
# silently, so an unknown type fails loudly at the seam.
OUTPUT_ITEM_TYPES = frozenset(
    {"message", "function_call", "reasoning", "mcp_call", "mcp_list_tools"}
)

# CONTENT parts inside a `message` output item: text, or an explicit refusal.
CONTENT_PART_TYPES = frozenset({"output_text", "refusal"})

# Citations ride an `output_text` part's `annotations` (upstream shape).
ANNOTATION_TYPES = frozenset({"url_citation", "file_citation"})

# Tool declarations a request may carry: platform function tools + MCP servers.
TOOL_TYPES = frozenset({"function", "mcp"})

# The `text.format` vocabularies (structured outputs).
TEXT_FORMAT_TYPES = frozenset({"text", "json_schema"})

# Response-level statuses (upstream): a completed turn, a truncated one, or a
# failed one. Progress states live on the streaming events, not on this object.
RESPONSE_STATUSES = frozenset({"completed", "incomplete", "failed"})

# Item-level statuses (upstream): an item is closed by the time the response
# body exists, but adapters may report a truncated item.
ITEM_STATUSES = frozenset({"in_progress", "completed", "incomplete"})

# The only role an OUTPUT message may carry (upstream): caller turns arrive as
# input items, never as response output.
OUTPUT_MESSAGE_ROLES = frozenset({"assistant"})

# The roles an INPUT message may carry (upstream's EasyInputMessage is a closed
# enum) — a role outside it is 400, never forwarded as an unknown label.
INPUT_MESSAGE_ROLES = frozenset({"user", "assistant", "system", "developer"})

# The request keys this module READS: validated and normalized. Every other
# top-level key is forwarded to the engine untouched (base item 3) — see
# parse_request.
_READ_KEYS = frozenset(
    {
        "model",
        "input",
        "tools",
        "text",
        "stream",
        "instructions",
        "max_output_tokens",
        "background",
    }
)

# --- the inbound shape -------------------------------------------------------


def parse_request(payload: object) -> dict:
    """Validate a `POST /v1/responses` body and return the request the engine
    seam receives.

    Absent optional keys take their documented default (`instructions` absent,
    `tools` empty, `text` plain text, `stream` false). The keys this module READS
    are validated and normalized; an unknown top-level key is **forwarded to the
    engine untouched** (base item 3: additive changes stay backward-compatible
    within a major) — an adapter that understands `temperature` or
    `tool_choice` must receive them, and silently dropping `tool_choice: "none"`
    would let the model call a tool the caller forbade. A DECLARED key outside a
    closed vocabulary (input part types, tool types) is 400 `invalid_request`,
    because the model would then run without the input the user thought they
    sent.
    """
    if not isinstance(payload, dict):
        raise invalid_request("POST /v1/responses expects a JSON object request body.")

    model = payload.get("model")
    if not isinstance(model, str) or not model:
        raise invalid_request("'model' is required and must be a non-empty string.")

    # `background` is READ, not forwarded: family 5's async surface
    # (ADR-0001 §Families.5). An explicit `false` is the synchronous default and
    # is dropped; `true` — or any non-boolean, which could be a client trying to
    # sneak it past as 1/"true" — is refused rather than silently swallowed.
    if "background" in payload and payload["background"] is not False:
        raise invalid_request(
            "'background' must be false when present: background responses are the "
            "async-jobs family (ADR-0001 §Families.5), not family 1's synchronous "
            "surface."
        )

    # Everything this module does not read rides through untouched; the keys it
    # DOES read are replaced by their validated/normalized form.
    request: dict = {
        key: value for key, value in payload.items() if key not in _READ_KEYS
    }
    request.update(
        {
            "model": model,
            "input": _parse_input(payload.get("input")),
            "tools": _parse_tools(payload.get("tools")),
            "text": _parse_text(payload.get("text")),
            "stream": _parse_stream(payload.get("stream")),
        }
    )

    instructions = payload.get("instructions")
    if instructions is not None:
        if not isinstance(instructions, str):
            raise invalid_request("'instructions' must be a string when present.")
        request["instructions"] = instructions

    max_output_tokens = payload.get("max_output_tokens")
    if max_output_tokens is not None:
        if not isinstance(max_output_tokens, int) or isinstance(max_output_tokens, bool):
            raise invalid_request("'max_output_tokens' must be an integer when present.")
        if max_output_tokens < 1:
            raise invalid_request("'max_output_tokens' must be greater than 0.")
        request["max_output_tokens"] = max_output_tokens

    return request


def _parse_input(value: object) -> list[dict]:
    """Normalize `input` to a list of typed input items.

    A plain string is the shorthand for one `input_text` part (upstream
    behavior); a list carries input parts and/or role-tagged message objects.
    """
    if value is None:
        raise invalid_request("'input' is required (a string or a list of input items).")
    if isinstance(value, str):
        return [{"type": "input_text", "text": value}]
    if not isinstance(value, list):
        raise invalid_request("'input' must be a string or a list of input items.")
    if not value:
        raise invalid_request("'input' must not be an empty list.")

    items: list[dict] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise invalid_request(f"input[{index}] must be a JSON object.")
        # An entry carrying `role` is a message. Upstream's EasyInputMessage also
        # carries an optional `type: "message"` discriminator; accept it and
        # normalize it away. Any OTHER type on a role-carrying entry is
        # ambiguous, and is refused rather than guessed.
        if "role" in entry:
            entry_type = entry.get("type", "message")
            if entry_type != "message":
                raise invalid_request(
                    f"input[{index}] carries 'role' with type {entry_type!r} — a "
                    "role-tagged message is type 'message' (or carries no type); a "
                    "standalone input item carries a type and no 'role'."
                )
            items.append(
                _parse_message({key: value for key, value in entry.items() if key != "type"}, index)
            )
            continue
        items.append(_parse_input_item(entry, f"input[{index}]"))
    return items


def _parse_message(entry: dict, index: int) -> dict:
    role = entry.get("role")
    if not isinstance(role, str) or role not in INPUT_MESSAGE_ROLES:
        raise invalid_request(
            f"input[{index}] carries role {role!r}; an input message's role is one of "
            f"{sorted(INPUT_MESSAGE_ROLES)!r}."
        )
    content = entry.get("content")
    # Upstream accepts a bare string here as the shorthand for one input_text
    # part (`EasyInputMessage.content`); an empty string is a legal (if useless)
    # text part, like a whitespace-only list part — nothing special-cases it.
    if isinstance(content, str):
        content = [{"type": "input_text", "text": content}]
    if not isinstance(content, list) or not content:
        raise invalid_request(
            f"input[{index}] ('{role}') must carry a 'content' string or a non-empty list."
        )
    parts = [
        _parse_input_item(
            part, f"input[{index}].content[{position}]", allowed=MESSAGE_CONTENT_PART_TYPES
        )
        for position, part in enumerate(content)
    ]
    return {"role": role, "content": parts}


def _parse_input_item(part: object, where: str, *, allowed: frozenset[str] = INPUT_ITEM_TYPES) -> dict:
    """One standalone input item / message content part, validated per its type."""
    if not isinstance(part, dict):
        raise invalid_request(f"{where} must be a JSON object.")
    part_type = part.get("type")
    # `not in allowed` on an unhashable value raises TypeError (a 500 for a
    # client error), so the type check comes first.
    if not isinstance(part_type, str) or part_type not in allowed:
        raise invalid_request(
            f"{where}.type {part_type!r} is not one of {sorted(allowed)!r} — "
            "multimodal content parts are 'input_text' / 'input_image' / "
            "'input_audio'; a tool loop's items are 'function_call' and "
            "'function_call_output' (ADR-0001 §Families.1). Upstream's "
            "'item_reference' is not carried: this module keeps no response store."
        )
    if part_type == "input_text":
        if not isinstance(part.get("text"), str):
            raise invalid_request(f"{where} ('input_text') requires a string 'text'.")
    elif part_type == "input_image":
        image_url = part.get("image_url")
        if isinstance(image_url, dict):
            image_url = image_url.get("url")
        if not isinstance(image_url, str) or not image_url:
            raise invalid_request(
                f"{where} ('input_image') requires 'image_url' (a URL string, or "
                "an object carrying 'url')."
            )
    elif part_type == "input_audio":
        audio = part.get("input_audio")
        if not isinstance(audio, dict):
            raise invalid_request(
                f"{where} ('input_audio') requires an 'input_audio' object "
                "carrying 'data' and 'format'."
            )
        if not isinstance(audio.get("data"), str) or not isinstance(audio.get("format"), str):
            raise invalid_request(
                f"{where} ('input_audio') requires string 'data' and 'format' keys."
            )
    elif part_type == "function_call":
        # The assistant's previous call, sent back so the loop can close.
        if not isinstance(part.get("call_id"), str) or not part["call_id"]:
            raise invalid_request(
                f"{where} ('function_call') requires a string 'call_id'."
            )
        if not isinstance(part.get("name"), str) or not part["name"]:
            raise invalid_request(f"{where} ('function_call') requires a string 'name'.")
        if not isinstance(part.get("arguments"), str):
            raise invalid_request(
                f"{where} ('function_call') requires 'arguments' as a JSON string."
            )
        # A caller's malformed arguments is a CLIENT error (400), never the
        # internal_error that the engine-reply side raises. The EMPTY string is
        # a legal no-argument call (upstream allows it); every NON-empty value —
        # whitespace included — has to parse as JSON.
        if part["arguments"]:
            try:
                json.loads(part["arguments"])
            except ValueError:
                raise invalid_request(
                    f"{where}.arguments must be a JSON string."
                ) from None
    else:  # function_call_output — the tool result that answers the call
        if not isinstance(part.get("call_id"), str) or not part["call_id"]:
            raise invalid_request(
                f"{where} ('function_call_output') requires a string 'call_id' "
                "(the call it answers)."
            )
        output = part.get("output")
        if not isinstance(output, (str, list)):
            raise invalid_request(
                f"{where} ('function_call_output') requires 'output' (a string, or "
                "a list of content parts)."
            )
        if isinstance(output, list):
            if not output:
                raise invalid_request(
                    f"{where} ('function_call_output') carries an empty 'output' list."
                )
            # Each entry is a real content part: the same validation a part in a
            # message's `content` gets, so an image part without its URL cannot
            # ride in through a tool result.
            output = [
                _parse_input_item(
                    entry, f"{where}.output[{position}]", allowed=MESSAGE_CONTENT_PART_TYPES
                )
                for position, entry in enumerate(output)
            ]
            part = {**part, "output": output}
    return dict(part)


def _parse_tools(value: object) -> list[dict]:
    """`tools` = function tools + MCP servers (the two kinds ADR-0001 fixes)."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise invalid_request("'tools' must be a list when present.")
    tools: list[dict] = []
    for index, tool in enumerate(value):
        if not isinstance(tool, dict):
            raise invalid_request(f"tools[{index}] must be a JSON object.")
        tool_type = tool.get("type")
        if not isinstance(tool_type, str) or tool_type not in TOOL_TYPES:
            raise invalid_request(
                f"tools[{index}].type {tool_type!r} is not a tool type "
                f"({sorted(TOOL_TYPES)!r}) — family 1 declares function tools and "
                "MCP servers (ADR-0001 §Families.1)."
            )
        if tool_type == "function":
            if not isinstance(tool.get("name"), str) or not tool["name"]:
                raise invalid_request(f"tools[{index}] ('function') requires a string 'name'.")
        else:  # mcp
            if not isinstance(tool.get("server_label"), str) or not tool["server_label"]:
                raise invalid_request(
                    f"tools[{index}] ('mcp') requires a string 'server_label'."
                )
        tools.append(dict(tool))
    return tools


def _parse_text(value: object) -> dict:
    """`text.format` — plain text or a JSON schema (structured outputs)."""
    if value is None:
        return {"format": {"type": "text"}}
    if not isinstance(value, dict):
        raise invalid_request("'text' must be a JSON object when present.")
    fmt = value.get("format")
    if fmt is None:
        return {"format": {"type": "text"}}
    if not isinstance(fmt, dict):
        raise invalid_request("'text.format' must be a JSON object when present.")
    format_type = fmt.get("type")
    if not isinstance(format_type, str) or format_type not in TEXT_FORMAT_TYPES:
        raise invalid_request(
            f"'text.format.type' {format_type!r} is not a format type "
            f"({sorted(TEXT_FORMAT_TYPES)!r})."
        )
    if format_type == "json_schema":
        if not isinstance(fmt.get("name"), str) or not fmt["name"]:
            raise invalid_request("'text.format' ('json_schema') requires a string 'name'.")
        if not isinstance(fmt.get("schema"), dict):
            raise invalid_request(
                "'text.format' ('json_schema') requires a 'schema' object "
                "(structured outputs are schema-declared, never inferred)."
            )
    return {"format": dict(fmt)}


def _parse_stream(value: object) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise invalid_request("'stream' must be a boolean when present.")
    return value


# --- the outbound shape ------------------------------------------------------


def normalize_response(request: dict, engine_output: object) -> dict:
    """Turn one engine reply into the contract response body.

    The engine supplies the CONTENT (output items + token usage); this module
    owns everything the contract fixes — the `resp_` id, `object`/`status`/
    `model`, the item/part vocabulary, and the `usage` totals. A reply that
    breaks the seam (unknown item type, a JSON-schema turn whose text is not
    JSON, usage that does not add up) is 500 `internal_error`: the
    implementation, not the caller, is wrong.
    """
    if not isinstance(engine_output, dict):
        raise internal_error(
            "The engine returned a non-object reply; family 1's seam expects a "
            "response body object."
        )

    output = engine_output.get("output")
    if not isinstance(output, list):
        raise internal_error("The engine reply carries no 'output' list.")
    items = [_normalize_item(item, request, index) for index, item in enumerate(output)]

    status = engine_output.get("status", "completed")
    if not isinstance(status, str) or status not in RESPONSE_STATUSES:
        raise internal_error(
            f"The engine reply's status {status!r} is not one of "
            f"{sorted(RESPONSE_STATUSES)!r}."
        )

    created_at = engine_output.get("created_at")
    if created_at is None:
        created_at = _now_seconds()
    elif not isinstance(created_at, int) or isinstance(created_at, bool) or created_at < 0:
        raise internal_error("The engine reply's 'created_at' must be a non-negative integer.")

    response = {
        "id": _response_id(engine_output.get("id")),
        "object": "response",
        "created_at": created_at,
        "status": status,
        "model": request["model"],
        "output": items,
        "usage": _normalize_usage(engine_output.get("usage")),
    }
    if request.get("instructions") is not None:
        response["instructions"] = request["instructions"]
    return response


def _item_id(item: dict, fallback: str) -> str:
    """An item id / call_id the contract says is a string. A non-string is
    replaced by a generated one rather than passed through: a `call_id` that is
    not a string could never be echoed back on the next turn."""
    value = item.get("id")
    return value if isinstance(value, str) and value else fallback


def _call_id(item: dict, fallback: str) -> str:
    value = item.get("call_id")
    return value if isinstance(value, str) and value else fallback


def _item_status(item: dict, index: int) -> str:
    """The item's status — validated, because an unknown value (or a non-string)
    in the body is a seam break, not a passthrough. Every item type carries it
    (upstream does); the `isinstance` guard keeps it inside the 500 taxonomy
    instead of raising a bare TypeError out of the route."""
    status = item.get("status", "completed")
    if not isinstance(status, str) or status not in ITEM_STATUSES:
        raise internal_error(
            f"output[{index}] carries status {status!r}, not one of "
            f"{sorted(ITEM_STATUSES)!r}."
        )
    return status


def _normalize_item(item: object, request: dict, index: int) -> dict:
    if not isinstance(item, dict):
        raise internal_error(f"output[{index}] is not a JSON object.")
    item_type = item.get("type")
    if not isinstance(item_type, str) or item_type not in OUTPUT_ITEM_TYPES:
        raise internal_error(
            f"output[{index}].type {item_type!r} is not a family-1 output item type "
            f"({sorted(OUTPUT_ITEM_TYPES)!r})."
        )
    if item_type == "message":
        return _normalize_message(item, request, index)
    if item_type == "function_call":
        name, arguments = item.get("name"), item.get("arguments")
        if not isinstance(name, str) or not name:
            raise internal_error(f"output[{index}] ('function_call') requires a string 'name'.")
        if not isinstance(arguments, str):
            raise internal_error(
                f"output[{index}] ('function_call') requires 'arguments' as a JSON "
                "string (upstream shape)."
            )
        if arguments:  # "" is a no-argument call (upstream emits it)
            _require_json(arguments, f"output[{index}].arguments")
        return {
            "type": "function_call",
            "id": _item_id(item, f"fc_{index}"),
            "status": _item_status(item, index),
            "call_id": _call_id(item, f"call_{index}"),
            "name": name,
            "arguments": arguments,
        }
    if item_type == "reasoning":
        summary = item.get("summary", [])
        if not isinstance(summary, list):
            raise internal_error(f"output[{index}] ('reasoning') requires a 'summary' list.")
        parts = []
        for position, part in enumerate(summary):
            if not isinstance(part, dict) or not isinstance(part.get("text"), str):
                raise internal_error(
                    f"output[{index}].summary[{position}] must carry a string 'text'."
                )
            parts.append({"type": "summary_text", "text": part["text"]})
        return {
            "type": "reasoning",
            "id": _item_id(item, f"rs_{index}"),
            "status": _item_status(item, index),
            "summary": parts,
        }
    if item_type == "mcp_call":
        if not isinstance(item.get("name"), str) or not isinstance(item.get("server_label"), str):
            raise internal_error(
                f"output[{index}] ('mcp_call') requires string 'name' and 'server_label'."
            )
        arguments = item.get("arguments", "")
        if not isinstance(arguments, str):
            raise internal_error(
                f"output[{index}] ('mcp_call') requires 'arguments' as a JSON string "
                "(upstream shape), like its function_call sibling."
            )
        if arguments:  # omitted/empty is a no-argument call
            _require_json(arguments, f"output[{index}].arguments")
        return {
            "type": "mcp_call",
            "id": _item_id(item, f"mc_{index}"),
            "status": _item_status(item, index),
            "name": item["name"],
            "server_label": item["server_label"],
            "arguments": arguments,
        }
    # mcp_list_tools
    if not isinstance(item.get("server_label"), str):
        raise internal_error(f"output[{index}] ('mcp_list_tools') requires a string 'server_label'.")
    tools = item.get("tools", [])
    if not isinstance(tools, list) or not all(isinstance(tool, dict) for tool in tools):
        raise internal_error(
            f"output[{index}] ('mcp_list_tools') requires 'tools' as a list of tool "
            "objects."
        )
    return {
        "type": "mcp_list_tools",
        "id": _item_id(item, f"ml_{index}"),
        "status": _item_status(item, index),
        "server_label": item["server_label"],
        "tools": [dict(tool) for tool in tools],
    }


def _normalize_message(item: dict, request: dict, index: int) -> dict:
    role = item.get("role", "assistant")
    if not isinstance(role, str) or role not in OUTPUT_MESSAGE_ROLES:
        raise internal_error(
            f"output[{index}] ('message') carries role {role!r}; an output message is "
            f"{sorted(OUTPUT_MESSAGE_ROLES)!r} (caller turns are input items)."
        )
    status = _item_status(item, index)
    content = item.get("content")
    if not isinstance(content, list):
        raise internal_error(f"output[{index}] ('message') requires a 'content' list.")
    parts = [
        _normalize_content_part(part, request, index, position, content)
        for position, part in enumerate(content)
    ]
    return {
        "type": "message",
        "id": _item_id(item, f"msg_{index}"),
        "role": role,
        "status": status,
        "content": parts,
    }


def _normalize_content_part(
    part: object, request: dict, index: int, position: int, content: list
) -> dict:
    where = f"output[{index}].content[{position}]"
    if not isinstance(part, dict):
        raise internal_error(f"{where} is not a JSON object.")
    part_type = part.get("type")
    if not isinstance(part_type, str) or part_type not in CONTENT_PART_TYPES:
        raise internal_error(
            f"{where}.type {part_type!r} is not a message content part type "
            f"({sorted(CONTENT_PART_TYPES)!r})."
        )
    if part_type == "refusal":
        refusal = part.get("refusal")
        if not isinstance(refusal, str) or not refusal:
            raise internal_error(f"{where} ('refusal') requires a non-empty string 'refusal'.")
        return {"type": "refusal", "refusal": refusal}

    text = part.get("text")
    if not isinstance(text, str):
        raise internal_error(f"{where} ('output_text') requires a string 'text'.")
    # Structured outputs: a turn that asked for a JSON schema and came back with
    # text that is not JSON has broken the family contract — say so loudly. The
    # schema itself is the implementation's to honor (this module fixes the
    # shape, not the engine); see docs/family-1-responses.md.
    if request.get("text", {}).get("format", {}).get("type") == "json_schema":
        try:
            json.loads(text)
        except ValueError:
            raise internal_error(
                f"{where}.text is not valid JSON, and this turn declared a "
                "json_schema structured output."
            ) from None

    return {
        "type": "output_text",
        "text": text,
        "annotations": _normalize_annotations(part.get("annotations", []), where),
    }


def _normalize_annotations(annotations: object, where: str) -> list[dict]:
    """Citations ride the `output_text` part (upstream: `annotations`)."""
    if annotations is None:
        return []
    if not isinstance(annotations, list):
        raise internal_error(f"{where}.annotations must be a list when present.")
    normalized = []
    for position, annotation in enumerate(annotations):
        if not isinstance(annotation, dict):
            raise internal_error(f"{where}.annotations[{position}] is not a JSON object.")
        annotation_type = annotation.get("type")
        if not isinstance(annotation_type, str) or annotation_type not in ANNOTATION_TYPES:
            raise internal_error(
                f"{where}.annotations[{position}].type {annotation_type!r} is not one of "
                f"{sorted(ANNOTATION_TYPES)!r}."
            )
        normalized.append(dict(annotation))
    return normalized


def _normalize_usage(usage: object) -> dict:
    """`usage` in tokens (base item 8, unit fixed by family 1)."""
    if not isinstance(usage, dict):
        raise internal_error(
            "The engine reply carries no 'usage' object — family 1 reports token "
            "usage on every response (ADR-0001 base item 8)."
        )
    counts = {}
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise internal_error(f"usage.{key} must be a non-negative integer.")
        counts[key] = value
    total = usage.get("total_tokens")
    expected = counts["input_tokens"] + counts["output_tokens"]
    if total is None:
        total = expected
    elif not isinstance(total, int) or isinstance(total, bool) or total != expected:
        raise internal_error(
            f"usage.total_tokens ({total}) does not equal input_tokens + output_tokens "
            f"({expected})."
        )
    return {**counts, "total_tokens": total}


def _response_id(value: object) -> str:
    """The response id is contract-shaped (`resp_…`) — the module guarantees
    the prefix rather than trusting every adapter to remember it."""
    if isinstance(value, str) and value:
        return value if value.startswith("resp_") else f"resp_{value}"
    return f"resp_{uuid.uuid4().hex}"


def _require_json(text: str, where: str) -> None:
    """A JSON string the seam promised to carry — a neutral message; callers that
    promise more (a structured output's schema turn) say so themselves."""
    try:
        json.loads(text)
    except ValueError:
        raise internal_error(f"{where} is not valid JSON.") from None


def _now_seconds() -> int:
    return int(time.time())
