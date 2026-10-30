
import pytest

from core.installation.build import (
    InstallInvalid,
    install_build,
    install_publish,
    installation_build_input,
)
from core.installation.models import CableTray, Installation, InstallMeta
from core.spec.models import PlacedObject
from tests.spec.fixtures import spec_with_rooms

TEMPLATES = {"rack-42u-600x1200": "rack"}


def inst(trays=(), objects=(), **meta):
    return Installation(meta=InstallMeta(version=2, layout_version=1, **meta), cable_trays=list(trays), objects=list(objects))


TRAY = CableTray(id="T1", path=[(500, 3000), (9000, 3000)], tray_class="data")
RACK = PlacedObject(id="RK1", template_id="rack-42u-600x1200", template_version="1.0.0", position=(2000, 2700, 0), dims=(600, 1200, 2000))


def names(doc):
    return {m["name"] for m in doc["meshes"]}


def test_doc_has_layout_and_installation(tmp_path):
    doc, _ = installation_build_input(inst([TRAY], [RACK]), spec_with_rooms(), None, TEMPLATES, tmp_path, "BLENDER_EEVEE")
    n = names(doc)
    assert {"wall_W1", "tray_data_T1", "drop_RK1_T1", "ceiling"} <= n and any(x.startswith("hanger_T1_") for x in n)
    assert {"file": "installation.glb", "collections": ["Installation"]} in doc["exports"]
    assert "Ceiling" in next(e for e in doc["exports"] if e["file"] == "layout_installation.glb")["collections"]
    assert any(c["target"] == "wall_W5" for c in doc["cutters"])
    assert doc["materials"]["tray_galv"]["texture"].endswith("perforation.png") and (tmp_path / "perforation.png").exists()
    assert doc["render"]["engine"] == "BLENDER_EEVEE"
    assert all(c["hide"] == ["Ceiling"] for c in doc["cameras"] if c["name"] in ("cam_top", "cam_iso_ne"))
    assert not any(c["name"].startswith("cam_room_") for c in doc["cameras"])


def test_floor_moves_down_with_raised_floor(tmp_path):
    flat, _ = installation_build_input(inst([TRAY]), spec_with_rooms(), None, TEMPLATES, tmp_path, "BLENDER_EEVEE")
    raised, _ = installation_build_input(inst([TRAY], raised_floor_height=600), spec_with_rooms(), None, TEMPLATES, tmp_path, "BLENDER_EEVEE")
    z = lambda doc: min(v[2] for m in doc["meshes"] if m["name"].startswith("room_") for v in m["verts"])
    assert z(flat) == 0 and z(raised) == -600  # room floors (and the slab, when the layout has an outline) move down
    assert any(c["name"] == "cam_underfloor" and c["hide"] == ["Ceiling", "RaisedFloor"] for c in raised["cameras"])
    assert not any(c["name"] == "cam_underfloor" for c in flat["cameras"])


def test_errors_refuse_the_build(tmp_path):
    bad = inst([TRAY.model_copy(update={"mounting": "underfloor"})])
    with pytest.raises(InstallInvalid) as e:
        install_build(bad, spec_with_rooms(), tmp_path, None, TEMPLATES, "BLENDER_EEVEE", blender_bin="/bin/false")
    assert any(i.code == "I002" for i in e.value.issues)


def test_publish_replaces_atomically(tmp_path):
    work, root = tmp_path / "work", tmp_path / "project" / "installation_outputs"
    (work / "renders").mkdir(parents=True)
    for f in ("installation.glb", "layout_installation.glb", "installation.json"):
        (work / f).write_text(f)
    (work / "renders" / "top.png").write_text("png")
    (tmp_path / "project" / "outputs").mkdir(parents=True)
    install_publish(work, root, 2)
    (work / "installation.json").write_text("v2 again")
    out = install_publish(work, root, 2)
    assert sorted(p.name for p in root.iterdir()) == ["v2"] and (out / "installation.json").read_text() == "v2 again"
    assert (out / "renders" / "top.png").exists() and list((tmp_path / "project" / "outputs").iterdir()) == []
