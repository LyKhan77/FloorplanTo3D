# M1 — Spec & Ground Truth Gatsu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kontrak data final (model spec, ops, validator, penyimpanan berversi, skema TS) dan ground truth Gatsu yang terverifikasi sebagai data uji untuk M2–M5.

**Architecture:** Paket `core/spec/` berisi model Pydantic murni, fungsi turunan, pembentukan ruang (Shapely), `apply(spec, ops)` yang murni, validator V001–V019, dan `SpecStore` append-only di filesystem. GT ditulis sebagai YAML ringkas berbasis grid. `gt_author` mengubahnya menjadi `gt_spec.json` lewat jalur kode yang sama (ruang dibentuk otomatis dari dinding), lalu menggambar overlay di atas `plan.jpeg` untuk verifikasi visual.

**Tech Stack:** Python 3.12, Pydantic v2, Shapely 2, NumPy, OpenCV, PyYAML, pytest + pytest-cov; `json-schema-to-typescript` (npm, devDependency `web/`).

**Spec:** `PRD/03-layout-spec.md` (otoritas utama), `PRD/04-extraction.md` Tahap 4 dan §5.4b, `PRD/02-architecture.md` §4, `ROADMAP.md` M1. Branch dasar: `m0-foundation`.

## Global Constraints

- Semua perintah shell diawali `rtk`. Python lewat `uv run` (`--env-file .env` bila menyentuh Blender/WeasyPrint).
- Jangan membaca atau meng-commit `server-info.txt`.
- Kerja di branch baru `m1-spec-gt`, dibuat dari `m0-foundation`.
- Satuan panjang **mm integer**, dibulatkan ke 1 mm. Sudut dalam derajat, CCW, 0° = +X. +X timur, +Y utara, +Z atas.
- Origin = perpotongan grid vertikal pertama dan grid horizontal terakhir (Gatsu: **A × 3**). Gatsu: A=0, B=6000, C=12000, D=16000, E=22000, F=28000; 3=0, 2=6000, 1=12000.
- Poligon: titik `[x, y]` **CCW** tanpa titik penutup duplikat. `holes`: **CW**.
- Prefiks ID: `W` dinding, `C` kolom, `D` pintu, `N` jendela, `R` ruang, `S` tangga, `O` objek, `G` grid. ID stabil antar-versi, dan ID yang dihapus tidak dipakai ulang.
- `schema_version: "1.0"`. Model memakai `extra="forbid"`.
- Default `meta.defaults`: `wall_height 3000, wall_thickness 150, door_height 2100, window_sill 900, window_height 1200, floor_to_floor 4000`.
- Bobot skor validator persis seperti `03` §12. Skor = `1 − Σ(bobot × rasio_pelanggaran)`, dibatasi ke [0, 1]. Ada `error` berarti tidak lolos.
- `meta.condition` hanya `"existing"`.
- Builder (M2) tidak mengimpor `core/`. Tidak ada kode Blender di M1.

## Review Focus

1. **Ops tidak valid di tengah daftar** (ID tidak ada, parameter salah). Harus `OpError` dengan indeks op, dan spec input tidak berubah (atomik). Ditest di Task 4: `test_apply_is_atomic_on_bad_op`.
2. **Save basi atau crash di tengah tulis.** `base_version ≠ HEAD` harus `VersionConflict` tanpa file baru. `HEAD` tidak pernah menunjuk file yang belum ada. Ditest di Task 6: `test_stale_base_rejected_no_write`, `test_head_written_after_spec`.
3. **Menghapus dinding yang punya bukaan.** Bukaan ikut terhapus, sehingga tidak ada `wall_id` menggantung (V002). Ditest di Task 4: `test_delete_wall_cascades_openings`.
4. **Edit dinding yang membuka atau menggabung ruang.** Nama dan tipe ruang yang bertahan diwarisi lewat IoU ≥ 0.5. Tidak crash bila tidak ada area interior. Ditest di Task 3: `test_reconcile_keeps_names_after_partition_removed`, `test_form_rooms_empty_when_open`.
5. **Input dari editor berupa float dan arah poligon terbalik.** Dibulatkan ke mm integer, dan poligon dinormalisasi (CCW, holes CW). Ditest di Task 1: `test_float_mm_rounded`, `test_polygon_orientation_normalized`.

---

### Task 1: Model spec Pydantic + dokumen skema

**Files:**
- Create: `core/spec/__init__.py`, `core/spec/models.py`
- Modify: `pyproject.toml` (tambah `pydantic`, `shapely`, `pyyaml`; dev `pytest-cov`), `PRD/03-layout-spec.md` (prefiks `S` di tabel ID §1; field `meta.id_seq` di §3)
- Test: `tests/spec/__init__.py`, `tests/spec/fixtures.py`, `tests/spec/test_models.py`

**Interfaces:**
- Produces (`core.spec.models`):
  - `Mm = Annotated[int, BeforeValidator(round_mm)]`; `Point = tuple[Mm, Mm]`; `Polygon = list[Point]`.
  - Model: `Provenance`, `Defaults`, `ImageInfo`, `Meta`, `GridAxis`, `Grid`, `Wall`, `Column`, `Opening`, `Room`, `Flight`, `Stair`, `PlacedObject`, `ProvenanceLogEntry`, `Spec`. Field, tipe, enum, dan default persis `03` §3–§10 dan §8b.
  - Tambahan di luar dokumen (ditulis ke `03`): `Meta.id_seq: dict[str, int] = {}`, yaitu nomor terakhir yang pernah dipakai per prefiks.
  - `Provenance` default: `source="manual", confidence=1.0, changed_in=0`.
  - Field turunan punya default kosong: `area_m2=0`, `perimeter_m=0`, `bounding_walls=[]`, `doors=[]`, `room_id=None`, `gross_area_m2=0`.
  - Helper: `Spec.all_ids() -> list[str]`; `Grid.axis(label) -> GridAxis`; `Grid.point(ref: str) -> tuple[int, int]` (mis. `"A3"` → `(0, 0)`, label vertikal dulu lalu horizontal).
- `tests/spec/fixtures.py`: `two_room_spec() -> Spec`. Kotak 10000 × 6000. Dinding exterior t=200: W1 (0,0)→(10000,0), W2 (10000,0)→(10000,6000), W3 (10000,6000)→(0,6000), W4 (0,6000)→(0,0). Partisi W5 (5000,0)→(5000,6000) t=100 `interior`. Pintu D1 di W5 offset 2000 lebar 900 `single_swing`. Pintu D2 di W1 offset 1000 lebar 1800 `double_swing`. Kolom C1 di (0,0) `rect` 200×200 `grid_ref ["GA","G2"]` (seluruhnya di dalam sudut dinding, jadi tidak menonjol keluar dan tidak memotong ruang). Grid GA x=0, GB x=10000, G1 y=6000, G2 y=0. `px_to_mm [10,0,0,0,-10,6000]`. Ruang belum diisi (dibentuk Task 3).

- [ ] **Step 1: Branch + dependencies**

```bash
rtk git checkout -b m1-spec-gt m0-foundation
rtk uv add pydantic shapely pyyaml && rtk uv add --dev pytest-cov
```

- [ ] **Step 2: Tulis test yang gagal** (`tests/spec/test_models.py`)

```python
def test_fixture_roundtrips_json():
    s = two_room_spec()
    assert Spec.model_validate_json(s.model_dump_json()) == s

def test_float_mm_rounded():
    w = Wall(id="W9", a=(0.4, 10.6), b=(1000.5, 10), thickness=149.6, kind="interior")
    assert w.a == (0, 11) and w.thickness == 150   # round half to even: 1000.5 -> 1000
    assert w.b == (1000, 10)

def test_polygon_orientation_normalized():
    cw = [(0, 0), (0, 1000), (1000, 1000), (1000, 0), (0, 0)]       # CW + duplicate closing point
    r = Room(id="R9", polygon=cw, holes=[[(100, 100), (200, 100), (200, 200), (100, 200)]])  # CCW hole
    assert r.polygon == [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]  # CCW, start at original first point
    assert signed_area(r.holes[0]) < 0                                # CW

def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Wall(id="W9", a=(0, 0), b=(1, 0), thickness=100, kind="interior", colour="red")

def test_grid_point_from_ref():
    assert two_room_spec().grid.point("B1") == (10000, 6000)   # labels: vertical "B", horizontal "1"
```
`signed_area` diekspor dari `core.spec.models`.

- [ ] **Step 3: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/spec/test_models.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'core.spec'`

- [ ] **Step 4: Implement `core/spec/models.py`**

- `round_mm(v)`: float → `round(v)` (banker's rounding bawaan Python), int dibiarkan, tipe lain diteruskan ke Pydantic.
- Normalisasi poligon di `field_validator` milik `Room.polygon`/`Room.holes` dan `Meta.building_outline`. Langkahnya: buang titik penutup duplikat, lalu balik urutan bila arahnya salah. Rotasi titik awal tidak diubah.
- `signed_area(poly) -> float` (shoelace, positif = CCW).
- `Grid.point(ref)`: pisahkan ref menjadi label vertikal (huruf) dan label horizontal (angka), lalu kembalikan `(offset_vertikal, offset_horizontal)`. Label tidak dikenal → `KeyError`.

- [ ] **Step 5: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/spec -q`
Expected: 5 PASS

- [ ] **Step 6: Update `PRD/03-layout-spec.md`, lalu commit**

Di §1 baris ID, tambah `` `S` tangga ``. Di §3, tambah baris `` | `id_seq` | object | Nomor terakhir yang pernah dipakai per prefiks ID (`{"W": 41, ...}`), agar ID yang dihapus tidak dipakai ulang. Dikelola core. | ``.

```bash
rtk git add -A core/spec tests/spec pyproject.toml uv.lock PRD/03-layout-spec.md
rtk git commit -m "feat(spec): pydantic layout spec models"
```

---

### Task 2: Field turunan + metrik tangga

**Files:**
- Create: `core/spec/derive.py`
- Test: `tests/spec/test_derive.py`

**Interfaces:**
- Consumes: model Task 1.
- Produces (`core.spec.derive`):
  - `wall_footprint(wall: Wall, spec: Spec) -> shapely.Polygon`. Garis tengah di-buffer `t/2` dengan `cap_style="flat"`, `join_style="mitre"`. Sebelum buffer, setiap ujung yang **terhubung** diperpanjang `t/2`, agar sudut L tertutup tanpa takik. Ujung terhubung = jarak ≤ `t/2` ke garis tengah dinding lain atau ke tapak kolom. Ujung bebas tidak diperpanjang.
  - `column_footprint(col: Column) -> shapely.Polygon` (rect/h_section = persegi `size` terotasi; circle = `buffer(d/2, 24)`).
  - `endpoint_connected(spec: Spec, wall: Wall, end: Literal["a","b"]) -> bool`. Dipakai ulang oleh V004.
  - `stair_metrics(stair: Stair, defaults: Defaults) -> list[FlightMetrics]`, dengan `FlightMetrics(riser_mm: float, tread_mm: float, start_z: float, end_z: float)`. Tinggi tanjakan = (`top_z` atau `floor_to_floor` − `base_z`) / Σrisers. Kedalaman injakan = panjang flight / risers. Flight ke-i mulai di ketinggian kumulatif.
  - `derive(spec: Spec) -> Spec` (salinan baru). Mengisi:
    - per ruang: `area_m2` (luas `polygon` − `holes`, /1e6, round 2), `perimeter_m` (keliling luar /1000, round 2), `bounding_walls` (dinding yang tapaknya berjarak ≤ 1 mm dari poligon ruang, terurut ID), `doors` (bukaan `door` yang `wall_id`-nya ada di `bounding_walls`, terurut ID);
    - `objects[].room_id` (ruang yang memuat pivot);
    - `stairs[].room_id` (ruang yang memuat titik tengah flight pertama);
    - `meta.gross_area_m2` (Σ luas `building_outline`, round 2).

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_l_corner_footprints_close_outer_corner():
    s = two_room_spec()
    u = unary_union([wall_footprint(w, s) for w in s.walls])
    assert u.envelope.bounds == (-100, -100, 10100, 6100)   # no notch at outer corners
    assert Polygon(u.exterior).area == pytest.approx(10200 * 6200)

def test_free_end_not_extended():
    s = two_room_spec()
    stub = Wall(id="W9", a=(2000, 3000), b=(3000, 3000), thickness=100, kind="partition", free_ends=True)
    s = s.model_copy(update={"walls": [*s.walls, stub]})
    assert wall_footprint(stub, s).bounds == (2000, 2950, 3000, 3050)

def test_room_derived_fields():
    s = derive(spec_with_rooms())          # helper in fixtures: two_room_spec + rooms R1 (left), R2 (right) with C1 hole none
    r1 = next(r for r in s.rooms if r.id == "R1")
    assert r1.area_m2 == pytest.approx(round(4850 * 5800 / 1e6, 2))  # inner faces: x 100..4950, y 100..5900
    assert r1.bounding_walls == ["W1", "W3", "W4", "W5"]
    assert r1.doors == ["D1", "D2"]

def test_area_subtracts_holes():
    room = Room(id="R9", polygon=[(0, 0), (2000, 0), (2000, 2000), (0, 2000)],
                holes=[[(500, 500), (500, 900), (900, 900), (900, 500)]])
    s = derive(two_room_spec().model_copy(update={"rooms": [room]}))
    assert s.rooms[0].area_m2 == pytest.approx(4.0 - 0.16)

def test_stair_metrics_two_flights():
    st = Stair(id="S1", flights=[Flight(start=(0, 0), end=(0, 3300), width=1100, risers=12),
                                 Flight(start=(1500, 3300), end=(1500, 0), width=1100, risers=12)])
    m = stair_metrics(st, Defaults())
    assert m[0].riser_mm == pytest.approx(4000 / 24) and m[0].tread_mm == pytest.approx(275)
    assert (m[1].start_z, m[1].end_z) == pytest.approx((2000, 4000))
```
Tambah ke `tests/spec/fixtures.py`: `spec_with_rooms()` = `derive(two_room_spec() + rooms)`, dengan R1 `[(100,100),(4950,100),(4950,5900),(100,5900)]` (nama "KIRI", tipe `office`) dan R2 `[(5050,100),(9900,100),(9900,5900),(5050,5900)]` (nama "KANAN", tipe `storage`). Fixture ini menjadi spec valid acuan untuk Task 4–6.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/spec/test_derive.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'core.spec.derive'`

- [ ] **Step 3: Implement `core/spec/derive.py`** sesuai Interfaces. Shapely 2 (`shapely.geometry`, `shapely.ops.unary_union`).

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/spec -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/spec/derive.py tests/spec && rtk git commit -m "feat(spec): derived fields, wall footprints, stair metrics"
```

---

### Task 3: Pembentukan ruang + rekonsiliasi ID

**Files:**
- Create: `core/spec/rooms.py`, `core/spec/ids.py`
- Test: `tests/spec/test_rooms.py`, `tests/spec/test_ids.py`

**Interfaces:**
- Consumes: `wall_footprint`, `column_footprint`, `derive` (Task 2).
- Produces:
  - `core.spec.ids.next_id(spec: Spec, prefix: str) -> tuple[str, Spec]`. Mengembalikan ID baru (`max(id_seq[prefix], nomor terbesar yang ada) + 1`) dan spec dengan `id_seq` yang sudah diperbarui.
  - `core.spec.rooms.form_rooms(spec: Spec) -> tuple[list[shapely.Polygon], list[shapely.Polygon]]` = (poligon ruang dengan holes, outline per massa), sesuai `04` Tahap 4 langkah 1–3 dan 2b:
    1. U = union tapak dinding + tapak kolom (bukaan tidak memotong);
    2. outline = `Polygon(part.exterior)` per bagian U;
    3. interior = union(outline) − U, lalu dipecah per poligon;
    4. buang luas < 1 m² dan rasio aspek `minimum_rotated_rectangle` > 20.
  - `core.spec.rooms.rebuild_rooms(spec: Spec, labels: list[RoomLabel] | None = None) -> Spec`, dengan `RoomLabel(at: Point, name: str, type: str)`. Langkah:
    1. bentuk ruang;
    2. untuk tiap poligon baru, warisi ID dari ruang lama yang cocok (aturan pewarisan di bawah), setiap ruang lama paling banyak sekali; label yang titiknya ada di dalam poligon menimpa nama dan tipe; poligon tanpa pasangan mendapat ID baru via `next_id` dengan nama `""` dan tipe `"other"` (kecuali ada label);
    3. poligon baru tanpa ID diurut (−cy, cx) sebelum diberi ID;
    4. set `meta.building_outline`;
    5. panggil `derive`.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_form_rooms_two_rooms():
    rooms, outlines = form_rooms(two_room_spec())
    assert len(rooms) == 2 and len(outlines) == 1
    assert [round(r.area / 1e6, 2) for r in rooms] == [round(4850 * 5800 / 1e6, 2)] * 2

def test_form_rooms_column_inside_becomes_hole():
    s = two_room_spec()
    s.columns.append(Column(id="C2", center=(2500, 3000), shape="rect", size=(400, 400)))
    rooms, _ = form_rooms(s)
    assert any(len(r.interiors) == 1 for r in rooms)

def test_form_rooms_empty_when_open():
    s = two_room_spec()
    s = s.model_copy(update={"walls": [w for w in s.walls if w.id != "W3"]})
    rooms, outlines = form_rooms(s)
    assert rooms == []          # U-shape encloses nothing; no exception

def test_rebuild_assigns_labels_and_outline():
    s = rebuild_rooms(two_room_spec(), [RoomLabel(at=(2500, 3000), name="R. MEETING", type="meeting")])
    left = next(r for r in s.rooms if r.name == "R. MEETING")
    assert left.type == "meeting" and s.meta.gross_area_m2 == pytest.approx(10.2 * 6.2, abs=0.005)
    assert [r.id for r in s.rooms] == ["R1", "R2"] and s.meta.id_seq["R"] == 2

def test_reconcile_keeps_names_after_partition_removed():
    s = rebuild_rooms(two_room_spec(), [RoomLabel(at=(2500, 3000), name="A", type="office"),
                                         RoomLabel(at=(7500, 3000), name="B", type="storage")])
    s2 = rebuild_rooms(s.model_copy(update={"walls": [w for w in s.walls if w.id != "W5"]}))
    assert len(s2.rooms) == 1 and (s2.rooms[0].id, s2.rooms[0].name) == ("R1", "A")
```
Aturan pewarisan (keputusan plan; ditulis juga ke `04` §5.4b): ruang lama cocok bila IoU ≥ 0.5 **atau** ≥ 90% luasnya tercakup poligon baru. Bila ada beberapa yang cocok, pilih IoU tertinggi, lalu ID terkecil. Pada kasus gabung di atas, IoU kiri ≈ 0.495, tetapi kedua ruang lama 100% tercakup. IoU keduanya sama, jadi ID terkecil (R1, "A") yang menang.

```python
# tests/spec/test_ids.py
def test_next_id_never_reuses_deleted():
    s = two_room_spec().model_copy(deep=True)
    s.meta.id_seq["W"] = 7                     # W6, W7 existed and were deleted
    nid, s2 = next_id(s, "W")
    assert nid == "W8" and s2.meta.id_seq["W"] == 8 and s.meta.id_seq["W"] == 7
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/spec/test_rooms.py tests/spec/test_ids.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `ids.py` dan `rooms.py`** sesuai Interfaces. Konversi Shapely ke `Room`: `polygon = list(exterior.coords)[:-1]`, `holes = [list(i.coords)[:-1] for i in interiors]`. Validator model Task 1 menormalkan arah dan pembulatan.

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/spec -q`
Expected: semua PASS

- [ ] **Step 5: Catat aturan containment di `PRD/04-extraction.md` §5.4b**, lalu commit

Tambahkan di bullet pencocokan ruang: "atau ≥ 90% luas ruang lama tercakup ruang baru (kasus gabung); bila beberapa cocok, pilih IoU tertinggi, lalu ID terkecil".

```bash
rtk git add core/spec tests/spec PRD/04-extraction.md && rtk git commit -m "feat(spec): room formation and id reconciliation"
```

---

### Task 4: Ops + `apply`

**Files:**
- Create: `core/spec/ops.py`
- Test: `tests/spec/test_ops.py`

**Interfaces:**
- Consumes: `next_id` (Task 3), `rebuild_rooms` (Task 3), `derive` (Task 2).
- Produces (`core.spec.ops`):
  - Satu model Pydantic per op di `03` §11, dengan diskriminator `op`. Daftar op: `add_object`, `update_object`, `delete_object`, `set_wall_height`, `set_default`, `rename_room`, `set_room_type`, `delete_wall`, `merge_walls`, `split_wall`, `move_wall`, `add_wall`, `set_door`, `delete_opening`, `add_opening`, `set_stair`, `delete_stair`, `add_stair`. Union: `SpecOp = Annotated[Union[...], Field(discriminator="op")]`. Op dengan `reason` mewajibkan string non-kosong.
  - `OpError(Exception)` dengan atribut `index: int`, `op: str`, `message: str`.
  - `apply(spec: Spec, ops: list[SpecOp], by: Literal["editor","llm","manual","pipeline"], version: int) -> Spec`. Murni dan atomik (bekerja pada `deep copy`). Untuk setiap elemen yang dibuat/diubah: `provenance = Provenance(source=by if by != "pipeline" else "cv", confidence=1.0 bila editor/manual, changed_in=version)`. Setiap op ditambahkan ke `provenance_log` sebagai `{op, id, by, reason}`. Bila ada op dinding atau kolom, panggil `rebuild_rooms` sekali di akhir. Selalu `derive` di akhir.
  - Semantik yang tidak tertulis di `03`:
    - `delete_wall` menghapus juga bukaan di dinding itu (dicatat di log);
    - `split_wall at_offset` membuat dinding kedua dengan ID baru; bukaan dipindah sesuai posisinya; bukaan yang melintasi titik pisah → `OpError`;
    - `merge_walls ids` hanya untuk dinding sejajar (±1.5°) dengan offset tegak lurus ≤ tebal maksimum; hasilnya memakai ID terkecil dengan ujung = proyeksi ekstrem; offset bukaan dihitung ulang;
    - `set_wall_height "*"` berlaku untuk semua dinding (int atau `null`);
    - `set_default key` harus field `Defaults`;
    - `add_object`/`update_object` tidak memeriksa batas template (itu V016).

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_add_wall_gets_new_id_and_provenance():
    s = apply(spec_with_rooms(), [{"op": "add_wall", "a": (2500, 100), "b": (2500, 5900), "thickness": 100, "kind": "partition"}], "editor", 2)
    w = s.walls[-1]
    assert w.id == "W6" and w.provenance.source == "editor" and w.provenance.changed_in == 2
    assert len(s.rooms) == 3          # rooms rebuilt

def test_apply_is_atomic_on_bad_op():
    base = spec_with_rooms()
    before = base.model_dump()
    with pytest.raises(OpError) as e:
        apply(base, [{"op": "rename_room", "id": "R1", "name": "X"}, {"op": "delete_wall", "id": "W99", "reason": "x"}], "editor", 2)
    assert e.value.index == 1 and base.model_dump() == before

def test_delete_wall_cascades_openings():
    s = apply(spec_with_rooms(), [{"op": "delete_wall", "id": "W5", "reason": "bukan dinding"}], "editor", 2)
    assert all(o.wall_id != "W5" for o in s.openings) and "D1" not in [o.id for o in s.openings]

def test_split_wall_moves_openings():
    s = apply(spec_with_rooms(), [{"op": "split_wall", "id": "W1", "at_offset": 5000}], "manual", 2)
    w_new = s.walls[-1]
    assert w_new.a == (5000, 0) and next(o for o in s.openings if o.id == "D2").wall_id == "W1"

def test_split_through_opening_rejected():
    with pytest.raises(OpError):
        apply(spec_with_rooms(), [{"op": "split_wall", "id": "W1", "at_offset": 1500}], "manual", 2)

def test_set_wall_height_star_null_resets_all():
    s = apply(spec_with_rooms(), [{"op": "set_wall_height", "id": "W1", "height": 4500},
                                  {"op": "set_wall_height", "id": "*", "height": None}], "editor", 2)
    assert all(w.height is None for w in s.walls)

def test_set_door_offset_and_width():
    s = apply(spec_with_rooms(), [{"op": "set_door", "id": "D1", "offset": 2500, "width": 1000}], "editor", 2)
    d = next(o for o in s.openings if o.id == "D1")
    assert (d.offset, d.width) == (2500, 1000)

def test_add_object_room_id_derived():
    s = apply(spec_with_rooms(), [{"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.0.0",
                                   "position": (2000, 2000, 0), "rotation": 0, "dims": (600, 1200, 2000)}], "editor", 2)
    assert s.objects[0].id == "O1" and s.objects[0].room_id == "R1"

def test_stair_flip_via_set_stair():
    base = spec_with_rooms().model_copy(update={"stairs": [Stair(id="S1", flights=[Flight(start=(1000, 1000), end=(1000, 4000), width=1000, risers=12)])]})
    s = apply(base, [{"op": "set_stair", "id": "S1", "flights": [{"start": (1000, 4000), "end": (1000, 1000), "width": 1000, "risers": 12}]}], "editor", 2)
    assert s.stairs[0].flights[0].start == (1000, 4000)
```
Ops diberikan sebagai dict, lalu `apply` memvalidasinya dengan `TypeAdapter(list[SpecOp])`. Kegagalan skema → `OpError` dengan indeks yang benar.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/spec/test_ops.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `core/spec/ops.py`.** Satu fungsi handler per op dalam dict `HANDLERS: dict[str, Callable[[Spec, SpecOp, Ctx], None]]`, yang memutasi salinan kerja. Validasi skema per item agar indeks error akurat.

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/spec -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/spec/ops.py tests/spec/test_ops.py && rtk git commit -m "feat(spec): ops and pure atomic apply"
```

---

### Task 5: Validator V001–V019 + skor

**Files:**
- Create: `core/spec/validate.py`
- Test: `tests/spec/test_validate.py`

**Interfaces:**
- Consumes: `endpoint_connected`, `wall_footprint`, `column_footprint`, `stair_metrics` (Task 2).
- Produces (`core.spec.validate`):
  - `Issue(code: str, severity: Literal["error","warning","info"], element_ids: list[str], message: str)`.
  - `ValidationContext(ocr_dimensions: list[tuple[str, str, int]] | None = None, thick_line_length_mm: float | None = None, templates: dict[str, TemplateLimits] | None = None)`. `ocr_dimensions` = `(label_sumbu_a, label_sumbu_b, mm)`. `TemplateLimits(min: tuple[int,int,int], max: tuple[int,int,int])`, dengan key `"<template_id>@<version>"`.
  - `ValidationResult(score: float, passed: bool, issues: list[Issue], ratios: dict[str, float])`.
  - `validate(spec: Spec, ctx: ValidationContext | None = None) -> ValidationResult`.
  - `WEIGHTS: dict[str, float]`, persis `03` §12. Jumlah bobot harus 1.00.
- Penyebut `rasio_pelanggaran` per aturan:
  - dinding untuk V003–V007;
  - pintu untuk V010;
  - ruang ≥ 4 m² untuk V012;
  - kolom ber-`grid_ref` untuk V014;
  - objek untuk V016–V017;
  - pasangan dimensi OCR untuk V013;
  - V015: `max(0, 0.7 − named_ratio) / 0.7`;
  - V018: 1 bila Σpanjang dinding < 0.6 × estimasi, selain itu 0.
  - Penyebut 0 → rasio 0.
  - Aturan yang butuh konteks (V013, V018, dan batas dimensi V016) dilewati bila konteksnya `None`, dengan rasio 0.
- Detail aturan yang tidak tertulis eksplisit di `03`:
  - V004 terhubung juga ke tapak kolom (`endpoint_connected`);
  - V006 mengukur sudut dinding mod 90° terhadap sumbu (grid axis-aligned);
  - V007 = pasangan sejajar (±1.5°) dengan jarak tegak lurus < tebal maksimum / 2 dan overlap proyeksi > 50% dinding terpendek;
  - V001 = `px_to_mm` 6 angka dengan determinan `a·e − b·d ≠ 0`.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_valid_fixture_scores_one():
    r = validate(spec_with_rooms())
    assert r.passed and r.score == pytest.approx(1.0) and r.issues == []

def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)

@pytest.mark.parametrize("code,mutate,severity", CASES)   # one negative case per rule, table below
def test_rule_flags_violation(code, mutate, severity):
    r = validate(mutate(spec_with_rooms()), CTX)
    assert any(i.code == code and i.severity == severity for i in r.issues)
    assert r.passed == (severity != "error")
```
`CTX = ValidationContext(ocr_dimensions=[("A","B",10000)], thick_line_length_mm=40000, templates={"rack@1.0.0": TemplateLimits((600,1000,1800),(800,1400,2400))})`. Kasus positif sudah dicakup `test_valid_fixture_scores_one` dengan konteks yang sama. Tambah satu `test_valid_fixture_scores_one_with_ctx`.

Tabel `CASES` (mutasi pada salinan `spec_with_rooms()`):

| Kode | Mutasi | Severity |
|---|---|---|
| V001 | `meta.px_to_mm = [0,0,0,0,0,0]` | error |
| V002 | `openings[0].wall_id = "W99"` | error |
| V003 | tambah dinding 50 mm `free_ends=True` di (2000,3000) | warning |
| V004 | tambah dinding (2000,2000)→(3000,2000) tanpa `free_ends` | warning |
| V005 | `walls[0].thickness = 700` | warning |
| V006 | `walls[4].b = (5200, 6000)` + `allow_skew=False` | warning |
| V007 | duplikat W5 dengan ID W9 | warning |
| V008 | `D2.offset = 9000` | error |
| V009 | tambah D9 = salinan D1 (W5, lebar 900) dengan offset 2400, sehingga tumpang tindih D1 (2000–2900) | error |
| V010 | `D1.width = 500` | warning |
| V011 | `rooms[0].polygon` bowtie `[(0,0),(1000,1000),(1000,0),(0,1000)]` | error |
| V012 | hapus D1 dan D2 | warning |
| V013 | `ctx.ocr_dimensions=[("A","B",9000)]` | warning |
| V014 | `columns[0].center = (300, 0)` | warning |
| V015 | semua `rooms[].name = ""` | warning |
| V016 | objek `rack@1.0.0` dims (600,1200,3000) di R1 | warning |
| V017 | objek di (5000, 3000) menembus W5 | info |
| V018 | `ctx.thick_line_length_mm = 200000` | warning |
| V019 | tangga di R1 dengan 1 flight 1000 mm `risers=4` (injakan 250, tanjakan 1000) | warning |

Untuk mutasi yang butuh ruang dihitung ulang, jangan panggil `rebuild_rooms` (validator memeriksa spec apa adanya), tetapi panggil `derive`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/spec/test_validate.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `validate.py`.** Satu fungsi per aturan `rule_vNNN(spec, ctx) -> tuple[list[Issue], float]` (issues, rasio), didaftarkan di `RULES` berurutan. Validasi poligon V011 memakai `shapely.Polygon.is_valid`.

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/spec -q`
Expected: semua PASS (≥ 21 test validator)

- [ ] **Step 5: Commit**

```bash
rtk git add core/spec/validate.py tests/spec/test_validate.py && rtk git commit -m "feat(spec): validator V001-V019 with score"
```

---

### Task 6: `SpecStore` append-only

**Files:**
- Create: `core/spec/store.py`
- Test: `tests/spec/test_store.py`

**Interfaces:**
- Consumes: `apply` (Task 4), `validate` (Task 5).
- Produces (`core.spec.store`):
  - `VersionConflict(Exception)` dengan atribut `base: int`, `head: int | None`.
  - `ValidationFailed(Exception)` dengan atribut `issues: list[Issue]`.
  - `SpecStore(specs_dir: Path)`, yaitu folder `projects/<id>/specs/` (`02` §4).
    - `head() -> int | None`
    - `load(version: int | Literal["HEAD"]) -> Spec`
    - `versions() -> list[int]`
    - `save_new(spec: Spec, source: str, run_id: str | None = None, message: str = "") -> Spec`. Set `meta.version = head+1` (atau 1), `parent_version = head`, `created_at = now(tz)`, `source`, `run_id`; jalankan `validate`; error → `ValidationFailed` tanpa menulis apa pun.
    - `commit_ops(base_version: int, ops: list[dict], by: str, message: str = "") -> tuple[Spec, ValidationResult]`. `base_version ≠ head()` → `VersionConflict`; selain itu `apply(..., version=head+1)` lalu `save_new`.
  - Penulisan: `spec.vN.json` via file sementara + `os.replace`, **lalu** `HEAD` via file sementara + `os.replace`. Seluruh operasi tulis dikunci `fcntl.flock` pada `specs_dir/.lock`.
  - `message` disimpan di `provenance_log` sebagai entri `{"op": "commit", "reason": message}` bila tidak kosong.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_save_new_assigns_versions(tmp_path):
    st = SpecStore(tmp_path)
    v1 = st.save_new(spec_with_rooms(), "manual")
    v2 = st.save_new(v1, "manual")
    assert (v1.meta.version, v2.meta.version, v2.meta.parent_version, st.head()) == (1, 2, 1, 2)
    assert st.load("HEAD") == v2 and st.versions() == [1, 2]

def test_stale_base_rejected_no_write(tmp_path):
    st = SpecStore(tmp_path); st.save_new(spec_with_rooms(), "manual"); st.save_new(st.load(1), "manual")
    with pytest.raises(VersionConflict):
        st.commit_ops(1, [{"op": "rename_room", "id": "R1", "name": "X"}], "editor")
    assert st.versions() == [1, 2]

def test_invalid_result_rejected_no_write(tmp_path):
    st = SpecStore(tmp_path); st.save_new(spec_with_rooms(), "manual")
    with pytest.raises(ValidationFailed) as e:
        st.commit_ops(1, [{"op": "set_door", "id": "D2", "offset": 9000}], "editor")
    assert any(i.code == "V008" for i in e.value.issues) and st.versions() == [1]

def test_head_written_after_spec(tmp_path, monkeypatch):
    st = SpecStore(tmp_path); st.save_new(spec_with_rooms(), "manual")
    real_replace = os.replace
    def boom(src, dst):
        if str(dst).endswith("HEAD"): raise OSError("crash before HEAD")
        real_replace(src, dst)
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        st.save_new(st.load(1), "manual")
    assert st.head() == 1 and st.load("HEAD").meta.version == 1   # spec.v2 may exist, HEAD still valid
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/spec/test_store.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `store.py`.** Catatan: `versions()` hanya menghitung versi ≤ HEAD, sehingga file yatim dari crash diabaikan dan akan ditimpa pada save berikutnya.

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/spec -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/spec/store.py tests/spec/test_store.py && rtk git commit -m "feat(spec): append-only spec store with version conflict"
```

---

### Task 7: Ekspor JSON Schema + tipe TypeScript

**Files:**
- Create: `core/spec/export_schema.py`, `schema/layout-spec.schema.json`, `schema/spec-ops.schema.json`, `web/src/types/spec.ts`, `web/src/types/ops.ts`
- Modify: `web/package.json` (devDependency `json-schema-to-typescript`, script `gen:types`)
- Test: `tests/spec/test_schema_export.py`

**Interfaces:**
- Produces: `core.spec.export_schema.build_schemas() -> dict[str, dict]` dengan key `"layout-spec.schema.json"` (`Spec.model_json_schema()`) dan `"spec-ops.schema.json"` (`TypeAdapter(list[SpecOp]).json_schema()`). `python -m core.spec.export_schema` menulis kedua file ke `schema/` (JSON indent 2, key terurut, newline di akhir).
- Script npm: `"gen:types": "json2ts -i ../schema/layout-spec.schema.json -o src/types/spec.ts && json2ts -i ../schema/spec-ops.schema.json -o src/types/ops.ts"`.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_committed_schemas_match_models():
    for name, schema in build_schemas().items():
        on_disk = json.loads((Path("schema") / name).read_text())
        assert on_disk == schema, f"{name} stale: run uv run python -m core.spec.export_schema"
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/spec/test_schema_export.py -q`
Expected: FAIL (modul atau file schema belum ada)

- [ ] **Step 3: Implement + generate**

```bash
rtk uv run python -m core.spec.export_schema
cd web && rtk npm i -D json-schema-to-typescript && rtk npm run gen:types && rtk npm run build
```
Expected: kedua file `.ts` terbentuk, dan `npm run build` sukses.

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/spec -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/spec/export_schema.py schema web/package.json web/package-lock.json web/src/types tests/spec/test_schema_export.py
rtk git commit -m "feat(spec): json schema export and generated ts types"
```

---

### Task 8: Alat bantu GT (`gt_author`)

**Files:**
- Create: `benchmarks/__init__.py`, `benchmarks/tools/__init__.py`, `benchmarks/tools/gt_author.py`, `benchmarks/tools/crop_zoom.py`
- Test: `tests/benchmarks/__init__.py`, `tests/benchmarks/test_gt_author.py`

**Interfaces:**
- Consumes: `Spec` + model (Task 1), `rebuild_rooms`/`RoomLabel` (Task 3), `validate` (Task 5).
- Format YAML GT (keputusan plan):
  ```yaml
  project_id: msc-gatsu-l1
  floor_name: Lantai 1
  site_type: data_center
  image: floorplan/plan.jpeg
  grid: {x: {A: 0, B: 6000, C: 12000, D: 16000, E: 22000, F: 28000}, y: {"3": 0, "2": 6000, "1": 12000}}
  calibration: {A3: [px, py], F3: [px, py], A1: [px, py], F1: [px, py]}   # px gambar di perpotongan grid
  defaults: {wall_height: 3000}                                           # sisanya default
  walls:   [{id: W1, a: A1, b: F1, t: 200, kind: exterior, free_ends?: bool, allow_skew?: bool}]
  columns: [{id: C1, at: A1, shape: h_section, size: [400, 400], kind?: pilaster, grid?: true}]
  openings: [{id: D1, wall: W3, offset: 2200, width: 1600, type: double_swing, hinge: both, swing: right}]
  stairs:  [{id: S1, flights: [{start: P, end: P, width: 1100, risers: 12}], landings: [[P, P, P, P]], top_z?: int}]
  rooms:   [{at: P, name: "R. MEETING", type: meeting}]                  # label, poligon dari rebuild_rooms
  ```
  Titik `P` = `"A1"` (perpotongan grid), `[x, y]` mm, atau `["A1", dx, dy]` (grid + offset mm). `grid: true` pada kolom mengisi `grid_ref` dari referensi `at`. Pada jendela dipakai `category: window`.
- Produces (`benchmarks.tools.gt_author`):
  - `parse_point(p, grid: Grid) -> tuple[int, int]`
  - `fit_px_to_mm(calibration: dict[str, tuple[float, float]], grid: Grid) -> tuple[list[float], float]` = (matriks 2×3 piksel→mm hasil least squares `numpy.linalg.lstsq`, RMS residu mm)
  - `load_gt(path: Path) -> Spec` (bangun spec, `source="manual"`, `rebuild_rooms` dengan label, `id_seq` dari ID tertinggi)
  - `render_overlay(spec: Spec, image_path: Path, out: Path) -> None` (tapak dinding magenta, kolom cyan, pintu oranye, poligon ruang hijau tipis + ID; memakai invers `px_to_mm`)
  - CLI: `python -m benchmarks.tools.gt_author <gt.yaml> [--out-dir DIR]` menulis `gt_spec.json` + `gt_overlay.png` ke folder YAML, lalu mencetak skor, issues, residu kalibrasi, jumlah elemen, dan luas kotor.
- `crop_zoom.py` (alat ukur, tanpa test): `python -m benchmarks.tools.crop_zoom <image> x0 y0 x1 y1 [--scale 4] [--out PATH]` membuat crop yang diperbesar dengan tick piksel setiap 10 px dan label setiap 50 px, untuk membaca koordinat secara visual. Default output ke scratchpad.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_parse_point_forms():
    g = gatsu_grid()   # helper in test: grid from the YAML grid block above
    assert parse_point("D2", g) == (16000, 6000)
    assert parse_point([1234, 5678], g) == (1234, 5678)
    assert parse_point(["A1", 100, -200], g) == (100, 11800)

def test_fit_px_to_mm_recovers_affine():
    g = gatsu_grid()
    true = np.array([[25.85, 0, -5170], [0, -25.85, 15460]])
    calib = {}
    for ref in ("A3", "F3", "A1", "F1"):
        x, y = parse_point(ref, g)
        px = np.linalg.solve(true[:, :2], np.array([x, y]) - true[:, 2])
        calib[ref] = tuple(px)
    m, rms = fit_px_to_mm(calib, g)
    assert m == pytest.approx(true.ravel().tolist(), abs=1e-6) and rms < 1e-6

def test_load_gt_minimal_yaml(tmp_path):
    (tmp_path / "gt.yaml").write_text(MINIMAL_YAML)   # 1 room 6000x6000 between A..B, 3..2, one door, calibration exact
    s = load_gt(tmp_path / "gt.yaml")
    assert len(s.rooms) == 1 and s.rooms[0].name == "TEST" and validate(s).passed
```
`MINIMAL_YAML`: grid Gatsu, kalibrasi yang dihitung dari matriks `true` di atas, 4 dinding exterior t=200 A3→B3→B2→A2→A3, pintu D1 di W1 offset 2000 lebar 900, label ruang di `["A3", 3000, 3000]`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/benchmarks -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `gt_author.py` dan `crop_zoom.py`**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add benchmarks tests/benchmarks && rtk git commit -m "feat(gt): yaml ground truth authoring tool with overlay"
```

---

### Task 9: Ground truth Gatsu

**Files:**
- Create: `benchmarks/gatsu/gt.yaml`, `benchmarks/gatsu/gt_spec.json`, `benchmarks/gatsu/gt_overlay.png`, `benchmarks/gatsu/NOTES.md`
- Test: `tests/benchmarks/test_gatsu_gt.py`

**Interfaces:**
- Consumes: CLI `gt_author`, `crop_zoom` (Task 8), `validate` (Task 5).

Cakupan GT (keputusan pengguna, `PRD/01` FR-EX-15…17, `00` G1):
- grid A–F, 1–3;
- semua dinding exterior dan interior, termasuk Capasitor Room dan **pita luar** di luar grid;
- kolom H di perpotongan grid, dan **blok sirip** pita luar sebagai `kind: pilaster`;
- semua pintu (tipe, engsel, arah) dan jendela yang terlihat;
- **tangga** (flight, tanjakan, arah naik dari teks "NK", bordes) dan ruang lift;
- **kondisi existing**: tanpa elemen PROPOSED; dinding yang akan dibongkar tetap ada;
- label ruang: R. MEETING, GUDANG, PANTRY, toilet, GALERY, BATTERY ROOM, EX MUSHOLA, AHU ROOM, MDF ROOM, CAPASITOR ROOM, tangga, lift, dan area pita luar (`outdoor`/`corridor`).

- [ ] **Step 1: Tulis test acceptance yang gagal**

```python
GT = Path("benchmarks/gatsu/gt_spec.json")

def test_gatsu_gt_valid_and_scored():
    s = Spec.model_validate_json(GT.read_text())
    r = validate(s)
    assert r.passed and r.score >= 0.95, [(i.code, i.element_ids) for i in r.issues]

def test_gatsu_gt_matches_yaml():
    assert load_gt(Path("benchmarks/gatsu/gt.yaml")) .model_dump(exclude={"meta": {"created_at"}}) == \
        Spec.model_validate_json(GT.read_text()).model_dump(exclude={"meta": {"created_at"}})

def test_gatsu_gt_scope():
    s = Spec.model_validate_json(GT.read_text())
    names = {r.name for r in s.rooms}
    for n in ("R. MEETING", "GUDANG", "PANTRY", "GALERY", "BATTERY ROOM", "AHU ROOM", "MDF ROOM", "CAPASITOR ROOM"):
        assert n in names
    assert len(s.stairs) >= 1 and any(c.kind == "pilaster" for c in s.columns)
    assert {a.label for a in s.grid.axes} == set("ABCDEF123")
    assert len(s.meta.building_outline) == 2        # main building + Capasitor Room
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/benchmarks/test_gatsu_gt.py -q`
Expected: FAIL (`gt_spec.json` belum ada)

- [ ] **Step 3: Kalibrasi**

Temukan piksel perpotongan grid A3, F3, A1, F1 di `plan.jpeg`. Garis sumbu grid melewati pusat bulatan A–F (bawah) dan 1–3 (kiri). Pakai `crop_zoom` di tiap bulatan dan garis sumbu. Tulis ke `calibration`. Target RMS residu ≤ 26 mm (≈ 1 px). Bila lebih besar, ukur ulang.

- [ ] **Step 4: Tulis `gt.yaml` bertahap, verifikasi overlay di tiap tahap**

Urutan:
1. dinding exterior bangunan utama;
2. pita luar + pilaster;
3. dinding interior baris 1–2;
4. dinding interior baris 2–3;
5. Capasitor Room;
6. kolom grid;
7. pintu/jendela;
8. tangga;
9. label ruang.

Setelah tiap tahap, jalankan CLI dan buka `gt_overlay.png` (zoom area terkait dengan `crop_zoom` pada overlay). Tebal dinding = jarak antar-garis tepi × `mm_per_px`, dibulatkan ke 10 mm. Posisi garis tengah di-snap ke grid bila ≤ 150 mm dari sumbu. Catat di `NOTES.md` setiap keputusan interpretasi, mis. arti blok tertentu dan dinding mana yang dianggap "dismantle".

Run: `rtk uv run python -m benchmarks.tools.gt_author benchmarks/gatsu/gt.yaml`
Expected (akhir): `passed=True`, `score ≥ 0.95`. Tidak ada issue `error`. Warning tersisa dijelaskan di `NOTES.md`, atau diselesaikan dengan flag (`free_ends`, `allow_skew`) yang memang benar secara arsitektur.

- [ ] **Step 5: Verifikasi visual**

Overlay: tapak dinding menutupi garis dinding denah dengan deviasi ≤ 1–2 px di seluruh bangunan. Periksa per kuadran grid dengan `crop_zoom` pada `gt_overlay.png`. Simpan 4 crop kuadran ke scratchpad sebagai bukti.

- [ ] **Step 6: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests -q`
Expected: semua PASS

- [ ] **Step 7: Commit**

```bash
rtk git add benchmarks/gatsu tests/benchmarks/test_gatsu_gt.py && rtk git commit -m "feat(gt): msc gatsu l1 ground truth"
```

- [ ] **Step 8 (tindakan pengguna):** review GT oleh orang kedua (R-17) memakai `benchmarks/gatsu/gt_overlay.png` dan `NOTES.md`. Agen tidak menunggu; review diminta di laporan akhir.

---

### Task 10: Verifikasi kriteria selesai M1

- [ ] **Step 1: Suite + coverage**

Run: `rtk uv run --env-file .env pytest -q --cov=core/spec --cov-report=term-missing`
Expected: semua PASS (OCR grid tetap XFAIL dari M0). Coverage `core/spec` ≥ 85%. Bila kurang, tambahkan test untuk cabang ops/validator yang belum tersentuh. Jangan menurunkan ambang.

- [ ] **Step 2: Lint + build web**

Run: `rtk uv run ruff check .` dan `cd web && rtk npm run lint && rtk npm run build`
Expected: bersih.

- [ ] **Step 3: Centang ROADMAP M1 dan tulis status**

Centang tugas M1 di `ROADMAP.md`, lalu tambahkan blok "Status M1" di bawah "Kriteria selesai" M1: jumlah test, coverage, skor GT, RMS kalibrasi, jumlah elemen GT, dan luas kotor.

```bash
rtk git add ROADMAP.md && rtk git commit -m "docs: close M1"
```
