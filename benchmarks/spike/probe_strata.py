"""Throwaway capability probe for Strata (PRD/05 §8, M6 Task 1). Writes benchmarks/spike/out/probe.json.

Run: uv run --env-file .env python benchmarks/spike/probe_strata.py
"""

import base64
import json
import os
import re
import statistics
import time
from pathlib import Path

import cv2
import httpx
import numpy as np
from openai import OpenAI

BASE = os.environ.get("STRATA_BASE_URL", "http://192.168.2.142:8081/v1")
MODEL = os.environ.get("STRATA_MODEL", "qwen3.8-flash-next-iq2_xs")
ROOT = BASE.removesuffix("/").removesuffix("/v1")
OUT = Path(__file__).parent / "out"
client = OpenAI(base_url=BASE, api_key="none", timeout=180, max_retries=0)

SYSTEM = "Answer ONLY with JSON matching the given schema. No explanation outside JSON."
YESNO = {"type": "object", "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}},
         "required": ["answer"], "additionalProperties": False}
WORDS = {6: "KAPUR", 8: "MERAH", 10: "DELTA", 12: "SINAR", 16: "BUKIT", 20: "LAMPU"}


def call(messages, **kw):
    t0 = time.monotonic()
    try:
        r = client.chat.completions.create(model=MODEL, messages=messages, temperature=0, max_tokens=800, **kw)
        ms = int((time.monotonic() - t0) * 1000)
        m = r.choices[0].message
        return {"ok": True, "ms": ms, "content": m.content or "", "tool_calls": [
            {"name": t.function.name, "arguments": t.function.arguments} for t in (m.tool_calls or [])],
            "usage": r.usage.model_dump() if r.usage else None}
    except Exception as e:  # noqa: BLE001 - probe records every failure
        return {"ok": False, "ms": int((time.monotonic() - t0) * 1000), "error": f"{type(e).__name__}: {e}"[:400]}


def strict_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


def text_probe(n=5, **kw):
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": 'Is 7 a prime number? Schema: {"answer": "yes"|"no"}'}]
    rows = [call(msgs, **kw) for _ in range(n)]
    ok = [r for r in rows if r["ok"]]
    return {"calls": n, "ok": len(ok), "errors": [r["error"] for r in rows if not r["ok"]][:2],
            "strict_json": sum(strict_json(r["content"]) for r in ok),
            "think": sum("<think>" in r["content"] for r in ok), "fence": sum("```" in r["content"] for r in ok),
            "median_ms": statistics.median(r["ms"] for r in ok) if ok else None,
            "sample": ok[0]["content"][:200] if ok else None}


def png_uri(img: np.ndarray) -> str:
    return "data:image/png;base64," + base64.b64encode(cv2.imencode(".png", img)[1].tobytes()).decode()


def word_image(side: int) -> np.ndarray:
    img = np.full((side, side, 3), 255, np.uint8)
    y = side // 10
    for h, word in WORDS.items():
        (_, base_h), _ = cv2.getTextSize("H", cv2.FONT_HERSHEY_SIMPLEX, 1.0, 1)
        scale = h / base_h
        cv2.putText(img, word, (side // 10, y + h), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 1, cv2.LINE_AA)
        y += side // 8
    return img


def image_probe(side: int):
    img = word_image(side)
    cv2.imwrite(str(OUT / f"words_{side}.png"), img)
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": 'Transcribe every word you can read, top to bottom. Schema: {"words": [string]}'},
                {"type": "image_url", "image_url": {"url": png_uri(img)}}]}]
    r = call(msgs)
    seen = set(re.findall(r"[A-Z]{4,}", (r.get("content") or "").upper()))
    read = {h: w in seen for h, w in WORDS.items()}
    smallest = min((h for h, ok in read.items() if ok), default=None)
    return {"side": side, "ok": r["ok"], "ms": r["ms"], "read": read, "smallest_px": smallest,
            "raw": (r.get("content") or r.get("error") or "")[:300]}


def tool_probe():
    tools = [{"type": "function", "function": {"name": "finish", "description": "End the review.",
                                               "parameters": {"type": "object", "properties": {"summary": {"type": "string"}},
                                                              "required": ["summary"]}}},
             {"type": "function", "function": {"name": "delete_wall", "description": "Delete a wall that is not architectural.",
                                               "parameters": {"type": "object", "properties": {"id": {"type": "string"}, "reason": {"type": "string"}},
                                                              "required": ["id", "reason"]}}}]
    msgs = [{"role": "user", "content": "Delete wall W3 because it is a dimension line. Use the tools."}]
    r = call(msgs, tools=tools, extra_body={"reasoning_effort": "medium"})
    valid = []
    for t in r.get("tool_calls") or []:
        valid.append(strict_json(t["arguments"]))
    return {"ok": r["ok"], "ms": r["ms"], "tool_calls": r.get("tool_calls"), "args_json_valid": valid,
            "content": (r.get("content") or r.get("error") or "")[:200]}


def latency_probe(n=5):
    small = cv2.resize(word_image(768), (384, 384))
    big = word_image(768)
    q = {"type": "text", "text": 'Is there any text in the image? Schema: {"answer": "yes"|"no"}'}
    variants = {
        "text": [{"role": "user", "content": 'Is 9 a prime number? Schema: {"answer": "yes"|"no"}'}],
        "img768": [{"role": "user", "content": [q, {"type": "image_url", "image_url": {"url": png_uri(big)}}]}],
        "img768+384": [{"role": "user", "content": [q, {"type": "image_url", "image_url": {"url": png_uri(big)}},
                                                    {"type": "image_url", "image_url": {"url": png_uri(small)}}]}],
    }
    out = {}
    for name, msgs in variants.items():
        ms = sorted(r["ms"] for r in (call([{"role": "system", "content": SYSTEM}, *msgs],
                                           extra_body={"reasoning_effort": "low"}) for _ in range(n)) if r["ok"])
        out[name] = {"n": len(ms), "median_ms": statistics.median(ms) if ms else None,
                     "p90_ms": ms[min(len(ms) - 1, int(0.9 * len(ms)))] if ms else None}
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"model": MODEL, "base": BASE}
    for ep in ("/health", "/status", "/v1/models"):
        try:
            r = httpx.get(ROOT + ep, timeout=5)
            res[ep] = {"code": r.status_code, "body": r.text[:300]}
        except httpx.HTTPError as e:
            res[ep] = {"error": str(e)}
    print("b: plain JSON"); res["b_plain"] = text_probe()
    print("c: response_format"); res["c_response_format"] = text_probe(
        response_format={"type": "json_schema", "json_schema": {"name": "yesno", "schema": YESNO, "strict": True}})
    print("d: reasoning_effort")
    res["d_effort"] = {e: text_probe(3, extra_body={"reasoning_effort": e}) for e in ("none", "low", "medium")}
    print("e: image size"); res["e_image"] = [image_probe(768), image_probe(1536)]
    print("f: tools"); res["f_tools"] = tool_probe()
    print("g: latency"); res["g_latency"] = latency_probe()
    (OUT / "probe.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=1)[:6000])


if __name__ == "__main__":
    main()
