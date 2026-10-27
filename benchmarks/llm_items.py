"""LLM benchmark items from the Gatsu ground truth (PRD/05 §7.1), scoring and the §7.2 activation gates.

Run: uv run --env-file .env python -m benchmarks.llm_items --out benchmarks/gatsu/llm_items
Stages 0-5 run once on floorplan/plan.jpeg into benchmarks/.cache/gatsu (deterministic, so element IDs are stable),
then every stage-4 candidate's elements are labelled against benchmarks/gatsu/gt_spec.json.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
from shapely.geometry import Point
from shapely.geometry import Polygon as SPolygon

from benchmarks.extraction_metrics import _nearest, _samples
from core.extraction.params import parse_prompt
from core.extraction.rooms.labels import _letters, levenshtein, match_type
from core.spec.carryover import _door_centre
from core.spec.models import Spec

PLAN = Path("floorplan/plan.jpeg")
GT_PATH = Path("benchmarks/gatsu/gt_spec.json")
CACHE = Path("benchmarks/.cache/gatsu")
FEWSHOT_ROOT = Path("benchmarks/gatsu/fewshot")
WALL_TOL_MM, WALL_ANGLE_DEG = 150, 5  # the rule wall_precision counts with
WALL_YES, WALL_NO = 0.8, 0.1  # centreline share within tolerance: wall / annotation; between: ambiguous
DOOR_MATCH_MM, DOOR_NONE_MM = 300, 1000
FEWSHOT_N = 4
T1_PER_CLASS = 50  # 100 balanced items: above the >= 40 target, and one variant runs in minutes, not an hour
T2_MAX_NEGATIVES = 20  # CV doors far from any GT door; the hinge/swing gate only reads the true doors
NAME_MATCH = 0.4  # a T3 label belongs to its GT room when within 40% edits of the room name (or contained)
T0_FIELDS = ("wall_height", "door_height", "wall_thickness", "floor_name", "site_type")


# --- the Gatsu run ------------------------------------------------------------------------------------------------

def gatsu_stages(cache: Path = CACHE) -> Path:
    """Stages folder of a stage 0-5 run of plan.jpeg; runs the stages only when the cache is missing."""
    from core.extraction.stages import (
        stage_extract,
        stage_grid,
        stage_input,
        stage_preprocess,
        stage_rooms,
        stage_validate,
    )

    st = cache / "runs" / "r" / "stages"
    if (st / "05_validate" / "chosen.json").exists():
        return st
    data = PLAN.read_bytes()
    (cache / "input").mkdir(parents=True, exist_ok=True)
    (cache / "input" / "original.jpg").write_bytes(data)
    (cache / "input" / "input.json").write_text(json.dumps({
        "filename": PLAN.name, "sha256": hashlib.sha256(data).hexdigest(), "prompt": "", "params": {}, "page": None,
        "type": "jpg"}))
    steps = [("00_input", stage_input), ("01_preprocess", stage_preprocess), ("02_grid", stage_grid),
             ("03_extract", lambda p, w: stage_extract(p, w, 12)), ("04_rooms", stage_rooms),
             ("05_validate", lambda p, w: stage_validate(p, w, "r"))]
    for d, fn in steps:
        fn(cache, st / d)
    return st


def candidate_specs(st: Path) -> dict[int, Spec]:
    rows = json.loads((st / "04_rooms" / "candidates.json").read_text())
    return {r["index"]: Spec.model_validate_json((st / "04_rooms" / "candidates" / str(r["index"]) / "spec.json").read_text())
            for r in rows if not r["error"]}


# --- item builders ------------------------------------------------------------------------------------------------

def typo_variants(text: str) -> list[str]:
    """Deterministic OCR-like typos: drop the middle letter, swap it with the one before, first O->0 (else I->1)."""
    m = len(text) // 2
    out = [text[:m] + text[m + 1:], text[:m - 1] + text[m] + text[m - 1] + text[m + 1:] if m >= 1 else text]
    for a, b in (("O", "0"), ("I", "1")):
        if a in text:
            out.append(text.replace(a, b, 1))
            break
    return [v for v in dict.fromkeys(out) if v != text]


def _wall_share(w, gt: Spec) -> float:
    pts, lens, angs = _samples([w])
    if not len(pts):
        return 0.0
    d = _nearest(pts, angs, gt.walls, WALL_ANGLE_DEG)
    return float(lens[d <= WALL_TOL_MM].sum() / lens.sum())


def _spread(rows: list, n: int) -> list:
    """n rows evenly spaced through `rows` (deterministic subsample)."""
    if n >= len(rows):
        return rows
    return [rows[math.floor(i * len(rows) / n)] for i in range(n)]


def _t1(specs: dict[int, Spec], gt: Spec, balance: bool) -> list[dict]:
    kept: list[tuple[tuple[float, float], float, dict]] = []
    for k in sorted(specs):
        for w in specs[k].walls:
            share = _wall_share(w, gt)
            verdict = "wall" if share >= WALL_YES else "annotation" if share <= WALL_NO else None
            if verdict is None:
                continue
            centre, length = ((w.a[0] + w.b[0]) / 2, (w.a[1] + w.b[1]) / 2), math.dist(w.a, w.b)
            if any(math.dist(centre, c) <= 100 and abs(length / max(L, 1) - 1) <= 0.1 for c, L, _ in kept):
                continue  # the same line found by another candidate
            kept.append((centre, length, {
                "task": "T1", "candidate": k, "element": w.id, "label": {"verdict": verdict},
                "baseline": {"verdict": "wall" if w.provenance.confidence >= 0.5 else "annotation"},
                "pair_overlap": w.provenance.evidence.get("pair_overlap") or 0, "fewshot": False}))
    rows = [r for _, _, r in kept]
    if balance:
        walls = [r for r in rows if r["label"]["verdict"] == "wall"]
        notes = [r for r in rows if r["label"]["verdict"] == "annotation"]
        n = min(len(walls), len(notes), T1_PER_CLASS)
        rows = _spread(walls, n) + _spread(notes, n)
    return rows


def _t2(specs: dict[int, Spec], gt: Spec) -> list[dict]:
    gt_doors = [(o, _door_centre(gt, o)) for o in gt.openings if o.category == "door"]
    seen_gt, negatives, rows = set(), [], []
    for k in sorted(specs):
        s = specs[k]
        for o in (o for o in s.openings if o.category == "door"):
            c = _door_centre(s, o)
            if c is None:
                continue
            dists = sorted((math.dist(c, gc), g.id, g) for g, gc in gt_doors if gc is not None)
            base = {"is_door": True, "door_type": o.door_type, "hinge": o.hinge, "swing": o.swing}
            row = {"task": "T2", "candidate": k, "element": o.id, "baseline": base, "fewshot": False}
            if dists and dists[0][0] <= DOOR_MATCH_MM:
                g = dists[0][2]
                if g.id in seen_gt:
                    continue
                seen_gt.add(g.id)
                rows.append(row | {"label": {"is_door": True, "door_type": g.door_type, "hinge": g.hinge, "swing": g.swing}})
            elif not dists or dists[0][0] > DOOR_NONE_MM:
                if all(math.dist(c, nc) > 100 for nc in negatives):
                    negatives.append(c)
                    rows.append(row | {"label": {"is_door": False, "door_type": None, "hinge": None, "swing": None}})
    positives = [r for r in rows if r["label"]["is_door"]]
    return positives + _spread([r for r in rows if not r["label"]["is_door"]], T2_MAX_NEGATIVES)


def _names_room(text: str, name: str) -> bool:
    t, n = _letters(text), _letters(name)
    return bool(t and n) and (t in n or n in t or levenshtein(t, n) <= NAME_MATCH * max(len(t), len(n)))


def _t3(gt: Spec, labels: list[tuple[str, tuple[float, float]]]) -> list[dict]:
    rows, seen = [], set()
    for text, at in labels:
        room = next((r for r in gt.rooms if r.type != "other" and SPolygon(r.polygon, r.holes).covers(Point(at))), None)
        if room is None or text in seen or not _names_room(text, room.name):
            continue
        seen.add(text)
        for variant, synthetic in [(text, False), *((v, True) for v in typo_variants(text))]:
            rows.append({"task": "T3", "room": room.id, "element": room.id, "text": variant, "synthetic": synthetic,
                         "label": {"type": room.type}, "baseline": {"type": match_type(variant)[0]}, "fewshot": False})
    return rows


def _pick_fewshot(rows: list[dict], wanted: list) -> None:
    """Mark up to FEWSHOT_N rows (never more than a quarter of them) as few-shot: one row per wanted predicate
    in order, then the next unused rows."""
    n = min(FEWSHOT_N, len(rows) // 4)
    chosen: list[int] = []
    for pred in wanted:
        i = next((i for i, r in enumerate(rows) if i not in chosen and pred(r)), None)
        if i is not None and len(chosen) < n:
            chosen.append(i)
    chosen += [i for i in range(len(rows)) if i not in chosen][:n - len(chosen)]
    for i in chosen:
        rows[i]["fewshot"] = True


def build_items_from_specs(specs: dict[int, Spec], gt: Spec, labels: list[tuple[str, tuple[float, float]]],
                           balance: bool = True) -> dict[str, list[dict]]:
    out = {"T1": _t1(specs, gt, balance), "T2": _t2(specs, gt), "T3": _t3(gt, labels)}
    _pick_fewshot(out["T1"], [lambda r: r["label"]["verdict"] == "wall", lambda r: r["label"]["verdict"] == "annotation",
                              lambda r: r["label"]["verdict"] == "annotation" and r["pair_overlap"] > 0,
                              lambda r: r["label"]["verdict"] == "wall" and r["baseline"]["verdict"] == "annotation"])
    _pick_fewshot(out["T2"], [lambda r: r["label"]["is_door"], lambda r: not r["label"]["is_door"],
                              lambda r: r["label"]["hinge"] == "end", lambda r: r["label"]["door_type"] == "double_swing"])
    _pick_fewshot(out["T3"], [lambda r: not r["synthetic"], lambda r: r["synthetic"],
                              lambda r: r["baseline"]["type"] != r["label"]["type"], lambda r: r["synthetic"]])
    for task, rows in out.items():
        for i, r in enumerate(rows):
            r["id"] = f"{task}-{i + 1:03d}"
    return out


def build_items(st: Path, gt: Spec) -> dict[str, list[dict]]:
    from core.extraction.rooms.labels import labels_from_ocr

    grid = json.loads((st / "02_grid" / "grid.json").read_text())
    ocr = json.loads((st / "02_grid" / "ocr.json").read_text())
    labels = [(lb.name, tuple(lb.at)) for lb in labels_from_ocr(ocr, grid["px_to_mm"])]
    return build_items_from_specs(candidate_specs(st), gt, labels)


def evaluation(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not r["fewshot"]]


# --- scoring (PRD/05 §7.2) ----------------------------------------------------------------------------------------

def _acc(hits: list[bool]) -> float:
    return sum(hits) / len(hits) if hits else 0.0


def _confusion(rows, answers, field) -> dict:
    out: dict = {}
    for r in rows:
        a = answers.get(r["id"])
        pred = "invalid" if a is None else str(a.get(field))
        out.setdefault(str(r["label"][field]), {}).setdefault(pred, 0)
        out[str(r["label"][field])][pred] += 1
    return out


def score_task(task: str, items: list[dict], answers: dict[str, dict | None]) -> dict:
    rows = evaluation(items)
    get = lambda r: answers.get(r["id"]) or {}
    rep = {"task": task, "n": len(rows), "invalid_rate": _acc([answers.get(r["id"]) is None for r in rows])}
    if task == "T1":
        hit = [get(r).get("verdict") == r["label"]["verdict"] for r in rows]
        deletes = [r for r in rows if get(r).get("verdict") == "annotation"]
        notes = [r for r in rows if r["label"]["verdict"] == "annotation"]
        precision = _acc([r["label"]["verdict"] == "annotation" for r in deletes]) if deletes else None
        recall = _acc([get(r).get("verdict") == "annotation" for r in notes]) if notes else 0.0
        rep |= {"accuracy": _acc(hit), "baseline_accuracy": _acc([r["baseline"] == r["label"] for r in rows]),
                "delete_precision": precision,
                "f1_annotation": 2 * precision * recall / (precision + recall) if precision and recall else 0.0,
                "confusion": _confusion(rows, answers, "verdict")}
        rep["passes"] = bool(rep["accuracy"] >= rep["baseline_accuracy"] + 0.05 and precision is not None
                             and precision >= 0.90)
    elif task == "T2":
        fields = ("door_type", "hinge", "swing")
        doors = [r for r in rows if r["label"]["is_door"]]
        rep["per_field"] = {"is_door": _acc([get(r).get("is_door") == r["label"]["is_door"] for r in rows]),
                            **{f: _acc([get(r).get(f) == r["label"][f] for r in doors]) for f in fields}}
        rep["baseline_per_field"] = {"is_door": _acc([r["baseline"]["is_door"] == r["label"]["is_door"] for r in rows]),
                                     **{f: _acc([r["baseline"][f] == r["label"][f] for r in doors]) for f in fields}}
        rep["accuracy"] = _acc([all(get(r).get(f) == r["label"][f] for f in ("is_door", *fields)) for r in rows])
        rep["baseline_accuracy"] = _acc([r["baseline"] == r["label"] for r in rows])
        rep["confusion"] = {f: _confusion(doors, answers, f) for f in ("hinge", "swing")}
        pf, bf = rep["per_field"], rep["baseline_per_field"]
        rep["passes"] = bool(doors and pf["hinge"] >= bf["hinge"] + 0.10 and pf["swing"] >= bf["swing"] + 0.10)
    elif task == "T3":
        rep["accuracy"] = _acc([get(r).get("type") == r["label"]["type"] for r in rows])
        rep["baseline_accuracy"] = _acc([r["baseline"]["type"] == r["label"]["type"] for r in rows])
        rep["lexicon_fail_rate"] = 1 - rep["baseline_accuracy"] if rows else 0.0
        rep["confusion"] = _confusion(rows, answers, "type")
        rep["passes"] = bool(rows and (rep["accuracy"] >= rep["baseline_accuracy"] + 0.05 or (
            rep["lexicon_fail_rate"] >= 0.20 and rep["accuracy"] >= rep["baseline_accuracy"])))
    else:  # T0: Strata only fills the fields the rule parser left empty
        merged, rule = [], []
        for r in rows:
            parsed = parse_prompt(r["prompt"])
            full = {**get(r), **parsed}
            for f in T0_FIELDS:
                merged.append(full.get(f) == r["expected"].get(f))
                rule.append(parsed.get(f) == r["expected"].get(f))
        rep |= {"accuracy": _acc(merged), "baseline_accuracy": _acc(rule)}
        rep["passes"] = bool(rows and rep["accuracy"] >= rep["baseline_accuracy"] + 0.05)
    return rep


# --- few-shot files -----------------------------------------------------------------------------------------------

def write_fewshot(st: Path, items: dict[str, list[dict]], gt: Spec, root: Path = FEWSHOT_ROOT) -> None:
    """benchmarks/gatsu/fewshot/<task>/items.json + crops, in the format core.llm_review.tasks.load_fewshot reads."""
    from benchmarks.run_llm_bench import render_item
    from core.llm_review.stage import _inputs

    specs, inputs = candidate_specs(st), _inputs(st)
    for task, rows in items.items():
        d = root / task
        d.mkdir(parents=True, exist_ok=True)
        out = []
        for r in (r for r in rows if r["fewshot"]):
            item = render_item(r, specs, inputs, gt, zoom=1.0)
            img = ctx = None
            if item.image is not None:
                img, ctx = f"{r['id']}.png", f"{r['id']}_ctx.png"
                cv2.imwrite(str(d / img), item.image)
                cv2.imwrite(str(d / ctx), item.context)
            out.append({"element": item.element, "evidence": item.evidence, "label": item.label,
                        "answer": {"id": item.element, **r["label"]} if task != "T3" else
                        {"id": item.element, "type": r["label"]["type"], "name_normalized": r["text"].upper()},
                        "image": img, "context": ctx})
        (d / "items.json").write_text(json.dumps(out, indent=1))


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("benchmarks/gatsu/llm_items"))
    ap.add_argument("--cache", type=Path, default=CACHE)
    a = ap.parse_args(argv)
    st = gatsu_stages(a.cache)
    gt = Spec.model_validate_json(GT_PATH.read_text())
    items = build_items(st, gt)
    a.out.mkdir(parents=True, exist_ok=True)
    for task, rows in items.items():
        (a.out / f"{task}.json").write_text(json.dumps(rows, indent=1))
    write_fewshot(st, items, gt)
    counts = {t: {"eval": len(evaluation(r)), "fewshot": sum(x["fewshot"] for x in r)} for t, r in items.items()}
    print(json.dumps(counts))
    return counts


if __name__ == "__main__":
    main()
