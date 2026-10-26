"""1:1 check of the exported shell (NFR-AC-09): wall bounding boxes in shell.glb vs build_input, <= 1 mm."""

from pathlib import Path

import numpy as np
from pygltflib import GLTF2

TOLERANCE_MM = 1.0


def glb_check(glb: Path, doc: dict) -> dict:
    try:
        g = GLTF2().load(str(glb))
    except Exception as e:  # noqa: BLE001 - an unreadable export is a failed check, not a crash
        return {"max_err_mm": None, "pass": False, "checked": 0, "error": f"cannot read {glb.name}: {e}"}
    nodes = {n.name: n for n in g.nodes if n.name and n.mesh is not None}
    errors = []
    for item in doc["meshes"]:
        if not item["name"].startswith("wall_") or item["name"] not in nodes:
            continue
        v = np.array(item["verts"], float)
        expected = np.concatenate([v.min(axis=0), v.max(axis=0)])
        lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
        for prim in g.meshes[nodes[item["name"]].mesh].primitives:
            acc = g.accessors[prim.attributes.POSITION]
            lo, hi = np.minimum(lo, acc.min), np.maximum(hi, acc.max)
        # glTF (x, y-up, z) -> spec mm (x, -z, y)
        got = np.array([lo[0], -hi[2], lo[1], hi[0], -lo[2], hi[1]]) * 1000
        errors.append(float(np.abs(got - expected).max()))
    max_err = max(errors, default=0.0)
    return {"max_err_mm": round(max_err, 3), "pass": bool(errors) and max_err <= TOLERANCE_MM, "checked": len(errors)}
