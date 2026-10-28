"""Stage 6 (PRD/05 §5-6): Strata review of the stage-5 spec, skipped when disabled, switched off by the user,
without the run's stage 1-3 artefacts, or when Strata is down. Accepted ops are replayed on the stage-5
version with commit_ops, so an editor commit made during the review is never overwritten."""

import json
import logging
import math
import threading
import time
from collections.abc import Callable
from pathlib import Path

import cv2

from core.config import Settings
from core.extraction.rooms.labels import labels_from_ocr
from core.extraction.rooms.overlay import px_from_mm
from core.extraction.stages import validation_context
from core.llm_review.client import StrataClient
from core.llm_review.harness import ReviewInputs, run_review
from core.spec.store import SpecStore, ValidationFailed, VersionConflict

log = logging.getLogger(__name__)
REVIEW_TASKS = ("T1", "T2", "T3", "T4")
STAGE_LIMIT_S = 600
REASONS = {
    "disabled": "tidak ada tugas Strata yang aktif (LLM_TASKS_ENABLED)",
    "disabled_by_user": "Strata dimatikan untuk run ini",
    "no_artifacts": "artefak tahap 1-5 run ini tidak ada",
    "strata_unavailable": "Strata tidak tersedia (healthcheck gagal)",
}


def _skip(reason: str) -> dict:
    return {"status": "skipped", "message": REASONS[reason], "metrics": {"reason": reason}}


def _inputs(st: Path) -> ReviewInputs:
    grid = json.loads((st / "02_grid" / "grid.json").read_text())
    a, b, c, d, e, f = grid["px_to_mm"]
    ocr = json.loads((st / "02_grid" / "ocr.json").read_text()) if (st / "02_grid" / "ocr.json").exists() else []
    texts = []
    for t in ocr:
        x0, y0, x1, y1 = t["bbox"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        texts.append({"text": t["text"], "cls": t.get("cls", "other"), "at_mm": (a * cx + b * cy + c, d * cx + e * cy + f)})
    hatch_path = st / "03_extract" / "masks" / "hatch.png"
    return ReviewInputs(
        page=cv2.imread(str(st / "01_preprocess" / "page.png"), cv2.IMREAD_GRAYSCALE),
        to_px=px_from_mm(grid["px_to_mm"]), mm_per_px=math.hypot(a, d), texts=texts,
        hatch=cv2.imread(str(hatch_path), cv2.IMREAD_GRAYSCALE) if hatch_path.exists() else None,
        labels=[(lb.name, tuple(lb.at)) for lb in labels_from_ocr(ocr, grid["px_to_mm"])],
        vctx=validation_context(st))


def stage_review(project_dir: Path, work: Path, run_id: str, settings: Settings, *, version: int | None,
                 use_strata: bool, client=None, emit: Callable[[str, dict], None] | None = None,
                 progress: Callable[[int, str], None] | None = None,
                 clock: Callable[[], float] = time.monotonic, cancelled: threading.Event | None = None) -> dict:
    tasks = {t for t in settings.llm_tasks_enabled if t in REVIEW_TASKS}
    if not tasks:
        return _skip("disabled")
    if not use_strata:
        return _skip("disabled_by_user")
    st = work.parent
    if version is None or not (st / "01_preprocess" / "page.png").exists() or not (st / "02_grid" / "grid.json").exists():
        return _skip("no_artifacts")
    client = client or StrataClient.from_settings(settings)
    if not client.health():
        return _skip("strata_unavailable")
    if progress:
        progress(5, f"review Strata: {', '.join(sorted(tasks))}")
    store = SpecStore(project_dir / "specs")
    try:
        result = run_review(store.load(version), _inputs(st), client, tasks=tasks, votes=settings.llm_votes,
                            max_iter=settings.llm_max_iter, deadline=clock() + STAGE_LIMIT_S, out=work,
                            version=version, clock=clock, emit=emit, cancelled=cancelled)
    except Exception as e:  # the review is optional: the run goes on with the stage-5 spec
        log.exception("stage 6 review failed")
        return {"status": "succeeded", "metrics": {"saved": False},
                "warnings": [f"review Strata gagal ({type(e).__name__}: {e}); spec tahap 5 dipakai"],
                "message": "review Strata gagal; spec tahap 5 dipakai"}
    decided = result.decisions
    metrics = {"reviewed": len({(d["task"], d["element"]) for d in decided}),
               "accepted": sum(d["decision"] == "accepted" for d in decided),
               "rejected": sum(d["decision"] == "rejected" for d in decided),
               "calls": result.calls, "invalid": result.invalid,
               "score_before": round(result.score_before, 4), "score_after": round(result.score_after, 4)}
    warnings = []
    if result.timed_out:
        warnings.append("batas waktu tahap 6 tercapai; hasil sejauh ini dipakai")
    if result.aborted:
        warnings.append("Strata berhenti merespons; review dihentikan, hasil sejauh ini dipakai")
    if result.cancelled:
        warnings.append("run dibatalkan; perubahan Strata tidak disimpan")
    elif result.ops:
        metrics["saved"] = False
        try:  # the spec the gates scored, not a replay of its ops (a replay rebuilds rooms once, not per change)
            saved = store.save_on(version, result.spec, "llm", run_id, f"review Strata: {metrics['accepted']} perubahan")
            metrics.update(version=saved.meta.version, saved=True)
        except VersionConflict:
            warnings.append("HEAD berubah selama review; perubahan Strata tidak disimpan")
        except ValidationFailed as e:
            warnings.append("spec hasil review gagal validasi: " + ", ".join(sorted({i.code for i in e.issues})))
    if progress:
        progress(100, "selesai")
    return {"status": "succeeded", "metrics": metrics, "warnings": warnings,
            "message": f"{metrics['accepted']} perubahan diterima dari {metrics['reviewed']} elemen"}
