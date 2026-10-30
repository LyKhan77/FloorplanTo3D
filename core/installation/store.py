"""Installation versions on disk (design §5.1): installations/installation.vN.json + HEAD, like the layout's specs/."""

from datetime import datetime
from typing import Literal

from core.installation.models import Installation, InstallMeta
from core.installation.ops import apply
from core.installation.validate import validate_installation
from core.spec.models import ProvenanceLogEntry, Spec
from core.spec.store import SpecStore, ValidationFailed, VersionConflict
from core.spec.validate import Issue


class InstallationStore(SpecStore):
    """SpecStore's lock, atomic write and HEAD handling, for installation documents."""

    def versions(self) -> list[int]:
        head = self.head() or 0
        return [v for v in range(1, head + 1) if (self.dir / f"installation.v{v}.json").exists()]

    def load(self, version: int | Literal["HEAD"]) -> Installation:
        v = self.head() if version == "HEAD" else version
        if v is None:
            raise FileNotFoundError(f"no installation in {self.dir}")
        return Installation.model_validate_json((self.dir / f"installation.v{v}.json").read_text())

    def _save(self, inst: Installation, source: str, message: str) -> Installation:
        head = self.head()
        s = inst.model_copy(deep=True)
        s.meta.version, s.meta.parent_version = (head or 0) + 1, head
        s.meta.created_at, s.meta.source, s.meta.message = datetime.now().astimezone(), source, message
        if message:
            s.provenance_log.append(ProvenanceLogEntry(op="commit", by=source, reason=message))
        s = Installation.model_validate(s.model_dump())
        self._write(f"installation.v{s.meta.version}.json", s.model_dump_json(indent=2))
        self._write("HEAD", f"{s.meta.version}\n")  # only after the file exists
        return s

    def start(self, layout_version: int, ceiling_height: int | None, raised_floor_height: int | None,
              default_mounting: str) -> Installation:
        with self._locked():
            if self.head() is not None:
                raise FileExistsError(f"installation already started in {self.dir}")
            meta = InstallMeta(layout_version=layout_version, ceiling_height=ceiling_height,
                               raised_floor_height=raised_floor_height, default_mounting=default_mounting)
            return self._save(Installation(meta=meta), "editor", "mulai instalasi")

    def commit_ops(self, base_version: int, ops: list[dict], by: str, message: str, layout: Spec,
                   templates: dict[str, str], layout_head: int | None = None) -> tuple[Installation, list[Issue]]:
        with self._locked():
            head = self.head()
            if base_version != head:
                raise VersionConflict(base_version, head)
            new = apply(self.load(head), ops, by, version=head + 1)
            issues = validate_installation(new, layout, templates, layout_head)
            if any(i.severity == "error" for i in issues):
                raise ValidationFailed(issues)
            return self._save(new, by if by != "llm" else "editor", message), issues

    def rebase(self, layout_version: int, layout: Spec, templates: dict[str, str],
               previous: Spec | None = None) -> tuple[Installation, list[Issue]]:
        """Move onto a newer layout version. Always saves: the errors it brings are fixed in the installation.
        `previous` (the layout it was on) names the layout racks the new version no longer has (I008)."""
        with self._locked():
            inst = self.load("HEAD")
            inst.meta.layout_version = layout_version
            inst.provenance_log = []
            saved = self._save(inst, "editor", f"rebase ke layout v{layout_version}")
            issues = validate_installation(saved, layout, templates)
            if previous is not None:
                kept = {o.id for o in layout.objects}
                issues += [Issue("I008", "warning", [o.id], f"rack {o.id} tidak ada lagi di layout v{layout_version}")
                           for o in previous.objects if templates.get(o.template_id) == "rack" and o.id not in kept]
            return saved, issues
