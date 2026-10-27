import json

import numpy as np
import pytest

from core.llm_review.tasks import (
    EFFORT,
    SCHEMAS,
    FewShot,
    ReviewItem,
    T1Answer,
    T2Answer,
    T3Answer,
    agree_key,
    load_fewshot,
    load_prompt,
    majority,
    messages_for,
    ops_for,
    parse_prompt_llm,
)
from core.spec.models import Provenance
from tests.llm_review.conftest import FakeStrata
from tests.spec.fixtures import spec_with_rooms


def cv(conf: float) -> Provenance:
    return Provenance(source="cv", confidence=conf)


def spec_cv(wall_conf=0.4, door_conf=0.4, room_source="cv"):
    s = spec_with_rooms()
    for w in s.walls:
        w.provenance = cv(wall_conf)
    for o in s.openings:
        o.provenance = cv(door_conf)
    for r in s.rooms:
        r.provenance = Provenance(source=room_source)
    return s


def test_schemas_and_effort():
    assert set(SCHEMAS) == {"T0", "T1", "T2", "T3"}
    assert EFFORT == {"T0": "low", "T1": "low", "T2": "low", "T3": "none", "T4": "medium"}


def test_prompts_are_versioned_and_t1_t3_carry_the_frame():
    for t in ("T1", "T2", "T3"):
        p = load_prompt(t)
        assert p.startswith("You are a floor plan verification assistant for data center drawings.")
        assert "Cable routes, dimension lines, leaders and MEP annotations are NOT walls." in p
    assert "millimetres" in load_prompt("T0", "v1")
    with pytest.raises(FileNotFoundError):
        load_prompt("T1", "v99")


def test_majority_needs_two_agreeing():
    a, b = T1Answer(id="W1", verdict="annotation"), T1Answer(id="W1", verdict="wall")
    assert majority("T1", [a, b, None]) is None
    assert majority("T1", [a, b, a]).verdict == "annotation"
    assert majority("T1", [None, None, None]) is None


def test_t3_agreement_ignores_case_and_spaces():
    x = T3Answer(id="R1", type="pantry", name_normalized="Pantry ")
    y = T3Answer(id="R1", type="pantry", name_normalized="PANTRY")
    assert agree_key("T3", x) == agree_key("T3", y) and majority("T3", [x, y]) is not None


def test_ops_for_t1_respects_confidence_limit():
    assert ops_for("T1", spec_cv(0.4), "W5", T1Answer(id="W5", verdict="annotation")) == \
        [{"op": "delete_wall", "id": "W5", "reason": "strata: annotation"}]
    assert ops_for("T1", spec_cv(0.85), "W5", T1Answer(id="W5", verdict="annotation")) == []
    assert ops_for("T1", spec_cv(0.4), "W5", T1Answer(id="W5", verdict="wall")) == []
    assert ops_for("T1", spec_cv(0.4), "W5", T1Answer(id="W5", verdict="unsure")) == []


def test_ops_for_t2_only_changed_fields():
    ans = T2Answer(id="D1", is_door=True, door_type="single_swing", hinge="end", swing="left")
    assert ops_for("T2", spec_cv(), "D1", ans) == [{"op": "set_door", "id": "D1", "hinge": "end"}]
    same = T2Answer(id="D1", is_door=True, door_type="single_swing", hinge="start", swing="left")
    assert ops_for("T2", spec_cv(), "D1", same) == []
    gone = T2Answer(id="D1", is_door=False, door_type=None, hinge=None, swing=None)
    assert ops_for("T2", spec_cv(), "D1", gone) == [{"op": "delete_opening", "id": "D1", "reason": "strata: not a door"}]
    assert ops_for("T2", spec_cv(door_conf=0.9), "D1", gone) == []


def test_ops_for_t3_type_and_name():
    ans = T3Answer(id="R1", type="pantry", name_normalized="PANTRY")
    assert ops_for("T3", spec_cv(), "R1", ans) == [{"op": "set_room_type", "id": "R1", "type": "pantry"},
                                                   {"op": "rename_room", "id": "R1", "name": "PANTRY"}]
    assert ops_for("T3", spec_cv(), "R1", T3Answer(id="R1", type="office", name_normalized="")) == []


def test_ops_for_rejects_wrong_id_and_human_edits():
    assert ops_for("T1", spec_cv(0.4), "W5", T1Answer(id="W9", verdict="annotation")) == []
    assert ops_for("T3", spec_cv(room_source="editor"), "R1", T3Answer(id="R1", type="toilet", name_normalized="WC")) == []
    manual = spec_cv(0.4)
    manual.walls[4].provenance = Provenance(source="manual", confidence=0.4)
    assert ops_for("T1", manual, "W5", T1Answer(id="W5", verdict="annotation")) == []


def item_with_images():
    img = np.full((768, 768, 3), 255, np.uint8)
    return ReviewItem(task="T1", element="W1", evidence="Element W1\n- length: 4200 mm", image=img,
                      context=np.full((384, 384, 3), 255, np.uint8))


def test_messages_for_layout():
    fs = FewShot(item=ReviewItem(task="T1", element="W9", evidence="Element W9", image=None, context=None),
                 answer={"id": "W9", "verdict": "wall"})
    m = messages_for(item_with_images(), [fs], evidence=True)
    assert m[0]["role"] == "system" and "Answer ONLY with JSON" in m[0]["content"]
    assert [x["role"] for x in m[1:3]] == ["user", "assistant"] and json.loads(m[2]["content"]) == fs.answer
    parts = m[-1]["content"]
    assert parts[0]["type"] == "text" and "Element W1" in parts[0]["text"] and '"verdict"' in parts[0]["text"]
    imgs = [p for p in parts if p["type"] == "image_url"]
    assert len(imgs) == 2 and imgs[0]["image_url"]["url"].startswith("data:image/png;base64,")
    bare = messages_for(item_with_images(), [], evidence=False)
    assert len(bare) == 2 and "Element W1" not in bare[-1]["content"][0]["text"]
    assert "W1" in bare[-1]["content"][0]["text"]


def test_t3_message_keeps_label_without_evidence():
    item = ReviewItem(task="T3", element="R1", evidence="Element R1", image=None, context=None, label="PANTRI")
    text = messages_for(item, [], evidence=False)[-1]["content"][0]["text"]
    assert 'OCR label: "PANTRI"' in text


def test_load_fewshot(tmp_path):
    d = tmp_path / "T1"
    d.mkdir()
    import cv2

    cv2.imwrite(str(d / "W3.png"), np.zeros((768, 768, 3), np.uint8))
    (d / "items.json").write_text(json.dumps([{"element": "W3", "evidence": "Element W3", "label": "",
                                               "answer": {"id": "W3", "verdict": "annotation"},
                                               "image": "W3.png", "context": None}]))
    [fs] = load_fewshot("T1", tmp_path)
    assert fs.answer["verdict"] == "annotation" and fs.item.image.shape == (768, 768, 3) and fs.item.context is None
    assert load_fewshot("T2", tmp_path) == []


def test_parse_prompt_llm_keeps_stated_fields_only():
    fake = FakeStrata(lambda m, kw: {"wall_height": 4500, "door_height": None, "wall_thickness": None,
                                     "floor_name": "Lantai 1", "site_type": "data_hall"})
    assert parse_prompt_llm(fake, "data hall lantai satu, dinding 4,5 meter") == \
        {"wall_height": 4500, "floor_name": "Lantai 1", "site_type": "data_hall"}
    assert fake.calls[0]["effort"] == "low" and fake.calls[0]["temperature"] == 0
    assert parse_prompt_llm(FakeStrata(lambda m, kw: "nope"), "x") == {}
    assert parse_prompt_llm(fake, "") == {}
