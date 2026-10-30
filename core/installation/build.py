"""Installation build (M12b, design §6.7): one Blender build of the layout plus the installation, exported apart from
the layout's own outputs (installation_outputs/v<M>)."""

import copy
import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from core.blender_run import run_blender
from core.build_prep.assemble import _instances, build_input_for
from core.build_prep.perforation import write_perforation_png
from core.build_prep.schema import MATERIALS
from core.installation.derive import drops, lengths
from core.installation.geometry import floor_drop, installation_items
from core.installation.models import Installation
from core.installation.validate import validate_installation
from core.spec.models import Spec
from core.spec.validate import Issue

TRAY_COLOR = "#B8BCC2"
INSTALL_MATERIALS = {
    "tray_galv": {"color": TRAY_COLOR, "roughness": 0.4, "alpha": 1.0, "metallic": 0.8},
    "tray_edge_data": {"color": "#33B1FF", "roughness": 0.5, "alpha": 1.0},
    "tray_edge_power": {"color": "#FF832B", "roughness": 0.5, "alpha": 1.0},
    "hanger": {"color": "#7A7F85", "roughness": 0.5, "alpha": 1.0, "metallic": 0.6},
    "ceiling": {"color": "#F2F2F2", "roughness": 0.9, "alpha": 0.25},
    "raised_floor": {"color": "#C6C6C6", "roughness": 0.7, "alpha": 0.35},
}
EXPORTS = [
    {"file": "installation.glb", "collections": ["Installation"]},
    {"file": "layout_installation.glb", "collections": ["Shell", "Objects", "Installation", "RaisedFloor", "Ceiling"]},  # the viewer hides the ceiling by default
    {"file": "installation.blend", "collections": []},
]
OUTPUT_FILES = ("installation.glb", "layout_installation.glb", "installation.blend", "installation.json",
                "installation_report.html", "installation_report.pdf", "report.css", "verify.json")
DOC_CAMERAS = ("cam_top", "cam_iso_ne", "cam_iso_nw", "cam_iso_se", "cam_iso_sw")


class InstallInvalid(Exception):
    def __init__(self, issues: list[Issue]):
        super().__init__(", ".join(sorted({i.code for i in issues if i.severity == "error"})))
        self.issues = issues


class InstallBuildFailed(Exception):
    def __init__(self, rc: int, log: Path):
        super().__init__(f"blender failed (exit {rc}); log: {log}")


def installation_build_input(inst: Installation, layout: Spec, templates_root: Path | None, templates: dict[str, str],
                             work: Path, engine: str) -> tuple[dict, list[str]]:
    doc, warnings = build_input_for(layout, templates_root, None, engine)
    dz = floor_drop(layout, inst)
    if dz:  # the structural slab and room floors sit under the raised floor panels in this build only
        for m in doc["meshes"]:
            if m["collection"] == "Floors":
                m["verts"] = [[x, y, z + dz] for x, y, z in m["verts"]]
    meshes, cutters = installation_items(inst, layout, templates)
    doc["meshes"] += meshes
    doc["cutters"] += cutters
    racks, rack_warnings = _instances(layout.model_copy(update={"objects": inst.objects}), templates_root)
    for r in racks:
        r["name"], r["collection"] = r["name"].replace("obj_", "rack_", 1), "Racks"
        r["props"] |= {"spec_type": "rack", "spec_version": inst.meta.version}
    doc["instances"] += racks
    warnings += rack_warnings
    png = write_perforation_png(Path(work) / "perforation.png", TRAY_COLOR)
    doc["materials"] = MATERIALS | copy.deepcopy(INSTALL_MATERIALS)
    doc["materials"]["tray_galv"]["texture"] = str(png.resolve())
    cams = [c | {"hide": ["Ceiling"]} for c in doc["cameras"] if c["name"] in DOC_CAMERAS]
    if inst.meta.raised_floor_height:
        iso = next(c for c in cams if c["name"] == "cam_iso_ne")
        cams.append(iso | {"name": "cam_underfloor", "output": "renders/underfloor.png", "hide": ["Ceiling", "RaisedFloor"]})
    doc["cameras"] = cams
    doc["exports"] = EXPORTS
    doc["installation_version"] = inst.meta.version
    return doc, warnings


def install_build(inst: Installation, layout: Spec, work: Path, templates_root: Path | None, templates: dict[str, str],
                  engine: str, on_line: Callable[[str], None] | None = None, on_start: Callable | None = None,
                  timeout_s: int = 600, blender_bin: str | None = None, layout_head: int | None = None) -> tuple[dict, list[str]]:
    """Stage 7 of an installation run. Refused while the installation has errors (InstallInvalid)."""
    from core.config import load_settings

    issues = validate_installation(inst, layout, templates, layout_head)
    if any(i.severity == "error" for i in issues):
        raise InstallInvalid(issues)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    doc, warnings = installation_build_input(inst, layout, templates_root, templates, work, engine)
    (work / "build_input.json").write_text(json.dumps(doc))
    (work / "installation.json").write_text(json.dumps(
        {"version": inst.meta.version, "layout_version": inst.meta.layout_version,
         "lengths": lengths(inst, layout, templates), "drops": drops(inst, layout, templates),
         "issues": [vars(i) for i in issues]}, indent=2))
    rc = run_blender(work / "build_input.json", work, blender_bin or load_settings().blender_bin, timeout_s, on_line, on_start)
    if rc != 0:
        raise InstallBuildFailed(rc, work / "blender.log")
    return doc, warnings


def install_publish(work: Path, root: Path, version: int) -> Path:
    """Stage 10: copy the deliverables to installation_outputs/v<M> atomically; the layout's outputs/ is never touched."""
    root.mkdir(parents=True, exist_ok=True)
    final, tmp = root / f"v{version}", root / f"v{version}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    for name in OUTPUT_FILES:
        if (work / name).exists():
            shutil.copy2(work / name, tmp / name)
    if (work / "renders").exists():
        shutil.copytree(work / "renders", tmp / "renders")
    if final.exists():
        shutil.rmtree(final)
    os.rename(tmp, final)
    return final
