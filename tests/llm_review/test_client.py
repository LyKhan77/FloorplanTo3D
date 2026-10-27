import json
from typing import Literal

import httpx
import pytest
from pydantic import BaseModel

from core.llm_review.client import StrataClient, extract_json


class T1Like(BaseModel):
    id: str
    verdict: Literal["wall", "annotation", "unsure"]


MSGS = [{"role": "user", "content": "is W7 a wall?"}]


def completion(content: str | None = None, tool_calls=None, prompt=60, completion_tokens=5) -> dict:
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop", "message": msg}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": completion_tokens, "total_tokens": prompt + completion_tokens}}


def make_client(replies, bodies=None, **kw) -> StrataClient:
    """Fake server: each POST pops the next reply (dict -> JSON 200, Exception -> raised)."""
    replies = list(replies)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/health"):
            return httpx.Response(200, json={"status": "ok"})
        if bodies is not None:
            bodies.append(json.loads(request.content))
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return httpx.Response(200, json=r)

    return StrataClient("http://strata.test/v1", "m", 5, http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kw)


def test_extract_json_strips_think_and_fences():
    text = '<think>hmm</think>\n```json\n{"id": "W7", "verdict": "wall"}\n```'
    assert extract_json(text) == {"id": "W7", "verdict": "wall"}
    with pytest.raises(ValueError):
        extract_json("sure, it is a wall")


def test_ask_json_retries_invalid_then_succeeds():
    bodies = []
    c = make_client([completion("sure!"), completion('{"id": "W7", "verdict": "wall"}')], bodies)
    r = c.ask_json(MSGS, T1Like, effort="low", temperature=0)
    assert r.valid and r.attempts == 2 and r.parsed == {"id": "W7", "verdict": "wall"}
    assert bodies[1]["messages"][-2] == {"role": "assistant", "content": "sure!"}
    assert "invalid" in bodies[1]["messages"][-1]["content"].lower()


def test_ask_json_gives_up_after_two_retries():
    c = make_client([completion("no json")] * 3)
    r = c.ask_json(MSGS, T1Like, effort="low", temperature=0)
    assert not r.valid and r.attempts == 3 and r.parsed is None and r.error


def test_schema_violation_counts_as_invalid():
    c = make_client([completion('{"id": "W7", "verdict": "maybe"}')])
    r = c.ask_json(MSGS, T1Like, effort="low", temperature=0, max_retries=0)
    assert r.valid is False and r.raw == '{"id": "W7", "verdict": "maybe"}'


def test_timeout_is_an_invalid_result_not_an_exception():
    c = make_client([httpx.ReadTimeout("slow")])
    r = c.ask_json(MSGS, T1Like, effort="low", temperature=0)
    assert not r.valid and "timeout" in r.error.lower() and r.attempts == 1


def test_tokens_and_latency_recorded():
    c = make_client([completion("x", prompt=60, completion_tokens=4), completion('{"id": "W7", "verdict": "wall"}', prompt=60, completion_tokens=5)])
    r = c.ask_json(MSGS, T1Like, effort="low", temperature=0)
    assert r.tokens == {"prompt": 120, "completion": 9} and r.latency_ms >= 0


def test_ask_tools_parses_tool_calls():
    tc = [{"id": "c1", "type": "function", "function": {"name": "delete_wall", "arguments": '{"id": "W3", "reason": "dim line"}'}}]
    c = make_client([completion(None, tool_calls=tc)])
    r = c.ask_tools(MSGS, [{"type": "function", "function": {"name": "delete_wall", "parameters": {"type": "object"}}}], effort="medium")
    assert r.valid and r.tool_calls == [{"id": "c1", "name": "delete_wall", "arguments": {"id": "W3", "reason": "dim line"}}]


def test_ask_tools_bad_arguments_are_kept_as_raw():
    tc = [{"id": "c1", "type": "function", "function": {"name": "finish", "arguments": "{oops"}}]
    r = make_client([completion(None, tool_calls=tc)]).ask_tools(MSGS, [], effort="medium")
    assert r.tool_calls == [{"id": "c1", "name": "finish", "arguments": None}]


def test_health_false_on_connection_error():
    def down(request):
        raise httpx.ConnectError("refused")

    c = StrataClient("http://strata.test/v1", "m", 1, http_client=httpx.Client(transport=httpx.MockTransport(down)))
    assert c.health() is False
    assert make_client([]).health() is True


def test_request_carries_model_temperature_effort_and_schema():
    bodies = []
    make_client([completion('{"id": "W7", "verdict": "wall"}')], bodies).ask_json(MSGS, T1Like, effort="low", temperature=0.4)
    b = bodies[0]
    assert b["model"] == "m" and b["temperature"] == 0.4 and b["reasoning_effort"] == "low"
    assert b["response_format"]["type"] == "json_schema" and "verdict" in json.dumps(b["response_format"])
    bodies = []
    make_client([completion('{"id": "W7", "verdict": "wall"}')], bodies, use_response_format=False).ask_json(MSGS, T1Like, effort="low", temperature=0)
    assert "response_format" not in bodies[0]
