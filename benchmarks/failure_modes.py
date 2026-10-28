"""Attribute the Gatsu extraction errors to failure modes (M7a): which GT walls are missed and why, where the false
walls sit, and which GT rooms are not formed.

Run: uv run --env-file .env python -m benchmarks.failure_modes --out benchmarks/reports/m7a-baseline
Writes <out>.md, <out>.json and <out>.png (missed magenta, false red, found green, GT outdoor rooms blue).
"""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import LineString, Point
from shapely.geometry import Polygon as SPolygon

from benchmarks.extraction_metrics import _nearest, _samples, evaluate
from core.spec.derive import endpoint_connected
from core.spec.models import Spec, Wall

INKED = 0.6  # share of samples on ink for a face line to count as drawn
REGION_SHARE = 0.3
TEXT_NEAR_MM = 600


def wall_coverage(w: Wall, ref: list[Wall], tol_mm: float = 150, angle_deg: float = 5) -> float:
    """Share of `w`'s centreline within tol of a parallel wall in `ref` (the wall_metrics rule)."""
    pts, lens, angs = _samples([w])
    if not len(pts) or not ref:
        return 0.0
    d = _nearest(pts, angs, ref, angle_deg)
    return float(lens[d <= tol_mm].sum() / lens.sum())


def _points(w: Wall, offset_mm: float, n: int = 40):
    (ax, ay), (bx, by) = w.a, w.b
    length = math.dist(w.a, w.b) or 1.0
    nx, ny = -(by - ay) / length, (bx - ax) / length
    for t in np.linspace(0.05, 0.95, n):
        yield ax + (bx - ax) * t + nx * offset_mm, ay + (by - ay) * t + ny * offset_mm


def _share(img: np.ndarray, pts_mm, to_px, window: int = 1) -> float:
    h, w = img.shape[:2]
    pts = list(pts_mm)
    hits = 0
    for x, y in pts:
        px, py = (round(v) for v in to_px(x, y))
        win = img[max(0, py - window):min(h, py + window + 1), max(0, px - window):min(w, px + window + 1)]
        hits += bool(win.size) and bool((win > 0).any())
    return hits / len(pts) if pts else 0.0


def ink_profile(img: np.ndarray, w: Wall, to_px, offsets_mm: tuple[float, ...]) -> tuple[float, ...]:
    """Share of 40 samples (5-95% of the length) on ink within a 3x3 window, per normal offset."""
    return tuple(_share(img, _points(w, off), to_px) for off in offsets_mm)


def classify_missed(gt: Spec, pred: Spec, binary: np.ndarray, clean: np.ndarray, to_px) -> list[dict]:
    """GT walls the prediction covers < 50%, with the reason: single (one face drawn), double (both faces after
    masking: a pairing failure), erased (drawn, but gone after masking), faint (not drawn enough)."""
    out = []
    for g in gt.walls:
        if wall_coverage(g, pred.walls) >= 0.5:
            continue
        offs = (-g.thickness / 2, 0.0, g.thickness / 2)
        b, c = ink_profile(binary, g, to_px, offs), ink_profile(clean, g, to_px, offs)
        if max(b) >= INKED and max(c) < INKED:
            mode = "erased"
        elif min(c[0], c[2]) >= INKED:
            mode = "double"
        elif max(c) >= INKED:
            mode = "single"
        else:
            mode = "faint"
        out.append({"id": g.id, "kind": g.kind, "thickness": g.thickness, "length_mm": round(math.dist(g.a, g.b)),
                    "mode": mode, "ink_binary": [round(v, 2) for v in b], "ink_clean": [round(v, 2) for v in c]})
    return out


def classify_false(pred: Spec, gt: Spec, masks: dict, texts_mm: list[dict], to_px) -> list[dict]:
    """Predicted walls GT covers < 50%, by the first region that applies: hatch, symbol, text (an annotation within
    600 mm), stair, free_end (neither end joins a wall or column), other."""
    out = []
    for w in pred.walls:
        if wall_coverage(w, gt.walls) >= 0.5:
            continue
        centre = list(_points(w, 0.0))
        line = LineString([w.a, w.b])
        if _share(masks["hatch"], centre, to_px, 0) >= REGION_SHARE:
            region = "hatch"
        elif _share(masks["symbol"], centre, to_px, 0) >= REGION_SHARE:
            region = "symbol"
        elif any(line.distance(Point(t["at_mm"])) <= TEXT_NEAR_MM for t in texts_mm):
            region = "text"
        elif masks.get("stair") is not None and _share(masks["stair"], centre, to_px, 0) >= REGION_SHARE:
            region = "stair"
        elif not endpoint_connected(pred, w, "a") and not endpoint_connected(pred, w, "b"):
            region = "free_end"
        else:
            region = "other"
        out.append({"id": w.id, "length_mm": round(line.length), "confidence": round(w.provenance.confidence, 2),
                    "region": region})
    return out


def _shape(r) -> SPolygon:
    return SPolygon(r.polygon, r.holes)


def classify_rooms(gt: Spec, pred: Spec) -> dict:
    """GT rooms matched by a predicted room (IoU >= 0.5), split inner/outdoor, and predicted rooms that swallow
    two or more GT rooms (each covered >= 50%): rooms that leaked into each other."""
    shapes = [(p.id, _shape(p)) for p in pred.rooms]

    def matched(g) -> bool:
        gs = _shape(g)
        for _, ps in shapes:
            inter = gs.intersection(ps).area
            if inter and inter / gs.union(ps).area >= 0.5:
                return True
        return False

    inner = [g for g in gt.rooms if g.type != "outdoor"]
    outdoor = [g for g in gt.rooms if g.type == "outdoor"]
    merged = []
    for _, ps in shapes:
        covered = sorted(g.id for g in gt.rooms if _shape(g).area and _shape(g).intersection(ps).area >= 0.5 * _shape(g).area)
        if len(covered) >= 2:
            merged.append(covered)
    return {"inner_gt": len(inner), "inner_matched": sum(map(matched, inner)), "outdoor_gt": len(outdoor),
            "outdoor_matched": sum(map(matched, outdoor)), "merged": merged}


# --- Gatsu run ----------------------------------------------------------------------------------------------------

def _gatsu_inputs(cache: Path | None = None):
    from benchmarks.llm_items import CACHE, GT_PATH, gatsu_stages
    from core.extraction.geometry.masks import build_masks
    from core.extraction.preprocess import binarize
    from core.extraction.rooms.overlay import px_from_mm
    from core.spec.store import SpecStore

    run_dir = cache or CACHE
    st = gatsu_stages(run_dir)
    grid = json.loads((st / "02_grid" / "grid.json").read_text())
    meta = json.loads((st / "01_preprocess" / "meta.json").read_text())
    ocr = json.loads((st / "02_grid" / "ocr.json").read_text())
    params = json.loads((st / "05_validate" / "chosen.json").read_text())["params"] or {}
    page = cv2.imread(str(st / "01_preprocess" / "page.png"), cv2.IMREAD_GRAYSCALE)
    binary = cv2.imread(str(st / "01_preprocess" / "bin.png"), cv2.IMREAD_GRAYSCALE)
    k = params.get("sauvola_k", 0.2)
    if k != 0.2:  # the same binarisation stage 3 used for the chosen candidate
        binary = binarize(page, k=k, window=25 * meta["upscale"])
    colour = cv2.imread(str(st / "01_preprocess" / "colour.png"), cv2.IMREAD_GRAYSCALE)
    m = build_masks(binary, colour, ocr, meta["drawing_bbox"], grid["mm_per_px_work"], grid.get("axes", []))
    stair = st / "03_extract" / "masks" / "stair.png"
    m["stair"] = cv2.imread(str(stair), cv2.IMREAD_GRAYSCALE) if stair.exists() else None
    a, b, c, d, e, f = grid["px_to_mm"]
    texts = [{"text": t["text"], "cls": t.get("cls"), "at_mm": (a * (t["bbox"][0] + t["bbox"][2]) / 2 + b * (t["bbox"][1] + t["bbox"][3]) / 2 + c,
                                                              d * (t["bbox"][0] + t["bbox"][2]) / 2 + e * (t["bbox"][1] + t["bbox"][3]) / 2 + f)}
             for t in ocr if t.get("cls") in ("annotation", "proposed")]
    gt = Spec.model_validate_json(GT_PATH.read_text())
    pred = SpecStore(run_dir / "specs").load("HEAD")
    return gt, pred, page, binary, m, texts, px_from_mm(grid["px_to_mm"])


def _overlay(page, gt, pred, missed, false, to_px) -> np.ndarray:
    img = (cv2.cvtColor(page, cv2.COLOR_GRAY2BGR) * 0.5 + 127).astype(np.uint8)
    pt = lambda q: tuple(int(v) for v in to_px(*q))
    bad = {r["id"] for r in false}
    for w in pred.walls:
        cv2.line(img, pt(w.a), pt(w.b), (0, 0, 255) if w.id in bad else (0, 170, 0), 3)
    lost = {r["id"] for r in missed}
    for g in gt.walls:
        if g.id in lost:
            cv2.line(img, pt(g.a), pt(g.b), (255, 0, 255), 5)
    for r in gt.rooms:
        if r.type == "outdoor":
            cv2.polylines(img, [np.array([pt(p) for p in r.polygon], np.int32)], True, (255, 160, 0), 2)
    k = 1800 / max(img.shape[:2])
    return cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else img


def report(name: str, metrics: dict, missed: list, false: list, rooms: dict) -> str:
    by_mode = Counter(r["mode"] for r in missed)
    mode_len = {m: round(sum(r["length_mm"] for r in missed if r["mode"] == m) / 1000, 1) for m in by_mode}
    by_region = Counter(r["region"] for r in false)
    region_len = {g: round(sum(r["length_mm"] for r in false if r["region"] == g) / 1000, 1) for g in by_region}
    keys = ("wall_recall", "wall_precision", "wall_iou", "door_recall", "room_match", "rooms_pred", "rooms_gt",
            "gross_area_err")
    lines = [f"# Atribusi galat Gatsu — {name}", "", "| Metrik | Nilai |", "|---|---|"]
    lines += [f"| {k} | {metrics[k]:.3f} |" if isinstance(metrics.get(k), float) else f"| {k} | {metrics.get(k)} |"
              for k in keys]
    lines += ["", f"**Dinding GT terlewat:** {len(missed)} ({round(sum(r['length_mm'] for r in missed) / 1000, 1)} m)", "",
              "| Mode | Jumlah | Panjang (m) |", "|---|---|---|"]
    lines += [f"| {m} | {n} | {mode_len[m]} |" for m, n in by_mode.most_common()]
    lines += ["", f"**Dinding palsu:** {len(false)} ({round(sum(r['length_mm'] for r in false) / 1000, 1)} m)", "",
              "| Wilayah | Jumlah | Panjang (m) |", "|---|---|---|"]
    lines += [f"| {g} | {n} | {region_len[g]} |" for g, n in by_region.most_common()]
    lines += ["", (f"**Ruang:** dalam {rooms['inner_matched']}/{rooms['inner_gt']} cocok, outdoor "
              f"{rooms['outdoor_matched']}/{rooms['outdoor_gt']} cocok; ruang prediksi yang menelan ≥ 2 ruang GT: "
              f"{len(rooms['merged'])} ({', '.join('+'.join(m) for m in rooms['merged']) or '—'}).")]
    lines += ["", "Rincian dinding terlewat (id, jenis, tebal, panjang, mode, tinta binary/clean [kiri, tengah, kanan]):", ""]
    lines += [f"- {r['id']} {r['kind']} {r['thickness']} mm, {r['length_mm']} mm: **{r['mode']}** "
              f"{r['ink_binary']} / {r['ink_clean']}" for r in missed]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True, help="path prefix, e.g. benchmarks/reports/m7a-baseline")
    ap.add_argument("--cache", type=Path, default=None, help="Gatsu run folder (default benchmarks/.cache/gatsu)")
    ap.add_argument("--fresh", action="store_true", help="rerun stages 0-5 with the current code")
    a = ap.parse_args(argv)
    if a.fresh and a.cache:
        import shutil

        shutil.rmtree(a.cache, ignore_errors=True)
    gt, pred, page, binary, masks, texts, to_px = _gatsu_inputs(a.cache)
    metrics = {k: v for k, v in evaluate(pred, gt).items() if k != "passed"}
    missed = classify_missed(gt, pred, binary, masks["clean"], to_px)
    false = classify_false(pred, gt, masks, texts, to_px)
    rooms = classify_rooms(gt, pred)
    from benchmarks.correction_effort import correction_minutes, correction_ops

    ops = correction_ops(pred, gt)
    effort = {"ops": ops, "minutes": correction_minutes(ops)}
    doc = {"metrics": metrics, "missed": missed, "false": false, "rooms": rooms, "effort": effort}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.with_suffix(".json").write_text(json.dumps(doc, indent=1))
    a.out.with_suffix(".md").write_text(report(a.out.name, metrics, missed, false, rooms)
                                        + f"\n**Upaya koreksi:** {effort['minutes']} menit "
                                        + f"({', '.join(f'{k} {n}' for k, n in ops.items() if n)}).\n")
    cv2.imwrite(str(a.out.with_suffix(".png")), _overlay(page, gt, pred, missed, false, to_px))
    print(json.dumps({"minutes": effort["minutes"], "missed": Counter(r["mode"] for r in missed),
                      "false": Counter(r["region"] for r in false),
                      "rooms": {k: v for k, v in rooms.items() if k != "merged"}}))
    return doc


if __name__ == "__main__":
    main()
