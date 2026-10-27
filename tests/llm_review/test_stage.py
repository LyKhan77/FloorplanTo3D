import dataclasses
import json

import cv2
import numpy as np
import pytest

from core.config import load_settings
from core.llm_review.stage import stage_review
from core.spec.store import SpecStore
from tests.llm_review.conftest import FakeStrata, element_of
from tests.llm_review.test_harness import review_spec


def settings(tasks=("T1",)):
    return dataclasses.replace(load_settings({}), llm_tasks_enabled=tasks)


@pytest.fixture
def run_dir(tmp_path):
    """A project with HEAD v1 and the stage 1-3 artefacts stage 6 reads."""
    project = tmp_path / "proj"
    st = project / "runs" / "rid" / "stages"
    for d in ("01_preprocess", "02_grid", "03_extract/masks"):
        (st / d).mkdir(parents=True)
    cv2.imwrite(str(st / "01_preprocess" / "page.png"), np.full((600, 1000), 255, np.uint8))
    (st / "02_grid" / "grid.json").write_text(json.dumps({"px_to_mm": [10, 0, 0, 0, -10, 6000], "axes": []}))
    (st / "02_grid" / "ocr.json").write_text("[]")
    (st / "03_extract" / "candidates.json").write_text(json.dumps([{"index": 0, "line_len_m": 0}]))
    SpecStore(project / "specs").save_new(review_spec(), "pipeline", "rid", "stage 5")
    return project, st / "06_review"


def w6_annotation(messages, kw):
    el = element_of(messages)
    return {"id": el, "verdict": "annotation" if el == "W6" else "wall"}


def review(run_dir, **kw):
    project, work = run_dir
    args = {"settings": settings(), "version": 1, "use_strata": True, "client": FakeStrata(w6_annotation)} | kw
    return stage_review(project, work, "rid", **args)


def test_skipped_when_no_tasks_enabled(run_dir):
    r = review(run_dir, settings=settings(()))
    assert r["status"] == "skipped" and r["metrics"]["reason"] == "disabled"
    assert review(run_dir, settings=settings(("T0",)))["metrics"]["reason"] == "disabled"  # T0 runs in stage 0


def test_skipped_when_user_turned_strata_off(run_dir):
    assert review(run_dir, use_strata=False)["metrics"]["reason"] == "disabled_by_user"


def test_skipped_when_strata_down(run_dir):
    r = review(run_dir, client=FakeStrata(w6_annotation, healthy=False))
    assert r["status"] == "skipped" and r["metrics"]["reason"] == "strata_unavailable"


def test_skipped_without_artifacts(run_dir):
    _, work = run_dir
    assert review(run_dir, version=None)["metrics"]["reason"] == "no_artifacts"
    (work.parent / "01_preprocess" / "page.png").unlink()  # a from_stage=6 run without stages 1-5
    assert review(run_dir)["metrics"]["reason"] == "no_artifacts"


def test_accepted_ops_saved_as_llm_version(run_dir):
    project, work = run_dir
    events = []
    r = review(run_dir, emit=lambda t, d: events.append(t))
    assert r["status"] == "succeeded" and r["metrics"]["version"] == 2 and r["metrics"]["accepted"] == 1
    s = SpecStore(project / "specs").load(2)
    assert s.meta.source == "llm" and s.meta.run_id == "rid" and s.meta.parent_version == 1
    assert all(w.id != "W6" for w in s.walls)
    assert (work / "decisions.json").exists() and (work / "transcript.jsonl").exists()
    assert events and set(events) == {"llm.decision"}


def test_nothing_accepted_saves_nothing(run_dir):
    project, _ = run_dir
    r = review(run_dir, client=FakeStrata(lambda m, kw: {"id": element_of(m), "verdict": "wall"}))
    assert r["status"] == "succeeded" and "version" not in r["metrics"] and SpecStore(project / "specs").head() == 1


def test_head_moved_during_review_keeps_editor_work(run_dir):
    project, _ = run_dir
    store = SpecStore(project / "specs")

    def editor_commits_first(messages, kw):
        if store.head() == 1:
            store.commit_ops(1, [{"op": "rename_room", "id": "R2", "name": "GUDANG"}], "editor")
        return w6_annotation(messages, kw)

    r = review(run_dir, client=FakeStrata(editor_commits_first))
    assert store.head() == 2 and store.load(2).meta.source == "editor"
    assert r["status"] == "succeeded" and "version" not in r["metrics"]
    assert any("HEAD berubah" in w for w in r["warnings"])


def test_deadline_warning(run_dir):
    r = review(run_dir, clock=iter([0] + [10_000] * 50).__next__)
    assert any("batas waktu" in w for w in r["warnings"])


# --- final review fixes ---------------------------------------------------------------------------------------------

def test_harness_exception_never_fails_the_stage(run_dir):
    project, _ = run_dir

    def boom(messages, kw):
        raise RuntimeError("unexpected")

    class Exploding(FakeStrata):
        def ask_json(self, *a, **kw):
            raise RuntimeError("unexpected")

    r = review(run_dir, client=Exploding(boom))
    assert r["status"] == "succeeded" and any("review Strata gagal" in w for w in r["warnings"])
    assert SpecStore(project / "specs").head() == 1


def test_saved_version_is_the_spec_the_gates_scored(run_dir, monkeypatch):
    """The gates scored result.spec; replaying the ops in one apply() can rebuild rooms differently."""
    import core.llm_review.stage as stage_mod
    from core.llm_review.harness import ReviewResult

    project, _ = run_dir
    gated = review_spec()
    gated.rooms[0].name = "GATED"
    monkeypatch.setattr(stage_mod, "run_review", lambda *a, **kw: ReviewResult(
        gated, [{"op": "rename_room", "id": "R1", "name": "REPLAYED"}], 0.97, 0.98,
        [{"element": "R1", "task": "T3", "decision": "accepted"}]))
    r = review(run_dir)
    saved = SpecStore(project / "specs").load(2)
    assert r["metrics"]["version"] == 2 and saved.rooms[0].name == "GATED" and saved.meta.source == "llm"


def test_discarded_changes_are_reported_unsaved(run_dir):
    project, _ = run_dir
    store = SpecStore(project / "specs")

    def editor_commits_first(messages, kw):
        if store.head() == 1:
            store.commit_ops(1, [{"op": "rename_room", "id": "R2", "name": "GUDANG"}], "editor")
        return w6_annotation(messages, kw)

    r = review(run_dir, client=FakeStrata(editor_commits_first))
    assert r["metrics"]["saved"] is False
    assert review(run_dir, version=2)["metrics"]["saved"] is True  # a fresh review of HEAD v2 saves v3


def test_cancelled_review_commits_nothing(run_dir):
    import threading

    project, _ = run_dir
    cancel = threading.Event()
    cancel.set()
    r = review(run_dir, cancelled=cancel)
    assert SpecStore(project / "specs").head() == 1 and "version" not in r["metrics"]
