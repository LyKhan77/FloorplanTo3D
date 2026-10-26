import json

import pytest
from pydantic import ValidationError

from core.config import load_settings
from core.templates.make_placeholders import make_placeholders
from core.templates.model import TemplateMeta
from core.templates.registry import load_template
from core.templates.validate import validate_template
from tests.builder.helpers import skip_without_blender


def sample_meta(**overrides) -> dict:
    meta = {"id": "rack-42u-600x1200", "version": "1.0.0", "name": "Rack", "category": "rack",
            "dims": {"w": 600, "d": 1200, "h": 2000}, "pivot": "bottom_center", "front": "+y",
            "resizable": {"w": False, "d": {"min": 1000, "max": 1200, "step": 100}, "h": False},
            "scale_mode": "stretch", "snap": {"grid_mm": 600, "align": "edge"}}
    meta.update(overrides)
    return meta


@pytest.mark.blender
@skip_without_blender
def test_placeholders_generate_and_validate(tmp_path):
    paths = make_placeholders(tmp_path, load_settings().blender_bin)
    assert len(paths) == 7
    assert all(validate_template(p) == [] for p in paths), {p.parent.name: validate_template(p) for p in paths}
    meta, glb = load_template(tmp_path, "rack-42u-600x1200", "1.0.0")
    assert meta.dims.h == 2000 and meta.resizable.w is False and glb.name == "asset.glb"


@pytest.mark.blender
@skip_without_blender
def test_validate_catches_dims_mismatch(tmp_path):
    p = make_placeholders(tmp_path, load_settings().blender_bin)[0]
    meta = json.loads((p / "template.json").read_text())
    meta["dims"]["h"] = int(meta["dims"]["h"] * 1.2)
    meta["resizable"]["h"] = False
    (p / "template.json").write_text(json.dumps(meta))
    assert any("dims" in v for v in validate_template(p))


def test_template_meta_accepts_sample():
    assert TemplateMeta.model_validate(sample_meta()).dims.d == 1200


def test_template_meta_rejects_bad_resize_range():
    with pytest.raises(ValidationError):
        TemplateMeta.model_validate(sample_meta(resizable={"w": {"min": 700, "max": 900, "step": 50}, "d": False,
                                                           "h": False}))


def test_fixed_scale_mode_requires_no_resizable_axis():
    with pytest.raises(ValidationError):
        TemplateMeta.model_validate(sample_meta(scale_mode="fixed"))


def test_load_template_missing_returns_none(tmp_path):
    assert load_template(tmp_path, "nope", "1.0.0") is None
