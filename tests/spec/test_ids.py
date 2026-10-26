from core.spec.ids import next_id
from tests.spec.fixtures import two_room_spec


def test_next_id_never_reuses_deleted():
    s = two_room_spec().model_copy(deep=True)
    s.meta.id_seq["W"] = 7
    nid, s2 = next_id(s, "W")
    assert nid == "W8" and s2.meta.id_seq["W"] == 8 and s.meta.id_seq["W"] == 7


def test_next_id_from_existing_when_no_seq():
    nid, _ = next_id(two_room_spec(), "W")
    assert nid == "W6"
