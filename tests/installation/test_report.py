from core.installation.report import write_installation_report

SUMMARY = {
    "version": 3, "layout_version": 7,
    "lengths": {"data": {"horizontal": 23382, "drops": 9689, "total": 33071}, "power": {"horizontal": 15019, "drops": 8486, "total": 23505}},
    "drops": [{"rack_id": "RK1", "tray_id": "T1", "tray_class": "data", "at": [0, 0], "to": [0, 300], "horizontal": 560, "vertical": 1600}],
    "issues": [{"code": "I006", "severity": "info", "element_ids": ["RK3"], "message": "RK3 tidak terhubung ke tray data"},
               {"code": "I003", "severity": "warning", "element_ids": ["T1", "W5"], "message": "T1 menembus dinding W5"}],
    "trays": [{"id": "T1", "tray_class": "data", "width": 200, "mounting": "overhead", "elevation": 3600, "length": 23382}],
    "racks": ["RK1", "RK3"],
}


def test_report_lists_lengths_and_unconnected_racks(tmp_path):
    html, pdf = write_installation_report(tmp_path, SUMMARY, {"top": "renders/top.png"}, project="Gatsu", pdf=False)
    text = html.read_text()
    assert "33.1" in text and "23.5" in text and "RK3" in text and "W5" in text and "renders/top.png" in text
    assert pdf is None


def test_equipment_schedule_counts_every_device(tmp_path):
    from core.installation.models import Installation, InstallMeta
    from core.installation.report import equipment_schedule
    from core.spec.models import PlacedObject

    obj = lambda i, t: PlacedObject(id=i, template_id=t, template_version="1.1.0", position=(0, 0, 0), dims=(1, 1, 1))
    inst = Installation(meta=InstallMeta(version=1, layout_version=1),
                        objects=[obj("RK1", "rack-42u-600x1200"), obj("RK2", "rack-42u-600x1200"), obj("O3", "ups-cabinet-generic")])
    sched = equipment_schedule(inst, {"rack-42u-600x1200": "rack", "ups-cabinet-generic": "power"})
    assert sched == [{"template_id": "rack-42u-600x1200", "category": "rack", "count": 2},
                     {"template_id": "ups-cabinet-generic", "category": "power", "count": 1}]
    html, _ = write_installation_report(tmp_path, {**SUMMARY, "equipment": sched}, {}, project="Gatsu", pdf=False)
    assert "ups-cabinet-generic" in html.read_text()
