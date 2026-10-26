"""Filesystem storage under DATA_DIR (PRD/02 §4) with traversal-safe path joins (NFR-SC-04)."""

import json
import os
import re
import secrets
import unicodedata
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from server.errors import ApiError


class Storage:
    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    def projects_dir(self) -> Path:
        return self.root / "projects"

    @property
    def templates_dir(self) -> Path:
        return self.root / "templates"

    @property
    def profiles_dir(self) -> Path:
        return self.root / "profiles"

    def project_dir(self, pid: str) -> Path:
        d = self.projects_dir / pid
        if not re.fullmatch(r"[a-z0-9-]+", pid) or not (d / "project.json").exists():
            raise ApiError(404, "project_not_found", f"project {pid} not found")
        return d

    @staticmethod
    def new_project_id(name: str) -> str:
        ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40].strip("-") or "project"
        return f"{slug}-{secrets.token_hex(2)}"

    @staticmethod
    def new_run_id() -> str:
        return f"{datetime.now():%Y%m%dT%H%M%S}-{secrets.token_hex(1)}"

    @staticmethod
    def safe_join(base: Path, rel: str) -> Path:
        """Resolve `rel` inside `base`; absolute paths, '..', symlinks and escapes are a 404."""
        not_found = ApiError(404, "not_found", "file not found")
        rel = unquote(rel)
        parts = PurePosixPath(rel).parts
        if not rel or rel.startswith(("/", "\\")) or any(p in ("..", "") for p in parts):
            raise not_found
        path = base
        for part in parts:
            path = path / part
            if path.is_symlink():
                raise not_found
        try:
            path.resolve().relative_to(base.resolve())
        except ValueError:
            raise not_found from None
        return path

    @staticmethod
    def read_json(path: Path) -> dict:
        return json.loads(Path(path).read_text())

    @staticmethod
    def write_json_atomic(path: Path, data: dict) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
