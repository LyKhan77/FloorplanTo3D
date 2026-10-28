"""Augmentation benchmark (M7a): stages 0-5 on every variant of plan.jpeg, scored against the Gatsu GT and judged
relative to the unaltered drawing (a00): a variant passes when every metric is >= 0.9 x a00's (<= a00's / 0.9 for
lower-is-better metrics). User decision 2026-10-28: robustness is relative; absolute NFR accuracy is the
extractor work's target.

Run: uv run --env-file .env python -m benchmarks.run_augment_bench [--variants a00,a05] [--workers 4]
     [--out benchmarks/reports/m7a-augment-<name>] [--fresh]
"""

import argparse
import json
import os
import shutil
import subprocess
import time
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from benchmarks.augment.variants import IDENTITY, VARIANTS, render_variant
from benchmarks.correction_effort import capped_minutes
from benchmarks.extraction_metrics import LOWER_IS_BETTER, THRESHOLDS, evaluate
from benchmarks.llm_items import GT_PATH, PLAN, run_stages
from core.spec.models import Spec
from core.spec.store import SpecStore

CACHE = Path("benchmarks/.cache/augment")
REL = 0.9
SUMMARY_KEYS = ("wall_recall", "wall_precision", "wall_iou", "door_recall", "room_match", "gross_area_err")


def relative_pass(metrics: dict, base: dict) -> tuple[bool, list[str]]:
    """Every THRESHOLDS metric the base has within REL of it; a base of 0 cannot be compared and is skipped."""
    failed = []
    for k in THRESHOLDS:
        b = base.get(k)
        if b is None or b == 0:
            continue
        v = metrics.get(k)
        if v is None or (v > b / REL if k in LOWER_IS_BETTER else v < REL * b):
            failed.append(k)
    return not failed, sorted(failed)


ALIGN_RES_MM, ALIGN_MAX_MM = 50, 3000


def gt_for(v: dict) -> Spec:
    """The Gatsu GT as seen through variant v: same mm geometry, mm per original px scaled with the image."""
    gt = Spec.model_validate_json(GT_PATH.read_text())
    gt.meta.mm_per_px = gt.meta.mm_per_px / v["scale"]
    return gt


def translate(spec: Spec, dx: float, dy: float) -> Spec:
    """The spec moved by (dx, dy) mm: every absolute coordinate (openings are relative to their wall)."""
    s = spec.model_copy(deep=True)
    mv = lambda p: (round(p[0] + dx), round(p[1] + dy))
    for w in s.walls:
        w.a, w.b = mv(w.a), mv(w.b)
    for c in s.columns:
        c.center = mv(c.center)
    for r in s.rooms:
        r.polygon, r.holes = [mv(p) for p in r.polygon], [[mv(p) for p in h] for h in r.holes]
        r.label_pos = mv(r.label_pos) if r.label_pos else None
    for st in s.stairs:
        for f in st.flights:
            f.start, f.end = mv(f.start), mv(f.end)
        st.landings = [[mv(p) for p in poly] for poly in st.landings]
    for o in s.objects:
        o.position = (*mv(o.position[:2]), o.position[2])
    s.meta.building_outline = [[mv(p) for p in poly] for poly in s.meta.building_outline]
    for a in s.grid.axes:
        a.offset = round(a.offset + (dx if a.orientation == "vertical" else dy))
    return s


def _raster(spec: Spec, x0: float, y1: float, w: int, h: int) -> np.ndarray:
    img = np.zeros((h, w), np.float32)
    px = lambda p: (int((p[0] - x0) / ALIGN_RES_MM), int((y1 - p[1]) / ALIGN_RES_MM))
    for wall in spec.walls:
        cv2.line(img, px(wall.a), px(wall.b), 1.0, 3)
    return img


def best_shift(pred: Spec, gt: Spec) -> tuple[int, int]:
    """Translation (mm) that lays pred's walls on gt's, by phase correlation of the two wall rasters; (0, 0) when
    the estimate is beyond +-3 m (no overlap to align on). The frame origin is a stage-2 choice (which axis was
    read first), not an accuracy the benchmark scores."""
    xs = [p[0] for w in gt.walls for p in (w.a, w.b)]
    ys = [p[1] for w in gt.walls for p in (w.a, w.b)]
    if not xs or not pred.walls:
        return 0, 0
    x0, y1 = min(xs) - ALIGN_MAX_MM, max(ys) + ALIGN_MAX_MM
    w = int((max(xs) + ALIGN_MAX_MM - x0) / ALIGN_RES_MM) + 1
    h = int((y1 - (min(ys) - ALIGN_MAX_MM)) / ALIGN_RES_MM) + 1
    (sx, sy), _ = cv2.phaseCorrelate(_raster(gt, x0, y1, w, h), _raster(pred, x0, y1, w, h))
    dx, dy = -sx * ALIGN_RES_MM, sy * ALIGN_RES_MM  # raster y grows downwards, mm y upwards
    if abs(dx) > ALIGN_MAX_MM or abs(dy) > ALIGN_MAX_MM:
        return 0, 0
    # under one raster cell is sub-pixel noise of the correlation, far inside the 150 mm metric tolerance
    snap = lambda v: 0 if abs(v) < ALIGN_RES_MM else round(v / ALIGN_RES_MM) * ALIGN_RES_MM
    return snap(dx), snap(dy)


def _code() -> str:
    """HEAD plus a hash of uncommitted core/ changes, so a cached row never outlives the code that made it."""
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)
    diff = subprocess.run(["git", "diff", "HEAD", "--", "core"], capture_output=True, check=False).stdout
    return (head.stdout.strip() or "unknown") + (f"+{zlib.crc32(diff):08x}" if diff else "")


def run_variant(v: dict, root: Path, base: dict | None, stage_overrides: dict | None = None) -> dict:
    """One variant from scratch in root/<id>; a stage that stops the run, or no saved spec, fails the variant."""
    project = root / v["id"]
    shutil.rmtree(project, ignore_errors=True)
    t0 = time.monotonic()
    img = render_variant(cv2.imread(str(PLAN), cv2.IMREAD_COLOR), v)
    data = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 100])[1].tobytes()
    _, results = run_stages(project, data, f"{v['id']}.jpg", stage_overrides)
    row = {"id": v["id"], "variant": v, "passed": False, "reason": None, "failed_metrics": [], "metrics": {},
           "seconds": round(time.monotonic() - t0, 1), "code": _code(),
           "correction_min": capped_minutes(None, gt_for(v))}  # stopped: a full redraw
    for d, r in results.items():
        if r.get("status") == "failed" or (r.get("status") == "needs_attention" and d in ("01_preprocess", "02_grid")):
            row["reason"] = f"stage {int(d[:2])} {r['status']}: {r.get('message') or ''}".strip()
            return row
    head = SpecStore(project / "specs").head()
    if head is None:
        row["reason"] = f"stage 5 {results.get('05_validate', {}).get('status')}: no spec saved"
        return row
    gt = gt_for(v)
    pred = SpecStore(project / "specs").load(head)
    dx, dy = best_shift(pred, gt)
    row["shift_mm"] = [dx, dy]
    aligned = translate(pred, dx, dy)
    row["metrics"] = {k: v for k, v in evaluate(aligned, gt).items() if k != "passed"}
    row["correction_min"] = capped_minutes(aligned, gt)
    if base is None:
        row["passed"] = True
    else:
        row["passed"], row["failed_metrics"] = relative_pass(row["metrics"], base)
        if not row["passed"]:
            row["reason"] = "metrics below 0.9 x a00: " + ", ".join(row["failed_metrics"])
    return row


def _cached(v: dict, root: Path, code: str) -> dict | None:
    f = root / v["id"] / "row.json"
    if f.exists():
        row = json.loads(f.read_text())
        if row.get("code") == code and row.get("variant") == v:
            return row
    return None


def _job(args) -> dict:
    v, root, base = args
    row = run_variant(v, Path(root), base)
    (Path(root) / v["id"] / "row.json").write_text(json.dumps(row, indent=1))
    return row


def robustness_score(rows: list[dict]) -> float:
    """Mean over variants (not a00) of the share of comparable metrics within 0.9 x a00; a stopped run scores 0.
    A gate that moves with partial gains, where the all-metrics pass rate stays at 0."""
    rest = [r for r in rows if r["id"] != "a00"]
    if not rest:
        return 0.0
    base = next((r["metrics"] for r in rows if r["id"] == "a00"), {})
    n = sum(1 for k in THRESHOLDS if base.get(k))
    return sum((1 - len(r["failed_metrics"]) / n) if r["metrics"] and n else 0.0 for r in rest) / len(rest)


MEAN_KEYS = ("wall_recall", "wall_precision", "wall_iou", "door_recall", "room_match", "gross_area_err")


def absolute_means(rows: list[dict]) -> dict[str, float]:
    """Mean of each metric over all variants (a00 included); a stopped run counts as the worst value (0, or 1 for
    gross_area_err). The M7a gate: unlike the relative score, it does not penalise a better a00."""
    out = {}
    for k in MEAN_KEYS:
        worst = 1.0 if k in LOWER_IS_BETTER else 0.0
        vals = [r["metrics"][k] if r["metrics"] and r["metrics"].get(k) is not None else worst for r in rows]
        out[k] = round(sum(vals) / len(vals), 4) if vals else worst
    minutes = [r["correction_min"] for r in rows if r.get("correction_min") is not None]
    if minutes:
        out["correction_min"] = round(sum(minutes) / len(minutes), 1)
    return out


def _factor(v: dict) -> str:
    diff = [k for k in ("scale", "jpeg_q", "rotate_deg", "margin_px", "blur", "noise") if v[k] != IDENTITY[k]]
    return f"{diff[0]}={v[diff[0]]}" if len(diff) == 1 else "kombinasi" if diff else "identitas"


def _fmt(x) -> str:
    return f"{x:.3f}" if isinstance(x, float) else "—" if x is None else str(x)


def markdown(name: str, rows: list[dict]) -> str:
    rest = [r for r in rows if r["id"] != "a00"]
    rate = sum(r["passed"] for r in rest) / len(rest) if rest else 0.0
    fails = Counter(m for r in rest for m in r["failed_metrics"])
    stops = Counter(r["reason"].split(":")[0] for r in rest if r["reason"] and not r["failed_metrics"])
    lines = [f"# Set augmentasi — {name}", "", (f"**Skor ketahanan: {robustness_score(rows):.3f}** (rata-rata porsi metrik "
             "yang ≥ 0.9 × a00 per varian; run yang berhenti = 0)."), "",
             "**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** "
             + ", ".join(f"{k} {v:.4f}" for k, v in absolute_means(rows).items()), "",
             (f"**Lolos: {sum(r['passed'] for r in rest)}/{len(rest)} varian ({rate:.0%})** (a00 = gambar asli, pembanding; "
             "lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better)."), "",
             (f"Metrik yang paling sering gagal: {', '.join(f'{k} ({n})' for k, n in fails.most_common(6)) or '—'}. "
             f"Run yang berhenti: {', '.join(f'{k} ({n})' for k, n in stops.most_common()) or '—'}."), "",
             "| Varian | faktor | lolos | " + " | ".join(SUMMARY_KEYS) + " | koreksi (menit) | geser (mm) | s | alasan |",
             "|" + "---|" * (7 + len(SUMMARY_KEYS))]
    for r in rows:
        v, m = r["variant"], r["metrics"]
        lines.append(f"| {r['id']} | {_factor(v)} | {'ya' if r['passed'] else 'tidak'} | "
                     + " | ".join(_fmt(m.get(k)) for k in SUMMARY_KEYS)
                     + f" | {r.get('correction_min', '—')} | {r.get('shift_mm') or ''} | {r['seconds']} | {r['reason'] or ''} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> list[dict]:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--variants", default="", help="comma-separated ids (default: all)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--out", type=Path, default=Path("benchmarks/reports/m7a-augment"))
    ap.add_argument("--root", type=Path, default=CACHE)
    ap.add_argument("--fresh", action="store_true", help="ignore cached rows")
    a = ap.parse_args(argv)
    wanted = set(filter(None, a.variants.split(",")))
    chosen = [v for v in VARIANTS if not wanted or v["id"] in wanted or v["id"] == "a00"]
    code = _code()
    a.root.mkdir(parents=True, exist_ok=True)
    os.environ["SWEEP_WORKERS"] = "1"  # variants run in parallel: each sweep stays in its own process
    base_row = (not a.fresh and _cached(chosen[0], a.root, code)) or _job((chosen[0], str(a.root), None))
    rows = {"a00": base_row}
    todo = []
    for v in chosen[1:]:
        hit = None if a.fresh else _cached(v, a.root, code)
        if hit:  # same code and variant: a00 is the same too, so the verdict stands
            rows[v["id"]] = hit
        else:
            todo.append((v, str(a.root), base_row["metrics"]))
    if todo:
        with ProcessPoolExecutor(max_workers=max(1, a.workers)) as pool:
            for row in pool.map(_job, todo):
                rows[row["id"]] = row
    ordered = [rows[v["id"]] for v in chosen]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.with_suffix(".json").write_text(json.dumps(ordered, indent=1))
    a.out.with_suffix(".md").write_text(markdown(a.out.name, ordered))
    rest = [r for r in ordered if r["id"] != "a00"]
    print(json.dumps({"passed": sum(r["passed"] for r in rest), "of": len(rest),
                      "score": round(robustness_score(ordered), 3), "means": absolute_means(ordered)}))
    return ordered


if __name__ == "__main__":
    main()
