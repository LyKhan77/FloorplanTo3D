import pytest

from core.blender_run import run_blender
from core.pipeline import BuildFailed, outputs_complete, publish, stage_build
from tests.spec.fixtures import spec_with_rooms


def test_publish_atomic_and_replaces(tmp_path):
    work = tmp_path / "work"
    (work / "renders").mkdir(parents=True)
    for f in ("shell.glb", "layout.blend", "report.html"):
        (work / f).write_text(f)
    (work / "renders" / "top.png").write_text("png")
    (work / "blender.log").write_text("log")
    (tmp_path / "outputs" / "v3.tmp").mkdir(parents=True)  # orphan from a crash
    (tmp_path / "outputs" / "v3").mkdir()
    (tmp_path / "outputs" / "v3" / "stale.txt").write_text("old")
    out = publish(work, tmp_path / "outputs", 3)
    assert out == tmp_path / "outputs" / "v3" and outputs_complete(out)
    assert (out / "renders" / "top.png").exists() and not (out / "blender.log").exists()
    assert not (out / "stale.txt").exists() and not (tmp_path / "outputs" / "v3.tmp").exists()
    assert (work / "shell.glb").exists()  # run artifacts stay viewable


def test_outputs_complete_requires_core_files(tmp_path):
    (tmp_path / "shell.glb").write_text("x")
    assert not outputs_complete(tmp_path)


def test_stage_build_raises_with_log_on_failure(tmp_path):
    with pytest.raises(BuildFailed) as e:
        stage_build(spec_with_rooms(), tmp_path, None, None, "BLENDER_WORKBENCH", blender_bin="/usr/bin/false")
    assert e.value.exit_code == 1 and e.value.log.exists()
    assert (tmp_path / "build_input.json").exists()


def test_run_blender_reports_process_to_on_start(tmp_path):
    seen = []
    run_blender(tmp_path / "x.json", tmp_path, "/usr/bin/true", on_start=seen.append)
    assert len(seen) == 1 and seen[0].pid > 0
