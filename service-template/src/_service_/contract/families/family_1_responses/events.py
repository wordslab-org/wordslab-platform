"""Family 1 — the typed streaming event vocabulary (ADR-0001 §Families.1).

ADR-0001 fixes the streaming contract as **SSE with typed events** and a
Responses-API event vocabulary; base item 1 fixes the transport
(`text/event-stream`). This module owns the vocabulary and the event
SEQUENCE — the two things a client's parser depends on — and nothing about
latency: token-by-token emission is an engine adapter's business (the
Inference service's implementation tickets), so `events_for()` derives the
typed sequence from a COMPLETE response body. An adapter that already streams
can emit the same event types in the same order earlier; the client sees the
same contract either way.

Each frame is `event: <type>` + `data: <json event object>`, and every event
carries its `type` in the body too (upstream does both, so a client may key on
either). `sequence_number` is the ordering anchor: upstream's field, strictly
increasing, starting at 0. The stream ends with the terminal event
(`response.completed` / `response.failed` / `response.incomplete`) — there is
no `[DONE]` sentinel in the Responses API, unlike Chat Completions.
"""

from __future__ import annotations

import json

from .shapes import CONTENT_PART_TYPES

# The streaming vocabulary this family ships. Names are upstream's: a client
# written against the OpenAI Responses API parses these unchanged.
EVENT_TYPES = frozenset(
    {
        "response.created",
        "response.in_progress",
        "response.output_item.added",
        "response.output_item.done",
        "response.content_part.added",
        "response.content_part.done",
        "response.output_text.delta",
        "response.output_text.done",
        "response.refusal.delta",
        "response.refusal.done",
        "response.function_call_arguments.delta",
        "response.function_call_arguments.done",
        "response.reasoning_summary_text.delta",
        "response.reasoning_summary_text.done",
        "response.completed",
        "response.incomplete",
        "response.failed",
    }
)

TERMINAL_EVENT_TYPES = frozenset(
    {"response.completed", "response.incomplete", "response.failed"}
)

# The default granularity of a synthesized delta, in characters. Small enough
# that a stream is visibly incremental, large enough that a 10 KB answer is not
# 10 000 frames.
DEFAULT_CHUNK_CHARS = 24


def events_for(response: dict, *, chunk_chars: int = DEFAULT_CHUNK_CHARS) -> list[dict]:
    """The typed event sequence for one complete response body.

    Ordering (upstream's): the response is created and in progress, then each
    output item is announced, its parts are announced and streamed, each part
    and item is closed, and finally the response is closed with its terminal
    event carrying the FULL response body — the same body a non-streaming call
    returns, so both surfaces agree by construction.
    """
    if chunk_chars < 1:
        raise ValueError("chunk_chars must be at least 1")

    events: list[dict] = []
    terminal = _terminal_type(response.get("status", "completed"))

    created = {**response, "status": "in_progress", "output": [], "usage": None}
    events.append({"type": "response.created", "response": created})
    events.append({"type": "response.in_progress", "response": created})

    for output_index, item in enumerate(response.get("output", [])):
        events.extend(_item_events(item, output_index, chunk_chars))

    events.append({"type": terminal, "response": response})

    for sequence_number, event in enumerate(events):
        event["sequence_number"] = sequence_number
    return events


def sse_frames(events: list[dict]) -> str:
    """Render events as the SSE wire format (base item 1: `text/event-stream`).

    `ensure_ascii=False` keeps non-ASCII text readable on the wire; `separators`
    keeps one event per block (`\\n\\n`), which is what makes the frame boundary
    unambiguous for the client's parser.
    """
    frames = []
    for event in events:
        data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        frames.append(f"event: {event['type']}\ndata: {data}\n\n")
    return "".join(frames)


def _terminal_type(status: str) -> str:
    if status == "incomplete":
        return "response.incomplete"
    if status == "failed":
        return "response.failed"
    return "response.completed"


def _item_events(item: dict, output_index: int, chunk_chars: int) -> list[dict]:
    """One output item's announcement, part streaming, and close."""
    events: list[dict] = [
        {
            "type": "response.output_item.added",
            "output_index": output_index,
            "item": _opened_item(item),
        }
    ]

    if item.get("type") == "message":
        content = item.get("content", [])
        for content_index, part in enumerate(content):
            events.extend(_part_events(part, output_index, content_index, chunk_chars))
    elif item.get("type") == "function_call":
        events.extend(_function_call_events(item, output_index, chunk_chars))
    elif item.get("type") == "reasoning":
        events.extend(_reasoning_events(item, output_index, chunk_chars))

    events.append(
        {"type": "response.output_item.done", "output_index": output_index, "item": item}
    )
    return events


def _part_events(
    part: dict, output_index: int, content_index: int, chunk_chars: int
) -> list[dict]:
    part_type = part.get("type")
    if part_type not in CONTENT_PART_TYPES:  # normalize_response rejected these already
        raise ValueError(f"unknown content part type {part_type!r} on the streaming seam")

    # The upstream event names differ per part type (`response.output_text.*`
    # vs `response.refusal.*`), and so do the payload fields: an output_text
    # part carries `text`, a refusal part carries `refusal`.
    name = "output_text" if part_type == "output_text" else "refusal"
    field = "text" if part_type == "output_text" else "refusal"
    streamed = part.get(field, "")
    events: list[dict] = [
        {
            "type": "response.content_part.added",
            "output_index": output_index,
            "content_index": content_index,
            "part": {**part, field: ""},
        }
    ]
    for chunk in _chunks(streamed, chunk_chars):
        events.append(
            {
                "type": f"response.{name}.delta",
                "output_index": output_index,
                "content_index": content_index,
                "delta": chunk,
            }
        )
    events.append(
        {
            "type": f"response.{name}.done",
            "output_index": output_index,
            "content_index": content_index,
            field: streamed,
        }
    )
    events.append(
        {
            "type": "response.content_part.done",
            "output_index": output_index,
            "content_index": content_index,
            "part": part,
        }
    )
    return events


def _function_call_events(item: dict, output_index: int, chunk_chars: int) -> list[dict]:
    arguments = item.get("arguments", "")
    events: list[dict] = []
    for chunk in _chunks(arguments, chunk_chars):
        events.append(
            {
                "type": "response.function_call_arguments.delta",
                "output_index": output_index,
                "item_id": item.get("id"),
                "delta": chunk,
            }
        )
    events.append(
        {
            "type": "response.function_call_arguments.done",
            "output_index": output_index,
            "item_id": item.get("id"),
            "arguments": arguments,
        }
    )
    return events


def _reasoning_events(item: dict, output_index: int, chunk_chars: int) -> list[dict]:
    events: list[dict] = []
    for summary_index, part in enumerate(item.get("summary", [])):
        text = part.get("text", "")
        for chunk in _chunks(text, chunk_chars):
            events.append(
                {
                    "type": "response.reasoning_summary_text.delta",
                    "output_index": output_index,
                    "summary_index": summary_index,
                    "delta": chunk,
                }
            )
        events.append(
            {
                "type": "response.reasoning_summary_text.done",
                "output_index": output_index,
                "summary_index": summary_index,
                "text": text,
            }
        )
    return events


def _opened_item(item: dict) -> dict:
    """The item as announced: its identity and role, with empty content — a
    client learns what is coming before any text arrives."""
    item_type = item.get("type")
    if item_type == "message":
        return {**item, "content": [], "status": "in_progress"}
    if item_type == "function_call":
        return {**item, "arguments": ""}
    if item_type == "reasoning":
        return {**item, "summary": []}
    return dict(item)


def _chunks(text: str, size: int) -> list[str]:
    return [text[offset : offset + size] for offset in range(0, len(text), size)]
