import numpy as np

from core.extraction.rooms.overlay import px_from_mm
from core.llm_review.crops import (
    context_thumb,
    crop_box_px,
    door_evidence,
    element_crop,
    room_evidence,
    wall_evidence,
)
from core.spec.models import Provenance, Wall
from tests.spec.fixtures import spec_with_rooms, two_room_spec

TO_PX = px_from_mm([10, 0, 0, 0, -10, 6000])  # 10 mm per px, page 1000 x 600 px
PAGE = np.full((600, 1000), 255, np.uint8)


def side(box):
    return box[2] - box[0]


def test_crop_side_clamped_and_zoomed():
    spec = two_room_spec()
    box = crop_box_px(spec, "W5", TO_PX)  # 6000 mm * 1.6 = 9600 -> max 8000 mm
    assert side(box) == box[3] - box[1] == 800
    assert side(crop_box_px(spec, "W5", TO_PX, zoom=1.3)) == round(8000 / 1.3 / 10)
    assert side(crop_box_px(spec, "D1", TO_PX)) == 200  # 900 * 1.6 = 1440 -> min 2000 mm


def test_crop_is_centred_on_the_element():
    x0, y0, x1, y1 = crop_box_px(two_room_spec(), "D1", TO_PX)  # D1 on W5 (x 5000), centre at y 2450 mm
    assert (x0 + x1) / 2 == 500 and abs((y0 + y1) / 2 - (6000 - 2450) / 10) <= 1


def magenta(img):
    return (img[:, :, 0] == 255) & (img[:, :, 1] == 0) & (img[:, :, 2] == 255)


def test_element_crop_size_and_magenta_target():
    img = element_crop(PAGE, two_room_spec(), "W5", TO_PX)
    assert img.shape == (768, 768, 3) and img.dtype == np.uint8
    assert magenta(img).sum() > 500
    door = element_crop(PAGE, two_room_spec(), "D1", TO_PX)
    assert magenta(door).sum() > 500


def test_crop_near_page_edge_pads_white():
    page = np.zeros((600, 1000), np.uint8)  # black page: anything white comes from padding
    img = element_crop(page, two_room_spec(), "W4", TO_PX)  # W4 on x = 0: left half of the crop is off-page
    assert (img[100:600, :300] == 255).all()


def test_context_thumb_has_red_box():
    t = context_thumb(PAGE, (100, 100, 600, 500))
    assert t.shape == (384, 384, 3)
    assert ((t[:, :, 2] == 255) & (t[:, :, 0] == 0) & (t[:, :, 1] == 0)).any()


def lone_wall_spec():
    s = two_room_spec()
    s.walls.append(Wall(id="W6", a=(2000, 3000), b=(6200, 3000), thickness=90, kind="partition",
                        provenance=Provenance(source="cv", confidence=0.41, evidence={"pair_overlap": 0.0})))
    return s


def test_wall_evidence_lines():
    hatch = np.zeros((600, 1000), np.uint8)
    hatch[:, :410] = 255  # x < 4100 mm: the first half of W6
    texts = [{"text": "NYY 4x1C", "cls": "annotation", "at_mm": (4100, 3300)},
             {"text": "FAR", "cls": "annotation", "at_mm": (4100, 4000)}]
    text = wall_evidence(lone_wall_spec(), "W6", mm_per_px=29.0, hatch=hatch, texts=texts, to_px=TO_PX)
    assert text.splitlines()[0] == "Element W6"
    assert "- length: 4200 mm, thickness: 90 mm (stroke 3.1 px), orientation: horizontal" in text
    assert "- connects to walls at ends: start=none, end=none" in text
    assert "- passes through dense-hatch area: yes (50% of length)" in text
    assert '- nearest text within 600 mm: "NYY 4x1C" (annotation class)' in text
    assert "- parallel partner line found: no" in text
    assert "- CV confidence: 0.41" in text


def test_wall_evidence_connections_and_no_hatch():
    text = wall_evidence(two_room_spec(), "W5", mm_per_px=10, hatch=None, texts=[], to_px=TO_PX)
    assert "start=W1, end=W3" in text and "orientation: vertical" in text
    assert "dense-hatch area: no (0% of length)" in text and "nearest text within 600 mm: none" in text


def test_door_and_room_evidence():
    d = door_evidence(two_room_spec(), "D1")
    assert d.splitlines()[0] == "Element D1"
    assert "host wall: W5" in d and "width: 900 mm" in d and "door_type: single_swing, hinge: start, swing: left" in d
    # W5 runs (5000,0) -> (5000,6000): bottom -> top in the image; looking up, left is the image left
    assert 'host wall runs from its start (bottom) to its end (top): hinge "start" = the bottom end' in d
    assert 'swing "left" = the leaf opens towards the left, "right" = towards the right' in d
    w1 = door_evidence(two_room_spec(), "D2")  # W1 (0,0) -> (10000,0): left -> right; left side = image top
    assert 'start (left) to its end (right)' in w1 and '"left" = the leaf opens towards the top' in w1
    r = room_evidence(spec_with_rooms(), "R1", "PANTRI")
    assert r.splitlines()[0] == "Element R1" and '- OCR label: "PANTRI"' in r and "- current type: office" in r
    assert "- area: 28.1 m2" in r
