import dataclasses
import json

import numpy as np
import pymupdf as fitz
import pytest

import core.extraction.stages as st
from core.extraction.rooms.assemble import assemble_spec
from core.extraction.stages import stage_extract, stage_grid, stage_rooms, stage_validate
from core.extraction.vector.candidate import VECTOR_INDEX, pick_seeds, vector_elements
from core.spec.rooms import RoomLabel
from tests.extraction.test_stages import make_project, run_0_2
from tests.inputs import ANCOL, requires_ancol

GRID = {"px_to_mm": [10, 0, 0, 0, -10, 0], "px_to_mm_original": [10, 0, 0, 0, -10, 0], "mm_per_px": 10, "axes": [],
        "scale_source": "manual", "mm_per_px_work": 10}
META = {"drawing_bbox": [0, 0, 2000, 1500], "work_from_original": [1, 0, 0, 0, 1, 0]}


def test_scan_has_no_vector_candidate(tmp_path):
    doc = fitz.open()
    doc.new_page(width=600, height=400).draw_line((10, 10), (500, 10))
    pdf = tmp_path / "s.pdf"
    doc.save(pdf)
    assert vector_elements(pdf, 1, GRID, META, [], {}, np.zeros((1500, 2000), np.uint8)) is None


def _elements(closed):
    walls = [((0, 0), (5000, 0)), ((5800, 0), (5800, 4000)), ((5800, 4000), (0, 4000)), ((0, 4000), (0, 0))]
    return {"walls": [{"a": list(a), "b": list(b), "thickness": 150, "kind": "interior"} for a, b in walls],
            "columns": [], "openings": [], "stairs": [], "lifts": [], **({"closed": True} if closed else {})}


def test_closed_elements_keep_their_gaps():
    info = {"project_id": "t", "floor_name": "", "site_type": "other", "defaults": {},
            "image": {"sha256": "0", "width_px": 1, "height_px": 1}}
    spec, _ = assemble_spec(_elements(True), GRID, [], info)
    assert max(w.b[0] for w in spec.walls if w.a[1] == w.b[1] == 0) == 5000
    spec, _ = assemble_spec(_elements(False), GRID, [], info)
    assert max(max(w.a[0], w.b[0]) for w in spec.walls if w.a[1] == w.b[1] == 0) > 5000


def test_seeds_skip_repeats_and_join_lines_of_a_label():
    labels = [RoomLabel((0, 0), "PAC", "other"), RoomLabel((9000, 0), "PAC", "other"), RoomLabel((18000, 0), "PAC", "other"),
              RoomLabel((5000, 5000), "RUANG A", "other"), RoomLabel((5000, 4000), "LUAS 20 M2", "other")]
    assert pick_seeds(labels) == [(5000, 5000)]


@requires_ancol
@pytest.mark.slow
def test_ancol_vector_candidate_runs_to_a_saved_spec(tmp_path):
    project = make_project(tmp_path / "p", ANCOL.read_bytes(), "pdf", params={"extract_source": "vector"}, page=13)
    stages, _ = run_0_2(project)
    assert stage_extract(project, stages / "03_extract", 1)["status"] == "succeeded"
    assert stage_rooms(project, stages / "04_rooms")["status"] == "succeeded"
    res = stage_validate(project, stages / "05_validate", "r1")
    assert res["metrics"].get("candidate") == VECTOR_INDEX, res
    chosen = json.loads((stages / "05_validate" / "chosen.json").read_text())
    assert chosen["index"] == VECTOR_INDEX


@requires_ancol
@pytest.mark.slow
def test_vector_is_opt_in(tmp_path):
    project = make_project(tmp_path / "p", ANCOL.read_bytes(), "pdf", page=13)
    stages, _ = run_0_2(project)
    stage_extract(project, stages / "03_extract", 1)
    assert not (stages / "03_extract" / "candidates" / str(VECTOR_INDEX)).exists()


def _run_vector(tmp_path, monkeypatch=None):
    project = make_project(tmp_path / "p", ANCOL.read_bytes(), "pdf", params={"extract_source": "vector"}, page=13)
    stages, _ = run_0_2(project)
    return project, stages


@requires_ancol
@pytest.mark.slow
def test_empty_vector_candidate_is_no_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "vector_elements", lambda *a: {"walls": [], "openings": [], "columns": [], "stairs": [],
                                                           "lifts": [], "line_len_m": 0, "closed": True})
    project, stages = _run_vector(tmp_path)
    res = stage_extract(project, stages / "03_extract", 1)
    assert not (stages / "03_extract" / "candidates" / str(VECTOR_INDEX)).exists()
    assert any(w.startswith("Jalur vektor tidak dipakai") for w in res["warnings"])


@requires_ancol
@pytest.mark.slow
def test_crash_in_the_vector_path_leaves_raster_running(tmp_path, monkeypatch):
    def boom(*a):
        raise ValueError("bad page")
    monkeypatch.setattr(st, "vector_elements", boom)
    project, stages = _run_vector(tmp_path)
    res = stage_extract(project, stages / "03_extract", 1)
    assert res["status"] == "succeeded" and any("bad page" in w for w in res["warnings"])


@requires_ancol
@pytest.mark.slow
def test_refused_vector_candidate_falls_back_with_a_warning(tmp_path, monkeypatch):
    real = st.validate

    def strict(spec, ctx):
        res = real(spec, ctx)
        if any(w.provenance.evidence.get("source") for w in spec.walls):
            return dataclasses.replace(res, passed=False)
        return res
    monkeypatch.setattr(st, "validate", strict)
    project, stages = _run_vector(tmp_path)
    stage_extract(project, stages / "03_extract", 1)
    stage_rooms(project, stages / "04_rooms")
    res = stage_validate(project, stages / "05_validate", "r1")
    assert res["metrics"]["candidate"] != VECTOR_INDEX
    assert any(w.startswith("Jalur vektor tidak dipakai") for w in res["warnings"])


@requires_ancol
@pytest.mark.slow
def test_vector_candidate_follows_the_door_width(tmp_path):
    project, stages = _run_vector(tmp_path)
    stage_extract(project, stages / "03_extract", 1)
    first = json.loads((stages / "03_extract" / "candidates.json").read_text())[-1]["wall_len_m"]
    wide = {"door_leaf_width": 1000}
    stage_grid(project, stages / "02_grid", wide)
    stage_extract(project, stages / "03_extract", 1, None, wide)
    second = json.loads((stages / "03_extract" / "candidates.json").read_text())[-1]["wall_len_m"]
    assert second / first == pytest.approx(1.25, rel=0.15)
