"""/api/templates (PRD/09 §2.7) and /api/profiles (§2.8)."""

import json
import logging
from functools import lru_cache

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.extraction.profiles import ProfileConflict, ProfileNotFound, save_profile
from core.templates.registry import load_template
from core.templates.validate import validate_template
from server.errors import ApiError

router = APIRouter(prefix="/api")
log = logging.getLogger("floorplan3d.templates")


@lru_cache(maxsize=256)
def _problems(folder: str, mtime: float) -> tuple[str, ...]:
    from pathlib import Path

    return tuple(validate_template(Path(folder)))


def _semver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split(".")) if all(x.isdigit() for x in v.split(".")) else (0,)


@router.get("/templates")
def list_templates(request: Request, category: str | None = None):
    root = request.app.state.storage.templates_dir
    out = []
    if not root.exists():
        return out
    for tdir in sorted(p for p in root.iterdir() if p.is_dir()):
        for version in sorted((p.name for p in tdir.iterdir() if p.is_dir()), key=_semver, reverse=True):
            found = load_template(root, tdir.name, version)
            folder = tdir / version
            problems = _problems(str(folder), max(f.stat().st_mtime for f in folder.iterdir())) if found else ("missing files",)
            if problems:
                log.warning("template %s@%s hidden: %s", tdir.name, version, problems[0])
                continue
            meta = found[0]
            if category and meta.category != category:
                break
            base = f"/api/templates/{meta.id}/{meta.version}"
            out.append(meta.model_dump(mode="json") | {"thumbnail_url": f"{base}/thumbnail.png",
                                                       "asset_url": f"{base}/asset.glb"})
            break  # newest valid version only
    return out


def _template_file(request: Request, tid: str, version: str, name: str):
    st = request.app.state.storage
    f = st.safe_join(st.templates_dir, f"{tid}/{version}/{name}")
    if not f.is_file():
        raise ApiError(404, "template_not_found", f"template {tid}@{version} not found")
    return f


@router.get("/templates/{tid}/{version}")
def get_template(tid: str, version: str, request: Request):
    return json.loads(_template_file(request, tid, version, "template.json").read_text())


@router.get("/templates/{tid}/{version}/asset.glb")
def template_asset(tid: str, version: str, request: Request):
    return FileResponse(_template_file(request, tid, version, "asset.glb"), media_type="model/gltf-binary")


@router.get("/templates/{tid}/{version}/thumbnail.png")
def template_thumbnail(tid: str, version: str, request: Request):
    return FileResponse(_template_file(request, tid, version, "thumbnail.png"), media_type="image/png")


@router.get("/profiles")
def list_profiles(request: Request):
    d = request.app.state.storage.profiles_dir
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))] if d.exists() else []


class ProfileBody(BaseModel):
    name: str
    from_run: str


@router.post("/profiles", status_code=201)
def create_profile(body: ProfileBody, request: Request):
    try:
        return save_profile(request.app.state.storage, body.name, body.from_run)
    except ProfileNotFound as e:
        raise ApiError(404, "not_found", str(e)) from None
    except ProfileConflict as e:
        raise ApiError(409, "conflict", str(e)) from None
