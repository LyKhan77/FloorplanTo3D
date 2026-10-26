"""Stable element IDs: never reuse a deleted ID (PRD/03 §1, meta.id_seq)."""

import re

from core.spec.models import Spec


def seed_id_seq(spec: Spec) -> None:
    """Raise id_seq to the highest existing number per prefix, so deleting the top ID never frees it."""
    for eid in spec.all_ids():
        if m := re.fullmatch(r"([A-Z]+)(\d+)", eid):
            spec.meta.id_seq[m[1]] = max(spec.meta.id_seq.get(m[1], 0), int(m[2]))


def take_id(spec: Spec, prefix: str) -> str:
    """Allocate the next ID for `prefix`, mutating spec.meta.id_seq."""
    used = [int(m[1]) for eid in spec.all_ids() if (m := re.fullmatch(rf"{prefix}(\d+)", eid))]
    n = max([spec.meta.id_seq.get(prefix, 0), *used]) + 1
    spec.meta.id_seq[prefix] = n
    return f"{prefix}{n}"


def next_id(spec: Spec, prefix: str) -> tuple[str, Spec]:
    s = spec.model_copy(deep=True)
    return take_id(s, prefix), s
