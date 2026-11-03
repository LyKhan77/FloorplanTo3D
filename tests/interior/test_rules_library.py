import json

import pytest

from core.interior.library import layout_kind, load_library
from core.interior.rules import load_rules


def test_defaults_load():
    r = load_rules()
    assert (r.cold_aisle_mm, r.hot_aisle_mm, r.grid_mm, r.max_row_len) == (1200, 1000, 600, 12)
    assert "cctv-camera-bullet" in r.wall_mounted


def test_unknown_key_rejected(tmp_path):
    f = tmp_path / "r.yaml"
    f.write_text("colde_aisle_mm: 1200\n")
    with pytest.raises(ValueError):
        load_rules(f)


def test_library_newest_version(tmp_path, library_dir):
    lib = load_library(library_dir)
    assert lib["rack-42u-600x1200"].version == "1.1.0" and lib["rack-42u-600x1200"].front_clear == 1200
    old = library_dir / "rack-42u-600x1200" / "0.9.0"
    old.mkdir()
    (old / "template.json").write_text((library_dir / "rack-42u-600x1200" / "1.1.0" / "template.json").read_text()
                                       .replace('"1.1.0"', '"0.9.0"'))
    assert load_library(library_dir)["rack-42u-600x1200"].version == "1.1.0"
    assert json.loads((old / "template.json").read_text())["version"] == "0.9.0"


def test_layout_kind(library_dir):
    lib = load_library(library_dir)
    assert layout_kind(["rack-42u-600x1200", "pdu-floor-generic"], lib) == "rows"
    assert layout_kind(["ups-cabinet-generic", "battery-rack-generic"], lib) == "lineup"
    assert layout_kind(["network-rack-2post"], lib) == "rows"
    assert layout_kind(["inrow-cooler-300x1200"], lib) == "rows"
