"""Family 1 — LLM & agents inference conformance (ADR-0001 §Families.1).

`POST /v1/responses` is the OpenAI Responses API by reference: the response
body, `usage` in tokens, tool calling, structured outputs, citations, reasoning
items, refusals, and the typed SSE event vocabulary. This block asserts the
CONTRACT SHAPES at the HTTP seam — never engine internals — against the
vendored family module (see the block's `conftest.py`).

Runs only when `families/manifest.toml` lists family "1" (the test-side
manifest, ticket #70). `gated_client` is the never-bypassable red gate: no
assertion here can pass while the base contract is violated on this seam.
"""

from __future__ import annotations

import json

import pytest

from contract.families.family_1_responses import (
    EVENT_TYPES,
    SupportMatrix,
    required_features,
)
from tests.contract.runner import contract_family

from .conftest import ScenarioEngine

pytestmark = contract_family("1")

PING = {"model": "stub-model", "input": "ping"}


def parse_sse(body: str) -> list[dict]:
    """Parse an SSE body into its typed events, asserting the frame format
    (`event: <type>` + `data: <json>`, one block per event) as it goes."""
    events = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        assert lines[0].startswith("event: "), block
        data_lines = [line[len("data: "):] for line in lines if line.startswith("data: ")]
        assert data_lines, block
        event = json.loads("".join(data_lines))
        assert event["type"] == lines[0][len("event: "):], block
        events.append(event)
    return events


def reply(**overrides) -> dict:
    """A minimal engine reply carrying `output` + `usage`."""
    base = {
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "hello"}],
            }
        ],
        "usage": {"input_tokens": 2, "output_tokens": 1},
    }
    base.update(overrides)
    return base


# --- the response body (family 1: the Responses API by reference) ------------


def test_post_responses_returns_the_responses_body(gated_client):
    r = gated_client.post("/v1/responses", json=PING)
    assert r.status_code == 200
    body = r.json()
    assert body["id"].startswith("resp_")
    assert body["object"] == "response"
    assert body["model"] == "stub-model"
    assert body["status"] == "completed"
    assert isinstance(body["output"], list) and body["output"]
    assert r.headers["X-Request-Id"]  # base item 4 — every response


def test_usage_is_reported_in_tokens_and_adds_up(gated_client, make_gated_client):
    # Base item 8 — usage on resource-consuming operations; family 1 fixes the
    # unit (tokens). The stub derives the total; an engine that supplies its own
    # correct total must have it PRESERVED (a wrong one is a 500, see the
    # malformed-reply test).
    usage = gated_client.post("/v1/responses", json=PING).json()["usage"]
    assert set(usage) >= {"input_tokens", "output_tokens", "total_tokens"}
    assert usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]

    declared = make_gated_client(
        ScenarioEngine(
            reply(
                output=[
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "hi"}],
                    }
                ],
                usage={"input_tokens": 2, "output_tokens": 5, "total_tokens": 7},
            )
        )
    )
    assert declared.post("/v1/responses", json=PING).json()["usage"]["total_tokens"] == 7


def test_the_engine_receives_the_parsed_request(make_gated_client):
    engine = ScenarioEngine(reply())
    client = make_gated_client(engine)
    assert client.post("/v1/responses", json=PING).status_code == 200

    call = engine.calls[0]
    assert call["operation"] == "responses"
    sent = call["request"]
    assert sent["model"] == "stub-model"
    # a bare string input is the shorthand for one input_text part
    assert sent["input"] == [{"type": "input_text", "text": "ping"}]
    assert sent["tools"] == []
    assert sent["text"] == {"format": {"type": "text"}}
    assert sent["stream"] is False


def test_output_text_is_a_typed_content_part(gated_client):
    message = gated_client.post("/v1/responses", json=PING).json()["output"][0]
    assert message["type"] == "message"
    assert message["role"] == "assistant"
    part = message["content"][0]
    assert part["type"] == "output_text"
    assert isinstance(part["text"], str)
    assert part["annotations"] == []


def test_a_bare_engine_id_gains_the_resp_prefix(make_gated_client):
    client = make_gated_client(ScenarioEngine(reply(id="bare-id")))
    assert client.post("/v1/responses", json=PING).json()["id"] == "resp_bare-id"


# --- structured outputs / citations / reasoning / refusals -------------------


def test_structured_output_must_be_json(make_gated_client):
    request = {
        **PING,
        "text": {"format": {"type": "json_schema", "name": "answer", "schema": {"type": "object"}}},
    }
    good = make_gated_client(
        ScenarioEngine(
            reply(
                output=[
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": '{"a": 1}'}],
                    }
                ]
            )
        )
    )
    assert good.post("/v1/responses", json=request).status_code == 200

    # The engine broke the structured-output contract: 500 internal_error (the
    # implementation is at fault), never a 200 carrying unparseable text.
    bad = make_gated_client(
        ScenarioEngine(
            reply(
                output=[
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "not json"}],
                    }
                ]
            )
        )
    )
    r = bad.post("/v1/responses", json=request)
    assert r.status_code == 500
    assert r.json()["error"]["type"] == "internal_error"


def test_citations_ride_the_output_text_part(make_gated_client):
    annotated = reply(
        output=[
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "as documented",
                        "annotations": [{"type": "url_citation", "url": "https://example.org/doc"}],
                    }
                ],
            }
        ]
    )
    body = make_gated_client(ScenarioEngine(annotated)).post("/v1/responses", json=PING).json()
    assert body["output"][0]["content"][0]["annotations"][0]["type"] == "url_citation"

    # An unknown annotation type is not silently passed through.
    unknown = reply(
        output=[
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "x", "annotations": [{"type": "magic"}]}
                ],
            }
        ]
    )
    r = make_gated_client(ScenarioEngine(unknown)).post("/v1/responses", json=PING)
    assert r.status_code == 500


def test_refusal_is_a_typed_content_part(make_gated_client):
    refusal = reply(
        output=[
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "refusal", "refusal": "I can't help with that."}],
            }
        ]
    )
    body = make_gated_client(ScenarioEngine(refusal)).post("/v1/responses", json=PING).json()
    assert body["output"][0]["content"][0] == {
        "type": "refusal",
        "refusal": "I can't help with that.",
    }


def test_reasoning_items_carry_summary_parts(make_gated_client):
    reasoning = reply(
        output=[
            {
                "type": "reasoning",
                "id": "rs_1",
                "summary": [{"type": "summary_text", "text": "thought about it"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "done"}],
            },
        ]
    )
    body = make_gated_client(ScenarioEngine(reasoning)).post("/v1/responses", json=PING).json()
    item = body["output"][0]
    assert item["type"] == "reasoning"
    assert item["summary"] == [{"type": "summary_text", "text": "thought about it"}]

    malformed = reply(output=[{"type": "reasoning", "summary": "not a list"}])
    assert make_gated_client(ScenarioEngine(malformed)).post("/v1/responses", json=PING).status_code == 500


def test_function_call_items_are_typed(make_gated_client):
    call = reply(
        output=[
            {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": '{"q": "x"}',
            }
        ]
    )
    item = make_gated_client(ScenarioEngine(call)).post("/v1/responses", json=PING).json()["output"][0]
    assert item["type"] == "function_call"
    assert item["name"] == "lookup"
    assert item["call_id"] == "call_1"
    assert item["status"] == "completed"  # every item type carries a status

    # `arguments` must be a JSON string (upstream shape), not an object
    bad = reply(output=[{"type": "function_call", "name": "lookup", "arguments": {"q": "x"}}])
    assert make_gated_client(ScenarioEngine(bad)).post("/v1/responses", json=PING).status_code == 500


def test_a_malformed_engine_reply_is_internal_error(make_gated_client):
    for engine_reply in (
        {"usage": {"input_tokens": 1, "output_tokens": 1}},  # no output
        reply(output=[{"type": "telepathy"}]),  # unknown item type
        reply(usage={"input_tokens": 5, "output_tokens": 1, "total_tokens": 99}),  # totals lie
        {"output": [], "usage": {}},  # usage is not token counts
    ):
        r = make_gated_client(ScenarioEngine(engine_reply)).post("/v1/responses", json=PING)
        assert r.status_code == 500, engine_reply
        assert r.json()["error"]["type"] == "internal_error"


# --- streaming (typed SSE events) -------------------------------------------


def test_stream_true_returns_typed_sse_events(gated_client):
    r = gated_client.post("/v1/responses", json={**PING, "stream": True})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(r.text)
    assert events[0]["type"] == "response.created"
    assert events[-1]["type"] == "response.completed"
    for event in events:
        assert event["type"] in EVENT_TYPES
    assert [e["sequence_number"] for e in events] == list(range(len(events)))
    # Part events carry the item id: upstream clients route deltas by
    # (item_id, content_index), never by position alone.
    part_events = [e for e in events if "content_index" in e]
    assert part_events
    assert all(e["item_id"] == "msg_0" for e in part_events)
    # the Responses API has no [DONE] sentinel — the terminal event closes it
    assert "[DONE]" not in r.text


def test_the_streamed_deltas_reconstruct_the_text(gated_client):
    events = parse_sse(gated_client.post("/v1/responses", json={**PING, "stream": True}).text)
    deltas = [e["delta"] for e in events if e["type"] == "response.output_text.delta"]
    done = [e for e in events if e["type"] == "response.output_text.done"]
    assert deltas and done
    assert "".join(deltas) == done[0]["text"]
    # the closed part carries the same text the deltas built
    part_done = [e for e in events if e["type"] == "response.content_part.done"][0]
    assert part_done["part"]["text"] == done[0]["text"]


def test_the_stream_and_the_sync_body_agree(gated_client):
    sync_body = gated_client.post("/v1/responses", json=PING).json()
    events = parse_sse(gated_client.post("/v1/responses", json={**PING, "stream": True}).text)
    completed = events[-1]["response"]
    for key in ("output", "usage", "model", "status", "object"):
        assert completed[key] == sync_body[key], key


# --- request validation (400 invalid_request) -------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "not an object",
        {"input": "ping"},  # no model
        {"model": "", "input": "ping"},
        {"model": "m"},  # no input
        {"model": "m", "input": []},
        {"model": "m", "input": [{"type": "input_video"}]},
        {"model": "m", "input": [{"type": "input_text"}]},  # no text
        {"model": "m", "input": [{"type": "input_image"}]},  # no image_url
        {"model": "m", "input": "ping", "tools": [{"type": "magic"}]},
        {"model": "m", "input": "ping", "tools": [{"type": "function"}]},  # no name
        {"model": "m", "input": "ping", "text": {"format": {"type": "json_schema"}}},
        {"model": "m", "input": "ping", "stream": "yes"},
        {"model": "m", "input": "ping", "background": True},  # family 5's, not ours
        {"model": "m", "input": "ping", "max_output_tokens": 0},
        {"model": "m", "input": "ping", "background": 1},  # not a boolean false
        {"model": "m", "input": [{"role": "user", "content": 5}]},
        {"model": "m", "input": [{"role": "banana", "content": "hi"}]},  # closed role enum
        {  # ambiguous: a message has no item 'type', an item has no 'role'
            "model": "m",
            "input": [{"role": "user", "type": "input_text", "text": "hi"}],
        },
        {"model": "m", "input": [{"type": "function_call_output", "output": "x"}]},  # no call_id
        {  # a tool result is an ITEM, never a message content part
            "model": "m",
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "function_call_output", "call_id": "c", "output": "x"}
                    ],
                }
            ],
        },
        {  # ... and its output entries must be content parts
            "model": "m",
            "input": [{"type": "function_call_output", "call_id": "c", "output": [1, 2]}],
        },
    ],
)
def test_invalid_requests_are_400_invalid_request(gated_client, payload):
    r = gated_client.post("/v1/responses", json=payload)
    assert r.status_code == 400, payload
    assert r.json()["error"]["type"] == "invalid_request"


def test_an_empty_or_oversized_body_is_refused(make_gated_client):
    client = make_gated_client(ScenarioEngine(reply()))
    assert client.post("/v1/responses", content=b"").status_code == 400
    oversized = make_gated_client(ScenarioEngine(reply()), max_request_bytes=8)
    r = oversized.post("/v1/responses", json=PING)
    assert r.status_code == 413
    assert r.json()["error"]["type"] == "request_too_large"
    # ... and the post-read fallback still catches a CHUNKED body, which declares
    # no Content-Length to check before buffering.
    chunked = make_gated_client(ScenarioEngine(reply()), max_request_bytes=8)
    r = chunked.post("/v1/responses", content=iter([b'{"model": "m", "input": "ping"}']))
    assert r.status_code == 413
    assert r.json()["error"]["type"] == "request_too_large"


# --- the per-implementation support matrix (ADR-0004) -----------------------


def test_a_feature_the_implementation_lacks_is_refused_by_name(make_gated_client):
    engine = ScenarioEngine(reply())
    matrix = SupportMatrix(supported=frozenset({"function_tools", "structured_outputs"}))
    client = make_gated_client(engine, support=matrix, implementation="stub-llm")

    r = client.post(
        "/v1/responses",
        json={"model": "m", "input": [{"type": "input_image", "image_url": "https://x/y.png"}]},
    )
    assert r.status_code == 400
    message = r.json()["error"]["message"]
    assert "vision" in message and "stub-llm" in message
    assert engine.calls == []  # refused before the engine was called


def test_a_supported_feature_passes_the_gate(make_gated_client):
    matrix = SupportMatrix(supported=frozenset({"vision"}))
    client = make_gated_client(ScenarioEngine(reply()), support=matrix)
    r = client.post(
        "/v1/responses",
        json={"model": "m", "input": [{"type": "input_image", "image_url": "https://x/y.png"}]},
    )
    assert r.status_code == 200


def test_streaming_is_not_a_gated_feature(make_gated_client):
    # The typed event sequence is the MODULE's (events.py), so every
    # implementation of this route streams: declaring a narrow matrix must not
    # turn `stream: true` into a 400.
    client = make_gated_client(
        ScenarioEngine(reply()), support=SupportMatrix(supported=frozenset({"function_tools"}))
    )
    r = client.post("/v1/responses", json={**PING, "stream": True})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")


def test_an_empty_support_matrix_is_a_legitimate_variant(make_gated_client):
    # Plain text in, plain text out is family 1's always-supported base: a small
    # local model with no vision, tools or structured outputs declares nothing,
    # and must still serve (ADR-0004 — the union of variants, not the
    # intersection).
    client = make_gated_client(
        ScenarioEngine(reply()), support=SupportMatrix(supported=frozenset())
    )
    assert client.post("/v1/responses", json=PING).status_code == 200
    # and it refuses what it does not have
    assert (
        client.post(
            "/v1/responses",
            json={"model": "m", "input": [{"type": "input_image", "image_url": "https://x/y.png"}]},
        ).status_code
        == 400
    )


def test_the_support_matrix_reports_gaps_and_rejects_nonsense():
    matrix = SupportMatrix(supported=frozenset({"function_tools", "structured_outputs"}))
    assert matrix.gaps({"function_tools", "vision"}) == ("vision",)
    assert matrix.gaps({"function_tools"}) == ()
    assert matrix.supports("function_tools") is True
    with pytest.raises(ValueError, match="unknown family-1 feature"):
        matrix.supports("telepathy")
    with pytest.raises(ValueError, match="unknown family-1 feature"):
        SupportMatrix(supported=frozenset({"telepathy"}))
    # an empty set is legal — text-only is a real variant, not a broken one
    assert SupportMatrix(supported=frozenset()).gaps({"vision"}) == ("vision",)
    # ADR-0001 §Families.1: deviations are pinned to a reference date.
    with pytest.raises(ValueError, match="reference_date"):
        SupportMatrix(supported=frozenset({"vision"}), deviations=("no audio input",))
    pinned = SupportMatrix(
        supported=frozenset({"vision"}),
        deviations=("no audio input",),
        reference_date="2026-10-27",
    )
    assert pinned.deviations == ("no audio input",)


def test_required_features_follows_what_the_request_asks_for():
    assert required_features({"input": [{"type": "input_text", "text": "x"}]}) == frozenset()
    assert required_features(
        {"input": [{"type": "input_audio", "input_audio": {"data": "…", "format": "wav"}}]}
    ) == frozenset({"audio"})
    assert required_features(
        {"input": [], "tools": [{"type": "mcp", "server_label": "s"}]}
    ) == frozenset({"mcp_tools"})
    assert required_features({"text": {"format": {"type": "json_schema"}}}) == frozenset(
        {"structured_outputs"}
    )
    # streaming is served by the module itself, never required of an engine
    assert required_features({"stream": True}) == frozenset()


# --- the shapes the reference API accepts, one turn past the naive path ------


def test_a_tool_loop_round_trip_is_closable(make_gated_client):
    # A tool loop is the CALL plus its RESULT: an assistant's `function_call`
    # item sent back beside the caller's `function_call_output`. Without both,
    # the model can emit a call that nobody can ever answer.
    engine = ScenarioEngine(reply())
    client = make_gated_client(engine)
    r = client.post(
        "/v1/responses",
        json={
            "model": "m",
            "input": [
                {"type": "input_text", "text": "look it up"},
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "lookup",
                    "arguments": '{"q": "x"}',
                },
                {"type": "function_call_output", "call_id": "call_1", "output": '{"ok": true}'},
            ],
        },
    )
    assert r.status_code == 200
    sent = engine.calls[0]["request"]["input"]
    assert sent[1]["type"] == "function_call"
    assert sent[2] == {
        "type": "function_call_output",
        "call_id": "call_1",
        "output": '{"ok": true}',
    }


def test_a_message_content_may_be_a_plain_string(make_gated_client):
    # Upstream's EasyInputMessage accepts a string where a content list is
    # expected; the module normalizes it to one input_text part.
    engine = ScenarioEngine(reply())
    client = make_gated_client(engine)
    assert client.post(
        "/v1/responses", json={"model": "m", "input": [{"role": "user", "content": "hi"}]}
    ).status_code == 200
    assert engine.calls[0]["request"]["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]}
    ]

    # ... and upstream's optional `type: "message"` discriminator is accepted
    # (normalized away), so a reference-shaped payload is not refused.
    assert client.post(
        "/v1/responses",
        json={
            "model": "m",
            "input": [{"role": "user", "type": "message", "content": "hi"}],
        },
    ).status_code == 200
    assert engine.calls[1]["request"]["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]}
    ]


def test_a_malformed_tool_call_arguments_is_a_client_error(make_gated_client):
    # The caller's arguments must be a JSON string; a malformed one is 400 (base
    # item 4), not the 500 that a malformed ENGINE reply earns.
    client = make_gated_client(ScenarioEngine(reply()))
    r = client.post(
        "/v1/responses",
        json={
            "model": "m",
            "input": [
                {"type": "function_call", "call_id": "c", "name": "lookup", "arguments": "{nope"}
            ],
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


def test_an_empty_arguments_string_is_a_no_argument_call(make_gated_client):
    # Upstream allows `arguments: ""` for a call that takes none; only a
    # non-empty value has to parse as JSON.
    client = make_gated_client(ScenarioEngine(reply()))
    r = client.post(
        "/v1/responses",
        json={
            "model": "m",
            "input": [{"type": "function_call", "call_id": "c", "name": "ping", "arguments": ""}],
        },
    )
    assert r.status_code == 200


def test_a_part_inside_a_tool_result_is_validated_like_any_other_part(make_gated_client):
    # The same content-part rules apply inside `function_call_output.output`:
    # an input_text without its text is a 400 there too.
    client = make_gated_client(ScenarioEngine(reply()))
    r = client.post(
        "/v1/responses",
        json={
            "model": "m",
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "c",
                    "output": [{"type": "input_text"}],
                }
            ],
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


def test_media_inside_a_tool_result_is_gated_like_any_other_input(make_gated_client):
    # An image riding in through a tool result must not bypass the support gate:
    # a text-only implementation would otherwise receive one it declared it
    # cannot read.
    engine = ScenarioEngine(reply())
    client = make_gated_client(
        engine,
        support=SupportMatrix(supported=frozenset({"function_tools"})),
        implementation="stub-llm",
    )
    r = client.post(
        "/v1/responses",
        json={
            "model": "m",
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "c",
                    "output": [{"type": "input_image", "image_url": "https://x/y.png"}],
                }
            ],
        },
    )
    assert r.status_code == 400
    assert "vision" in r.json()["error"]["message"]
    assert engine.calls == []


def test_mcp_output_items_are_typed(make_gated_client):
    mcp_turn = reply(
        output=[
            {
                "type": "mcp_call",
                "name": "search",
                "server_label": "web",
                "arguments": '{"q": "x"}',
            },
            {"type": "mcp_list_tools", "server_label": "web", "tools": [{"name": "search"}]},
        ]
    )
    body = make_gated_client(ScenarioEngine(mcp_turn)).post("/v1/responses", json=PING).json()
    call, listed = body["output"]
    assert call["type"] == "mcp_call" and call["arguments"] == '{"q": "x"}'
    assert listed["type"] == "mcp_list_tools" and listed["tools"] == [{"name": "search"}]

    # the same seam violations its function_call sibling rejects
    for broken in (
        {"type": "mcp_call", "name": "search", "server_label": "web", "arguments": {"q": "x"}},
        {"type": "mcp_list_tools", "server_label": "web", "tools": "search"},
    ):
        r = make_gated_client(ScenarioEngine(reply(output=[broken]))).post(
            "/v1/responses", json=PING
        )
        assert r.status_code == 500, broken


def test_instructions_are_echoed_and_max_output_tokens_accepted(make_gated_client):
    engine = ScenarioEngine(reply())
    client = make_gated_client(engine)
    body = client.post(
        "/v1/responses",
        json={**PING, "instructions": "be brief", "max_output_tokens": 32, "background": False},
    ).json()
    assert body["instructions"] == "be brief"
    assert engine.calls[0]["request"]["max_output_tokens"] == 32
    # an explicit `background: false` is the synchronous default: dropped, not
    # forwarded as a meaningless key
    assert "background" not in engine.calls[0]["request"]


def test_a_message_output_item_must_be_an_assistant_turn(make_gated_client):
    # The contract fixes the item vocabulary: an output message is the
    # assistant's, and its status is one of the closed set.
    for broken in (
        {"type": "message", "role": "user", "content": [{"type": "output_text", "text": "x"}]},
        {
            "type": "message",
            "role": "assistant",
            "status": "banana",
            "content": [{"type": "output_text", "text": "x"}],
        },
    ):
        r = make_gated_client(ScenarioEngine(reply(output=[broken]))).post(
            "/v1/responses", json=PING
        )
        assert r.status_code == 500, broken


def test_unread_request_fields_are_forwarded_to_the_engine(make_gated_client):
    # Base item 3: a key the module does not read must still reach the engine.
    # Dropping `tool_choice: "none"` would let the model call a tool the caller
    # forbade; dropping `previous_response_id` turns a continuation into a fresh
    # turn. Both are wrong ANSWERS, not just lost knobs.
    engine = ScenarioEngine(reply())
    client = make_gated_client(engine)
    r = client.post(
        "/v1/responses",
        json={**PING, "temperature": 0.2, "tool_choice": "none", "previous_response_id": "resp_1"},
    )
    assert r.status_code == 200
    sent = engine.calls[0]["request"]
    assert sent["temperature"] == 0.2
    assert sent["tool_choice"] == "none"
    assert sent["previous_response_id"] == "resp_1"


def test_every_response_status_has_a_terminal_event():
    # A status the events module cannot close on would raise out of the route
    # (a bare 500): the vocabulary and the mapping are pinned together.
    from contract.families.family_1_responses import (
        RESPONSE_STATUSES,
        TERMINAL_EVENT_BY_STATUS,
        TERMINAL_EVENT_TYPES,
    )

    assert set(TERMINAL_EVENT_BY_STATUS) == RESPONSE_STATUSES
    assert frozenset(TERMINAL_EVENT_BY_STATUS.values()) == TERMINAL_EVENT_TYPES


# --- the fragment: document assembly and the agent surface -------------------


def test_the_fragment_and_the_route_agree_on_what_input_accepts():
    """The fragment is the AGENT-visible contract (its request schema becomes the
    MCP tool's `inputSchema`), so a schema advertising a shape the route 400s is
    exactly the drift the auto-generated surface is meant to make impossible
    (ADR-0002 §3). Both sides read the same vocabularies — this pins it."""
    from contract.families.family_1_responses import (
        INPUT_ITEM_TYPES,
        MESSAGE_CONTENT_PART_TYPES,
        openapi_fragment,
    )

    schema = openapi_fragment["paths"]["/v1/responses"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    members = schema["properties"]["input"]["items"]["anyOf"]

    # the message variant may carry CONTENT PARTS only — no tool item inside
    message = next(m for m in members if "role" in m["properties"])
    content = message["properties"]["content"]
    assert sorted(content["items"]["properties"]["type"]["enum"]) == sorted(
        MESSAGE_CONTENT_PART_TYPES
    )
    assert content["minItems"] == 1

    # the standalone variants are the route's item vocabulary, tool loop included
    part = next(m for m in members if "text" in m["properties"])
    assert sorted(part["properties"]["type"]["enum"]) == sorted(MESSAGE_CONTENT_PART_TYPES)
    consts = {
        member["properties"]["type"].get("const")
        for member in members
        if "type" in member.get("properties", {})
    }
    assert {"function_call", "function_call_output"} <= consts
    assert INPUT_ITEM_TYPES == MESSAGE_CONTENT_PART_TYPES | {
        "function_call",
        "function_call_output",
    }


def test_the_fragment_merges_and_reaches_the_mcp_tool():
    """The documented integration path, exercised end to end: merge the fragment
    with the canary's, serve the document, and read the auto-generated MCP
    tool. A duplicate component or a `$ref` in the request body breaks this —
    which is exactly what it exists to catch."""
    from starlette.testclient import TestClient

    from capabilities import canary
    from contract.base.app import create_service_app
    from contract.base.openapi import openapi_document
    from contract.families.family_1_responses import openapi_fragment, responses_routes
    from tests.support.stubs import StubEngine, stub_api_key

    document = openapi_document(
        title="family-1-probe",
        version="0.0.1",
        fragments=[canary.openapi_fragment, openapi_fragment],
    )
    assert "/v1/responses" in document["paths"]
    # the item-4 error schema is supplied once, by the base
    assert "error" in document["components"]["schemas"]

    key = stub_api_key()
    app = create_service_app(
        service_name="family-1-probe",
        version="0.0.1",
        api_keys=[key],
        openapi_doc=document,
        mcp=True,
        extra_routes=[*responses_routes(StubEngine())],
    )
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {key}"
        served = client.get("/openapi.json").json()
        assert "/v1/responses" in served["paths"]

        rpc = client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=headers
        )
        tools = {tool["name"]: tool for tool in rpc.json()["result"]["tools"]}

    assert "responses" in tools
    schema = tools["responses"]["inputSchema"]
    # an agent must see real parameters, not a dangling $ref
    assert "$ref" not in schema
    assert {"model", "input"} <= set(schema["properties"])
    assert tools["responses"]["description"]
