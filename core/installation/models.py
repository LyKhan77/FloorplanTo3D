"""Installation document (design 2026-10-30 §5): products placed on an approved layout version, kept apart from the
layout spec so an automatic pass can work on installation items only. Units: integer mm, same frame as the layout."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.spec.models import Mm, PlacedObject, Point, ProvenanceLogEntry

TrayClass = Literal["data", "power"]
Mounting = Literal["overhead", "underfloor"]
TRAY_WIDTHS = (100, 150, 200, 300, 400, 500, 600)
SIDE_HEIGHTS = (50, 100, 150)
DEFAULT_WIDTH = {"data": 200, "power": 400}


class _Model(BaseModel):  # a direct BaseModel subclass, so lint knows list defaults are copied per instance
    model_config = ConfigDict(extra="forbid")


class TrayProvenance(_Model):
    source: Literal["editor", "auto", "manual"] = "editor"
    confidence: float = Field(1.0, ge=0, le=1)
    evidence: dict[str, Any] = {}
    changed_in: int = 0


class CableTray(_Model):
    """Only what a person decides is stored; drops, hangers, fittings and lengths are derived (§5.2)."""

    id: str
    path: list[Point]
    tray_class: TrayClass
    width: Mm = 0  # 0 = the class default, filled in below
    side_height: Mm = 100
    tray_type: Literal["perforated"] = "perforated"
    mounting: Mounting | None = None  # None = meta.default_mounting
    elevation: Mm | None = None  # underside from the finished floor; None = default for the mounting (§6.2)
    flow: Literal["forward", "reverse"] = "forward"
    provenance: TrayProvenance = TrayProvenance()

    @model_validator(mode="after")
    def _class_width(self):
        if not self.width:
            self.width = DEFAULT_WIDTH[self.tray_class]
        return self


class InstallMeta(_Model):
    version: int = 0
    parent_version: int | None = None
    layout_version: int
    ceiling_height: Mm | None = None  # None = layout defaults.wall_height
    raised_floor_height: Mm | None = None  # None = no raised floor
    default_mounting: Mounting = "overhead"
    created_at: datetime | None = None
    source: Literal["editor", "auto", "migration"] = "editor"
    message: str = ""
    id_seq: dict[str, int] = {}  # highest ID number ever given per prefix: deleted IDs are never reused


class Installation(_Model):
    schema_version: Literal["1.0"] = "1.0"
    meta: InstallMeta
    cable_trays: list[CableTray] = []
    objects: list[PlacedObject] = []
    provenance_log: list[ProvenanceLogEntry] = []
