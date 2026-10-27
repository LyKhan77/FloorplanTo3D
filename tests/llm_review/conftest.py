"""FakeStrata: the StrataClient interface driven by a script, so no unit test talks to the real server."""

import json
import re
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from core.config import load_settings
from core.llm_review.client import CallResult, StrataClient, extract_json

_ELEMENT = re.compile(r"[Ee]lement (\w+)")


def _last_text(messages: list[dict]) -> str:
    content = messages[-1]["content"]
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if p.get("type") == "text")
    return content or ""


def element_of(messages: list[dict]) -> str | None:
    m = _ELEMENT.search(_last_text(messages))
    return m[1] if m else None


class FakeStrata:
    """script(messages, kwargs) -> reply. A str is the raw content, a dict is JSON-encoded (or, for ask_tools,
    {"tool_calls": [{"name", "arguments"}], "content"?}), an Exception is a transport failure."""

    def __init__(self, script: Callable[[list[dict], dict], object], healthy: bool = True):
        self.script, self.healthy, self.calls = script, healthy, []

    def health(self, timeout_s: float = 3.0) -> bool:
        return self.healthy

    def _record(self, messages, kw) -> object:
        self.calls.append({"messages": messages, "element": element_of(messages), **kw})
        return self.script(messages, kw)

    def ask_json(self, messages, schema, *, effort, temperature, max_retries=2, deadline=None) -> CallResult:
        raw, error = "", None
        for attempt in range(1, max_retries + 2):
            reply = self._record(messages, {"effort": effort, "temperature": temperature, "schema": schema})
            if isinstance(reply, Exception):
                return CallResult("", None, False, f"timeout: {reply}", 1, attempts=attempt, transport=True)
            raw = reply if isinstance(reply, str) else json.dumps(reply)
            try:
                return CallResult(raw, schema.model_validate(extract_json(raw)).model_dump(), True, None, 1,
                                  {"prompt": 10, "completion": 2}, attempts=attempt)
            except (ValueError, ValidationError) as e:
                error = str(e).splitlines()[0]
        return CallResult(raw, None, False, error, 1, attempts=max_retries + 1)

    def ask_tools(self, messages, tools, *, effort, temperature=0.0, deadline=None) -> CallResult:
        reply = self._record(messages, {"effort": effort, "temperature": temperature, "tools": tools})
        if isinstance(reply, Exception):
            return CallResult("", None, False, f"timeout: {reply}", 1, transport=True)
        calls = [{"id": f"c{i}", "name": c["name"], "arguments": c.get("arguments")}
                 for i, c in enumerate(reply.get("tool_calls", []))]
        return CallResult(reply.get("content", ""), None, True, None, 1, {"prompt": 10, "completion": 2}, calls)


@pytest.fixture
def strata_live() -> StrataClient:
    s = load_settings()
    client = StrataClient(s.strata_base_url, s.strata_model, s.strata_timeout_s)
    if not client.health():
        pytest.skip("Strata not reachable")
    return client
