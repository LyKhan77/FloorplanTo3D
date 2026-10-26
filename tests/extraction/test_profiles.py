import json

import pytest

from core.extraction.profiles import ProfileConflict, ProfileNotFound, load_profile, save_profile
from core.extraction.stages import write_json
from server.storage import Storage

PARAMS = {"strategy": "S2", "sauvola_k": 0.34, "t_min": 150, "t_max": 450, "l_fix": 5}


def finished_run(storage: Storage, status: str = "succeeded") -> str:
    run_dir = storage.projects_dir / "p" / "runs" / "r"
    (run_dir / "stages" / "05_validate").mkdir(parents=True)
    stages = [{"n": n, "status": "succeeded"} for n in range(11)]
    stages[5]["status"] = status
    write_json(run_dir / "run.json", {"run_id": "r", "project_id": "p", "stages": stages})
    write_json(run_dir / "stages" / "05_validate" / "chosen.json", {"index": 3, "params": PARAMS, "score": 0.9,
                                                                   "version": 1})
    return "p/r"


def test_save_profile_from_succeeded_run(tmp_path):
    st = Storage(tmp_path)
    prof = save_profile(st, "Gaya Gatsu", finished_run(st))
    assert prof["params"] == PARAMS and prof["name"] == "Gaya Gatsu" and prof["from_run"] == "p/r"
    assert prof["profile_id"].startswith("gaya-gatsu-")
    assert json.loads((st.profiles_dir / f"{prof['profile_id']}.json").read_text()) == prof
    assert load_profile(st, prof["profile_id"]) == prof


def test_save_profile_refuses_unfinished_run(tmp_path):
    st = Storage(tmp_path)
    with pytest.raises(ProfileConflict):
        save_profile(st, "x", finished_run(st, "needs_attention"))
    with pytest.raises(ProfileNotFound):
        save_profile(st, "x", "p/nope")


def test_unknown_profile_raises(tmp_path):
    with pytest.raises(ProfileNotFound):
        load_profile(Storage(tmp_path), "nope")


def test_run_with_profile_sweeps_around_it(tmp_path, monkeypatch):
    from core.extraction import stages
    from tests.extraction.test_select import fake_run

    seen = []

    def sweep(fn, params_list, workers=None):
        seen.extend(params_list)
        return [{"error": "skipped in test"} for _ in params_list]

    monkeypatch.setattr(stages, "run_sweep", sweep)
    project, work = fake_run(tmp_path, {})
    stages.stage_extract(project, work.parent / "03_extract", 12, profile=PARAMS)
    assert seen[0] == PARAMS


def test_from_run_outside_the_projects_folder_is_refused(tmp_path):
    st = Storage(tmp_path)
    finished_run(st)
    # a finished-looking run outside projects/: "../evil" resolves to projects/../runs/evil
    import shutil

    shutil.copytree(st.projects_dir / "p" / "runs" / "r", st.projects_dir.parent / "runs" / "evil")
    for bad in ("../evil", "p/../r", "p/r/../../p/r", "/etc/r", "p/"):
        with pytest.raises(ProfileNotFound):
            save_profile(st, "x", bad)


def test_run_without_params_is_a_conflict(tmp_path):
    st = Storage(tmp_path)
    ref = finished_run(st)
    write_json(st.projects_dir / "p" / "runs" / "r" / "stages" / "05_validate" / "chosen.json", {"index": 0, "params": None})
    with pytest.raises(ProfileConflict):
        save_profile(st, "x", ref)
