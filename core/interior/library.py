"""Template facts the engine needs, from the registry (newest valid version per id, as /api/templates lists)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from core.templates.registry import load_template, semver


@dataclass(frozen=True)
class Tpl:
    id: str
    version: str
    category: str
    w: float
    d: float
    h: float
    front_clear: float
    back_clear: float
    resizable: dict


def load_library(templates_dir: Path) -> dict[str, Tpl]:
    out: dict[str, Tpl] = {}
    root = Path(templates_dir)
    if not root.exists():
        return out
    for tdir in sorted(p for p in root.iterdir() if p.is_dir()):
        for version in sorted((p.name for p in tdir.iterdir() if p.is_dir()), key=semver, reverse=True):
            meta = _meta(root, tdir.name, version)
            if meta:
                c = meta.clearance
                rz = {a: (None if r is False else (r.min, r.max))
                      for a in ("w", "d", "h") for r in [getattr(meta.resizable, a)]}
                out[meta.id] = Tpl(meta.id, meta.version, meta.category, meta.dims.w, meta.dims.d, meta.dims.h,
                                   float(c.front if c else 0), float(c.back if c else 0), rz)
                break
    return out


def _meta(root: Path, tid: str, version: str):
    """template.json only: the engine needs no GLB (load_template also wants asset.glb)."""
    found = load_template(root, tid, version)
    if found:
        return found[0]
    from pydantic import ValidationError

    from core.templates.model import TemplateMeta

    f = root / tid / version / "template.json"
    try:
        return TemplateMeta.model_validate_json(f.read_text()) if f.exists() else None
    except ValidationError:
        return None


def layout_kind(items: list[str], lib: dict[str, Tpl]) -> Literal["rows", "lineup"]:
    cats = {lib[t].category for t in items if t in lib}
    return "rows" if cats & {"rack", "network"} or any(t.startswith("inrow") for t in items) else "lineup"
