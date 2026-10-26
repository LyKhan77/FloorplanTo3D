"""Compact diff between two spec versions (PRD/08 §3.3 tab Versions, PRD/09 §2.4)."""

from core.spec.derive import id_key
from core.spec.models import Spec

TYPES = ("walls", "columns", "openings", "rooms", "stairs", "objects")
DERIVED = {"provenance", "area_m2", "perimeter_m", "bounding_walls", "doors", "room_id"}


def diff_specs(a: Spec, b: Spec) -> dict:
    out: dict = {}
    for t in TYPES:
        old = {e.id: e.model_dump(exclude=DERIVED & set(type(e).model_fields)) for e in getattr(a, t)}
        new = {e.id: e.model_dump(exclude=DERIVED & set(type(e).model_fields)) for e in getattr(b, t)}
        out[t] = {"added": sorted(new.keys() - old.keys(), key=id_key),
                  "removed": sorted(old.keys() - new.keys(), key=id_key),
                  "changed": sorted((i for i in old.keys() & new.keys() if old[i] != new[i]), key=id_key)}
    out["ops"] = b.provenance_log
    return out
