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


def test_strata_api_key_is_read_and_never_printed():
    """The DGX Strata server (2026-10-28) rejects chat calls without a bearer key."""
    assert load_settings({}).strata_api_key == ""
    s = load_settings({"STRATA_API_KEY": "sk-test-123"})
    assert s.strata_api_key == "sk-test-123"
    assert "sk-test-123" not in repr(s)


def test_response_format_can_be_switched_off():
    """DGX Strata: json_schema decoding is ~6x slower; the output is still validated by pydantic."""
    assert load_settings({}).strata_response_format is True
    assert load_settings({"STRATA_RESPONSE_FORMAT": "0"}).strata_response_format is False
    from core.llm_review.client import StrataClient

    assert StrataClient.from_settings(load_settings({"STRATA_RESPONSE_FORMAT": "0"})).use_response_format is False
