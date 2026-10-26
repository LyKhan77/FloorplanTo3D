"""report.html (renders as relative files) and report.pdf via WeasyPrint (PRD/06 §7.3)."""

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).parent / "templates"


def write_report(out_dir: Path, data: dict, renders: dict[str, str]) -> tuple[Path, Path]:
    from weasyprint import HTML  # needs pango; imported lazily so the rest of core works without it

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
    env.tests["match"] = lambda value, prefix: str(value).startswith(prefix)
    html_path = out_dir / "report.html"
    html_path.write_text(env.get_template("report.html.j2").render(d=data, renders=renders))
    shutil.copy(TEMPLATES / "report.css", out_dir / "report.css")
    pdf_path = out_dir / "report.pdf"
    HTML(filename=str(html_path), base_url=str(out_dir)).write_pdf(str(pdf_path))
    return html_path, pdf_path
