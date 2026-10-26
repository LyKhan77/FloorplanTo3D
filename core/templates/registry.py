"""Template registry on disk: <root>/<template_id>/<version>/{asset.glb, template.json, thumbnail.png}."""

from pathlib import Path

from pydantic import ValidationError

from core.templates.model import TemplateMeta


def load_template(root: Path, template_id: str, version: str) -> tuple[TemplateMeta, Path] | None:
    folder = Path(root) / template_id / version
    meta_file, glb = folder / "template.json", folder / "asset.glb"
    if not meta_file.exists() or not glb.exists():
        return None
    try:
        return TemplateMeta.model_validate_json(meta_file.read_text()), glb
    except ValidationError:
        return None
