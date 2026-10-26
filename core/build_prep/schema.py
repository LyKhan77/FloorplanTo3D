"""build_input.json v1: the only contract between core and the Blender builder (PRD/03 §13).

All lengths are mm in spec axes (+X east, +Y north, +Z up); the builder divides by 1000.
Mesh verts are object-local: relative to the object's `location` and `rot_z` (world meshes use [0, 0, 0]).
"""

from typing import Literal, TypedDict

BUILD_INPUT_VERSION = 1


class MeshItem(TypedDict):
    name: str
    collection: str  # Walls | Columns | Doors | Windows | Stairs | Floors | Template
    verts: list[list[float]]
    faces: list[list[int]]
    material: str
    props: dict
    parent: str | None
    location: list[float]
    rot_z: float


class EmptyItem(TypedDict):
    name: str
    collection: str
    location: list[float]
    rot_z: float
    props: dict
    parent: str | None


class CutterItem(TypedDict):
    target: str
    verts: list[list[float]]  # world coordinates
    faces: list[list[int]]


class InstanceItem(TypedDict):
    name: str
    asset: str  # absolute path to asset.glb
    template_key: str  # "<template_id>@<version>"
    location: list[float]
    rot_z: float
    scale: list[float]
    props: dict


class LabelItem(TypedDict):
    text: str
    location: list[float]
    size: float


class GridLineItem(TypedDict):
    a: list[float]
    b: list[float]
    label: str


class CameraItem(TypedDict):
    name: str
    kind: Literal["ORTHO", "PERSP"]
    location: list[float]
    rotation_deg: list[float]
    ortho_scale: float | None
    fov_deg: float | None
    resolution: list[int]
    output: str
    mode: Literal["verify", "doc"]
    cutaway_mm: float | None


class ExportItem(TypedDict):
    file: str
    collections: list[str]  # empty = everything (used for .blend)


class Material(TypedDict):
    color: str
    roughness: float
    alpha: float


MATERIALS: dict[str, Material] = {
    "wall_ext": {"color": "#D9D9D9", "roughness": 0.9, "alpha": 1.0},
    "wall_int": {"color": "#E8E8E8", "roughness": 0.9, "alpha": 1.0},
    "column": {"color": "#A8A8A8", "roughness": 0.8, "alpha": 1.0},
    "floor": {"color": "#6F6F6F", "roughness": 0.7, "alpha": 1.0},
    "floor_data_hall": {"color": "#8D8D8D", "roughness": 0.6, "alpha": 1.0},
    "door_frame": {"color": "#4D4D4D", "roughness": 0.5, "alpha": 1.0},
    "door_leaf": {"color": "#8A6A4F", "roughness": 0.6, "alpha": 1.0},
    "door_leaf_metal": {"color": "#9AA0A6", "roughness": 0.6, "alpha": 1.0},
    "glass": {"color": "#BFD7EA", "roughness": 0.1, "alpha": 0.3},
}
