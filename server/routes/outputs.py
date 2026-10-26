"""/api/projects/{id}/outputs (PRD/09 §2.5): per-version files with ETag, plus a zip bundle."""

import hashlib
import tempfile
import zipfile
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from server.errors import ApiError
from server.projects import output_versions

router = APIRouter(prefix="/api/projects/{pid}/outputs")
REVALIDATE = "no-cache"  # vN is rewritten when a full or from-stage run republishes the same spec version


@lru_cache(maxsize=1024)
def _sha256(path: str, mtime: float, size: int) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _version_dir(request: Request, pid: str, v: int) -> Path:
    d = request.app.state.storage.project_dir(pid) / "outputs" / f"v{v}"
    if not d.is_dir():
        raise ApiError(404, "output_not_found", f"no outputs for version {v}")
    return d


@router.get("")
def list_outputs(pid: str, request: Request):
    out = []
    for v in output_versions(request.app.state.storage, pid):
        d = _version_dir(request, pid, v)
        files = [{"name": p.name, "bytes": p.stat().st_size} for p in sorted(d.iterdir()) if p.is_file()]
        renders = sorted(p.name for p in (d / "renders").glob("*")) if (d / "renders").exists() else []
        out.append({"version": v, "files": files, "renders": renders})
    return out


@router.get("/{v}/bundle.zip")
def bundle(pid: str, v: int, request: Request):
    d = _version_dir(request, pid, v)
    # closed by the background task once the response has been sent
    spool = tempfile.SpooledTemporaryFile(max_size=64 << 20)  # noqa: SIM115
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(d.rglob("*")):
            if p.is_file() and not p.is_symlink():
                z.write(p, p.relative_to(d).as_posix())
    spool.seek(0)
    chunks = iter(lambda: spool.read(1 << 20), b"")  # 1 MB reads; iterating the file itself splits on b"\n"
    return StreamingResponse(chunks, media_type="application/zip", background=BackgroundTask(spool.close),
                             headers={"Content-Disposition": f'attachment; filename="{pid}-v{v}.zip"'})


@router.get("/{v}/{path:path}")
def output_file(pid: str, v: int, path: str, request: Request):
    d = _version_dir(request, pid, v)
    f = request.app.state.storage.safe_join(d, path)
    if not f.is_file():
        raise ApiError(404, "not_found", "file not found")
    st = f.stat()
    etag = f'"{_sha256(str(f), st.st_mtime, st.st_size)}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": REVALIDATE})
    return FileResponse(f, headers={"ETag": etag, "Cache-Control": REVALIDATE})
