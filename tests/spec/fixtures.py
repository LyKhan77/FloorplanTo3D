"""Shared spec fixtures: a 10 m x 6 m box with one partition, two doors and a corner column."""

from core.spec.models import Column, Grid, GridAxis, ImageInfo, Meta, Opening, Spec, Wall


def two_room_spec() -> Spec:
    return Spec(
        meta=Meta(
            project_id="test",
            version=1,
            created_at="2026-10-26T00:00:00+07:00",
            source="manual",
            floor_name="Test",
            site_type="data_hall",
            image=ImageInfo(sha256="0", width_px=1000, height_px=600),
            px_to_mm=[10, 0, 0, 0, -10, 6000],
            mm_per_px=10,
            scale_source="manual",
        ),
        grid=Grid(axes=[
            GridAxis(id="GA", label="A", orientation="vertical", offset=0),
            GridAxis(id="GB", label="B", orientation="vertical", offset=10000),
            GridAxis(id="G1", label="1", orientation="horizontal", offset=6000),
            GridAxis(id="G2", label="2", orientation="horizontal", offset=0),
        ]),
        walls=[
            Wall(id="W1", a=(0, 0), b=(10000, 0), thickness=200, kind="exterior"),
            Wall(id="W2", a=(10000, 0), b=(10000, 6000), thickness=200, kind="exterior"),
            Wall(id="W3", a=(10000, 6000), b=(0, 6000), thickness=200, kind="exterior"),
            Wall(id="W4", a=(0, 6000), b=(0, 0), thickness=200, kind="exterior"),
            Wall(id="W5", a=(5000, 0), b=(5000, 6000), thickness=100, kind="interior"),
        ],
        columns=[
            Column(id="C1", center=(0, 0), shape="rect", size=(200, 200), grid_ref=("GA", "G2")),
        ],
        openings=[
            Opening(id="D1", category="door", wall_id="W5", offset=2000, width=900,
                    door_type="single_swing", hinge="start", swing="left"),
            Opening(id="D2", category="door", wall_id="W1", offset=1000, width=1800,
                    door_type="double_swing", hinge="both", swing="left"),
        ],
    )


def spec_with_rooms() -> Spec:
    """Valid baseline: two_room_spec + the two rooms, with derived fields filled."""
    from core.spec.derive import derive
    from core.spec.models import Room

    rooms = [
        Room(id="R1", name="KIRI", type="office",
             polygon=[(100, 100), (4950, 100), (4950, 5900), (100, 5900)]),
        Room(id="R2", name="KANAN", type="storage",
             polygon=[(5050, 100), (9900, 100), (9900, 5900), (5050, 5900)]),
    ]
    return derive(two_room_spec().model_copy(update={"rooms": rooms}))
