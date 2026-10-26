import pytest

from core.build_prep.assemble import build_input_for
from core.spec.ops import apply
from tests.spec.fixtures import spec_with_rooms


def test_assemble_two_room_counts_and_versions():
    doc, warnings = build_input_for(spec_with_rooms(), None, (1000, 600))
    names = {m["name"] for m in doc["meshes"]}
    assert {"wall_W1", "wall_W5", "column_C1", "room_R1", "room_R2", "frame_D1", "leaf_D1_a", "leaf_D2_b"} <= names
    assert len(doc["cutters"]) == 2 and warnings == []
    assert all(m["props"]["spec_version"] == 1 for m in doc["meshes"] if "spec_id" in m["props"])
    assert {c["name"] for c in doc["cameras"]} >= {"cam_verify", "cam_top", "cam_iso_ne", "cam_room_R1"}
    assert [e["file"] for e in doc["exports"]] == ["shell.glb", "layout_full.glb", "layout.blend", "layout.fbx",
                                                   "layout.obj"]


def test_verify_camera_maps_one_pixel_to_mm_per_px():
    doc, _ = build_input_for(spec_with_rooms(), None, (1000, 600))  # px_to_mm [10,0,0,0,-10,6000]
    cam = next(c for c in doc["cameras"] if c["name"] == "cam_verify")
    assert cam["ortho_scale"] == pytest.approx(10000) and cam["resolution"] == [1000, 600]
    assert cam["location"][:2] == pytest.approx([5000, 3000]) and cam["mode"] == "verify"


def test_room_camera_faces_longest_edge():
    doc, _ = build_input_for(spec_with_rooms(), None, None)
    cam = next(c for c in doc["cameras"] if c["name"] == "cam_room_R1")  # R1 4850 wide x 5800 tall: long edge vertical
    assert cam["kind"] == "PERSP" and cam["fov_deg"] == 75 and cam["location"][2] == 1600
    assert cam["rotation_deg"][0] == pytest.approx(90) and round(cam["rotation_deg"][2]) % 180 in (0, 90)


def test_missing_template_skipped_with_warning(tmp_path):
    s = apply(spec_with_rooms(), [{"op": "add_object", "template_id": "rack", "template_version": "9.9.9",
                                   "position": (2000, 2000, 0), "dims": (600, 1200, 2000)}], "editor", 2)
    doc, warnings = build_input_for(s, tmp_path, None)
    assert doc["instances"] == [] and warnings == ["object O1: template rack@9.9.9 not found"]


@pytest.mark.blender
def test_instance_scale_from_dims(placeholder_root):
    s = apply(spec_with_rooms(), [{"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.0.0",
                                   "position": (2000, 2000, 0), "dims": (600, 1000, 2200)}], "editor", 2)
    doc, _ = build_input_for(s, placeholder_root, None)
    inst = doc["instances"][0]
    assert inst["scale"] == pytest.approx([1.0, 1000 / 1200, 1.1]) and inst["name"] == "obj_O1"
    assert inst["props"]["template_id"] == "rack-42u-600x1200" and inst["template_key"] == "rack-42u-600x1200@1.0.0"
