"""Synthetic-plan benchmark (M7b): the Gatsu GT changed at random and drawn in CAD style, stages 0-5 on every
variant, scored against that variant's exact GT. PRD/01 §3: report it; target >= 70% of variants reaching >= 80% of
the NFR targets. s00 is the unchanged GT drawn by the same renderer: s00 against plan.jpeg shows the render style,
s01.. against s00 shows the geometry changes.

Run: uv run --env-file .env python -m benchmarks.run_synth_bench [--n 20] [--variants s00,s03] [--workers 4]
     [--out benchmarks/reports/m7b-synth]
"""

import argparse
import json
import os
import shutil
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from benchmarks.correction_effort import capped_minutes
from benchmarks.extraction_metrics import LOWER_IS_BETTER, THRESHOLDS, evaluate
from benchmarks.llm_items import run_stages
from benchmarks.run_augment_bench import SUMMARY_KEYS, absolute_means, best_shift
from benchmarks.synth.perturb import draw_ops, load_base, no_ops, perturb
from benchmarks.synth.render import render
from core.spec.store import SpecStore

CACHE = Path("benchmarks/.cache/synth")
SHARE, RATE = 0.8, 0.7


def target_pass(metrics: dict, share: float = SHARE) -> tuple[bool, list[str]]:
    """Every summary metric within `share` of its NFR target (a missing one fails)."""
    failed = []
    for k in SUMMARY_KEYS:
        v, limit = metrics.get(k), THRESHOLDS[k]
        bound = round(limit / share if k in LOWER_IS_BETTER else limit * share, 6)  # 0.8 x 0.95 is 0.7600000000000001
        if v is None or (v > bound if k in LOWER_IS_BETTER else v < bound):
            failed.append(k)
    return not failed, failed


def variants(n: int = 20) -> list[dict]:
    base = load_base()
    return [{"id": "s00", "seed": 0, "ops": no_ops(base)}] + \
        [{"id": f"s{i:02d}", "seed": i, "ops": draw_ops(base, np.random.default_rng(i))} for i in range(1, n + 1)]


def score(pred, gt) -> dict:
    """Metrics in the variant's own frame (stage 2 reads it from axis A and the bottom axis, as the GT is drawn).
    best_shift is reported only: a non-zero shift is a finding (a frame or a wall-face error), not a correction."""
    return {"metrics": {k: m for k, m in evaluate(pred, gt).items() if k != "passed"},
            "shift_mm": list(best_shift(pred, gt)),
            "correction_min": capped_minutes(pred, gt), "correction_min_bulk": capped_minutes(pred, gt, bulk=True)}


def run_variant(v: dict, root: Path, stage_overrides: dict | None = None) -> dict:
    """One variant from scratch in root/<id>; a stage that stops the run, or no saved spec, fails the variant."""
    project = root / v["id"]
    shutil.rmtree(project, ignore_errors=True)
    project.mkdir(parents=True)
    t0 = time.monotonic()
    spec, ops = perturb(load_base(), v["seed"], v["ops"])
    img, gt = render(spec, v["seed"])
    data = cv2.imencode(".png", img)[1].tobytes()
    (project / "input.png").write_bytes(data)
    _, results = run_stages(project, data, f"{v['id']}.png", stage_overrides)
    row = {"id": v["id"], "seed": v["seed"], "ops": ops, "passed": False, "reason": None, "failed_metrics": [],
           "metrics": {}, "shift_mm": None, "seconds": None,
           "correction_min": capped_minutes(None, gt), "correction_min_bulk": capped_minutes(None, gt, bulk=True)}
    for d, r in results.items():
        if r.get("status") == "failed" or (r.get("status") == "needs_attention" and d in ("01_preprocess", "02_grid")):
            row["reason"] = f"stage {int(d[:2])} {r['status']}: {r.get('message') or ''}".strip()
            break
    else:
        head = SpecStore(project / "specs").head()
        if head is None:
            row["reason"] = f"stage 5 {results.get('05_validate', {}).get('status')}: no spec saved"
        else:
            row |= score(SpecStore(project / "specs").load(head), gt)
            row["passed"], row["failed_metrics"] = target_pass(row["metrics"])
            if not row["passed"]:
                row["reason"] = "below 80% of target: " + ", ".join(row["failed_metrics"])
    row["seconds"] = round(time.monotonic() - t0, 1)
    return row


def _job(args) -> dict:
    v, root = args
    return run_variant(v, Path(root))


def _fmt(x) -> str:
    return f"{x:.3f}" if isinstance(x, float) else "—" if x is None else str(x)


def _ops(o: dict) -> str:
    parts = ["cermin"] * o["mirror"] + [f"-{o['drop_partitions']} partisi"] * bool(o["drop_partitions"]) + \
        [f"+{o.get('added_partitions', o['add_partitions'])} partisi"] * bool(o.get("added_partitions", o["add_partitions"])) + \
        [f"{o['door_types']} tipe pintu"] * bool(o["door_types"]) + [f"tangga {tuple(o['stair_shift'])}"] * any(o["stair_shift"])
    return ", ".join(["bay " + "/".join(str(b // 1000) for b in o["bays"])] + parts)


def markdown(name: str, rows: list[dict]) -> str:
    rest = [r for r in rows if r["id"] != "s00"]
    rate = sum(r["passed"] for r in rest) / len(rest) if rest else 0.0
    fails = Counter(m for r in rest for m in r["failed_metrics"])
    stops = Counter(r["reason"].split(":")[0] for r in rest if r["reason"] and not r["failed_metrics"])
    verdict = "tercapai" if rate >= RATE else "belum tercapai"
    lines = [f"# Denah sintetis — {name}", "",
             (f"**Lolos: {sum(r['passed'] for r in rest)}/{len(rest)} varian ({rate:.0%}); target ≥ 70 % {verdict}.** "
              "Lolos = setiap metrik ringkasan ≥ 80 % target NFR (≤ ambang / 0.8 untuk metrik lower-is-better); "
              "run yang berhenti gagal. s00 = GT tanpa perubahan, dirender dengan gaya yang sama (pembanding)."), "",
             "**Rata-rata absolut (s01…, run berhenti = nilai terburuk):** "
             + ", ".join(f"{k} {v:.4f}" for k, v in absolute_means(rest).items()), "",
             (f"Metrik yang paling sering gagal: {', '.join(f'{k} ({n})' for k, n in fails.most_common(6)) or '—'}. "
              f"Run yang berhenti: {', '.join(f'{k} ({n})' for k, n in stops.most_common()) or '—'}."), "",
             "| Varian | perubahan | lolos | " + " | ".join(SUMMARY_KEYS)
             + " | koreksi (menit) | koreksi massal (menit) | geser terbaik (mm, diagnostik) | s | alasan |",
             "|" + "---|" * (8 + len(SUMMARY_KEYS))]
    for r in rows:
        m = r["metrics"]
        lines.append(f"| {r['id']} | {_ops(r['ops'])} | {'ya' if r['passed'] else 'tidak'} | "
                     + " | ".join(_fmt(m.get(k)) for k in SUMMARY_KEYS)
                     + f" | {r['correction_min']} | {r['correction_min_bulk']} | {r['shift_mm'] or ''} | {r['seconds']} "
                     f"| {r['reason'] or ''} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> list[dict]:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--variants", default="", help="comma-separated ids (default: all)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--out", type=Path, default=Path("benchmarks/reports/m7b-synth"))
    ap.add_argument("--root", type=Path, default=CACHE)
    a = ap.parse_args(argv)
    wanted = set(filter(None, a.variants.split(",")))
    chosen = [v for v in variants(a.n) if not wanted or v["id"] in wanted]
    a.root.mkdir(parents=True, exist_ok=True)
    os.environ["SWEEP_WORKERS"] = "1"  # variants run in parallel: each sweep stays in its own process
    with ProcessPoolExecutor(max_workers=max(1, a.workers)) as pool:
        rows = list(pool.map(_job, [(v, str(a.root)) for v in chosen]))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.with_suffix(".json").write_text(json.dumps(rows, indent=1))
    a.out.with_suffix(".md").write_text(markdown(a.out.name, rows))
    rest = [r for r in rows if r["id"] != "s00"]
    print(json.dumps({"passed": sum(r["passed"] for r in rest), "of": len(rest), "means": absolute_means(rest)}))
    return rows


if __name__ == "__main__":
    main()
