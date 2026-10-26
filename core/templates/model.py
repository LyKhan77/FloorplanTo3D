"""Template package contract (PRD/10 §2): template.json model."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PosInt = Annotated[int, Field(gt=0)]
Category = Literal["rack", "cooling", "power", "battery", "network", "fire", "security", "furniture", "structure",
                   "other"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Dims(_M):
    w: PosInt
    d: PosInt
    h: PosInt


class Range(_M):
    min: PosInt
    max: PosInt
    step: PosInt


class Resizable(_M):
    w: Literal[False] | Range
    d: Literal[False] | Range
    h: Literal[False] | Range


class Snap(_M):
    grid_mm: PosInt
    align: Literal["edge", "center"]


class Clearance(_M):
    front: Annotated[int, Field(ge=0)] = 0
    back: Annotated[int, Field(ge=0)] = 0
    left: Annotated[int, Field(ge=0)] = 0
    right: Annotated[int, Field(ge=0)] = 0


class TemplateMeta(_M):
    id: Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
    version: Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]
    name: str
    category: Category
    tags: list[str] = []
    dims: Dims
    pivot: Literal["bottom_center"]
    front: Literal["+y"]
    resizable: Resizable
    scale_mode: Literal["stretch", "fixed"]
    snap: Snap
    clearance: Clearance = Clearance()
    stackable: bool = False
    allowed_room_types: list[str] = []
    metadata: dict[str, Any] = {}
    source: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _consistent(self):
        for axis in ("w", "d", "h"):
            r = getattr(self.resizable, axis)
            dim = getattr(self.dims, axis)
            if r is not False and not r.min <= dim <= r.max:
                raise ValueError(f"resizable.{axis}: dims {dim} outside [{r.min}, {r.max}]")
        if self.scale_mode == "fixed" and any(getattr(self.resizable, a) is not False for a in ("w", "d", "h")):
            raise ValueError("scale_mode fixed requires every resizable axis to be false")
        return self
