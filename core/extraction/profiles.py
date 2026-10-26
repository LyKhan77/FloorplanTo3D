"""Style profiles (FR-EX-12, PRD/04 §3.6, Tahap 5 langkah 8): the winning sweep parameters of a run, saved under a
name, so a later sweep starts from them and their ±1-step neighbours."""

import json
import re
import secrets
from datetime import datetime

PARAM_KEYS = ("strategy", "sauvola_k", "t_min", "t_max", "l_fix")


class ProfileNotFound(LookupError):
    pass


class ProfileConflict(ValueError):
    pass


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "profile"


def save_profile(storage, name: str, from_run: str) -> dict:
    """from_run = "<project_id>/<run_id>"; the run's stage 5 must have succeeded."""
    pid, _, rid = from_run.partition("/")
    if not re.fullmatch(r"[a-z0-9-]+", pid) or not re.fullmatch(r"[A-Za-z0-9-]+", rid):
        raise ProfileNotFound(f"run {from_run} not found")  # also keeps the path inside the projects folder
    run_dir = storage.projects_dir / pid / "runs" / rid
    chosen = run_dir / "stages" / "05_validate" / "chosen.json"
    if not (run_dir / "run.json").exists() or not chosen.exists():
        raise ProfileNotFound(f"run {from_run} has no stage 5 result")
    if json.loads((run_dir / "run.json").read_text())["stages"][5]["status"] != "succeeded":
        raise ProfileConflict(f"stage 5 of run {from_run} did not succeed")
    params = json.loads(chosen.read_text()).get("params") or {}
    if any(k not in params for k in PARAM_KEYS):
        raise ProfileConflict(f"run {from_run} has no sweep parameters")
    profile = {"profile_id": f"{_slug(name)}-{secrets.token_hex(2)}", "name": name,
               "params": {k: params[k] for k in PARAM_KEYS}, "from_run": from_run,
               "created_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    storage.profiles_dir.mkdir(parents=True, exist_ok=True)
    (storage.profiles_dir / f"{profile['profile_id']}.json").write_text(json.dumps(profile, indent=2) + "\n")
    return profile


def load_profile(storage, profile_id: str) -> dict:
    path = storage.profiles_dir / f"{profile_id}.json"
    if not re.fullmatch(r"[a-z0-9-]+", profile_id or "") or not path.exists():
        raise ProfileNotFound(f"profile {profile_id} not found")
    return json.loads(path.read_text())
