import hashlib
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

from benchmarks.extraction_metrics import scale_metrics
from core.extraction.stages import stage_grid, stage_input, stage_preprocess
from core.spec.models import Spec
from tests.inputs import ANCOL, requires_ancol

PLAN = Path("floorplan/plan.jpeg")
GT = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
pytestmark = pytest.mark.slow


def make_project(root: Path, data: bytes, ext: str = "jpg", params: dict | None = None,
                 page: int | None = None) -> Path:
    (root / "input").mkdir(parents=True)
    (root / "input" / f"original.{ext}").write_bytes(data)
    (root / "input" / "input.json").write_text(json.dumps({
        "filename": f"plan.{ext}", "sha256": hashlib.sha256(data).hexdigest(), "prompt": "", "params": params or {},
        "page": page, "type": ext}))
    return root


def run_0_2(project: Path, run: str = "r1", override: dict | None = None) -> tuple[Path, list[dict]]:
    stages = project / "runs" / run / "stages"
    results = [stage_input(project, stages / "00_input"), stage_preprocess(project, stages / "01_preprocess"),
               stage_grid(project, stages / "02_grid", override)]
    return stages, results


def test_stages_0_2_write_artifacts(tmp_path):
    project = make_project(tmp_path / "p", PLAN.read_bytes())
    stages, results = run_0_2(project)
    assert [r["status"] for r in results] == ["succeeded"] * 3, results
    for f in ("00_input/input.json", "01_preprocess/page.png", "01_preprocess/bin.png", "01_preprocess/meta.json",
              "02_grid/ocr.json", "02_grid/grid.json", "02_grid/overlay.png"):
        assert (stages / f).is_file(), f
    grid = json.loads((stages / "02_grid/grid.json").read_text())
    assert scale_metrics(grid["mm_per_px"], GT)["scale_err"] <= 0.005
    assert grid["scale_source"] == "grid_dimensions"  # dimensions present: no door estimate
    assert results[2]["metrics"]["axes_v"] == 6 and results[2]["metrics"]["axes_h"] == 3
    page = cv2.imread(str(stages / "01_preprocess/page.png"))
    overlay = cv2.imread(str(stages / "02_grid/overlay.png"))
    assert overlay.shape == page.shape


def test_stages_0_2_are_deterministic(tmp_path):
    project = make_project(tmp_path / "p", PLAN.read_bytes())
    a, _ = run_0_2(project, "r1")
    b, _ = run_0_2(project, "r2")
    for f in ("02_grid/grid.json", "01_preprocess/meta.json", "02_grid/ocr.json"):
        assert (a / f).read_bytes() == (b / f).read_bytes(), f


def test_tilted_plan_keeps_scale(tmp_path):
    img = cv2.copyMakeBorder(cv2.imread(str(PLAN)), 80, 80, 80, 80, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    h, w = img.shape[:2]  # padded first: rotating in place would cut the corner bubbles off
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((w / 2, h / 2), 2.0, 1.0), (w, h), borderValue=(255, 255, 255))
    _, buf = cv2.imencode(".png", img)
    project = make_project(tmp_path / "p", buf.tobytes(), "png")
    stages, results = run_0_2(project)
    assert results[2]["status"] == "succeeded", results[2]
    assert results[2]["metrics"]["axes_v"] == 6 and results[2]["metrics"]["axes_h"] == 3
    grid = json.loads((stages / "02_grid/grid.json").read_text())
    assert scale_metrics(grid["mm_per_px"], GT)["scale_err"] <= 0.005


def test_manual_scale_param_wins(tmp_path):
    project = make_project(tmp_path / "p", PLAN.read_bytes(), params={"mm_per_px": 26.5})
    stages, results = run_0_2(project)
    grid = json.loads((stages / "02_grid/grid.json").read_text())
    assert grid["scale_source"] == "manual" and grid["mm_per_px"] == pytest.approx(26.5)
    # reported in the user's unit: mm per original pixel, as typed in the form
    assert any("skala manual 26.500 berbeda" in w for w in results[2]["warnings"]), results[2]["warnings"]


def test_input_image_falls_back_to_raster(tmp_path):
    import pymupdf

    from server.projects import input_image
    from server.storage import Storage

    pdf = pymupdf.open()
    page = pdf.new_page(width=1600 * 0.24, height=945 * 0.24)  # 1600 x 945 px at 300 dpi = 384 x 227 pt
    page.insert_image(page.rect, filename=str(PLAN))
    storage = Storage(tmp_path / "data")
    project = make_project(storage.projects_dir / "p-pdf", pdf.tobytes(), "pdf")
    (project / "project.json").write_text("{}")
    assert input_image(storage, "p-pdf") is None
    stage_input(project, project / "runs/r/stages/00_input")
    assert stage_preprocess(project, project / "runs/r/stages/01_preprocess")["status"] == "succeeded"
    assert input_image(storage, "p-pdf") == project / "input" / "raster.png"
    shutil.rmtree(project)


@requires_ancol
def test_ancol_p13_stage2_door_estimate(tmp_path):
    project = make_project(tmp_path / "p", ANCOL.read_bytes(), "pdf", page=13)
    _, results = run_0_2(project)
    res = results[2]
    assert res["status"] == "succeeded" and res["metrics"]["scale_source"] == "door_estimate"
    assert res["metrics"]["mm_per_px"] == pytest.approx(30.7, rel=0.05)
    assert res["metrics"]["doors_used"] >= 3
    assert any(w.startswith("Skala diperkirakan dari") and "(lebar pintu 800 mm)" in w for w in res["warnings"])


def test_door_width_beats_stored_mm_per_px(tmp_path):
    project = make_project(tmp_path / "p", PLAN.read_bytes(), params={"mm_per_px": 26.5})
    _, results = run_0_2(project, override={"door_leaf_width": 800})
    assert results[2]["metrics"]["scale_source"] == "door_estimate"


def test_no_dimensions_no_doors_needs_attention(tmp_path):
    img = np.full((1200, 1600, 3), 255, np.uint8)
    cv2.rectangle(img, (200, 200), (1400, 1000), (0, 0, 0), 6)
    project = make_project(tmp_path / "p", cv2.imencode(".png", img)[1].tobytes(), "png")
    _, results = run_0_2(project)
    assert results[2]["status"] == "needs_attention"
    assert results[2]["message"] == "Skala tidak dapat ditentukan: tidak ada dimensi maupun pintu"


def test_prompt_door_width_does_not_beat_grid(tmp_path):
    project = make_project(tmp_path / "p", PLAN.read_bytes())
    up = json.loads((project / "input" / "input.json").read_text())
    (project / "input" / "input.json").write_text(json.dumps({**up, "prompt": "lebar pintu 900 mm"}))
    _, results = run_0_2(project)
    assert results[2]["metrics"]["scale_source"] == "grid_dimensions"
