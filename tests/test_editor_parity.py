"""Parity fixture for the web editor's client reducer (web/src/editor/ops/reducer.ts).

Regenerate with UPDATE_PARITY=1 after changing core/spec/ops.py; the Vitest parity test then shows where the
client drifted.
"""

import json
import os
from pathlib import Path

from core.spec.ids import next_id
from core.spec.models import Spec
from core.spec.ops import apply

GT = Path("benchmarks/gatsu/gt_spec.json")
FIXTURE = Path("web/src/editor/ops/parity.fixture.json")


def _cases(gt: Spec) -> list[dict]:
    door = next(o for o in gt.openings if o.category == "door")
    host = next(w for w in gt.walls if w.id == door.wall_id)
    new_wall = next_id(gt, "W")[0]
    stair, other_stair = gt.stairs[0], gt.stairs[-1]
    room = next(r for r in gt.rooms if r.label_pos)
    other = next(r for r in gt.rooms if r.label_pos and r.id != room.id)
    w1 = gt.walls[0]
    split_at = door.offset + door.width + 100
    obj = {"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.0.0",
           "position": [*room.label_pos, 0], "rotation": 0, "dims": [600, 1200, 2000]}
    return [
        {"name": "move_wall", "ops": [{"op": "move_wall", "id": w1.id, "a": [w1.a[0] + 100, w1.a[1]]}]},
        {"name": "add_wall", "ops": [{"op": "add_wall", "a": [0, 0], "b": [3000, 0], "thickness": 150,
                                      "kind": "partition"}]},
        {"name": "split_wall", "ops": [{"op": "split_wall", "id": host.id, "at_offset": split_at}]},
        {"name": "split_then_merge", "ops": [{"op": "split_wall", "id": host.id, "at_offset": split_at},
                                             {"op": "merge_walls", "ids": [new_wall, host.id], "reason": "gabung"}]},
        {"name": "delete_wall_cascade", "ops": [{"op": "delete_wall", "id": host.id, "reason": "salah deteksi"}]},
        {"name": "set_door", "ops": [{"op": "set_door", "id": door.id, "width": door.width + 100, "hinge": "end"}]},
        {"name": "add_openings", "ops": [
            {"op": "add_opening", "wall_id": w1.id, "category": "door", "offset": 1000, "width": 900},
            {"op": "add_opening", "wall_id": w1.id, "category": "window", "offset": 3000, "width": 1500}]},
        {"name": "delete_opening", "ops": [{"op": "delete_opening", "id": door.id, "reason": "bukan pintu"}]},
        {"name": "set_stair", "ops": [{"op": "set_stair", "id": stair.id, "top_z": 4000, "flights": [
            {**f.model_dump(mode="json"), "start": list(f.end), "end": list(f.start)} for f in stair.flights]}]},
        {"name": "delete_stair", "ops": [{"op": "delete_stair", "id": other_stair.id, "reason": "duplikat"}]},
        {"name": "add_then_update_object", "ops": [
            obj, {"op": "update_object", "id": next_id(gt, "O")[0], "position": [*other.label_pos, 0],
                  "rotation": 90}]},
        {"name": "defaults_and_height", "ops": [{"op": "set_default", "key": "wall_height", "value": 4500},
                                                {"op": "set_wall_height", "id": w1.id, "height": 5000}]},
    ]


def _strip(items, drop=("provenance",)) -> list[dict]:
    return [{k: v for k, v in it.model_dump(mode="json").items() if k not in drop} for it in items]


def build_fixture() -> dict:
    gt = Spec.model_validate_json(GT.read_text())
    out = []
    for case in _cases(gt):
        s = apply(gt, case["ops"], "editor", 2)
        out.append({**case, "expected": {
            "walls": _strip(s.walls), "openings": _strip(s.openings),
            "stairs": _strip(s.stairs, ("provenance", "room_id")), "objects": _strip(s.objects),
            "defaults": s.meta.defaults.model_dump(mode="json"), "id_seq": s.meta.id_seq}})
    return {"cases": out}


def test_editor_parity_fixture_is_current():
    fixture = build_fixture()
    if os.environ.get("UPDATE_PARITY") == "1":
        FIXTURE.write_text(json.dumps(fixture, indent=1) + "\n")
    assert json.loads(FIXTURE.read_text()) == fixture, "run UPDATE_PARITY=1 pytest tests/test_editor_parity.py"
