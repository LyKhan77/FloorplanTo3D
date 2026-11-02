import pytest

from core.templates.lowpoly import MATERIALS, parts
from core.templates.make_placeholders import PLACEHOLDERS


@pytest.mark.parametrize(("tid", "dims"), [(t[0], t[1]) for t in PLACEHOLDERS])
def test_parts_fill_the_template_box_exactly(tid, dims):
    """The validator compares the GLB bbox with template.json dims: the parts must span them, never exceed them."""
    w, d, h = dims
    ps = parts(tid, dims)
    lo = [min(p.box[i] for p in ps) for i in (0, 2, 4)]
    hi = [max(p.box[i] for p in ps) for i in (1, 3, 5)]
    assert lo == pytest.approx([-w / 2, -d / 2, 0]) and hi == pytest.approx([w / 2, d / 2, h])
    assert len(ps) >= 6 and all(p.material in MATERIALS for p in ps)


@pytest.mark.parametrize("tid", [t[0] for t in PLACEHOLDERS])
def test_low_poly_budget(tid):
    dims = next(t[1] for t in PLACEHOLDERS if t[0] == tid)
    from core.templates.lowpoly import meshes

    tris = sum(len(f) - 2 for m in meshes(parts(tid, dims)).values() for f in m["faces"])
    assert 60 <= tris <= 3000
