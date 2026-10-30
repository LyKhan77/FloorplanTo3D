"""Stages 7-10 of an installation run (M12b): build, verify, report, publish to installation_outputs/v<M>."""

import json
import math
from pathlib import Path

from core.installation.build import InstallInvalid, install_build, install_publish
from core.installation.derive import mounting, rack_categories, racks, tray_elevation
from core.installation.store import InstallationStore
from core.spec.store import SpecStore

INSTALL_TIMEOUT_S = 900  # EEVEE renders of a whole floor take longer than the layout's Workbench


def _load(ctx):
    inst = InstallationStore(ctx.project_dir / "installations").load(ctx.version)
    specs = SpecStore(ctx.project_dir / "specs")
    return inst, specs.load(inst.meta.layout_version), specs.head()


def _build(ctx) -> dict:
    from server.orchestrator import _on_blender_line

    inst, layout, head = _load(ctx)
    templates = rack_categories(ctx.storage.templates_dir)
    try:
        doc, warnings = install_build(inst, layout, ctx.work_dir, ctx.storage.templates_dir, templates,
                                      ctx.settings.blender_install_engine, on_line=lambda line: _on_blender_line(ctx, line),
                                      on_start=ctx.register_process, timeout_s=INSTALL_TIMEOUT_S,
                                      blender_bin=ctx.settings.blender_bin, layout_head=head)
    except InstallInvalid as e:
        return {"status": "failed", "message": f"instalasi masih punya error: {e}"}
    ctx.state.update(inst=inst, layout=layout, templates=templates, doc=doc)
    return {"status": "succeeded", "warnings": warnings,
            "metrics": {"meshes": len(doc["meshes"]), "racks": len(doc["instances"])}}


def _verify(ctx) -> dict:
    """installation.glb holds one node per tray: the build lost no tray."""
    from pygltflib import GLTF2

    inst = ctx.state["inst"]
    summary = json.loads((ctx.work_dir / "installation.json").read_text())
    try:
        names = {n.name for n in GLTF2().load(str(ctx.work_dir / "installation.glb")).nodes if n.name}
    except Exception:  # noqa: BLE001 - an unreadable export is a failed check
        names = set()
    want = {f"tray_{t.tray_class}_{t.id}" for t in inst.cable_trays}
    ok = want <= names
    result = {"trays": len(want), "glb_ok": ok, "missing": sorted(want - names), "lengths": summary["lengths"],
              "drops": len(summary["drops"])}
    (ctx.work_dir / "verify.json").write_text(json.dumps(result, indent=2))
    return {"status": "succeeded" if ok else "failed", "metrics": {"trays": len(want), "glb_ok": ok},
            **({} if ok else {"message": f"tray hilang di installation.glb: {', '.join(result['missing'])}"})}


def _report(ctx) -> dict:
    from core.installation.report import write_installation_report

    inst, layout, templates = ctx.state["inst"], ctx.state["layout"], ctx.state["templates"]
    summary = json.loads((ctx.work_dir / "installation.json").read_text())
    summary["trays"] = [{"id": t.id, "tray_class": t.tray_class, "width": t.width, "mounting": mounting(t, inst.meta),
                         "elevation": tray_elevation(t, inst.meta, layout),
                         "length": round(sum(math.dist(a, b) for a, b in zip(t.path, t.path[1:], strict=False)))}
                        for t in inst.cable_trays]
    summary["racks"] = [r.id for r in racks(inst, layout, templates)]
    renders = {p.stem: f"renders/{p.name}" for p in sorted((ctx.work_dir / "renders").glob("*.png"))} \
        if (ctx.work_dir / "renders").exists() else {}
    project = json.loads((ctx.project_dir / "project.json").read_text()).get("name", ctx.pid)
    write_installation_report(ctx.work_dir, summary, renders, project)
    return {"status": "succeeded"}


def _publish(ctx) -> dict:
    out = install_publish(Path(ctx.work_dir), ctx.project_dir / "installation_outputs", ctx.version)
    files = sorted(p.name for p in out.iterdir() if p.is_file())
    return {"status": "succeeded", "metrics": {"files": len(files), "installation_version": ctx.version}}


INSTALL_IMPLS = {7: _build, 8: _verify, 9: _report, 10: _publish}
