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
