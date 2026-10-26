from pathlib import Path

from core.config import load_settings


def test_defaults_match_architecture_doc():
    s = load_settings({})
    assert s.data_dir == Path("./data")
    assert s.blender_render_device == "CPU"
    assert s.strata_base_url == "http://192.168.2.142:8081/v1"
    assert s.strata_model == "qwen3.8-flash-next-iq2_xs"
    assert s.strata_timeout_s == 120
    assert s.llm_tasks_enabled == ()
    assert (s.llm_max_iter, s.llm_votes) == (5, 3)
    assert (s.sweep_max_candidates, s.max_upload_mb) == (12, 50)


def test_overrides_are_parsed():
    s = load_settings({"STRATA_TIMEOUT_S": "30", "LLM_TASKS_ENABLED": "T1, T3", "DATA_DIR": "/x"})
    assert s.strata_timeout_s == 30
    assert s.llm_tasks_enabled == ("T1", "T3")
    assert s.data_dir == Path("/x")


def test_blender_bin_resolves_symlink(tmp_path):
    real = tmp_path / "Blender.app-bin"  # distinct name: macOS FS is case-insensitive
    real.write_text("#!/bin/sh\n")
    real.chmod(0o755)
    link = tmp_path / "blender"
    link.symlink_to(real)
    assert load_settings({"BLENDER_BIN": str(link)}).blender_bin == str(real.resolve())
