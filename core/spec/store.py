"""Append-only spec versions on disk (PRD/02 §4): specs/spec.vN.json + HEAD."""

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from core.spec.models import ProvenanceLogEntry, Spec
from core.spec.ops import apply
from core.spec.validate import Issue, ValidationResult, validate


class VersionConflict(Exception):
    def __init__(self, base: int, head: int | None):
        super().__init__(f"base_version {base} is not HEAD ({head})")
        self.base, self.head = base, head


class ValidationFailed(Exception):
    def __init__(self, issues: list[Issue]):
        super().__init__(f"{sum(i.severity == 'error' for i in issues)} validation error(s)")
        self.issues = issues


class SpecStore:
    def __init__(self, specs_dir: Path):
        self.dir = Path(specs_dir)

    def head(self) -> int | None:
        f = self.dir / "HEAD"
        return int(f.read_text().strip()) if f.exists() else None

    def versions(self) -> list[int]:
        # Only versions <= HEAD count; an orphan file from a crash before HEAD is ignored and overwritten.
        head = self.head() or 0
        return [v for v in range(1, head + 1) if (self.dir / f"spec.v{v}.json").exists()]

    def load(self, version: int | Literal["HEAD"]) -> Spec:
        v = self.head() if version == "HEAD" else version
        if v is None:
            raise FileNotFoundError(f"no spec versions in {self.dir}")
        return Spec.model_validate_json((self.dir / f"spec.v{v}.json").read_text())

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _write(self, name: str, text: str) -> None:
        tmp = self.dir / f".{name}.tmp"
        tmp.write_text(text)
        os.replace(tmp, self.dir / name)

    def _save_unlocked(self, spec: Spec, source: str, run_id: str | None, message: str) -> Spec:
        head = self.head()
        s = spec.model_copy(deep=True)
        s.meta.version = (head or 0) + 1
        s.meta.parent_version = head
        s.meta.created_at = datetime.now().astimezone()
        s.meta.source = source
        s.meta.run_id = run_id
        if message:
            s.provenance_log.append(ProvenanceLogEntry(op="commit", by=source, reason=message))
        s = Spec.model_validate(s.model_dump())
        result = validate(s)
        if not result.passed:
            raise ValidationFailed(result.issues)
        self._write(f"spec.v{s.meta.version}.json", s.model_dump_json(indent=2))
        self._write("HEAD", f"{s.meta.version}\n")  # only after the spec file exists
        return s

    def save_new(self, spec: Spec, source: str, run_id: str | None = None, message: str = "") -> Spec:
        with self._locked():
            return self._save_unlocked(spec, source, run_id, message)

    def commit_ops(self, base_version: int, ops: list[dict], by: str, message: str = "") -> tuple[Spec, ValidationResult]:
        with self._locked():
            head = self.head()
            if base_version != head:
                raise VersionConflict(base_version, head)
            new = apply(self.load(head), ops, by, version=head + 1)
            saved = self._save_unlocked(new, by, None, message)
            return saved, validate(saved)
