import pytest
from pydantic import ValidationError

from core.installation.models import CableTray, Installation, InstallMeta


def test_tray_defaults():
    t = CableTray(id="T1", path=[(0, 0), (1000, 0)], tray_class="data")
    assert (t.width, t.side_height, t.mounting, t.elevation, t.flow, t.tray_type) == (200, 100, None, None, "forward", "perforated")
    assert CableTray(id="T2", path=[(0, 0), (1000, 0)], tray_class="power").width == 400


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        CableTray(id="T1", path=[(0, 0), (1000, 0)], tray_class="data", colour="red")


def test_empty_installation_round_trips():
    inst = Installation(meta=InstallMeta(version=1, layout_version=20))
    assert inst.cable_trays == [] and inst.objects == [] and inst.meta.default_mounting == "overhead"
    assert Installation.model_validate_json(inst.model_dump_json()) == inst
