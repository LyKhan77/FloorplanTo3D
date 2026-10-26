"""Stage 0 parameters (PRD/04 tahap 0): rule-based prompt parser; explicit form parameters always win."""

import re

KNOWN = ("wall_height", "door_height", "wall_thickness", "floor_name", "site_type", "mm_per_px", "use_strata")
_NUM = r"(\d+(?:[.,]\d+)?)"
_UNIT = r"\s*(mm|cm|m)\b"
_TO_MM = {"mm": 1, "cm": 10, "m": 1000}


def _mm(value: str, unit: str) -> int:
    return round(float(value.replace(",", ".")) * _TO_MM[unit.lower()])


def parse_prompt(prompt: str) -> dict:
    p = prompt.lower()
    out: dict = {}
    if m := re.search(rf"tinggi\s+pintu\s+{_NUM}{_UNIT}", p):
        out["door_height"] = _mm(m[1], m[2])
    if m := re.search(rf"tinggi(?:\s+dinding)?\s+{_NUM}{_UNIT}", p):  # "tinggi pintu …" has no number right after "tinggi"
        out["wall_height"] = _mm(m[1], m[2])
    if m := re.search(rf"tebal(?:\s+dinding)?\s+{_NUM}{_UNIT}", p):
        out["wall_thickness"] = _mm(m[1], m[2])
    if m := re.search(r"lantai\s+(\d+)", p):
        out["floor_name"] = f"Lantai {m[1]}"
    if re.search(r"data\s+(hall|cent(er|re))", p):
        out["site_type"] = "data_center"
    if m := re.search(rf"skala\s+{_NUM}\s*mm\s*/\s*px", p):
        out["mm_per_px"] = float(m[1].replace(",", "."))
    return out


def merge_params(explicit: dict, parsed: dict) -> dict:
    return {k: v for k, v in (parsed | explicit).items() if k in KNOWN}


def input_doc(upload: dict) -> dict:
    """input.json of stage 0 from the upload record (input/input.json written by the server)."""
    explicit = {k: v for k, v in (upload.get("params") or {}).items() if k in KNOWN}
    parsed = parse_prompt(upload.get("prompt") or "")
    return {"prompt": upload.get("prompt") or "", "params_explicit": explicit, "params_parsed": parsed,
            "params_final": merge_params(explicit, parsed), "sha256": upload["sha256"],
            "filename": upload["filename"], "page": upload.get("page") or 1}
