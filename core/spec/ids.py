"""Stable element IDs: never reuse a deleted ID (PRD/03 §1, meta.id_seq)."""

import re

from core.spec.models import Spec


def take_id(spec: Spec, prefix: str) -> str:
    """Allocate the next ID for `prefix`, mutating spec.meta.id_seq."""
    used = [int(m[1]) for eid in spec.all_ids() if (m := re.fullmatch(rf"{prefix}(\d+)", eid))]
    n = max([spec.meta.id_seq.get(prefix, 0), *used]) + 1
    spec.meta.id_seq[prefix] = n
    return f"{prefix}{n}"


def next_id(spec: Spec, prefix: str) -> tuple[str, Spec]:
    s = spec.model_copy(deep=True)
    return take_id(s, prefix), s
