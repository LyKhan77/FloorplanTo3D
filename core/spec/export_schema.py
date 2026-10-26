"""Export JSON Schemas for the layout spec and ops. Run: uv run python -m core.spec.export_schema"""

import json
from pathlib import Path

from pydantic import TypeAdapter

from core.spec.models import Spec
from core.spec.ops import SpecOp

OUT_DIR = Path("schema")


def _draft7_tuples(node):
    """json-schema-to-typescript only understands draft-07 tuples (`items: [...]`), not `prefixItems`."""
    if isinstance(node, dict):
        out = {k: _draft7_tuples(v) for k, v in node.items() if k != "prefixItems"}
        if "prefixItems" in node:
            out["items"] = _draft7_tuples(node["prefixItems"])
        return out
    if isinstance(node, list):
        return [_draft7_tuples(v) for v in node]
    return node


def build_schemas() -> dict[str, dict]:
    """Canonical JSON Schema 2020-12 files, plus ts/ copies converted for TypeScript generation."""
    canonical = {
        "layout-spec.schema.json": Spec.model_json_schema(),
        "spec-ops.schema.json": TypeAdapter(list[SpecOp]).json_schema(),
    }
    return canonical | {f"ts/{name}": _draft7_tuples(schema) for name, schema in canonical.items()}


def main() -> None:
    for name, schema in build_schemas().items():
        (OUT_DIR / name).parent.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / name).write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        print(f"wrote {OUT_DIR / name}")


if __name__ == "__main__":
    main()
