from core.llm_review.tools import TOOLS, check_call
from core.spec.models import Provenance, Wall
from tests.spec.fixtures import spec_with_rooms


def cv(conf: float) -> Provenance:
    return Provenance(source="cv", confidence=conf)


def tool_spec():
    s = spec_with_rooms()
    for w in s.walls:
        w.provenance = cv(0.9)
    s.walls[0].provenance = cv(0.4)  # W1
    s.walls[2].provenance = Provenance(source="manual", confidence=0.4)  # W3: a person drew it
    s.walls += [
        Wall(id="W6", a=(1000, 3000), b=(2000, 3000), thickness=100, kind="partition", provenance=cv(0.5)),
        Wall(id="W7", a=(2050, 3000), b=(3000, 3000), thickness=100, kind="partition", provenance=cv(0.5)),  # gap 50
        Wall(id="W8", a=(1000, 3500), b=(2000, 3800), thickness=100, kind="partition", provenance=cv(0.5)),  # skewed
        Wall(id="W9", a=(5000 - 50, 3000), b=(4000, 3000), thickness=100, kind="partition", provenance=cv(0.5)),
    ]
    for o in s.openings:
        o.provenance = cv(0.4)
    for r in s.rooms:
        r.provenance = cv(1.0)
    return s


def test_tools_are_exactly_the_whitelist():
    names = sorted(t["function"]["name"] for t in TOOLS)
    assert names == sorted(["delete_wall", "merge_walls", "set_door", "delete_opening", "set_room_type",
                            "rename_room", "finish"])
    assert all(t["type"] == "function" and t["function"]["parameters"]["type"] == "object" for t in TOOLS)
    set_room = next(t for t in TOOLS if t["function"]["name"] == "set_room_type")
    assert "pantry" in set_room["function"]["parameters"]["properties"]["type"]["enum"]


def test_delete_wall_limits():
    s = tool_spec()
    assert check_call(s, "delete_wall", {"id": "W1", "reason": "dim"}) == \
        ([{"op": "delete_wall", "id": "W1", "reason": "dim"}], None)
    assert check_call(s, "delete_wall", {"id": "W2", "reason": "dim"}) == ([], "confidence>=0.8:W2")
    assert check_call(s, "delete_wall", {"id": "W99", "reason": "x"}) == ([], "unknown_id:W99")
    assert check_call(s, "delete_wall", {"id": "W3", "reason": "x"}) == ([], "human_edit:W3")


def test_delete_opening_limits():
    s = tool_spec()
    assert check_call(s, "delete_opening", {"id": "D1", "reason": "gap"})[1] is None
    s.openings[0].provenance = cv(0.95)
    assert check_call(s, "delete_opening", {"id": "D1", "reason": "gap"}) == ([], "confidence>=0.8:D1")


def test_merge_walls_needs_collinear_adjacent():
    s = tool_spec()
    assert check_call(s, "merge_walls", {"ids": ["W6", "W7"], "reason": "split"}) == \
        ([{"op": "merge_walls", "ids": ["W6", "W7"], "reason": "split"}], None)
    assert check_call(s, "merge_walls", {"ids": ["W6", "W8"], "reason": "x"}) == ([], "not_collinear")
    assert check_call(s, "merge_walls", {"ids": ["W6", "W9"], "reason": "x"}) == ([], "not_adjacent")
    assert check_call(s, "merge_walls", {"ids": ["W6", "W3"], "reason": "x"})[1] == "human_edit:W3"


def test_room_and_door_tools():
    s = tool_spec()
    assert check_call(s, "set_room_type", {"id": "R1", "type": "pantry"}) == \
        ([{"op": "set_room_type", "id": "R1", "type": "pantry"}], None)
    assert check_call(s, "rename_room", {"id": "R2", "name": "GUDANG"})[1] is None
    assert check_call(s, "set_door", {"id": "D1", "hinge": "end"}) == ([{"op": "set_door", "id": "D1", "hinge": "end"}], None)


def test_bad_args_and_unknown_tool():
    s = tool_spec()
    assert check_call(s, "set_room_type", {"id": "R1", "type": "garage"})[1].startswith("bad_args:")
    assert check_call(s, "set_door", {"id": "D1", "width": 900})[1].startswith("bad_args:")  # width not offered
    assert check_call(s, "delete_wall", None)[1].startswith("bad_args:")
    assert check_call(s, "add_wall", {}) == ([], "unknown_tool")
    assert check_call(s, "finish", {"summary": "done"}) == ([], None)
