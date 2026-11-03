"""installation_report.html / .pdf (M12b, design §6.9): tray lengths per class, trays, drops, unconnected racks, renders."""

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.report.render import TEMPLATES


def equipment_schedule(inst, templates: dict[str, str]) -> list[dict]:
    """Every device by template: [{template_id, category, count}], sorted by template id."""
    counts: dict[str, int] = {}
    for o in inst.objects:
        counts[o.template_id] = counts.get(o.template_id, 0) + 1
    return [{"template_id": t, "category": templates.get(t, "other"), "count": n} for t, n in sorted(counts.items())]


def write_installation_report(out_dir: Path, summary: dict, renders: dict[str, str], project: str,
                              pdf: bool = True) -> tuple[Path, Path | None]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
    html = out_dir / "installation_report.html"
    html.write_text(env.get_template("installation_report.html.j2").render(s=summary, renders=renders, project=project))
    shutil.copy(TEMPLATES / "report.css", out_dir / "report.css")
    if not pdf:
        return html, None
    from weasyprint import HTML  # needs pango; imported lazily

    out = out_dir / "installation_report.pdf"
    HTML(filename=str(html), base_url=str(out_dir)).write_pdf(str(out))
    return html, out
