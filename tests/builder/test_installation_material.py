"""M12b: the perforated tray material exports as an alpha-masked texture with UVs (run in the user's Terminal)."""

import pytest
from pygltflib import GLTF2

from core.build_prep.mesh import box
from core.build_prep.perforation import write_perforation_png
from core.build_prep.schema import MATERIALS
from tests.builder.helpers import build, doc, mesh, skip_without_blender

pytestmark = [pytest.mark.blender, skip_without_blender]


def test_material_texture_exports_mask(tmp_path):
    png = write_perforation_png(tmp_path / "perf.png", "#B8BCC2")
    d = doc([mesh("tray_data_T1", "TrayData", box(1500, 0, 50, 3000, 200, 1.5), "tray_galv") | {"uv_box_mm": 25}],
            exports=[{"file": "installation.glb", "collections": ["TrayData"]}])
    d["materials"] = MATERIALS | {"tray_galv": {"color": "#B8BCC2", "roughness": 0.4, "alpha": 1.0, "metallic": 0.8, "texture": str(png)}}
    d["cameras"] = []
    r = build(tmp_path, d)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    g = GLTF2().load(str(tmp_path / "out" / "installation.glb"))
    mat = next(m for m in g.materials if m.name == "tray_galv")
    assert mat.alphaMode == "MASK" and len(g.images) == 1
    assert g.meshes[0].primitives[0].attributes.TEXCOORD_0 is not None
