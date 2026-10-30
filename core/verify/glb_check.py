"""1:1 check of the exported shell (NFR-AC-09): wall bounding boxes in shell.glb vs build_input, <= 1 mm."""

from pathlib import Path

import numpy as np
from pygltflib import GLTF2

TOLERANCE_MM = 1.0


def expected_box(item: dict, cutters: list[dict]) -> np.ndarray:
    """The wall's box (min xyz, max xyz) after its openings: a cutter spanning the whole wall in plan (a door
    filling a gap) removes everything below its head, so the exported wall starts there."""
    v = np.array(item["verts"], float)
    box = np.concatenate([v.min(axis=0), v.max(axis=0)])
    for c in cutters:
        if c["target"] != item["name"]:
            continue
        cv = np.array(c["verts"], float)
        lo, hi = cv.min(axis=0), cv.max(axis=0)
        if (lo[:2] <= box[:2] + TOLERANCE_MM).all() and (hi[:2] >= box[3:5] - TOLERANCE_MM).all() \
                and lo[2] <= box[2] + TOLERANCE_MM:
            box[2] = max(box[2], min(hi[2], box[5]))
    return box


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
        expected = expected_box(item, doc.get("cutters", []))
        lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
        for prim in g.meshes[nodes[item["name"]].mesh].primitives:
            acc = g.accessors[prim.attributes.POSITION]
            lo, hi = np.minimum(lo, acc.min), np.maximum(hi, acc.max)
        # glTF (x, y-up, z) -> spec mm (x, -z, y)
        got = np.array([lo[0], -hi[2], lo[1], hi[0], -lo[2], hi[1]]) * 1000
        errors.append(float(np.abs(got - expected).max()))
    max_err = max(errors, default=0.0)
    return {"max_err_mm": round(max_err, 3), "pass": bool(errors) and max_err <= TOLERANCE_MM, "checked": len(errors)}
