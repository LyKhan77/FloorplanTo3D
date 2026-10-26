"""Ground-truth authoring: compact grid-based YAML -> layout spec + overlay on the source image.

Usage: uv run python -m benchmarks.tools.gt_author benchmarks/gatsu/gt.yaml [--out-dir DIR]
Point forms: "A1" (grid intersection), [x, y] (mm), ["A1", dx, dy] (grid + mm offset).
"""

import argparse
import hashlib
import math
import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml

from core.report.overlay import render_overlay
from core.spec.models import (
    Column,
    Defaults,
    Flight,
    Grid,
    GridAxis,
    ImageInfo,
    Meta,
    Opening,
    Provenance,
    Spec,
    Stair,
    Wall,
)
from core.spec.rooms import RoomLabel, rebuild_rooms
from core.spec.validate import validate

MANUAL = Provenance(source="manual", confidence=1.0, changed_in=1)


def build_grid(block: dict) -> Grid:
    axes = [GridAxis(id=f"G{lb}", label=str(lb), orientation="vertical", offset=v) for lb, v in block["x"].items()]
    axes += [GridAxis(id=f"G{lb}", label=str(lb), orientation="horizontal", offset=v) for lb, v in block["y"].items()]
    return Grid(axes=axes)


def parse_point(p, grid: Grid) -> tuple[int, int]:
    if isinstance(p, str):
        return grid.point(p)
    if len(p) == 2:
        return (round(p[0]), round(p[1]))
    x, y = grid.point(p[0])
    return (round(x + p[1]), round(y + p[2]))


def fit_px_to_mm(calibration: dict[str, tuple[float, float]], grid: Grid) -> tuple[list[float], float]:
    """Least-squares affine pixel -> mm. Returns ([a, b, c, d, e, f], RMS residual in mm)."""
    px = np.array([[u, v, 1.0] for u, v in calibration.values()])
    mm = np.array([grid.point(ref) for ref in calibration], dtype=float)
    coef, *_ = np.linalg.lstsq(px, mm, rcond=None)  # 3x2
    resid = px @ coef - mm
    rms = float(np.sqrt((resid**2).sum(axis=1).mean()))
    return coef.T.ravel().tolist(), rms


def _grid_ref(ref) -> tuple[str, str] | None:
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", ref) if isinstance(ref, str) else None
    return (f"G{m[1]}", f"G{m[2]}") if m else None


ALLOWED_KEYS = {
    "walls": {"id", "a", "b", "t", "kind", "free_ends", "allow_skew", "height", "base_z"},
    "columns": {"id", "at", "shape", "size", "rotation", "kind", "grid", "height"},
    "openings": {"id", "category", "wall", "offset", "width", "height", "sill", "type", "hinge", "swing", "leaf_split"},
    "stairs": {"id", "flights", "landings", "top_z", "base_z"},
    "rooms": {"at", "name", "type"},
}


def _check_keys(d: dict) -> None:
    """A typo in the YAML must fail loudly, not silently drop a measurement."""
    for section, allowed in ALLOWED_KEYS.items():
        for entry in d.get(section, []):
            unknown = set(entry) - allowed
            if unknown:
                raise ValueError(f"{section} entry {entry.get('id', entry)}: unknown key(s) {sorted(unknown)}")


def load_gt(path: Path) -> Spec:
    d = yaml.safe_load(Path(path).read_text())
    _check_keys(d)
    grid = build_grid(d["grid"])
    px_to_mm, _ = fit_px_to_mm({k: tuple(v) for k, v in d["calibration"].items()}, grid)
    image_path = Path(d["image"])
    h, w = cv2.imread(str(image_path)).shape[:2]

    def pt(p) -> tuple[int, int]:
        return parse_point(p, grid)


    walls = [Wall(id=x["id"], a=pt(x["a"]), b=pt(x["b"]), thickness=x["t"], kind=x["kind"],
                  free_ends=x.get("free_ends", False), allow_skew=x.get("allow_skew", False),
                  height=x.get("height"), base_z=x.get("base_z", 0), provenance=MANUAL)
             for x in d.get("walls", [])]
    columns = [Column(id=x["id"], center=pt(x["at"]), shape=x["shape"], size=tuple(x["size"]),
                      rotation=x.get("rotation", 0), kind=x.get("kind", "structural"), height=x.get("height"),
                      grid_ref=_grid_ref(x["at"]) if x.get("grid") else None, provenance=MANUAL)
               for x in d.get("columns", [])]
    openings = [Opening(id=x["id"], category=x.get("category", "door"), wall_id=x["wall"], offset=x["offset"],
                        width=x["width"], height=x.get("height"),
                        sill=x.get("sill", 0 if x.get("category", "door") == "door" else Defaults().window_sill),
                        door_type=x.get("type"), hinge=x.get("hinge"), swing=x.get("swing"),
                        leaf_split=x.get("leaf_split"), provenance=MANUAL)
                for x in d.get("openings", [])]
    stairs = [Stair(id=x["id"], top_z=x.get("top_z"), base_z=x.get("base_z", 0), provenance=MANUAL,
                    flights=[Flight(start=pt(f["start"]), end=pt(f["end"]), width=f["width"], risers=f["risers"])
                             for f in x["flights"]],
                    landings=[[pt(p) for p in poly] for poly in x.get("landings", [])])
              for x in d.get("stairs", [])]

    id_seq: dict[str, int] = {}
    for el in [*walls, *columns, *openings, *stairs]:
        m = re.fullmatch(r"([A-Z])(\d+)", el.id)
        id_seq[m[1]] = max(id_seq.get(m[1], 0), int(m[2]))
    meta = Meta(
        project_id=d["project_id"], created_at=datetime.now().astimezone(), source="manual",
        floor_name=d.get("floor_name", ""), site_type=d.get("site_type", "other"),
        image=ImageInfo(sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(), width_px=w, height_px=h),
        px_to_mm=px_to_mm, mm_per_px=math.sqrt(abs(px_to_mm[0] * px_to_mm[4] - px_to_mm[1] * px_to_mm[3])),
        scale_source="grid_dimensions", defaults=Defaults(**d.get("defaults", {})), id_seq=id_seq,
    )
    spec = Spec(meta=meta, grid=grid, walls=walls, columns=columns, openings=openings, stairs=stairs)
    labels = [RoomLabel(at=pt(r["at"]), name=r["name"], type=r["type"]) for r in d.get("rooms", [])]
    return rebuild_rooms(spec, labels)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gt_yaml", type=Path)
    ap.add_argument("--out-dir", type=Path)
    args = ap.parse_args(argv)
    out_dir = args.out_dir or args.gt_yaml.parent
    d = yaml.safe_load(args.gt_yaml.read_text())
    _, rms = fit_px_to_mm({k: tuple(v) for k, v in d["calibration"].items()}, build_grid(d["grid"]))
    spec = load_gt(args.gt_yaml)
    (out_dir / "gt_spec.json").write_text(spec.model_dump_json(indent=2) + "\n")
    render_overlay(spec, Path(d["image"]), out_dir / "gt_overlay.png")
    r = validate(spec)
    print(f"calibration RMS {rms:.1f} mm; mm/px {spec.meta.mm_per_px:.3f}")
    print(f"walls {len(spec.walls)}, columns {len(spec.columns)}, openings {len(spec.openings)}, "
          f"stairs {len(spec.stairs)}, rooms {len(spec.rooms)}; gross area {spec.meta.gross_area_m2} m²; "
          f"outlines {len(spec.meta.building_outline)}")
    print(f"passed={r.passed} score={r.score:.3f}")
    for i in r.issues:
        print(f"  {i.severity:7} {i.code} {','.join(i.element_ids)}: {i.message}")


if __name__ == "__main__":
    main()
