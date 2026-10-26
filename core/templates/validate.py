"""Template package validator (PRD/10 §5). Usage: python -m core.templates.validate <path>"""

import sys
from pathlib import Path

import cv2
import numpy as np
from pydantic import ValidationError
from pygltflib import GLTF2

from core.templates.model import TemplateMeta

MAX_TRIANGLES = 50_000
MAX_MATERIALS = 8
MAX_BYTES = 10 * 1024 * 1024
DIMS_TOL = 0.02
PIVOT_Y_TOL_M = 0.005


def _node_matrix(node) -> np.ndarray:
    if node.matrix:
        return np.array(node.matrix, float).reshape(4, 4).T  # glTF stores column-major
    t = np.eye(4)
    if node.translation:
        t[:3, 3] = node.translation
    r = np.eye(4)
    if node.rotation:
        x, y, z, w = node.rotation
        r[:3, :3] = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    s = np.eye(4)
    if node.scale:
        s[0, 0], s[1, 1], s[2, 2] = node.scale
    return t @ r @ s


def world_bbox(g: GLTF2) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """(min xyz, max xyz) of all mesh vertices in glTF world space, plus each node's world origin."""
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    origins = {}

    def walk(idx: int, parent: np.ndarray) -> None:
        nonlocal lo, hi
        node = g.nodes[idx]
        m = parent @ _node_matrix(node)
        origins[node.name or str(idx)] = m[:3, 3]
        if node.mesh is not None:
            for prim in g.meshes[node.mesh].primitives:
                acc = g.accessors[prim.attributes.POSITION]
                corners = np.array([[x, y, z, 1] for x in (acc.min[0], acc.max[0])
                                    for y in (acc.min[1], acc.max[1]) for z in (acc.min[2], acc.max[2])])
                pts = (m @ corners.T).T[:, :3]
                lo, hi = np.minimum(lo, pts.min(axis=0)), np.maximum(hi, pts.max(axis=0))
        for c in node.children or []:
            walk(c, m)

    for root in g.scenes[g.scene or 0].nodes:
        walk(root, np.eye(4))
    return lo, hi, origins


def validate_template(path: Path) -> list[str]:
    path = Path(path)
    problems: list[str] = []
    try:
        meta = TemplateMeta.model_validate_json((path / "template.json").read_text())
    except (OSError, ValidationError) as e:
        return [f"template.json: {e}"]
    if (meta.id, meta.version) != (path.parent.name, path.name):
        problems.append(f"id/version {meta.id}/{meta.version} do not match folder {path.parent.name}/{path.name}")

    glb_path = path / "asset.glb"
    try:
        g = GLTF2().load(str(glb_path))
    except Exception as e:  # noqa: BLE001 - any parse failure is a validation failure
        return [*problems, f"asset.glb: cannot parse ({e})"]
    if len(g.scenes) != 1:
        problems.append(f"asset.glb: expected 1 scene, found {len(g.scenes)}")
    if g.animations or g.cameras or "KHR_lights_punctual" in (g.extensionsUsed or []):
        problems.append("asset.glb: animations, cameras and lights are not allowed")
    roots = g.scenes[g.scene or 0].nodes
    if len(roots) != 1 or g.nodes[roots[0]].name != "template_root":
        problems.append("asset.glb: expected a single root node named template_root")

    lo, hi, origins = world_bbox(g)
    size_mm = (hi - lo) * 1000  # glTF x = w, y = h, z = d
    for axis, measured in (("w", size_mm[0]), ("h", size_mm[1]), ("d", size_mm[2])):
        expected = getattr(meta.dims, axis)
        if abs(measured - expected) > DIMS_TOL * expected:
            problems.append(f"dims.{axis}: template.json says {expected} mm, asset.glb measures {measured:.0f} mm")
    if abs(lo[1]) > PIVOT_Y_TOL_M:
        problems.append(f"pivot: asset bottom at y={lo[1] * 1000:.1f} mm, expected 0")
    for i, axis in ((0, "w"), (2, "d")):
        centre = (lo[i] + hi[i]) / 2 * 1000
        if abs(centre) > 0.01 * getattr(meta.dims, axis):
            problems.append(f"pivot: bbox centre on {axis} axis is {centre:.0f} mm from the origin")

    triangles = sum(g.accessors[p.indices].count // 3 for m in g.meshes for p in m.primitives if p.indices is not None)
    if triangles > MAX_TRIANGLES:
        problems.append(f"budget: {triangles} triangles > {MAX_TRIANGLES}")
    if len(g.materials) > MAX_MATERIALS:
        problems.append(f"budget: {len(g.materials)} materials > {MAX_MATERIALS}")
    if glb_path.stat().st_size > MAX_BYTES:
        problems.append(f"budget: asset.glb is {glb_path.stat().st_size} bytes > {MAX_BYTES}")

    thumb = cv2.imread(str(path / "thumbnail.png"), cv2.IMREAD_UNCHANGED)
    if thumb is None or thumb.shape[:2] != (512, 512):
        problems.append("thumbnail.png: missing or not 512x512")
    if "front_marker" in origins and origins["front_marker"][2] >= 0:
        problems.append("front: front_marker is not on the -Z (glTF) side")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    problems = validate_template(Path(args[0]))
    print("OK" if not problems else "\n".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
