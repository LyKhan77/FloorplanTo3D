"""Layout spec models (PRD/03-layout-spec.md). Units: integer mm, +X east, +Y north, +Z up."""

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def round_mm(v: Any) -> Any:
    return round(v) if isinstance(v, float) else v


Mm = Annotated[int, BeforeValidator(round_mm)]
Point = tuple[Mm, Mm]
Polygon = list[Point]


def signed_area(poly: list[tuple[float, float]]) -> float:
    """Shoelace area; positive = counter-clockwise."""
    n = len(poly)
    return sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) / 2


def _oriented(poly: list, ccw: bool) -> list:
    pts = [tuple(p) for p in poly]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    area = signed_area(pts)
    if (ccw and area < 0) or (not ccw and area > 0):
        pts = [pts[0], *reversed(pts[1:])]  # flip direction, keep start point
    return pts


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Provenance(_Model):
    source: Literal["cv", "llm", "editor", "manual"] = "manual"
    confidence: float = Field(1.0, ge=0, le=1)
    candidate: str | None = None
    evidence: dict[str, Any] = {}
    changed_in: int = 0


class Defaults(_Model):
    wall_height: Mm = 3000
    wall_thickness: Mm = 150
    door_height: Mm = 2100
    window_sill: Mm = 900
    window_height: Mm = 1200
    floor_to_floor: Mm = 4000


class ImageInfo(_Model):
    sha256: str
    width_px: int
    height_px: int
    dpi: float | None = None


class Meta(_Model):
    project_id: str
    version: int = Field(1, ge=1)
    parent_version: int | None = None
    created_at: datetime
    source: Literal["pipeline", "llm", "editor", "manual", "migration"]
    run_id: str | None = None
    floor_name: str = ""
    site_type: Literal["data_hall", "data_center", "office", "mixed", "other"] = "other"
    condition: Literal["existing"] = "existing"
    image: ImageInfo | None = None
    px_to_mm: list[float]
    mm_per_px: float
    scale_source: Literal["grid_dimensions", "dimension_text", "manual", "total_length"]
    defaults: Defaults = Defaults()
    building_outline: list[Polygon] = []
    gross_area_m2: float = 0
    id_seq: dict[str, int] = {}

    @field_validator("building_outline")
    @classmethod
    def _ccw(cls, v: list) -> list:
        return [_oriented(p, ccw=True) for p in v]


class GridAxis(_Model):
    id: str
    label: str
    orientation: Literal["vertical", "horizontal"]
    offset: Mm


class Grid(_Model):
    axes: list[GridAxis] = []

    def axis(self, label: str) -> GridAxis:
        return next(a for a in self.axes if a.label == label)

    def point(self, ref: str) -> tuple[int, int]:
        """Grid intersection by labels, vertical first: "B1" -> (x of B, y of 1)."""
        m = re.fullmatch(r"([A-Za-z]+)(\d+)", ref)
        if not m:
            raise KeyError(ref)
        try:
            vx = next(a for a in self.axes if a.orientation == "vertical" and a.label == m[1])
            hy = next(a for a in self.axes if a.orientation == "horizontal" and a.label == m[2])
        except StopIteration:
            raise KeyError(ref) from None
        return (vx.offset, hy.offset)


class Wall(_Model):
    id: str
    a: Point
    b: Point
    thickness: Mm
    height: Mm | None = None
    base_z: Mm = 0
    kind: Literal["exterior", "interior", "partition", "glass", "low"]
    grid_ref: list[str] = []
    free_ends: bool = False
    allow_skew: bool = False
    provenance: Provenance = Provenance()


class Column(_Model):
    id: str
    center: Point
    shape: Literal["rect", "circle", "h_section"]
    size: tuple[Mm, Mm]
    rotation: float = 0
    kind: Literal["structural", "pilaster"] = "structural"
    height: Mm | None = None
    grid_ref: tuple[str, str] | None = None
    provenance: Provenance = Provenance()


class Opening(_Model):
    id: str
    category: Literal["door", "window"]
    wall_id: str
    offset: Mm
    width: Mm
    height: Mm | None = None
    sill: Mm = 0
    door_type: Literal["single_swing", "double_swing", "sliding", "opening", "rolling"] | None = None
    hinge: Literal["start", "end", "both"] | None = None
    swing: Literal["left", "right"] | None = None
    leaf_split: float | None = None
    provenance: Provenance = Provenance()


RoomType = Literal[
    "data_hall", "ups_room", "battery_room", "electrical_room", "mdf", "ahu_room", "capacitor_room",
    "meeting", "office", "storage", "pantry", "toilet", "corridor", "lobby", "stair", "lift",
    "prayer_room", "outdoor", "other",
]


class Room(_Model):
    id: str
    polygon: Polygon
    holes: list[Polygon] = []
    name: str = ""
    type: RoomType = "other"
    area_m2: float = 0
    perimeter_m: float = 0
    bounding_walls: list[str] = []
    doors: list[str] = []
    label_pos: Point | None = None
    provenance: Provenance = Provenance()

    @field_validator("polygon")
    @classmethod
    def _ccw(cls, v: list) -> list:
        return _oriented(v, ccw=True)

    @field_validator("holes")
    @classmethod
    def _cw(cls, v: list) -> list:
        return [_oriented(h, ccw=False) for h in v]


class Flight(_Model):
    start: Point
    end: Point
    width: Mm
    risers: int = Field(ge=1)


class Stair(_Model):
    id: str
    flights: list[Flight] = Field(min_length=1)
    landings: list[Polygon] = []
    base_z: Mm = 0
    top_z: Mm | None = None
    room_id: str | None = None
    provenance: Provenance = Provenance()


class PlacedObject(_Model):
    id: str
    template_id: str
    template_version: str
    position: tuple[Mm, Mm, Mm]
    rotation: float = 0
    dims: tuple[Mm, Mm, Mm]
    room_id: str | None = None
    label: str | None = None
    locked: bool = False
    provenance: Provenance = Provenance()


class ProvenanceLogEntry(_Model):
    op: str
    id: str | None = None
    by: str | None = None
    reason: str | None = None


class Spec(_Model):
    schema_version: Literal["1.0"] = "1.0"
    meta: Meta
    grid: Grid = Grid()
    walls: list[Wall] = []
    columns: list[Column] = []
    openings: list[Opening] = []
    rooms: list[Room] = []
    stairs: list[Stair] = []
    objects: list[PlacedObject] = []
    provenance_log: list[ProvenanceLogEntry] = []

    def all_ids(self) -> list[str]:
        groups = (self.grid.axes, self.walls, self.columns, self.openings, self.rooms, self.stairs, self.objects)
        return [e.id for g in groups for e in g]
