"""Installation ops (design §5.3): every change is an op with provenance; geometry changes and deletes carry a reason.
Same shape as core/spec/ops.py, on the installation document."""

import re
from typing import Annotated, Any, ClassVar, Literal

from pydantic import Field, TypeAdapter, ValidationError, field_validator

from core.installation.models import (
    SIDE_HEIGHTS, TRAY_WIDTHS, CableTray, Installation, Mounting, TrayClass, TrayProvenance,
)
from core.spec.models import Mm, PlacedObject, Point, Provenance, ProvenanceLogEntry
from core.spec.ops import OpError, Reason, _Op


def _width(v: int | None) -> int | None:
    if v is not None and v not in TRAY_WIDTHS:
        raise ValueError(f"width {v} is not a standard tray width {TRAY_WIDTHS}")
    return v


def _side(v: int | None) -> int | None:
    if v is not None and v not in SIDE_HEIGHTS:
        raise ValueError(f"side height {v} is not one of {SIDE_HEIGHTS}")
    return v


class AddTray(_Op):
    op: Literal["add_tray"]
    nullable: ClassVar[frozenset[str]] = frozenset({"mounting", "elevation"})
    path: list[Point]
    tray_class: TrayClass
    width: Mm | None = None
    side_height: Mm | None = None
    mounting: Mounting | None = None
    elevation: Mm | None = None
    flow: Literal["forward", "reverse"] | None = None
    _w = field_validator("width")(_width)
    _s = field_validator("side_height")(_side)


class SetTray(_Op):
    op: Literal["set_tray"]
    nullable: ClassVar[frozenset[str]] = frozenset({"mounting", "elevation"})
    id: str
    tray_class: TrayClass | None = None
    width: Mm | None = None
    side_height: Mm | None = None
    mounting: Mounting | None = None
    elevation: Mm | None = None
    flow: Literal["forward", "reverse"] | None = None
    _w = field_validator("width")(_width)
    _s = field_validator("side_height")(_side)


class MoveTrayPath(_Op):
    op: Literal["move_tray_path"]
    id: str
    path: list[Point]
    reason: Reason


class DeleteTray(_Op):
    op: Literal["delete_tray"]
    id: str
    reason: Reason


class SetInstallationMeta(_Op):
    op: Literal["set_installation_meta"]
    nullable: ClassVar[frozenset[str]] = frozenset({"ceiling_height", "raised_floor_height"})
    ceiling_height: Mm | None = None
    raised_floor_height: Mm | None = None
    default_mounting: Mounting | None = None


class AddObject(_Op):
    op: Literal["add_object"]
    template_id: str
    template_version: str
    position: tuple[Mm, Mm, Mm]
    rotation: float = 0
    dims: tuple[Mm, Mm, Mm]
    label: str | None = None
    evidence: dict[str, Any] = {}


class UpdateObject(_Op):
    op: Literal["update_object"]
    nullable: ClassVar[frozenset[str]] = frozenset({"label"})
    id: str
    position: tuple[Mm, Mm, Mm] | None = None
    rotation: float | None = None
    dims: tuple[Mm, Mm, Mm] | None = None
    label: str | None = None
    template_id: str | None = None
    template_version: str | None = None
    reason: str | None = None


class DeleteObject(_Op):
    op: Literal["delete_object"]
    id: str
    reason: Reason


InstallOp = Annotated[AddTray | SetTray | MoveTrayPath | DeleteTray | SetInstallationMeta | AddObject | UpdateObject
                      | DeleteObject, Field(discriminator="op")]
_ADAPTER = TypeAdapter(InstallOp)


def _find(items: list, eid: str):
    for it in items:
        if it.id == eid:
            return it
    raise ValueError(f"unknown id {eid}")


def _take(inst: Installation, prefix: str) -> str:
    """Never reuse an ID, even after the top one is deleted (meta.id_seq, as in the layout)."""
    used = [int(m[1]) for x in (*inst.cable_trays, *inst.objects) if (m := re.fullmatch(rf"{prefix}(\d+)", x.id))]
    n = max([inst.meta.id_seq.get(prefix, 0), *used]) + 1
    inst.meta.id_seq[prefix] = n
    return f"{prefix}{n}"


def _given(op: _Op, skip: set[str]) -> dict[str, Any]:
    return {k: getattr(op, k) for k in op.model_fields_set if k not in skip}


def apply(inst: Installation, ops: list[Any], by: str, version: int) -> Installation:
    work = inst.model_copy(deep=True)
    work.provenance_log = []  # the log describes the ops that form this version only
    for i, raw in enumerate(ops):
        name = raw.get("op", "?") if isinstance(raw, dict) else getattr(raw, "op", "?")
        try:
            op = raw if isinstance(raw, _Op) else _ADAPTER.validate_python(raw)
            eid, reason = _step(work, op, by, version)
        except (ValidationError, ValueError) as e:
            raise OpError(i, str(name), str(e)) from e
        work.provenance_log.append(ProvenanceLogEntry(op=op.op, id=eid, by=by, reason=reason))
    try:
        return Installation.model_validate(work.model_dump())
    except ValidationError as e:
        raise OpError(len(ops) - 1, "result", str(e)) from e


def _step(s: Installation, op: _Op, by: str, version: int) -> tuple[str | None, str | None]:
    prov = TrayProvenance(source="manual" if by == "manual" else "auto" if by == "auto" else "editor", changed_in=version)
    match op:
        case AddTray():
            tid = _take(s, "T")
            s.cable_trays.append(CableTray(id=tid, provenance=prov, **_given(op, {"op"})))
            return tid, None
        case SetTray() | MoveTrayPath():
            t = _find(s.cable_trays, op.id)
            for k, v in _given(op, {"op", "id", "reason"}).items():
                setattr(t, k, v)
            t.provenance.changed_in = version
            return op.id, getattr(op, "reason", None)
        case DeleteTray():
            s.cable_trays.remove(_find(s.cable_trays, op.id))
            return op.id, op.reason
        case SetInstallationMeta():
            for k, v in _given(op, {"op"}).items():
                setattr(s.meta, k, v)
            return None, None
        case AddObject():
            oid = _take(s, "O")
            fields = _given(op, {"op", "evidence"})
            src = "manual" if by == "manual" else "editor"
            s.objects.append(PlacedObject(id=oid, provenance=Provenance(source=src, evidence=op.evidence, changed_in=version),
                                          **fields))
            return oid, None
        case UpdateObject():
            moved = op.position is not None or op.rotation is not None
            if moved and not (op.reason or "").strip():
                raise ValueError("moving or turning an object needs a reason")
            o = _find(s.objects, op.id)
            for k, v in _given(op, {"op", "id", "reason"}).items():
                setattr(o, k, v)
            o.provenance.changed_in = version
            return op.id, op.reason
        case DeleteObject():
            s.objects.remove(_find(s.objects, op.id))
            return op.id, op.reason
    raise ValueError(f"unknown op {op.op}")
