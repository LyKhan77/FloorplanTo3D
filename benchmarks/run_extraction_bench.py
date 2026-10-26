"""Extraction benchmark CLI: compare a spec (or only a stage-2 grid.json) with the ground truth.

uv run python -m benchmarks.run_extraction_bench --spec spec.json --out benchmarks/reports/extraction
uv run python -m benchmarks.run_extraction_bench --grid grid.json --out benchmarks/reports/m5a-grid
"""

import argparse
import json
from pathlib import Path

from benchmarks.extraction_metrics import (
    THRESHOLDS,
    door_metrics,
    evaluate,
    grid_metrics,
    passed,
    scale_metrics,
    stair_metrics_cmp,
    wall_iou,
    wall_metrics,
)
from core.spec.models import Spec


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.4f}"
    return "—" if v is None else str(v)


def markdown(title: str, m: dict) -> str:
    rows = ["| Metrik | Nilai | Ambang | Lulus |", "|---|---|---|---|"]
    for k, v in m.items():
        if k == "passed":
            continue
        ok = m["passed"].get(k)
        rows.append(f"| {k} | {_fmt(v)} | {_fmt(THRESHOLDS.get(k))} | {'—' if ok is None else '✓' if ok else '✗'} |")
    return f"# {title}\n\n" + "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", type=Path)
    ap.add_argument("--elements", type=Path, help="stage-3 elements.json (needs --grid): walls, doors, stairs, IoU")
    ap.add_argument("--grid", type=Path, help="stage-2 grid.json: scale + grid metrics, or the frame for --elements")
    ap.add_argument("--gt", type=Path, default=Path("benchmarks/gatsu/gt_spec.json"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    gt = Spec.model_validate_json(a.gt.read_text())
    if a.spec:
        m = evaluate(Spec.model_validate_json(a.spec.read_text()), gt)
        title = f"Benchmark ekstraksi: {a.spec.name}"
    elif a.elements:
        if not a.grid:
            ap.error("--elements needs --grid")
        from core.extraction.geometry.elements import elements_to_spec

        g = json.loads(a.grid.read_text())
        pred = elements_to_spec(json.loads(a.elements.read_text()), g)
        m = {**scale_metrics(g["mm_per_px"], gt), **wall_metrics(pred, gt), **door_metrics(pred, gt),
             **stair_metrics_cmp(pred, gt), "wall_iou": wall_iou(pred, gt)}
        m["passed"] = passed(m)
        title = f"Benchmark elemen tahap 3: {a.elements.name}"
    elif a.grid:
        g = json.loads(a.grid.read_text())
        m = {**scale_metrics(g["mm_per_px"], gt), **grid_metrics(g["axes"], gt)}
        m["passed"] = passed(m)
        title = f"Benchmark grid & skala: {a.grid.name}"
    else:
        ap.error("give --spec, --elements with --grid, or --grid")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.with_suffix(".json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    a.out.with_suffix(".md").write_text(markdown(title, m))
    return m


if __name__ == "__main__":
    main()
