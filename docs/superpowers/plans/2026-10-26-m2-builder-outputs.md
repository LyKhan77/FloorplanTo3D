# M2 — Builder & Outputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Spec (GT Gatsu) menghasilkan `layout.blend`, `shell.glb`, `layout_full.glb`, `layout.fbx`, `layout.obj`, render verifikasi dan dokumen, `verify.json`, serta `report.html`/`report.pdf`. Satu perintah CLI, deterministik.

**Architecture:** Core (Python 3.12) menghitung **semua geometri** menjadi mesh mentah (verts/faces dalam mm) di `build_input.json` v1. Builder Blender hanya merakit: membuat mesh, parent, material, Boolean cutter, instance template, kamera, render, dan export. Verifikasi dan dokumen dikerjakan di core setelah Blender selesai. Template placeholder dibangkitkan lewat builder yang sama.

**Tech Stack:** Python 3.12, Shapely 2.2 (`constrained_delaunay_triangles`), NumPy, OpenCV, pygltflib, Jinja2, WeasyPrint; Blender 5.2.2 (bpy, bmesh), Workbench render.

**Spec:** `PRD/06-builder-outputs.md` (otoritas utama), `PRD/03-layout-spec.md` §1 dan §13, `PRD/10-template-contract.md`, `ROADMAP.md` M2. Branch dasar: `m1-spec-gt`.

## Global Constraints

- Semua perintah shell diawali `rtk`. Test yang menyentuh Blender atau WeasyPrint dijalankan dengan `uv run --env-file .env pytest`.
- Jangan membaca atau meng-commit `server-info.txt`.
- Kerja di branch baru `m2-builder`, dibuat dari `m1-spec-gt`.
- Satuan `build_input.json` = **mm**. Builder membagi 1000 (1 unit Blender = 1 m). Sumbu spec = sumbu Blender (+X timur, +Y utara, +Z atas). glTF di-export Y-up, sehingga +Y spec menjadi −Z glTF.
- Builder hanya memakai stdlib + `bpy` + `bmesh` dan tidak mengimpor `core/`. Pemanggilan: `blender -b --factory-startup --python-exit-code 1 -P builder/build.py -- <build_input.json> <out_dir>`, dengan progres `@@PROGRESS <0-100> <pesan>`. Versi dicek `(5, 2)`.
- Nama objek: `wall_<id>`, `column_<id>`, `door_<id>` (Empty) + `frame_<id>`, `leaf_<id>_a|b`, `window_<id>`, `stair_<id>` (Empty) + `stair_<id>_f<i>`, `stair_<id>_l<j>`, `room_<id>`, `slab_<n>`, `obj_<id>`.
- Custom properties di setiap objek: `spec_id`, `spec_type` (`wall|column|door|window|room|stair|slab|object`), `spec_version`; ditambah `area_m2` (room), `height_mm` (wall), `template_id` (object). Semua diekspor sebagai glTF extras.
- Collection: `Shell/{Walls, Columns, Doors, Windows, Stairs, Floors}`, `Objects`, `Annotations` (tidak diekspor ke glb/fbx/obj), `Cameras`, `_templates` (tersembunyi).
- Material (06 §4.7): `wall_ext #D9D9D9 r0.9`, `wall_int #E8E8E8 r0.9`, `column #A8A8A8 r0.8`, `floor #6F6F6F r0.7`, `floor_data_hall #8D8D8D r0.6`, `door_frame #4D4D4D r0.5`, `door_leaf #8A6A4F r0.6`, `door_leaf_metal #9AA0A6 r0.6`, `glass #BFD7EA a0.3 r0.1`. Pilaster memakai `wall_ext`. Daun besi untuk ruang teknis (`ups_room, battery_room, electrical_room, mdf, ahu_room, capacitor_room`).
- Tinggi default dari `meta.defaults`. Slab: z −150…0. Kusen 50 mm. Daun 40 mm, tinggi `h − 10`. Cutter: lebar × (t + 20) × h, mulai di `sill`.
- Export (06 §5): `shell.glb` (Shell), `layout_full.glb` (Shell + Objects), `layout.blend` (semua + pack resources), `layout.fbx` (`global_scale=1.0`, `apply_unit_scale=True`), `layout.obj` (+`.mtl`). glb memakai `export_extras=True`, `export_apply=True`, `export_yup=True`, tanpa kamera/lampu.
- Verifikasi: galat glb ≤ 1 mm (NFR-AC-09). Ambang IoU: ≥ 0.85 `succeeded`, 0.70–0.85 `succeeded` + warning, < 0.70 `needs_attention`. IoU dihitung setelah kedua mask didilasi 1 px.
- Template (10 §3): glb Y-up meter, satu root `template_root`, pivot tengah-bawah, depan = +Y spec, dims cocok bbox ≤ 2%, ≤ 50.000 segitiga, ≤ 8 material, ≤ 10 MB, thumbnail 512×512 RGBA.

## Review Focus

1. **Bukaan di dekat sambungan dinding**, saat cutter melintasi tapak dinding tetangga. Hanya dinding induk yang terpotong, dan dinding tetangga tetap utuh. Ditest di Task 4: `test_cutter_only_cuts_its_wall`.
2. **Ruang dengan lubang kolom, dan tapak dinding yang terpecah dua karena dinding lain menembusnya** (MultiPolygon). Mesh lantai harus punya luas = `area_m2` dan dinding pecahan tetap satu objek. Ditest di Task 2: `test_floor_mesh_area_matches_room_with_hole`, `test_wall_solid_split_into_pieces_stays_one_mesh`.
3. **Spec tanpa objek, tanpa tangga, atau tanpa gambar input.** Build tetap jalan. IoU `skipped` bila tidak ada gambar, dan bagian dokumen yang kosong menampilkan "—". Ditest di Task 8: `test_verify_without_image_skips_iou`; Task 9: `test_report_renders_with_empty_sections`.
4. **Template tidak ditemukan atau tidak valid saat build.** Build tetap jalan tanpa objek itu, dan muncul warning yang menyebut ID objek. Tidak boleh crash dan tidak boleh diam-diam hilang. Ditest di Task 6: `test_missing_template_skipped_with_warning`.
5. **Blender gagal atau timeout.** CLI keluar dengan kode ≠ 0, menyebut log, dan tidak meninggalkan output setengah jadi di `out_dir` (tulis ke folder sementara, lalu rename). Ditest di Task 10: `test_cli_failed_build_leaves_no_partial_output`.

---

### Task 1: Primitif mesh + skema `build_input` v1

**Files:**
- Create: `core/build_prep/__init__.py`, `core/build_prep/mesh.py`, `core/build_prep/schema.py`
- Test: `tests/build_prep/__init__.py`, `tests/build_prep/test_mesh.py`

**Interfaces:**
- Produces (`core.build_prep.mesh`), semua dalam mm:
  - `MeshData = TypedDict("MeshData", verts=list[list[float]], faces=list[list[int]])`.
  - `prism(poly: shapely.Polygon | MultiPolygon, z0: float, z1: float) -> MeshData`: tutup bawah/atas dari `shapely.constrained_delaunay_triangles` (hanya segitiga di dalam poligon), sisi berupa quad per edge ring. Normal mengarah keluar: tutup atas CCW dilihat dari atas, sisi luar CCW dilihat dari luar. Vertex dipakai bersama sehingga mesh manifold (setiap edge tepat 2 face).
  - `flat(poly: Polygon, z: float) -> MeshData`: satu permukaan menghadap +Z (lantai).
  - `box(cx, cy, cz, sx, sy, sz, rot_z_deg=0.0) -> MeshData`: (cx, cy, cz) = pusat.
  - `merge(*meshes: MeshData) -> MeshData`: concat dengan offset indeks.
  - `is_closed(m: MeshData) -> bool`: setiap edge tak berarah dipakai tepat 2 face (dipakai test).
- Produces (`core.build_prep.schema`), TypedDict dokumentasi + konstanta:
  - `BUILD_INPUT_VERSION = 1`.
  - `MeshItem {name, collection, verts, faces, material, props, parent: str|None, location: [x,y,z], rot_z: float}`. Verts relatif terhadap `location`/`rot_z` objek; mesh dunia memakai `location=[0,0,0]`.
  - `EmptyItem {name, collection, location, rot_z, props, parent}`.
  - `CutterItem {target, verts, faces}` (koordinat dunia).
  - `InstanceItem {name, asset, template_key, location, rot_z, scale, props}`.
  - `LabelItem {text, location: [x,y], size}`; `GridLineItem {a, b, label}`.
  - `CameraItem {name, kind: "ORTHO"|"PERSP", location, rotation_deg: [rx,ry,rz], ortho_scale: float|None, fov_deg: float|None, resolution: [w,h], output: str, mode: "verify"|"doc", cutaway_mm: float|None}`.
  - `ExportItem {file, collections: list[str]}`.
  - Dokumen: `{version, spec_version, materials: {name: {color, roughness, alpha}}, meshes, empties, cutters, instances, labels, grid_lines, cameras, render: {engine}, exports}`.

- [ ] **Step 1: Branch + test yang gagal**

```bash
rtk git checkout -b m2-builder m1-spec-gt
```

```python
# tests/build_prep/test_mesh.py
from shapely.geometry import Polygon
from core.build_prep.mesh import box, flat, is_closed, merge, prism

def _area_top(m, z):  # sum of upward faces' area at height z
    ...  # helper: shoelace of each face whose verts all have z == z

def test_prism_square_closed_with_volume():
    m = prism(Polygon([(0, 0), (1000, 0), (1000, 2000), (0, 2000)]), 0, 3000)
    assert is_closed(m) and len(m["verts"]) == 8
    assert _area_top(m, 3000) == pytest.approx(2_000_000)

def test_prism_with_hole_is_closed_and_area_excludes_hole():
    ring = Polygon([(0, 0), (4000, 0), (4000, 4000), (0, 4000)], [[(1000, 1000), (1000, 2000), (2000, 2000), (2000, 1000)]])
    m = prism(ring, 0, 100)
    assert is_closed(m) and _area_top(m, 100) == pytest.approx(16e6 - 1e6)

def test_top_faces_point_up_and_sides_out():
    m = prism(Polygon([(0, 0), (1000, 0), (1000, 1000), (0, 1000)]), 0, 1000)
    assert all(normal(m, f)[2] > 0 for f in faces_at(m, 1000)) and all(normal(m, f)[2] < 0 for f in faces_at(m, 0))

def test_box_rotated_and_merge_offsets():
    b = box(0, 0, 50, 100, 10, 100, rot_z_deg=90)
    xs = [v[0] for v in b["verts"]]; ys = [v[1] for v in b["verts"]]
    assert (max(xs) - min(xs), max(ys) - min(ys)) == pytest.approx((10, 100))
    m = merge(b, box(500, 0, 50, 10, 10, 10))
    assert is_closed(m) and max(i for f in m["faces"] for i in f) == 15

def test_flat_faces_up():
    m = flat(Polygon([(0, 0), (1000, 0), (1000, 1000)]), 0)
    assert all(normal(m, f)[2] > 0 for f in m["faces"])
```
`normal(m, f)` dan `faces_at(m, z)` adalah helper di file test (cross product dua edge pertama; face yang semua vertex-nya di z).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/build_prep -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'core.build_prep'`

- [ ] **Step 3: Implement `mesh.py` dan `schema.py`.** `prism` memproses tiap bagian MultiPolygon. Segitiga dari `constrained_delaunay_triangles` disaring dengan `poly.contains(tri.representative_point())`, lalu dikonversi ke indeks vertex bersama (dict koordinat → indeks). Orientasi tiap face dicek dengan tanda luas lalu dibalik bila perlu.

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/build_prep -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/build_prep tests/build_prep && rtk git commit -m "feat(build_prep): mesh primitives and build_input v1 schema"
```

---

### Task 2: Shell — dinding, kolom, lantai, slab, tangga

**Files:**
- Create: `core/build_prep/shell.py`
- Test: `tests/build_prep/test_shell.py`

**Interfaces:**
- Consumes: `prism`, `flat`, `box`, `merge` (Task 1); `wall_footprint`, `column_footprint`, `stair_metrics` (`core.spec.derive`).
- Produces (`core.build_prep.shell`):
  - `wall_solids(spec: Spec) -> dict[str, Polygon | MultiPolygon]`: tapak dinding per ID **tanpa overlap**. Dinding diproses berurutan `id_key`, dan tiap tapak dikurangi union tapak sebelumnya, sehingga sudut menjadi milik dinding dengan ID lebih kecil.
  - `wall_items(spec) -> list[MeshItem]`: `wall_<id>`, collection `Walls`, prism `base_z … base_z + (height or wall_height)`, material `wall_ext` bila `kind == exterior` selain itu `wall_int` (`glass` → `glass`), props `spec_id`, `spec_type="wall"`, `height_mm`.
  - `column_items(spec) -> list[MeshItem]`: `column_<id>`, collection `Columns`. Bentuk: `rect` = persegi; `circle` = 24 segmen; `h_section` = profil H (flens penuh lebar `w`, tebal flens dan web = `size/10`, web di tengah). Tinggi `height or wall_height`. Material `column`, kecuali `pilaster` → `wall_ext`.
  - `floor_items(spec) -> list[MeshItem]`: `room_<id>` (`flat` dari polygon + holes, z=0, material `floor_data_hall` bila tipe `data_hall`, props `area_m2`) dan `slab_<n>` (prism outline −150…0, material `floor`, `spec_type="slab"`), collection `Floors`.
  - `stair_items(spec) -> tuple[list[EmptyItem], list[MeshItem]]`: Empty `stair_<id>` + `stair_<id>_f<i>` (anak tangga ke-k: box sepanjang arah flight `[ (k−1)·tread, k·tread ]`, dari `start_z` sampai `start_z + k·riser`, digabung `merge`) + `stair_<id>_l<j>` (prism landing dari `base_z` ke `end_z` flight sebelumnya `j`). Parent = Empty tangga, `location=[0,0,0]`.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_wall_solids_do_not_overlap_and_cover_footprints():
    s = spec_with_rooms()
    solids = wall_solids(s)
    union = unary_union([wall_footprint(w, s) for w in s.walls])
    assert sum(p.area for p in solids.values()) == pytest.approx(union.area, rel=1e-6)
    ids = list(solids)
    assert all(solids[a].intersection(solids[b]).area < 1 for a in ids for b in ids if a < b)

def test_wall_solid_split_into_pieces_stays_one_mesh():
    s = spec_with_rooms()
    s.walls.append(Wall(id="W6", a=(2500, -500), b=(2500, 500), thickness=100, kind="interior", free_ends=True))
    items = {i["name"]: i for i in wall_items(s)}
    assert "wall_W6" in items and is_closed(items["wall_W6"])

def test_wall_item_height_and_props():
    s = spec_with_rooms()
    s.walls[0].height = 4500
    w1 = next(i for i in wall_items(s) if i["name"] == "wall_W1")
    zs = [v[2] for v in w1["verts"]]
    assert (min(zs), max(zs)) == (0, 4500) and w1["props"] == {"spec_id": "W1", "spec_type": "wall", "height_mm": 4500}
    assert w1["material"] == "wall_ext"

def test_floor_mesh_area_matches_room_with_hole():
    s = spec_with_rooms()
    s.rooms[0].holes = [[(1000, 1000), (1000, 1400), (1400, 1400), (1400, 1000)]]
    s = derive(s)
    r1 = next(i for i in floor_items(s) if i["name"] == "room_R1")
    assert mesh_area(r1) == pytest.approx(s.rooms[0].area_m2 * 1e6, rel=1e-4)

def test_h_section_profile_area():
    s = spec_with_rooms()
    s.columns[0] = s.columns[0].model_copy(update={"shape": "h_section", "size": (400, 400)})
    c = column_items(s)[0]
    assert top_area(c) == pytest.approx(2 * 400 * 40 + 40 * (400 - 80))

def test_stair_steps_and_landing():
    s = spec_with_rooms()
    s.stairs = [Stair(id="S1", flights=[Flight(start=(1000, 1000), end=(1000, 3750), width=1000, risers=11)],
                      landings=[[(500, 3750), (1500, 3750), (1500, 4750), (500, 4750)]], top_z=1925)]
    empties, meshes = stair_items(s)
    f1 = next(m for m in meshes if m["name"] == "stair_S1_f1")
    l1 = next(m for m in meshes if m["name"] == "stair_S1_l1")
    assert len(f1["faces"]) == 11 * 6 and max(v[2] for v in f1["verts"]) == pytest.approx(1925)
    assert max(v[2] for v in l1["verts"]) == pytest.approx(1925) and empties[0]["name"] == "stair_S1"
```
`mesh_area` dan `top_area` adalah helper test (jumlah luas face yang menghadap atas).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/build_prep/test_shell.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `shell.py`**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/build_prep -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/build_prep/shell.py tests/build_prep/test_shell.py && rtk git commit -m "feat(build_prep): walls, columns, floors, slabs, stairs"
```

---

### Task 3: Bukaan — cutter, pintu, jendela

**Files:**
- Create: `core/build_prep/openings.py`
- Test: `tests/build_prep/test_openings.py`

**Interfaces:**
- Consumes: `box`, `merge` (Task 1).
- Produces (`core.build_prep.openings`):
  - `opening_frame(spec, o: Opening) -> tuple[tuple[float,float], float, float, float]` = (titik awal bukaan di garis tengah, sudut dinding derajat, tinggi `h`, `sill`). `h = o.height or (door_height | window_height)`.
  - `cutters(spec) -> list[CutterItem]`: satu box per bukaan, target `wall_<wall_id>`, ukuran `width × (t + 20) × h` dari `sill`.
  - `door_items(spec) -> tuple[list[EmptyItem], list[MeshItem]]`:
    - `door_<id>` Empty di titik awal bukaan, `rot_z` = sudut dinding, z = `sill`, collection `Doors`.
    - Anak-anaknya dalam koordinat lokal (x sepanjang dinding, y melintang, z atas):
      - `frame_<id>`: 2 tiang `50 × t × h` di x ∈ [0, 50] dan [w − 50, w] + ambang `w × t × 50` di z ∈ [h − 50, h], material `door_frame`;
      - daun: `single_swing` → `leaf_<id>_a` dengan `location` di engsel (x = 0 bila `hinge=start`, x = w bila `end`); `double_swing` → `_a` di x = 0 selebar `w·split` dan `_b` di x = w selebar `w·(1 − split)` (default `leaf_split` 0.5); verts relatif ke engsel, mengarah ke tengah bukaan; tebal 40 di tengah dinding, tinggi `h − 10`; `sliding` → satu daun selebar w, digeser y = ±(t/2 + 20) ke sisi `swing` (`left` = +y lokal); `opening` → hanya kusen; `rolling` → box `w × 300 × 300` di z ∈ [h − 300, h] di sisi `swing`;
      - material daun `door_leaf_metal` bila salah satu ruang pintu bertipe teknis, selain itu `door_leaf`.
    - Props door: `spec_id`, `spec_type="door"`, `door_type`, `hinge`, `swing`.
  - `window_items(spec) -> list[MeshItem]`: `window_<id>` (dunia, `merge` kusen 4 sisi 50 × 60 + kaca 10 mm di tengah tebal), material `glass`, props `spec_type="window"`.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_cutter_spans_opening_and_wall_thickness():
    s = spec_with_rooms()                         # D2 on W1: offset 1000, width 1800, t 200
    c = next(c for c in cutters(s) if c["target"] == "wall_W1")
    xs, ys, zs = zip(*c["verts"])
    assert (min(xs), max(xs)) == pytest.approx((1000, 2800))
    assert (min(ys), max(ys)) == pytest.approx((-110, 110)) and (min(zs), max(zs)) == pytest.approx((0, 2100))

def test_single_door_leaf_pivot_at_hinge():
    s = spec_with_rooms()                         # D1 on W5 (vertical, a=(5000,0)), offset 2000, hinge start
    empties, meshes = door_items(s)
    d1 = next(e for e in empties if e["name"] == "door_D1")
    assert d1["location"] == pytest.approx([5000, 2000, 0]) and d1["rot_z"] == pytest.approx(90)
    leaf = next(m for m in meshes if m["name"] == "leaf_D1_a")
    assert leaf["parent"] == "door_D1" and leaf["location"] == pytest.approx([0, 0, 0])
    xs = [v[0] for v in leaf["verts"]]
    assert (min(xs), max(xs)) == pytest.approx((0, 900)) and max(v[2] for v in leaf["verts"]) == pytest.approx(2090)

def test_double_door_two_leaves_meet_in_middle():
    s = spec_with_rooms()                         # D2 double, width 1800
    _, meshes = door_items(s)
    a = next(m for m in meshes if m["name"] == "leaf_D2_a"); b = next(m for m in meshes if m["name"] == "leaf_D2_b")
    assert b["location"][0] == pytest.approx(1800)
    assert max(v[0] for v in a["verts"]) == pytest.approx(900) and min(v[0] for v in b["verts"]) == pytest.approx(-900)

def test_opening_type_has_frame_only():
    s = spec_with_rooms()
    s.openings[0].door_type = "opening"
    _, meshes = door_items(s)
    assert not any(m["name"].startswith("leaf_D1") for m in meshes) and any(m["name"] == "frame_D1" for m in meshes)

def test_window_sits_at_sill():
    s = spec_with_rooms()
    s.openings.append(Opening(id="N1", category="window", wall_id="W3", offset=1000, width=1200, sill=900))
    w = window_items(s)[0]
    zs = [v[2] for v in w["verts"]]
    assert (min(zs), max(zs)) == pytest.approx((900, 2100)) and w["material"] == "glass"
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/build_prep/test_openings.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `openings.py`**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/build_prep -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/build_prep/openings.py tests/build_prep/test_openings.py && rtk git commit -m "feat(build_prep): opening cutters, parametric doors and windows"
```

---

### Task 4: Builder Blender v1 (mesh, parent, material, Boolean, export)

**Files:**
- Modify: `builder/build.py` (ganti format v0 dengan v1)
- Create: `builder/scene.py`, `builder/export.py`
- Modify: `tests/test_builder_smoke.py` (pindah ke format v1)
- Test: `tests/builder/__init__.py`, `tests/builder/test_build.py`

**Interfaces:**
- Consumes: dokumen `build_input` v1 (Task 1 schema).
- Produces:
  - `builder/build.py main(argv)`: urutan cek versi → `read_factory_settings(use_empty=True)` → collection → material → mesh + empty (parent setelah semua dibuat) → cutter (Boolean `DIFFERENCE` `EXACT`, apply, hapus cutter) → instance → label/grid (Annotations) → export → render (Task 7) → `@@PROGRESS`. Unit: semua koordinat dan ukuran mm dibagi 1000.
  - `builder/scene.py`:
    - `make_mesh(item, collections, materials) -> bpy.types.Object` (dari verts/faces, set props, `location`, `rotation_euler.z`, material; lalu merge by distance 0.0001 m dan recalc normals);
    - `make_empty(item, collections)`;
    - `apply_cutters(cutters)` (target tidak ada → abaikan + log `WARN cutter target missing <target>`).
  - `builder/export.py export_all(exports, out_dir)`. Per item:
    - pilih objek di collection yang disebut (rekursif, termasuk Empty);
    - `.glb` lewat `export_scene.gltf(use_selection=True, export_format="GLB", export_extras=True, export_apply=True, export_yup=True, export_cameras=False, export_lights=False)`;
    - `.fbx` lewat `export_scene.fbx(use_selection=True, global_scale=1.0, apply_unit_scale=True)`;
    - `.obj` lewat `wm.obj_export(export_selected_objects=True, export_materials=True)`;
    - `.blend` lewat `file.pack_all()` lalu `wm.save_as_mainfile(relative_remap=True)`.
  - Mode template (Task 5) = dokumen tanpa kamera dan dengan export `asset.glb`. Builder tidak membedakan mode.

- [ ] **Step 1: Tulis test yang gagal** (fixture `tests/builder/conftest.py`: `build(tmp_path, doc) -> CompletedProcess`, menjalankan Blender seperti M0)

```python
pytestmark = [pytest.mark.blender, skip_without_blender]

def test_meshes_props_and_hierarchy_in_glb(tmp_path):
    r = build(tmp_path, minimal_doc())          # hand-written: wall_W1 prism 1000x200x3000 + door Empty + leaf child
    assert r.returncode == 0 and "@@PROGRESS 100" in r.stdout
    g = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    names = {n.name for n in g.nodes}
    assert {"wall_W1", "door_D1", "leaf_D1_a"} <= names
    w = next(n for n in g.nodes if n.name == "wall_W1")
    assert w.extras == {"spec_id": "W1", "spec_type": "wall", "spec_version": 1, "height_mm": 3000}
    door = next(n for n in g.nodes if n.name == "door_D1")
    leaf_idx = next(i for i, n in enumerate(g.nodes) if n.name == "leaf_D1_a")
    assert leaf_idx in door.children

def test_cutter_only_cuts_its_wall(tmp_path):
    r = build(tmp_path, two_walls_corner_with_cutter_doc())   # cutter targets wall_W1, overlaps wall_W2's corner
    g = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    assert tri_count(g, "wall_W1") > 12 and tri_count(g, "wall_W2") == 12

def test_all_export_files_exist(tmp_path):
    build(tmp_path, minimal_doc())
    for f in ("shell.glb", "layout_full.glb", "layout.blend", "layout.fbx", "layout.obj", "layout.mtl"):
        assert (tmp_path / "out" / f).stat().st_size > 0

def test_annotations_not_exported(tmp_path):
    doc = minimal_doc(); doc["labels"] = [{"text": "R1", "location": [500, 500], "size": 300}]
    build(tmp_path, doc)
    g = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    assert not any((n.name or "").startswith("label_") for n in g.nodes)
```
`minimal_doc()` dan `two_walls_corner_with_cutter_doc()` adalah dict v1 yang ditulis tangan di `tests/builder/docs.py` memakai `core.build_prep.mesh.box/prism`. `tri_count(g, name)` = jumlah indeks primitive mesh node / 3.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/builder -q`
Expected: FAIL (builder masih v0: `KeyError: 'boxes'` / returncode ≠ 0)

- [ ] **Step 3: Implement builder v1.** `build.py` menambahkan direktorinya ke `sys.path`, lalu mengimpor `scene` dan `export`. Hapus format v0, lalu perbarui `tests/test_builder_smoke.py` agar memakai dokumen v1 yang setara (satu prism 1000×2000×3000, assertion translasi/extent tetap; mesh dunia → translasi node 0 dan extent dari accessor).

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run --env-file .env pytest tests/builder tests/test_builder_smoke.py -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add builder tests/builder tests/test_builder_smoke.py && rtk git commit -m "feat(builder): v1 mesh assembler, booleans, exports"
```

---

### Task 5: Template placeholder, validator template, dan registry

**Files:**
- Create: `core/templates/__init__.py`, `core/templates/model.py`, `core/templates/registry.py`, `core/templates/validate.py`, `core/templates/make_placeholders.py`
- Modify: `core/spec/export_schema.py` (tambah `template.schema.json`), `schema/` (regenerate)
- Test: `tests/templates/__init__.py`, `tests/templates/test_templates.py`

**Interfaces:**
- Produces:
  - `core.templates.model.TemplateMeta` (Pydantic, `extra="forbid"`), field persis `10` §2. `dims: {w,h,d}` int > 0. `pivot: Literal["bottom_center"]`. `front: Literal["+y"]`. `resizable` per sumbu `False | {min,max,step}`. `scale_mode`, `snap`, `clearance`, `stackable`, `allowed_room_types`, `metadata`, `source`, `stats` sesuai tabel. Validator: `min ≤ dims ≤ max`; `scale_mode == "fixed"` ⇒ semua `resizable` False.
  - `core.templates.registry.load_template(root: Path, template_id: str, version: str) -> tuple[TemplateMeta, Path] | None` (None bila folder/JSON hilang atau tidak valid). Dipakai Task 6.
  - `core.templates.validate.validate_template(path: Path) -> list[str]` (kosong = OK), dengan pemeriksaan 1–8 dari `10` §5. bbox dihitung dari node glTF dengan komposisi TRS (translation, rotation quaternion, scale) dari root ke daun. CLI: `python -m core.templates.validate <path>` mencetak `OK` atau pelanggaran, exit ≠ 0 bila ada pelanggaran.
  - `core.templates.make_placeholders.PLACEHOLDERS`: 7 baris persis tabel `10` §6 (id, dims, kategori, sumbu resizable; rentang resize = dims ± 25% dibulatkan 50 mm, step 50).
  - `make_placeholders(out_root: Path, blender_bin: str) -> list[Path]`. Per template:
    - tulis `build_input.json` mode template: mesh `template_root` (box `w × d × h`, z 0…h, warna per kategori), anak `front_panel` (box tipis gelap di sisi +Y), Empty `front_marker` di (0, d/2, h/2), collection `Template`, export `asset.glb` collection `Template`;
    - jalankan builder;
    - tulis `template.json` dan `thumbnail.png` (512×512 RGBA: latar transparan, kotak warna kategori, panah putih ke atas = depan, teks id).
    - CLI: `python -m core.templates.make_placeholders [--out data/templates]`.

- [ ] **Step 1: Tulis test yang gagal**

```python
@pytest.mark.blender
def test_placeholders_generate_and_validate(tmp_path):
    paths = make_placeholders(tmp_path, load_settings().blender_bin)
    assert len(paths) == 7
    assert all(validate_template(p) == [] for p in paths)
    meta, glb = load_template(tmp_path, "rack-42u-600x1200", "1.0.0")
    assert meta.dims.h == 2000 and meta.resizable.w is False and glb.name == "asset.glb"

@pytest.mark.blender
def test_validate_catches_dims_mismatch(tmp_path):
    p = make_placeholders(tmp_path, load_settings().blender_bin)[0]
    meta = json.loads((p / "template.json").read_text()); meta["dims"]["h"] = 2500
    (p / "template.json").write_text(json.dumps(meta))
    assert any("dims" in v for v in validate_template(p))

def test_template_meta_rejects_bad_resize_range():
    with pytest.raises(ValidationError):
        TemplateMeta.model_validate(sample_meta(resizable={"w": {"min": 700, "max": 900, "step": 50}}))  # dims.w=600

def test_load_template_missing_returns_none(tmp_path):
    assert load_template(tmp_path, "nope", "1.0.0") is None
```
`sample_meta(**overrides)` adalah helper test yang mengembalikan dict meta rack 600×1200×2000 yang valid.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/templates -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement.** Mode template memakai builder generik Task 4 (tanpa kode builder khusus).

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run --env-file .env pytest tests/templates -q && rtk uv run python -m core.spec.export_schema`
Expected: semua PASS, dan `schema/template.schema.json` tertulis.

- [ ] **Step 5: Commit**

```bash
rtk git add core/templates core/spec/export_schema.py schema tests/templates && rtk git commit -m "feat(templates): template contract model, validator, placeholder generator"
```

---

### Task 6: Assembler `build_input` + instance template + anotasi

**Files:**
- Create: `core/build_prep/assemble.py`, `core/build_prep/cameras.py`
- Modify: `builder/scene.py` (instance + label/grid)
- Test: `tests/build_prep/test_assemble.py`, `tests/builder/test_instances.py`

**Interfaces:**
- Consumes: Task 2–4.
- Produces:
  - `core.build_prep.cameras.cameras(spec, image_size: tuple[int,int] | None) -> list[CameraItem]`:
    - `cam_verify` (bila `image_size`): ORTHO di pusat gambar dalam mm (lewat `px_to_mm`), menghadap −Z, `ortho_scale = max(w_px, h_px) · mm_per_px`, resolusi = ukuran gambar, `mode="verify"`, output `verify_top.png`;
    - `cam_top`: ORTHO menutup bbox `building_outline` + 5% margin, 1600×1000, `mode="doc"`, output `renders/top.png`;
    - `cam_iso_ne|nw|se|sw`: ORTHO elevasi 35° (rotasi X = 55°, Z = 45°/315°/135°/225°), ortho_scale = diagonal bbox × 1.1, `cutaway_mm=1200`, output `renders/iso_<dir>.png`;
    - `cam_room_<id>` untuk ruang ≥ 4 m² yang bertipe bukan `outdoor`: PERSP di `representative_point` ruang, z = 1600, menghadap titik tengah tepi terpanjang poligon (rotasi `[90, 0, atan2(dy,dx)° − 90]`), FOV 75°, 1280×800, output `renders/room_<id>.png`.
    - Ruang pada `px_to_mm` dianggap axis-aligned (b = d = 0). Bila tidak, `cam_verify` dilewati dengan warning.
  - `core.build_prep.assemble.build_input_for(spec: Spec, templates_root: Path | None, image_size: tuple[int,int] | None, engine: str = "BLENDER_WORKBENCH") -> tuple[dict, list[str]]` = (dokumen v1, warnings). Isi:
    - materials (Global Constraints);
    - mesh/empty/cutter dari Task 2–3;
    - instance objek: `load_template` → `asset` absolut, `scale = dims / template.dims` (w → X, d → Y, h → Z), `template_key = "<id>@<ver>"`; template hilang/tidak valid → dilewati + warning `"object O3: template rack@9.9.9 not found"`;
    - label ruang (nama, atau ID bila nama kosong) di `label_pos` atau `representative_point`, ukuran 300;
    - garis grid (panjang = bbox + 2000);
    - kamera;
    - `render.engine`;
    - exports: `shell.glb`→`[Shell]`, `layout_full.glb`→`[Shell, Objects]`, `layout.blend`→`[]` (semua), `layout.fbx`/`layout.obj`→`[Shell, Objects]`.
    - Setiap props menyertakan `spec_version = spec.meta.version`.
  - `builder/scene.py`:
    - `make_instances(instances)`: impor `asset` sekali per `template_key` ke collection `_templates/<key>` (dikecualikan dari view layer); per instance buat Empty `obj_<id>` (location, rot_z, scale) + linked duplicate (`obj.copy()`, data dibagi) tiap objek impor sebagai anak, dengan matriks lokal sama dengan di template;
    - `make_annotations(labels, grid_lines)`: text object `label_<i>` (body = teks, size mm/1000, rata tengah) + mesh garis tipis `grid_<label>` (box 20 mm) di collection `Annotations`.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_assemble_two_room_counts_and_versions():
    doc, warnings = build_input_for(spec_with_rooms(), None, (1000, 600))
    names = {m["name"] for m in doc["meshes"]}
    assert {"wall_W1", "wall_W5", "column_C1", "room_R1", "room_R2", "frame_D1", "leaf_D1_a", "leaf_D2_b"} <= names
    assert len(doc["cutters"]) == 2 and warnings == []
    assert all(m["props"]["spec_version"] == 1 for m in doc["meshes"] if "spec_id" in m["props"])
    assert {c["name"] for c in doc["cameras"]} >= {"cam_verify", "cam_top", "cam_iso_ne", "cam_room_R1"}

def test_verify_camera_maps_one_pixel_to_mm_per_px():
    doc, _ = build_input_for(spec_with_rooms(), None, (1000, 600))   # px_to_mm [10,0,0,0,-10,6000]
    cam = next(c for c in doc["cameras"] if c["name"] == "cam_verify")
    assert cam["ortho_scale"] == pytest.approx(10000) and cam["resolution"] == [1000, 600]
    assert cam["location"][:2] == pytest.approx([5000, 3000])

def test_missing_template_skipped_with_warning(tmp_path):
    s = apply(spec_with_rooms(), [{"op": "add_object", "template_id": "rack", "template_version": "9.9.9",
                                   "position": (2000, 2000, 0), "dims": (600, 1200, 2000)}], "editor", 2)
    doc, warnings = build_input_for(s, tmp_path, None)
    assert doc["instances"] == [] and warnings == ["object O1: template rack@9.9.9 not found"]

def test_instance_scale_from_dims(tmp_path, placeholder_root):            # placeholder_root fixture: make_placeholders once per session
    s = apply(spec_with_rooms(), [{"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.0.0",
                                   "position": (2000, 2000, 0), "dims": (600, 1000, 2200)}], "editor", 2)
    doc, _ = build_input_for(s, placeholder_root, None)
    assert doc["instances"][0]["scale"] == pytest.approx([1.0, 1000 / 1200, 1.1])
```

```python
# tests/builder/test_instances.py
@pytest.mark.blender
def test_instances_are_linked_duplicates_and_only_in_full_glb(tmp_path, placeholder_root):
    s = apply(spec_with_rooms(), [add_rack((2000, 2000)), add_rack((3000, 2000))], "editor", 2)
    doc, _ = build_input_for(s, placeholder_root, None); doc["cameras"] = []
    assert build(tmp_path, doc).returncode == 0
    full = GLTF2().load(str(tmp_path / "out" / "layout_full.glb")); shell = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    assert {"obj_O1", "obj_O2"} <= {n.name for n in full.nodes} and "obj_O1" not in {n.name for n in shell.nodes}
    assert len(full.meshes) < len(full.nodes)          # instances share mesh data
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/build_prep/test_assemble.py tests/builder/test_instances.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement assembler, kamera, instance, anotasi**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run --env-file .env pytest tests/build_prep tests/builder -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/build_prep builder tests && rtk git commit -m "feat(build_prep): build_input assembler, cameras, template instances, annotations"
```

---

### Task 7: Render di builder (verifikasi + dokumen)

**Files:**
- Create: `builder/render.py`
- Modify: `builder/build.py`
- Test: `tests/builder/test_render.py`

**Interfaces:**
- Consumes: `cameras` di dokumen v1.
- Produces: `builder/render.py render_all(cameras, render_cfg, out_dir)`, dijalankan setelah export. Per kamera:
  - **`mode="verify"`**: Workbench, `shading.light="FLAT"`, `color_type="OBJECT"`. Objek di `Walls`/`Columns` diberi warna hitam, objek lain disembunyikan dari render. Latar putih (`world`/`film_transparent=False`, warna latar #FFFFFF), `display.render_aa="OFF"`, `color_management.view_transform="Standard"`. Hasilnya 8-bit PNG.
  - **`mode="doc"`**: engine dari `render.engine` (default Workbench, `color_type="MATERIAL"`, `light="STUDIO"`, `render_aa="8"`). Annotations terlihat hanya untuk `cam_top`.
  - **`cutaway_mm`**: sebelum render, tambahkan modifier `BOOLEAN` `INTERSECT` (solver `FAST`) ke setiap objek `Walls`/`Columns` dengan kotak potong z 0…cutaway (disembunyikan); hapus setelah render. Export sudah selesai lebih dulu, jadi file export tidak terpengaruh.
  - Progres `@@PROGRESS` 70–99 dibagi rata per kamera.

- [ ] **Step 1: Tulis test yang gagal**

```python
@pytest.mark.blender
def test_verify_render_is_binary_and_aligned(tmp_path):
    doc, _ = build_input_for(spec_with_rooms(), None, (1000, 600))
    assert build(tmp_path, doc).returncode == 0
    img = cv2.imread(str(tmp_path / "out" / "verify_top.png"), cv2.IMREAD_GRAYSCALE)
    assert img.shape == (600, 1000) and set(np.unique(img)) <= {0, 255}
    # W1 runs along y=0 mm -> image row 600 (bottom); its 200 mm thickness = 20 px tall band ending at the bottom
    assert img[595, 500] == 0 and img[300, 250] == 255         # wall pixel black, room interior white

@pytest.mark.blender
def test_doc_renders_exist(tmp_path):
    doc, _ = build_input_for(spec_with_rooms(), None, None)
    build(tmp_path, doc)
    for f in ("top.png", "iso_ne.png", "iso_nw.png", "iso_se.png", "iso_sw.png", "room_R1.png", "room_R2.png"):
        assert cv2.imread(str(tmp_path / "out" / "renders" / f)) is not None
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/builder/test_render.py -q`
Expected: FAIL (file render tidak ada)

- [ ] **Step 3: Implement `render.py`**, lalu panggil dari `build.py` setelah export.

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run --env-file .env pytest tests/builder -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add builder tests/builder/test_render.py && rtk git commit -m "feat(builder): verification and document renders with cutaway"
```

---

### Task 8: Verifikasi (glb 1:1, grid, IoU)

**Files:**
- Create: `core/verify/__init__.py`, `core/verify/glb_check.py`, `core/verify/iou.py`, `core/verify/run.py`
- Test: `tests/verify/__init__.py`, `tests/verify/test_verify.py`

**Interfaces:**
- Consumes: `build_input` (meshes), `shell.glb`, `verify_top.png`, gambar input.
- Produces:
  - `glb_check(glb: Path, doc: dict) -> dict`: untuk setiap node `wall_*`, bbox dari accessor POSITION (glTF → spec: x, −z, y, ×1000) dibandingkan bbox verts mesh di dokumen (setelah cutter, bbox tidak berubah). Hasil `{max_err_mm, pass: max_err_mm ≤ 1, checked}`.
  - `grid_check(spec: Spec, dims: list[tuple[str,str,int]] | None) -> dict`: `{status: "skipped"}` bila `dims` None; selain itu `{max_err_mm, pass}` (selisih jarak sumbu vs dimensi). Di M2 selalu `skipped`; diisi OCR di M5.
  - `plan_wall_mask(image: np.ndarray) -> np.ndarray` (uint8 0/255): mask dinding sederhana:
    1. biner `gray < 110`;
    2. hapus teks: bbox `run_ocr` (diisi putih, dilasi 2 px);
    3. closing kernel 7×7 (mengisi celah garis ganda);
    4. opening kernel 3×3 (membuang garis tipis tunggal);
    5. buang komponen < 40 px.
    Disempurnakan di M5.
  - `iou(render_mask: np.ndarray, plan_mask: np.ndarray) -> float`: kedua mask didilasi 1 px, lalu |∩|/|∪|.
  - `diff_image(render_mask, plan_mask) -> np.ndarray`: BGR; hijau = keduanya, merah = hanya denah, biru = hanya model.
  - `run_verify(out_dir: Path, spec: Spec, doc: dict, image_path: Path | None) -> dict`: menulis `verify.json` (format persis `06` §6) + `iou_mask.png`. Tanpa gambar → `iou: null`, `status` dari glb saja, warning `"no input image: IoU skipped"`. Status: glb gagal → `failed`; IoU < 0.70 → `needs_attention`; 0.70–0.85 → `succeeded` + warning; ≥ 0.85 → `succeeded`.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_iou_identical_and_disjoint():
    a = np.zeros((50, 50), np.uint8); a[10:20, 10:40] = 255
    b = np.zeros((50, 50), np.uint8); b[30:40, 10:40] = 255
    assert iou(a, a) == pytest.approx(1.0) and iou(a, b) == pytest.approx(0.0)

def test_status_thresholds():
    assert verify_status(glb_pass=True, iou=0.9) == ("succeeded", [])
    assert verify_status(True, 0.8)[0] == "succeeded" and verify_status(True, 0.8)[1]
    assert verify_status(True, 0.6)[0] == "needs_attention" and verify_status(False, 0.95)[0] == "failed"

def test_plan_mask_fills_double_line_wall():
    img = np.full((100, 200), 255, np.uint8); img[40, 20:180] = 0; img[46, 20:180] = 0   # 6 px double line
    m = plan_wall_mask(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), ocr=False)
    assert (m[41:46, 50] == 255).all()

@pytest.mark.blender
def test_glb_check_passes_on_built_fixture(tmp_path):
    doc, _ = build_input_for(spec_with_rooms(), None, None); doc["cameras"] = []
    build(tmp_path, doc)
    r = glb_check(tmp_path / "out" / "shell.glb", doc)
    assert r["pass"] and r["checked"] == 5 and r["max_err_mm"] <= 1

def test_verify_without_image_skips_iou(tmp_path, built_fixture_dir):   # fixture: built two-room output (session scope)
    v = run_verify(built_fixture_dir, spec_with_rooms(), load_doc(built_fixture_dir), None)
    assert v["iou"] is None and "no input image: IoU skipped" in v["warnings"] and v["status"] == "succeeded"
```
`plan_wall_mask(image, ocr=True)` memakai parameter `ocr` agar test unit tidak memanggil RapidOCR. `verify_status(glb_pass, iou) -> tuple[str, list[str]]` diekspor dari `run.py`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/verify -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `core/verify/*`**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run --env-file .env pytest tests/verify -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/verify tests/verify && rtk git commit -m "feat(verify): glb 1:1 check, grid check stub, wall mask and IoU"
```

---

### Task 9: Dokumen map 3D (HTML + PDF)

**Files:**
- Create: `core/report/__init__.py`, `core/report/overlay.py`, `core/report/data.py`, `core/report/render.py`, `core/report/templates/report.html.j2`, `core/report/templates/report.css`
- Modify: `benchmarks/tools/gt_author.py` (impor `render_overlay` dari `core.report.overlay`; hapus duplikatnya)
- Test: `tests/report/__init__.py`, `tests/report/test_report.py`

**Interfaces:**
- Produces:
  - `core.report.overlay.render_overlay(spec, image_path, out)`: dipindah dari `gt_author` tanpa perubahan perilaku.
  - `core.report.data.report_data(spec, verify: dict | None, run: dict) -> dict` untuk 12 bagian `06` §7.2:
    - `summary`: luas kotor, luas bersih total (Σ ruang non-`outdoor`), jumlah ruang/pintu/kolom, tinggi default, skala, sumber skala, IoU;
    - `rooms` (urut ID, tanpa `outdoor`);
    - `doors`: ruang A ↔ B dari `rooms[].doors`, "luar" bila hanya satu ruang;
    - `stairs` dari `stair_metrics`, dengan arah naik sebagai kompas 8 arah dari vektor flight pertama;
    - `walls`: total panjang per `kind` dan per tebal;
    - `objects` per template dan per ruang;
    - `issues` dari `validate(spec)` + `verify.warnings`;
    - `provenance`: elemen ber-`source` editor/manual/llm, dihitung per sumber;
    - `metadata`: sha256, run id, versi kode `git rev-parse --short HEAD`, versi Blender, versi prompt "—".
  - `core.report.render.write_report(out_dir: Path, data: dict, renders: dict[str, str]) -> tuple[Path, Path]`. Menulis `report.html` (gambar relatif `renders/…`) dan `report.pdf` (WeasyPrint, A4 landscape, nomor halaman lewat `@page { @bottom-right { content: counter(page) " / " counter(pages) } }`). CSS mengikuti Carbon light: latar #FFFFFF, teks #161616, aksen #0F62FE, tabel bergaris #E0E0E0, font `"IBM Plex Sans", Helvetica, Arial, sans-serif`. Bagian tanpa data menampilkan "—".

- [ ] **Step 1: Tulis test yang gagal**

```python
SECTIONS = ["Ringkasan", "Denah asli & overlay", "Top view", "Isometrik", "Tabel ruang", "Jadwal pintu", "Tangga",
            "Ringkasan dinding", "Objek", "Render per ruang", "Peringatan & provenance", "Metadata"]

def test_report_has_all_sections_and_pdf(tmp_path):
    data = report_data(spec_with_rooms(), {"iou": 0.9, "status": "succeeded", "warnings": []}, {"run_id": "r1"})
    html, pdf = write_report(tmp_path, data, renders={})
    text = html.read_text()
    assert all(f">{s}<" in text for s in SECTIONS) and "KIRI" in text
    assert pdf.read_bytes().startswith(b"%PDF")

def test_door_schedule_rooms():
    data = report_data(spec_with_rooms(), None, {})
    d1 = next(d for d in data["doors"] if d["id"] == "D1"); d2 = next(d for d in data["doors"] if d["id"] == "D2")
    assert (d1["rooms"], d2["rooms"]) == ("KIRI ↔ KANAN", "KIRI ↔ luar")

def test_report_renders_with_empty_sections(tmp_path):
    s = spec_with_rooms().model_copy(update={"stairs": [], "objects": []})
    html, _ = write_report(tmp_path, report_data(s, None, {}), renders={})
    assert html.read_text().count("—") >= 3

def test_overlay_moved_without_behaviour_change(tmp_path):
    from benchmarks.tools import gt_author
    assert gt_author.render_overlay is render_overlay
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/report -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `core/report/*` dan pindahkan overlay**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run --env-file .env pytest tests/report tests/benchmarks -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/report benchmarks/tools/gt_author.py tests/report && rtk git commit -m "feat(report): 3D map document html and pdf"
```

---

### Task 10: CLI `build` + end-to-end GT Gatsu

**Files:**
- Create: `core/cli.py`, `core/blender_run.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: semua task sebelumnya; `load_settings().blender_bin`.
- Produces:
  - `core.blender_run.parse_progress(line: str) -> tuple[int, str] | None` (mis. `"@@PROGRESS 60 built"` → `(60, "built")`).
  - `core.blender_run.run_blender(build_input: Path, out_dir: Path, blender_bin: str, timeout_s: int = 300, on_line: Callable[[str], None] | None = None) -> int`: stream stdout+stderr baris per baris ke `on_line` dan ke `out_dir/blender.log`; timeout → kill + return 124.
  - `core.cli main(argv)`, subcommand `build <spec.json> <out_dir> [--image PATH] [--templates DIR] [--engine BLENDER_WORKBENCH|BLENDER_EEVEE]`:
    1. validasi spec (error → exit 2);
    2. assemble;
    3. tulis ke `out_dir.tmp-<pid>/`;
    4. jalankan Blender;
    5. verify;
    6. report;
    7. rename atomik ke `out_dir` (folder lama dihapus dulu bila ada).

    Gagal di langkah mana pun → hapus folder sementara, cetak path log yang disalin ke `out_dir.failed.log`, exit 1. Cetak progres dan ringkasan (status, IoU, galat glb, durasi).

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_parse_progress():
    assert parse_progress("@@PROGRESS 60 built walls") == (60, "built walls") and parse_progress("noise") is None

@pytest.mark.blender
def test_cli_failed_build_leaves_no_partial_output(tmp_path, monkeypatch):
    monkeypatch.setenv("BLENDER_BIN", "/usr/bin/false")
    spec = tmp_path / "spec.json"; spec.write_text(spec_with_rooms().model_dump_json())
    assert cli_main(["build", str(spec), str(tmp_path / "out")]) == 1
    assert not (tmp_path / "out").exists() and not list(tmp_path.glob("out.tmp-*"))

@pytest.mark.blender
@pytest.mark.slow
def test_gatsu_end_to_end(tmp_path, placeholder_root):
    spec = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
    spec = apply(spec, ten_racks_in_galery(), "editor", spec.meta.version + 1)   # 10 placeholder objects
    p = tmp_path / "spec.json"; p.write_text(spec.model_dump_json())
    t0 = time.monotonic()
    rc = cli_main(["build", str(p), str(tmp_path / "out"), "--image", "floorplan/plan.jpeg", "--templates", str(placeholder_root)])
    elapsed = time.monotonic() - t0
    v = json.loads((tmp_path / "out" / "verify.json").read_text())
    print(f"elapsed {elapsed:.1f}s iou {v['iou']} glb {v['glb_check']}")
    assert rc == 0 and elapsed <= 90 and v["glb_check"]["pass"]
    for f in ("layout.blend", "shell.glb", "layout_full.glb", "layout.fbx", "layout.obj", "report.html", "report.pdf"):
        assert (tmp_path / "out" / f).exists()

@pytest.mark.blender
@pytest.mark.slow
def test_gatsu_iou_meets_target(gatsu_out):                                   # reuse output of the e2e test (session fixture)
    assert json.loads((gatsu_out / "verify.json").read_text())["iou"] >= 0.85
```
`ten_racks_in_galery()` = 10 op `add_object` rack-42u-600x1200 di galery (x = 2000…11000 mm step 1000, y = 2000). Fixture `placeholder_root` (session) menjalankan `make_placeholders` sekali ke `tmp_path_factory`. Fixture `gatsu_out` menjalankan e2e sekali dan dipakai kedua test.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/test_cli.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `blender_run.py` dan `cli.py`**

- [ ] **Step 4: Jalankan, lalu ukur**

Run: `rtk uv run --env-file .env pytest tests/test_cli.py -q -s`
Expected: PASS untuk parse/failed/e2e (≤ 90 s, glb ≤ 1 mm).

Untuk `test_gatsu_iou_meets_target`: bila IoU < 0.85 dengan mask sederhana M2, analisis `iou_mask.png`, apakah merahnya furnitur/teks/hatch denah atau biru (elemen model yang tidak ada di denah). Perbaikan mask yang **umum** (bukan khusus Gatsu) boleh dicoba sekali. Bila tetap < 0.85, tandai `xfail(strict=False, reason=...)`, catat angka dan penyebabnya di `benchmarks/reports/m2-verify.md`, dan bawa target ke M5 (mask dari kandidat ekstraksi). Jangan mengubah GT demi IoU.

- [ ] **Step 5: Verifikasi visual**

Buka `out/renders/top.png`, `iso_ne.png`, satu `room_*.png`, dan halaman pertama `report.pdf` (konversi via `pdftoppm`, atau screenshot dari HTML). Periksa: orientasi utara sama dengan denah, pintu terpotong, tangga bertingkat, rack di galery. Simpan bukti ke scratchpad.

- [ ] **Step 6: Commit, lalu tutup M2 di ROADMAP**

```bash
rtk git add core/cli.py core/blender_run.py tests/test_cli.py benchmarks/reports && rtk git commit -m "feat(cli): build command, atomic outputs, gatsu end-to-end"
```

Centang tugas M2 di `ROADMAP.md` dan tulis blok "Status M2": durasi build GT, galat glb, IoU, dan file output. Catat penyimpangan (Workbench sebagai engine default, grid check `skipped` sampai M5, IoU bila di-xfail, test builder lewat pytest alih-alih `builder/tests/run.py`).

```bash
rtk git add ROADMAP.md && rtk git commit -m "docs: close M2"
```
