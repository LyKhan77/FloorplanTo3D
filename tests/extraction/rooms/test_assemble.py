import pytest

from core.extraction.rooms.assemble import assemble_spec
from core.spec.rooms import RoomLabel
from core.spec.validate import validate

GRID = {"px_to_mm_original": [10, 0, 0, 0, -10, 10000], "mm_per_px": 10, "scale_source": "grid_dimensions",
        "axes": [{"id": "GA", "label": "A", "orientation": "vertical", "offset": 0},
                 {"id": "G1", "label": "1", "orientation": "horizontal", "offset": 0}]}
META = {"project_id": "t", "image": {"sha256": "0", "width_px": 1000, "height_px": 1000}, "floor_name": "L1",
        "site_type": "data_center", "defaults": {"wall_height": 4000}}


def wall(a, b, t=200, kind="exterior"):
    return {"a": list(a), "b": list(b), "thickness": t, "kind": kind, "strategy": "S2", "confidence": 0.9,
            "evidence": {}}


def door(wall_index, offset, width=900):
    return {"wall": wall_index, "category": "door", "offset": offset, "width": width, "door_type": "single_swing",
            "hinge": "start", "swing": "left", "confidence": 0.8, "evidence": {}}


def box_elements(**extra):
    walls = [wall((0, 0), (8000, 0)), wall((8000, 0), (8000, 5000)), wall((8000, 5000), (0, 5000)),
             wall((0, 5000), (0, 0)), wall((4000, 0), (4000, 5000), 100, "partition")]
    el = {"walls": walls, "columns": [], "openings": [door(0, 1000), door(4, 2000)], "stairs": [], "lifts": [],
          "issues": [], "params": {}}
    return el | extra


def test_two_rooms_with_labels_and_types():
    labels = [RoomLabel((2000, 2500), "PANTRY", "pantry"), RoomLabel((6000, 2500), "GUDANG", "storage")]
    spec, issues = assemble_spec(box_elements(), GRID, labels, META)
    assert sorted((r.name, r.type) for r in spec.rooms) == [("GUDANG", "storage"), ("PANTRY", "pantry")]
    assert all(r.doors for r in spec.rooms)
    assert spec.meta.gross_area_m2 == pytest.approx(42.6, abs=0.5)  # outline includes the wall thickness
    assert spec.meta.defaults.wall_height == 4000 and spec.meta.floor_name == "L1"
    assert issues == []


def test_stair_and_lift_rooms_typed():
    stair = {"flights": [{"start": [1000, 1000], "end": [1000, 3500], "width": 1000, "risers": 14}], "landings": [],
             "confidence": 0.9, "direction_source": "text"}
    spec, _ = assemble_spec(box_elements(stairs=[stair], lifts=[[5000, 1000, 7000, 3000]]), GRID, [], META)
    by_type = {r.type: r for r in spec.rooms}
    assert set(by_type) == {"stair", "lift"}
    assert spec.stairs[0].room_id == by_type["stair"].id


def test_outer_band_is_outdoor():
    el = box_elements()
    el["walls"] += [wall((0, -1200), (8000, -1200)), wall((0, -1200), (0, 0)), wall((8000, -1200), (8000, 0))]
    spec, _ = assemble_spec(el, GRID, [RoomLabel((2000, 2500), "PANTRY", "pantry")], META)
    band = [r for r in spec.rooms if max(y for _, y in r.polygon) <= 0]
    assert len(band) == 1 and band[0].type == "outdoor"


def test_two_labels_one_room_is_a_leak_warning():
    el = box_elements()
    el["walls"] = el["walls"][:4]
    el["openings"] = [door(0, 1000)]
    labels = [RoomLabel((2000, 2500), "PANTRY", "pantry"), RoomLabel((6000, 2500), "GUDANG", "storage")]
    _, issues = assemble_spec(el, GRID, labels, META)
    assert [i["code"] for i in issues] == ["ROOM_LEAK"] and issues[0]["element_ids"] == ["R1"]


def test_assembled_spec_validates_without_errors():
    spec, _ = assemble_spec(box_elements(), GRID, [], META)
    assert validate(spec).passed



def partition(spec):
    return next(w for w in spec.walls if w.a[0] == 4000 == w.b[0])


def test_dangling_wall_end_is_closed_onto_the_next_wall():
    el = box_elements()
    el["walls"][4] = wall((4000, 0), (4000, 4200), 100, "partition")  # stops 800 mm short of the north wall
    el["openings"] = [door(0, 1000), door(4, 1000)]
    spec, _ = assemble_spec(el, GRID, [], META)
    assert len(spec.rooms) == 2
    w = partition(spec)
    assert max(w.a[1], w.b[1]) == 5000  # onto the host's centreline: the footprint then closes the T
    assert w.provenance.confidence < 0.6 and w.provenance.evidence["extended_to_close_mm"] == 800


def test_closing_from_the_a_end_keeps_door_positions():
    el = box_elements()
    el["walls"][4] = wall((4000, 800), (4000, 5000), 100, "partition")  # a end stops 800 mm short of the south wall
    el["openings"] = [door(0, 1000), door(4, 1000)]
    spec, _ = assemble_spec(el, GRID, [], META)
    w = partition(spec)
    d = next(o for o in spec.openings if o.wall_id == w.id)
    assert w.a == (4000, 0) and d.offset == 1800  # the door stays 1800-2700 mm above y = 0


@pytest.mark.slow
def test_stage_rooms_gatsu(tmp_path):
    import json
    import shutil

    from core.extraction.stages import stage_extract, stage_rooms
    from tests.extraction.geometry.gatsu import gatsu_stages

    src = gatsu_stages()
    stages = tmp_path / "stages"
    for d in ("00_input", "01_preprocess", "02_grid"):
        shutil.copytree(src / d, stages / d)
    stage_extract(src.parents[2], stages / "03_extract", 12)
    r = stage_rooms(src.parents[2], stages / "04_rooms")
    assert r["status"] == "succeeded"
    rows = json.loads((stages / "04_rooms/candidates.json").read_text())
    c0 = rows[0]
    assert c0["error"] is None and c0["rooms"] >= 20 and c0["labelled"] >= 6  # measured 23 / 7 (GT 48 / 17)
    spec = json.loads((stages / "04_rooms/candidates/0/spec.json").read_text())
    assert len(spec["meta"]["building_outline"]) >= 2
    from shapely.geometry import Polygon

    for k in (r["index"] for r in rows if not r["error"]):  # V011: rounding to mm must not break a room
        s = json.loads((stages / f"04_rooms/candidates/{k}/spec.json").read_text())
        assert all(Polygon(r["polygon"], r["holes"]).is_valid for r in s["rooms"]), k
    assert (stages / "04_rooms/candidates/0/rooms.png").exists()
