from core.extraction.params import input_doc, merge_params, parse_prompt


def test_parse_prompt_units():
    assert parse_prompt("Tinggi dinding 4,5 m, lantai 2, data hall") == {
        "wall_height": 4500, "floor_name": "Lantai 2", "site_type": "data_center"}
    assert parse_prompt("tinggi 450 cm") == {"wall_height": 4500}
    assert parse_prompt("tinggi pintu 2100 mm") == {"door_height": 2100}
    assert parse_prompt("tebal dinding 150mm") == {"wall_thickness": 150}
    assert parse_prompt("skala 25.8 mm/px") == {"mm_per_px": 25.8}
    assert parse_prompt("DATA CENTER lantai 3") == {"site_type": "data_center", "floor_name": "Lantai 3"}
    assert parse_prompt("") == {}


def test_explicit_params_win():
    assert merge_params({"wall_height": 3000, "junk": 1}, {"wall_height": 4500, "floor_name": "Lantai 2"}) == {
        "wall_height": 3000, "floor_name": "Lantai 2"}


def test_input_doc_shape():
    doc = input_doc({"filename": "plan.jpeg", "sha256": "ab", "prompt": "tinggi 4 m", "params": {"mm_per_px": 25},
                     "page": None, "type": "jpg"})
    assert doc == {"prompt": "tinggi 4 m", "params_explicit": {"mm_per_px": 25}, "params_parsed": {"wall_height": 4000},
                   "params_final": {"mm_per_px": 25, "wall_height": 4000}, "sha256": "ab", "filename": "plan.jpeg",
                   "page": 1}


def _project(tmp_path, prompt: str, params: dict):
    import json

    (tmp_path / "input").mkdir()
    (tmp_path / "input" / "input.json").write_text(json.dumps(
        {"prompt": prompt, "params": params, "sha256": "0", "filename": "plan.jpeg"}))
    return tmp_path


def test_llm_params_fill_only_empty_fields(tmp_path):
    import json

    from core.extraction.stages import run_params

    project = _project(tmp_path, "tinggi 4.5 m", {"door_height": 2400})
    stages = tmp_path / "stages"
    (stages / "00_input").mkdir(parents=True)
    (stages / "00_input" / "input.json").write_text(json.dumps(
        {"params_parsed_llm": {"wall_height": 5000, "floor_name": "Lantai 1", "door_height": 2100}}))
    p = run_params(project, stages=stages)
    assert p["wall_height"] == 4500 and p["floor_name"] == "Lantai 1" and p["door_height"] == 2400
    assert "floor_name" not in run_params(project)  # without the stage-0 record only the rule parser counts


def test_stage_input_records_llm_params(tmp_path):
    import json

    from core.extraction.stages import stage_input

    project = _project(tmp_path, "data hall lantai satu", {})
    work = tmp_path / "stages" / "00_input"
    stage_input(project, work, llm_parse=lambda prompt: {"floor_name": "Lantai 1", "site_type": "data_hall"})
    doc = json.loads((work / "input.json").read_text())
    assert doc["params_parsed_llm"] == {"floor_name": "Lantai 1", "site_type": "data_hall"}
    assert doc["params_final"]["floor_name"] == "Lantai 1" and doc["params_final"]["site_type"] == "data_center"
    stage_input(project, work)
    assert json.loads((work / "input.json").read_text())["params_parsed_llm"] is None
