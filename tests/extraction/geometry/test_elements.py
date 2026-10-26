import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.extraction.geometry.elements import elements_to_spec, to_mm
from core.spec.models import Spec

GT = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())


def grid_doc(spec: Spec = GT) -> dict:
    return {"px_to_mm": spec.meta.px_to_mm, "px_to_mm_original": spec.meta.px_to_mm, "mm_per_px": spec.meta.mm_per_px,
            "scale_source": "grid_dimensions",
            "axes": [{"id": a.id, "label": a.label, "orientation": a.orientation, "offset": a.offset} for a in spec.grid.axes]}


def spec_to_elements(spec: Spec) -> dict:
    walls = [{"a": list(w.a), "b": list(w.b), "thickness": w.thickness, "kind": w.kind, "strategy": "S2",
              "confidence": 1.0, "evidence": {}} for w in spec.walls]
    index = {w.id: i for i, w in enumerate(spec.walls)}
    return {
        "walls": walls,
        "columns": [{"center": list(c.center), "size": list(c.size), "shape": c.shape, "rotation": c.rotation,
                     "kind": c.kind, "confidence": 1.0, "grid_ref": None} for c in spec.columns],
        "openings": [{"wall": index[o.wall_id], "category": o.category, "offset": o.offset, "width": o.width,
                      "door_type": o.door_type, "hinge": o.hinge, "swing": o.swing, "confidence": 1.0, "evidence": {}}
                     for o in spec.openings],
        "stairs": [{"flights": [f.model_dump(mode="json") for f in s.flights], "landings": s.landings,
                    "confidence": 1.0, "direction_source": "text"} for s in spec.stairs],
        "issues": [], "params": {},
    }


def test_elements_to_spec_maps_ids_and_mm():
    el = {
        "walls": [{"a": [0, 0], "b": [3000, 0], "thickness": 150, "kind": "exterior", "strategy": "S2", "confidence": 0.8,
                   "evidence": {"pair_overlap": 1.0}},
                  {"a": [0, 0], "b": [0, 3000], "thickness": 100, "kind": "partition", "strategy": "S2", "confidence": 0.5,
                   "evidence": {}},
                  {"a": [5, 5], "b": [5, 5], "thickness": 100, "kind": "partition", "strategy": "S2", "confidence": 0.5,
                   "evidence": {}}],
        "columns": [{"center": [0, 0], "size": [520, 520], "shape": "h_section", "rotation": 0, "kind": "structural",
                     "confidence": 0.9, "grid_ref": ["GA", "G3"]}],
        "openings": [{"wall": 1, "category": "door", "offset": 500, "width": 900, "door_type": "single_swing",
                      "hinge": "start", "swing": "left", "confidence": 0.7, "evidence": {}}],
        "stairs": [{"flights": [{"start": [1000, 1000], "end": [1000, 3000], "width": 1200, "risers": 15}], "landings": [],
                    "confidence": 0.9, "direction_source": "text"}],
        "issues": [], "params": {},
    }
    spec = elements_to_spec(el, grid_doc())
    assert [w.id for w in spec.walls] == ["W1", "W2"]  # the zero-length wall is dropped
    assert spec.openings[0].wall_id == "W2" and spec.openings[0].id == "D1"
    assert spec.walls[0].a == (0, 0) and spec.walls[0].b == (3000, 0)
    assert spec.walls[0].provenance.confidence == 0.8 and spec.walls[0].provenance.source == "cv"
    assert spec.rooms == [] and spec.meta.px_to_mm == GT.meta.px_to_mm
    assert spec.columns[0].grid_ref == ("GA", "G3") and spec.stairs[0].id == "S1"


def test_to_mm_rounds_with_work_affine():
    assert to_mm([12.5, 0, -100, 0, -12.5, 500], 10, 10) == (25, 375)


@pytest.mark.slow
def test_preprocess_exports_colour_mask():
    from core.extraction.preprocess import load_raster, preprocess

    r = preprocess(load_raster(Path("floorplan/plan.jpeg")))
    assert r.colour.shape == r.page.shape and set(r.colour.reshape(-1).tolist()) <= {0, 255}
    # bubble A ring (original centre ~ (200, 867), r ~ 21): magenta; wall W50 line (work x 1863, y 400): black
    ring = r.colour[2 * 867 - 46:2 * 867 + 46, 2 * 200 - 46:2 * 200 + 46]
    assert (ring == 255).sum() > 50
    assert r.colour[400, 1863] == 0


def test_cli_elements_mode(tmp_path):
    el, grid = tmp_path / "elements.json", tmp_path / "grid.json"
    el.write_text(json.dumps(spec_to_elements(GT)))
    grid.write_text(json.dumps(grid_doc()))
    out = tmp_path / "e"
    subprocess.run([sys.executable, "-m", "benchmarks.run_extraction_bench", "--elements", str(el), "--grid", str(grid),
                    "--out", str(out)], check=True)
    doc = json.loads(out.with_suffix(".json").read_text())
    assert doc["wall_recall"] == 1.0 and doc["door_recall"] == 1.0 and doc["wall_iou"] == pytest.approx(1.0)
    assert "room_match" not in doc
