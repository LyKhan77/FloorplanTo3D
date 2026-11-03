"""The calibration profile of the interior engine (rules.yaml)."""

from dataclasses import dataclass, fields
from pathlib import Path

import yaml

DEFAULT = Path(__file__).with_name("rules.yaml")


@dataclass(frozen=True)
class Rules:
    cold_aisle_mm: int
    hot_aisle_mm: int
    grid_mm: int
    row_end_clear_mm: int
    wall_clear_mm: int
    max_row_len: int
    door_clear_mm: int
    inrow_per_racks: int
    pdu_per_row: int
    crac_per_racks: int
    electrical_front_mm: int
    fm200_z_mm: int
    reader_z_mm: int
    cctv_below_ceiling_mm: int
    fire_cylinder_per_m2: int
    wall_mounted: tuple[str, ...]


def load_rules(path: Path | None = None) -> Rules:
    raw = yaml.safe_load(Path(path or DEFAULT).read_text()) or {}
    names = {f.name for f in fields(Rules)}
    if unknown := set(raw) - names:
        raise ValueError(f"unknown rule {', '.join(sorted(unknown))}")
    base = yaml.safe_load(DEFAULT.read_text())
    merged = {**base, **raw}  # a client profile may set only what differs
    merged["wall_mounted"] = tuple(merged["wall_mounted"])
    return Rules(**merged)
