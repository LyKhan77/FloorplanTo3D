"""Strata client (PRD/05 §5, §6): OpenAI-compatible chat with JSON-schema answers, tool calls, retries on
invalid output, and per-call latency and token accounting. Transport errors never raise; they come back as an
invalid CallResult so the harness can log them and move on."""

import json
import re
import time
from dataclasses import dataclass, field

import httpx
import openai
from pydantic import BaseModel, ValidationError

USE_RESPONSE_FORMAT = True  # the probe (benchmarks/reports/spike-strata.md) showed json_schema is honoured
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"```(?:json)?")


@dataclass
class CallResult:
    raw: str
    parsed: dict | None
    valid: bool
    error: str | None
    latency_ms: int
    tokens: dict = field(default_factory=lambda: {"prompt": 0, "completion": 0})
    tool_calls: list[dict] = field(default_factory=list)
    attempts: int = 1


def extract_json(text: str) -> dict:
    """The outermost {...} object of a reply, without <think> blocks or code fences."""
    t = _FENCE.sub("", _THINK.sub("", text or ""))
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    return json.loads(t[start:end + 1])  # starts with "{", so it is an object or a JSONDecodeError (a ValueError)


class StrataClient:
    def __init__(self, base_url: str, model: str, timeout_s: float, http_client: httpx.Client | None = None,
                 use_response_format: bool = USE_RESPONSE_FORMAT):
        self.model = model
        self.root = base_url.removesuffix("/").removesuffix("/v1")
        self.use_response_format = use_response_format
        self._http = http_client
        self._sdk = openai.OpenAI(base_url=base_url, api_key="none", timeout=timeout_s, max_retries=0,
                                  http_client=http_client)

    def health(self, timeout_s: float = 3.0) -> bool:
        try:
            get = self._http.get if self._http else httpx.get
            return get(f"{self.root}/health", timeout=timeout_s).status_code == 200
        except httpx.HTTPError:
            return False

    def _create(self, messages: list[dict], effort: str, temperature: float, **kw):
        t0 = time.monotonic()
        try:
            r = self._sdk.chat.completions.create(model=self.model, messages=messages, temperature=temperature,
                                                  extra_body={"reasoning_effort": effort}, **kw)
            return r, None, int((time.monotonic() - t0) * 1000)
        except openai.APITimeoutError as e:
            return None, f"timeout: {e}", int((time.monotonic() - t0) * 1000)
        except openai.APIError as e:
            return None, f"{type(e).__name__}: {e}", int((time.monotonic() - t0) * 1000)

    @staticmethod
    def _add_usage(tokens: dict, r) -> None:
        if r.usage:
            tokens["prompt"] += r.usage.prompt_tokens or 0
            tokens["completion"] += r.usage.completion_tokens or 0

    def ask_json(self, messages: list[dict], schema: type[BaseModel], *, effort: str, temperature: float,
                 max_retries: int = 2) -> CallResult:
        kw = {}
        if self.use_response_format:
            kw["response_format"] = {"type": "json_schema",
                                     "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}
        msgs, tokens, latency, raw, error = list(messages), {"prompt": 0, "completion": 0}, 0, "", None
        for attempt in range(1, max_retries + 2):
            r, err, ms = self._create(msgs, effort, temperature, **kw)
            latency += ms
            if r is None:  # transport errors are not retried: the server is down or overloaded
                return CallResult(raw, None, False, err, latency, tokens, attempts=attempt)
            self._add_usage(tokens, r)
            raw = r.choices[0].message.content or ""
            try:
                parsed = schema.model_validate(extract_json(raw)).model_dump()
                return CallResult(raw, parsed, True, None, latency, tokens, attempts=attempt)
            except (ValueError, ValidationError) as e:
                error = str(e).splitlines()[0] if str(e) else type(e).__name__
                msgs += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"Your previous output was invalid: {error}. "
                                                     "Answer ONLY with JSON matching the schema."}]
        return CallResult(raw, None, False, error, latency, tokens, attempts=max_retries + 1)

    def ask_tools(self, messages: list[dict], tools: list[dict], *, effort: str, temperature: float = 0.0) -> CallResult:
        r, err, ms = self._create(messages, effort, temperature, tools=tools)
        tokens = {"prompt": 0, "completion": 0}
        if r is None:
            return CallResult("", None, False, err, ms, tokens)
        self._add_usage(tokens, r)
        m = r.choices[0].message
        calls = []
        for t in m.tool_calls or []:
            try:
                args = json.loads(t.function.arguments or "{}")
            except ValueError:
                args = None  # the harness rejects it with bad_args and tells the model
            calls.append({"id": t.id, "name": t.function.name, "arguments": args})
        return CallResult(m.content or "", None, True, None, ms, tokens, tool_calls=calls)
