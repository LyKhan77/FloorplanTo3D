import html as htmllib

from core.report.data import report_data
from core.report.overlay import render_overlay
from core.report.render import write_report
from tests.spec.fixtures import spec_with_rooms

SECTIONS = ["Ringkasan", "Denah asli & overlay", "Top view", "Isometrik", "Tabel ruang", "Jadwal pintu", "Tangga",
            "Ringkasan dinding", "Objek", "Render per ruang", "Peringatan & provenance", "Metadata"]


def test_report_has_all_sections_and_pdf(tmp_path):
    data = report_data(spec_with_rooms(), {"iou": 0.9, "status": "succeeded", "warnings": []}, {"run_id": "r1"})
    html, pdf = write_report(tmp_path, data, renders={})
    text = htmllib.unescape(html.read_text())
    assert all(f">{s}<" in text for s in SECTIONS), [s for s in SECTIONS if f">{s}<" not in text]
    assert "KIRI" in text and "r1" in text
    assert pdf.read_bytes().startswith(b"%PDF")


def test_door_schedule_rooms():
    data = report_data(spec_with_rooms(), None, {})
    d1 = next(d for d in data["doors"] if d["id"] == "D1")
    d2 = next(d for d in data["doors"] if d["id"] == "D2")
    assert (d1["rooms"], d2["rooms"]) == ("KIRI ↔ KANAN", "KIRI ↔ luar")


def test_summary_and_wall_totals():
    data = report_data(spec_with_rooms(), None, {})
    assert data["summary"]["n_rooms"] == 2 and data["summary"]["n_doors"] == 2
    assert data["summary"]["net_area_m2"] == round(2 * 4850 * 5800 / 1e6, 2)
    ext = next(w for w in data["walls"]["by_kind"] if w["kind"] == "exterior")
    assert ext["length_m"] == 32.0


def test_report_renders_with_empty_sections(tmp_path):
    s = spec_with_rooms().model_copy(update={"stairs": [], "objects": []})
    html, _ = write_report(tmp_path, report_data(s, None, {}), renders={})
    assert html.read_text().count("—") >= 3


def test_overlay_moved_without_behaviour_change():
    from benchmarks.tools import gt_author
    assert gt_author.render_overlay is render_overlay
