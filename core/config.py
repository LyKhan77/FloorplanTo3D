"""Runtime settings from environment (PRD/02-architecture.md §7). Load .env via `uv run --env-file`."""

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    blender_bin: str
    blender_render_device: str
    strata_base_url: str
    strata_model: str
    strata_timeout_s: int
    llm_tasks_enabled: tuple[str, ...]
    llm_max_iter: int
    llm_votes: int
    sweep_max_candidates: int
    max_upload_mb: int
    strata_api_key: str = field(default="", repr=False)  # a secret: kept out of repr and logs
    strata_response_format: bool = True  # json_schema decoding; off on servers where it is slow (DGX)


def _resolve_bin(name: str) -> str:
    # Blender on macOS crashes when launched through a symlink, so always use the real path.
    found = shutil.which(name)
    return os.path.realpath(found) if found else name


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    e = os.environ if env is None else env
    return Settings(
        data_dir=Path(e.get("DATA_DIR", "./data")),
        blender_bin=_resolve_bin(e.get("BLENDER_BIN", "blender")),
        blender_render_device=e.get("BLENDER_RENDER_DEVICE", "CPU"),
        strata_base_url=e.get("STRATA_BASE_URL", "http://192.168.2.142:8081/v1"),
        strata_model=e.get("STRATA_MODEL", "qwen3.8-flash-next-iq2_xs"),
        strata_timeout_s=int(e.get("STRATA_TIMEOUT_S", "120")),
        llm_tasks_enabled=tuple(t.strip() for t in e.get("LLM_TASKS_ENABLED", "").split(",") if t.strip()),
        llm_max_iter=int(e.get("LLM_MAX_ITER", "5")),
        llm_votes=int(e.get("LLM_VOTES", "3")),
        sweep_max_candidates=int(e.get("SWEEP_MAX_CANDIDATES", "12")),
        max_upload_mb=int(e.get("MAX_UPLOAD_MB", "50")),
        strata_api_key=e.get("STRATA_API_KEY", ""),
        strata_response_format=e.get("STRATA_RESPONSE_FORMAT", "1").strip().lower() not in ("0", "false", "no"),
    )
