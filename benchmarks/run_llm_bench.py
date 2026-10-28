"""Strata benchmark (PRD/05 §7.3): accuracy against the §7.2 baselines per task, or the end-to-end metric delta.

Run: uv run --env-file .env python -m benchmarks.run_llm_bench --task T1 --prompt v1 --votes 3 [--no-evidence]
     [--no-fewshot]                         # T0-T3: labelled items in benchmarks/gatsu/llm_items
     --task T4 --tasks T1,T3                # the active tasks with and without T4 on the Gatsu stage-5 spec
     --task e2e --tasks T1,T3               # no Strata vs the given tasks on the Gatsu stage-5 spec
Reports: benchmarks/reports/llm-<task>-<prompt>-<variant>.md + .json
"""

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from benchmarks.extraction_metrics import LOWER_IS_BETTER, evaluate, typed_room_count
from benchmarks.llm_items import (
    CACHE,
    FEWSHOT_ROOT,
    GT_PATH,
    candidate_specs,
    gatsu_stages,
    score_task,
)
from core.config import load_settings
from core.llm_review.client import StrataClient
from core.llm_review.crops import (
    context_thumb,
    crop_box_px,
    door_evidence,
    element_crop,
    room_evidence,
    wall_evidence,
)
from core.llm_review.tasks import (
    EFFORT,
    SCHEMAS,
    ReviewItem,
    agree_key,
    load_fewshot,
    load_prompt,
    majority,
    messages_for,
)
from core.spec.models import Spec
from core.spec.store import SpecStore


def render_item(r: dict, specs: dict[int, Spec], inputs, gt: Spec, zoom: float = 1.0) -> ReviewItem:
    """What the harness would send for this item (same crops and evidence as stage 6)."""
    if r["task"] == "T3":
        blind = gt.model_copy(deep=True)  # the GT room without its type and name: no answer leaks
        for room in blind.rooms:
            room.type, room.name = "other", ""
        return ReviewItem("T3", r["element"], room_evidence(blind, r["element"], r["text"]), None, None, r["text"])
    spec, eid = specs[r["candidate"]], r["element"]
    img = element_crop(inputs.page, spec, eid, inputs.to_px, zoom)
    ctx = context_thumb(inputs.page, crop_box_px(spec, eid, inputs.to_px, zoom))
    ev = (wall_evidence(spec, eid, mm_per_px=inputs.mm_per_px, hatch=inputs.hatch, texts=inputs.texts,
                        to_px=inputs.to_px) if r["task"] == "T1" else door_evidence(spec, eid))
    return ReviewItem(r["task"], eid, ev, img, ctx)


def ask_votes(client, render, task: str, fewshot, votes: int, prompt: str, evidence: bool) -> tuple[dict | None, list]:
    """Majority answer over `votes` (vote 1 at temperature 0, zoom 1; then 0.4 and zoom 1.3), as in the harness."""
    answers, calls = [], []
    for vote in range(1, votes + 1):
        if vote == 3 and None not in answers[:2] and agree_key(task, answers[0]) == agree_key(task, answers[1]):
            break
        item = render(1.0 if vote == 1 else 1.3)
        r = client.ask_json(messages_for(item, fewshot, version=prompt, evidence=evidence), SCHEMAS[task],
                            effort=EFFORT[task], temperature=0 if vote == 1 else 0.4)
        calls.append({"latency_ms": r.latency_ms, "valid": r.valid, "raw": r.raw[:400]})
        answers.append(SCHEMAS[task].model_validate(r.parsed) if r.valid else None)
    best = majority(task, answers, min_agree=1 if votes == 1 else 2)
    return (best.model_dump() if best else None), calls


def run_items(task: str, items: list[dict], client, *, prompt: str, votes: int, evidence: bool, fewshot: bool,
              cache: Path) -> tuple[dict, list]:
    rows = [r for r in items if not r["fewshot"]]
    calls_all, answers = [], {}
    if task == "T0":
        for r in rows:
            res = client.ask_json([{"role": "system", "content": load_prompt("T0", prompt)},
                                   {"role": "user", "content": r["prompt"]}], SCHEMAS["T0"], effort=EFFORT["T0"],
                                  temperature=0)
            calls_all.append({"id": r["id"], "latency_ms": res.latency_ms, "valid": res.valid, "raw": res.raw[:400]})
            answers[r["id"]] = {k: v for k, v in res.parsed.items() if v is not None} if res.valid else None
        return answers, calls_all
    from core.llm_review.stage import _inputs

    st = gatsu_stages(cache)
    specs, inputs = candidate_specs(st), _inputs(st)
    gt = Spec.model_validate_json(GT_PATH.read_text())
    shots = load_fewshot(task, FEWSHOT_ROOT) if fewshot else []
    for r in rows:
        ans, calls = ask_votes(client, lambda z, r=r: render_item(r, specs, inputs, gt, z), task, shots, votes, prompt,
                               evidence)
        answers[r["id"]] = ans
        calls_all += [{"id": r["id"], **c} for c in calls]
    return answers, calls_all


def delta_passes(improvement: dict[str, float], need_gain: bool) -> bool:
    """No metric worse (M6: "dengan Strata >= tanpa Strata"); T4 (§7.2) also needs one metric better."""
    ok = all(d >= -1e-9 for d in improvement.values())
    return ok and (not need_gain or any(d > 1e-9 for d in improvement.values()))


def harness_delta(cache: Path, base_tasks: set[str], test_tasks: set[str], client, votes: int, max_iter: int,
                  need_gain: bool = False) -> dict:
    """GT metrics of the Gatsu stage-5 spec reviewed with `base_tasks` vs `test_tasks` (empty set = no Strata)."""
    from core.llm_review.harness import run_review
    from core.llm_review.stage import _inputs

    st = gatsu_stages(cache)
    spec5, inputs = SpecStore(cache / "specs").load("HEAD"), _inputs(st)
    gt = Spec.model_validate_json(GT_PATH.read_text())

    def reviewed(tasks: set[str]) -> tuple[Spec, dict]:
        if not tasks:
            return spec5, {"seconds": 0.0, "accepted": 0}
        t0 = time.monotonic()
        with tempfile.TemporaryDirectory() as tmp:
            r = run_review(spec5, inputs, client, tasks=tasks, votes=votes, max_iter=max_iter,
                           deadline=time.monotonic() + 600, out=Path(tmp), version=spec5.meta.version)
        return r.spec, {"seconds": round(time.monotonic() - t0, 1), "accepted": len(r.ops),
                        "score_before": round(r.score_before, 4), "score_after": round(r.score_after, 4),
                        "timed_out": r.timed_out, "ops": r.ops}

    (bs, binfo), (ts, tinfo) = reviewed(base_tasks), reviewed(test_tasks)
    bm = evaluate(bs, gt) | {"rooms_typed_ok": typed_room_count(bs, gt)}
    tm = evaluate(ts, gt) | {"rooms_typed_ok": typed_room_count(ts, gt)}
    delta = {}
    for k, v in tm.items():
        if k == "passed" or v is None or bm.get(k) is None:
            continue
        delta[k] = round((bm[k] - v) if k in LOWER_IS_BETTER else (v - bm[k]), 4)  # > 0 = better
    return {"base_tasks": sorted(base_tasks), "test_tasks": sorted(test_tasks), "base": binfo, "test": tinfo,
            "base_metrics": {k: v for k, v in bm.items() if k != "passed"},
            "test_metrics": {k: v for k, v in tm.items() if k != "passed"}, "improvement": delta,
            "passes": delta_passes(delta, need_gain)}


def _latency(calls: list) -> dict:
    ms = sorted(c["latency_ms"] for c in calls)
    return {"calls": len(ms), "mean_ms": round(statistics.mean(ms)) if ms else None,
            "p90_ms": ms[min(len(ms) - 1, int(0.9 * len(ms)))] if ms else None}


def markdown(name: str, rep: dict) -> str:
    keys = [k for k in ("n", "accuracy", "baseline_accuracy", "delete_precision", "f1_annotation", "lexicon_fail_rate",
                        "invalid_rate", "passes") if k in rep]
    lines = [f"# Benchmark Strata — {name}", "", (f"Model `{rep.get('model', '?')}`, prompt `{rep.get('prompt')}`, "
             f"votes {rep.get('votes')}, evidence {rep.get('evidence')}, few-shot {rep.get('fewshot')}."), "",
             "| Metrik | Nilai |", "|---|---|"]
    lines += [f"| {k} | {rep[k]:.3f} |" if isinstance(rep[k], float) else f"| {k} | {rep[k]} |" for k in keys]
    for block in ("per_field", "baseline_per_field", "latency", "improvement", "base", "test"):
        if block in rep:
            lines += ["", f"**{block}:** `{json.dumps(rep[block])}`"]
    if "confusion" in rep:
        lines += ["", "Matriks kebingungan (label → jawaban):", "", "```json", json.dumps(rep["confusion"], indent=1), "```"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", required=True, choices=["T0", "T1", "T2", "T3", "T4", "e2e"])
    ap.add_argument("--prompt", default="v1")
    ap.add_argument("--votes", type=int, default=3)
    ap.add_argument("--no-evidence", action="store_true")
    ap.add_argument("--no-fewshot", action="store_true")
    ap.add_argument("--tasks", default="", help="T4/e2e: comma-separated active tasks")
    ap.add_argument("--items", type=Path, default=Path("benchmarks/gatsu/llm_items"))
    ap.add_argument("--out-dir", type=Path, default=Path("benchmarks/reports"))
    ap.add_argument("--cache", type=Path, default=CACHE)
    ap.add_argument("--fake-oracle", action="store_true", help="tests only: answers = labels, Strata is not called")
    a = ap.parse_args(argv)
    s = load_settings()
    client = None if a.fake_oracle else StrataClient.from_settings(s)
    meta = {"model": s.strata_model, "prompt": a.prompt, "votes": a.votes, "evidence": not a.no_evidence,
            "fewshot": not a.no_fewshot}
    if a.task in ("T4", "e2e"):
        tasks = {t for t in a.tasks.split(",") if t}
        base, test = (tasks - {"T4"}, tasks | {"T4"}) if a.task == "T4" else (set(), tasks)
        rep = meta | harness_delta(a.cache, base, test, client, a.votes, s.llm_max_iter, need_gain=a.task == "T4")
        name = f"llm-{a.task}-{a.prompt}-{'-'.join(sorted(tasks)) or 'none'}"
    else:
        items = json.loads((a.items / f"{a.task}.json").read_text())
        if a.fake_oracle:
            answers = {r["id"]: (r["expected"] if a.task == "T0" else r["label"]) for r in items}
            calls = []
        else:
            answers, calls = run_items(a.task, items, client, prompt=a.prompt, votes=a.votes,
                                       evidence=not a.no_evidence, fewshot=not a.no_fewshot, cache=a.cache)
        rep = meta | score_task(a.task, items, answers) | {"latency": _latency(calls)}
        variant = "" if a.task == "T0" else f"-{'ev' if not a.no_evidence else 'noev'}-{'fs' if not a.no_fewshot else 'nofs'}"
        name = f"llm-{a.task}-{a.prompt}{variant}"
        if calls:  # raw answers per item, for reading the confusion matrix
            a.out_dir.mkdir(parents=True, exist_ok=True)
            (a.out_dir / f"{name}.calls.json").write_text(json.dumps({"answers": answers, "calls": calls}, indent=1))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / f"{name}.json").write_text(json.dumps(rep, indent=1, default=str))
    (a.out_dir / f"{name}.md").write_text(markdown(name, rep))
    print(json.dumps({k: rep[k] for k in ("n", "accuracy", "baseline_accuracy", "improvement", "passes") if k in rep}))
    return rep


if __name__ == "__main__":
    main()
