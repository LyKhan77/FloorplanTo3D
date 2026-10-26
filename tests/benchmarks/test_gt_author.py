from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from benchmarks.tools.gt_author import (
    build_grid,
    fit_px_to_mm,
    load_gt,
    parse_point,
    render_overlay,
)
from core.spec.validate import validate

GRID = {"x": {"A": 0, "B": 6000, "C": 12000, "D": 16000, "E": 22000, "F": 28000},
        "y": {"3": 0, "2": 6000, "1": 12000}}
TRUE = np.array([[25.85, 0, -5170], [0, -25.85, 15460]])


def gatsu_grid():
    return build_grid(GRID)


def px_of(ref: str) -> list[float]:
    x, y = parse_point(ref, gatsu_grid())
    return np.linalg.solve(TRUE[:, :2], np.array([x, y]) - TRUE[:, 2]).tolist()


def test_parse_point_forms():
    g = gatsu_grid()
    assert parse_point("D2", g) == (16000, 6000)
    assert parse_point([1234, 5678], g) == (1234, 5678)
    assert parse_point(["A1", 100, -200], g) == (100, 11800)


def test_fit_px_to_mm_recovers_affine():
    g = gatsu_grid()
    m, rms = fit_px_to_mm({ref: px_of(ref) for ref in ("A3", "F3", "A1", "F1")}, g)
    assert m == pytest.approx(TRUE.ravel().tolist(), abs=1e-6) and rms < 1e-6


def minimal_yaml() -> str:
    return yaml.safe_dump({
        "project_id": "test-gt", "floor_name": "Test", "site_type": "data_center",
        "image": "floorplan/plan.jpeg", "grid": GRID,
        "calibration": {ref: px_of(ref) for ref in ("A3", "B3", "A2", "B2")},
        "walls": [
            {"id": "W1", "a": "A3", "b": "B3", "t": 200, "kind": "exterior"},
            {"id": "W2", "a": "B3", "b": "B2", "t": 200, "kind": "exterior"},
            {"id": "W3", "a": "B2", "b": "A2", "t": 200, "kind": "exterior"},
            {"id": "W4", "a": "A2", "b": "A3", "t": 200, "kind": "exterior"},
        ],
        "openings": [{"id": "D1", "wall": "W1", "offset": 2000, "width": 900, "type": "single_swing",
                      "hinge": "start", "swing": "left"}],
        "rooms": [{"at": ["A3", 3000, 3000], "name": "TEST", "type": "office"}],
    })


def test_load_gt_minimal_yaml(tmp_path):
    (tmp_path / "gt.yaml").write_text(minimal_yaml())
    s = load_gt(tmp_path / "gt.yaml")
    assert len(s.rooms) == 1 and s.rooms[0].name == "TEST" and validate(s).passed
    assert s.meta.id_seq["W"] == 4 and s.meta.px_to_mm == pytest.approx(TRUE.ravel().tolist(), abs=1e-6)
    assert [a.id for a in s.grid.axes][:2] == ["GA", "GB"]


def test_render_overlay_writes_image(tmp_path):
    (tmp_path / "gt.yaml").write_text(minimal_yaml())
    s = load_gt(tmp_path / "gt.yaml")
    out = tmp_path / "overlay.png"
    render_overlay(s, Path("floorplan/plan.jpeg"), out)
    img = cv2.imread(str(out))
    assert img is not None and img.shape[:2] == (945, 1600)


def test_load_gt_carries_heights_and_rejects_unknown_keys(tmp_path):
    d = yaml.safe_load(minimal_yaml())
    d["walls"].append({"id": "W5", "a": ["A3", 1000, 3000], "b": ["A3", 2000, 3000], "t": 100, "kind": "low",
                       "height": 1000, "free_ends": True})
    (tmp_path / "gt.yaml").write_text(yaml.safe_dump(d))
    s = load_gt(tmp_path / "gt.yaml")
    assert next(w for w in s.walls if w.id == "W5").height == 1000
    d["walls"][-1]["heigth"] = 900
    (tmp_path / "gt.yaml").write_text(yaml.safe_dump(d))
    with pytest.raises(ValueError, match="heigth"):
        load_gt(tmp_path / "gt.yaml")
