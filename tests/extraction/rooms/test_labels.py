import pytest

from core.extraction.rooms.labels import best_label, labels_from_ocr, levenshtein, match_type
from core.spec.rooms import RoomLabel
from tests.extraction.geometry.synth import text_item

A = [10, 0, 0, 0, -10, 10000]  # 10 mm/px, y up


def test_match_type_lexicon():
    assert match_type("BATTERYROOM") == ("battery_room", 1.0)
    assert match_type("R.MEETING")[0] == "meeting"
    assert match_type("CAPASITR ROOM") == ("capacitor_room", 0.8)
    assert match_type("GALERY")[0] == "lobby"
    assert match_type("KM")[0] == "toilet"
    assert match_type("WC")[0] == "toilet"
    assert match_type("MSC GATSU") == ("other", 0.0)
    assert match_type("WCX")[0] == "other"  # a short word only matches exactly


def test_levenshtein():
    assert levenshtein("KITTEN", "SITTING") == 3
    assert levenshtein("", "AB") == 2


def test_stacked_lines_merge_and_duplicates_drop():
    items = [text_item("CAPASITOR", (100, 100, 190, 118), "room_label"),
             text_item("ROOM", (110, 121, 160, 139), "room_label"),
             text_item("BATTERY", (400, 100, 470, 115), "room_label"),
             text_item("BATTERY", (402, 101, 471, 116), "room_label")]
    labels = labels_from_ocr(items, A)
    assert sorted(lb.name for lb in labels) == ["BATTERY", "CAPASITOR ROOM"]
    cap = next(lb for lb in labels if lb.name == "CAPASITOR ROOM")
    assert cap.type == "capacitor_room" and cap.at == pytest.approx((1450, 8805), abs=15)


def test_best_label_prefers_score_then_length():
    a, b = RoomLabel((0, 0), "WC", "toilet"), RoomLabel((0, 0), "PANTRY", "pantry")
    c = RoomLabel((0, 0), "MSC GATSU", "other")
    assert best_label([c, a, b]).name == "PANTRY" and best_label([]) is None


@pytest.mark.slow
def test_gatsu_labels():
    from tests.extraction.geometry.gatsu import gatsu

    g = gatsu()
    labels = labels_from_ocr(g["ocr"], g["grid"]["px_to_mm"])
    types = {lb.type for lb in labels}
    assert {"pantry", "meeting", "storage", "battery_room", "mdf", "ahu_room", "lobby", "capacitor_room"} <= types
    assert all(lb.type == "other" for lb in labels if "PRDPDSED" in lb.name)
