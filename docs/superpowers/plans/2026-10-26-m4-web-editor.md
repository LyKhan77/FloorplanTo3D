# M4 — Web Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tab **Editor** di detail project memuat shell Gatsu dan spec. Di sana pengguna bisa:
- mengukur;
- mengubah tinggi dinding;
- menempatkan, memindah, dan me-resize template;
- mengoreksi dinding, pintu, dan tangga lewat panel numerik;
- menyimpan ops sebagai versi spec baru, lalu me-regenerate tanpa keluar dari editor.

**Architecture:** Semua kode editor ada di `web/src/editor/`, dalam tiga lapis:
1. **Inti murni TS** (`ops/`, `lib/`): reducer ops yang meniru `core/spec/ops.py` (termasuk alokasi ID), aturan komposisi ops lokal, serta util ukur, snap, resize, dan OBB. Semua diuji Vitest. Paritas reducer dengan server dijaga oleh fixture yang dibangkitkan pytest.
2. **Store Zustand** (`store.ts`): base spec, ops lokal, undo/redo, seleksi, tool, layer, dan ukuran.
3. **UI**: panel React + Carbon, ditambah viewport react-three-fiber/drei di `viewport/`.

Server M3 tidak berubah. Editor memakai `GET /specs/HEAD`, `POST /specs`, `POST /specs/validate`, `GET /outputs`, `GET /templates`, `POST /regenerate`, dan SSE yang sudah ada.

**Tech Stack:** React 18, TypeScript, three 0.186, @react-three/fiber 8, @react-three/drei 9, **zustand 5 (baru)**, `@carbon/react` g100, TanStack Query, Vitest + Testing Library (jsdom). E2E lewat Playwright MCP.

**Spec:**
- `PRD/07-web-editor.md` (otoritas editor);
- `PRD/10-template-contract.md` §2–§4 (resize, snap, clearance, orientasi);
- `PRD/03-layout-spec.md` §1 (sumbu) dan §11 (ops);
- `PRD/01-requirements.md` FR-WE-01…13, FR-WE-15, NFR-PF-04;
- `ROADMAP.md` M4.

Branch dasar: `m3-server`.

## Global Constraints

- **Lingkungan kerja:**
  - Semua perintah shell diawali `rtk`. Jangan membaca atau meng-commit `server-info.txt`.
  - Kerja di branch `m4-editor`, dibuat dari `m3-server`.
- **Sumbu dan satuan:**
  - Spec dalam mm: +X timur, +Y utara, +Z atas.
  - Konversi ke three (meter, Y-up): `X = x/1000`, `Y = z/1000`, `Z = −y/1000`.
  - `rotation` spec (derajat, CCW terhadap +Z) menjadi `rotation.y = +rotation·π/180`.
  - Template: `w` → X lokal, `d` → Y spec, `h` → Z spec. Pivot bottom-center. Depan = +Y spec.
- **Tampilan:**
  - Jarak dan tinggi ditampilkan dalam meter dengan 3 desimal (`12.400 m`). Luas dalam m² dengan 2 desimal. Input numerik dalam mm.
  - Warna: seleksi `#0f62fe`, tabrakan `#fa4d56`, pratinjau geometri `#ff832b`.
  - Layout editor minimal 1056 px. Panel kiri dan kanan bisa disembunyikan.
  - Teks UI berbahasa Indonesia, Carbon g100.
- **Nilai dan ambang:**
  - Tinggi dinding 1000–12000 mm.
  - Grid snap 600 mm, aktif secara default. `Alt` menonaktifkan snap sementara. `template.snap.align`: `edge` atau `center`; rotasi non-kelipatan 90° memakai `center`.
  - Rotasi: `R` = +90°, `Shift+R` = −90°. Gizmo rotasi snap 15°, `Alt` = bebas.
  - Validasi live memakai debounce 500 ms. Stack undo 100 langkah. InstancedMesh dipakai bila jumlah instance per template > 20.
- **Ops lokal:**
  - Ops lokal memakai JSON op server persis (tipe `SpecOpsSchema` di `web/src/types/ops.ts`, hasil generate; jangan diubah manual).
  - **Ops lokal tidak pernah merujuk ID yang tidak ada di base spec.** Edit pada elemen yang belum disimpan digabung ke op pembuatnya, atau ditolak (Task 3).
- **Lingkup:**
  - Reducer klien tidak menghitung ruang. Ruang dihitung ulang server saat Save (07 §6b).
  - Ukuran tidak disimpan ke spec. `add_stair` tidak tersedia di editor (07 §6b).
- **Dependensi:** hanya `zustand@^5` yang ditambahkan. SSAO ("kualitas tinggi", 07 §9) **tidak** dibuat karena butuh `postprocessing`. Penyimpangan ini dicatat di ROADMAP.
- **Mutu:** `npm test`, `npm run lint` (oxlint), dan `npm run build` (tsc + vite) hijau di setiap commit. Komponen 3D tidak bisa dirender di jsdom, jadi logikanya diletakkan di fungsi murni yang diuji Vitest, lalu diverifikasi di browser pada Task 15.
- **Hook debug:** di mode dev saja, `window.__editor = useEditorStore` dan `window.__editorStats` (fps, jumlah node shell per `spec_type`) disediakan untuk verifikasi E2E.

## Review Focus

1. **Rebase setelah 409 ketika tab lain menghapus elemen yang disentuh ops lokal, atau menambah objek sehingga ID bergeser.**
   - Harapan: ops lokal tidak pernah menimpa elemen lain. Op yang gagal didaftar. "Batal" tidak menghilangkan apa pun.
   - Test: Task 3 `rebase lists ops whose target vanished and never touches the other tab's new object`.
2. **Edit pada elemen yang belum disimpan** (memindah rack yang baru di-drop, menghapusnya, mengubah lebar pintu baru, memisah dinding baru).
   - Harapan: edit digabung ke op pembuat atau ditolak dengan pesan. Payload Save tidak berisi ID prediksi.
   - Test: Task 3 `folds edits of unsaved elements into their creation op` dan `rejects ops that would reference a predicted id`.
3. **Drop atau pindah ke luar ruang, ke dalam lubang ruang, atau tepat di batas.**
   - Harapan: drop ditolak dengan toast, pindah dikembalikan. Titik di batas masuk ke ruang pertama, sama seperti `shape.covers` server.
   - Test: Task 1 `roomAt matches server covers semantics (holes, boundary, outside)`.
4. **Resize atau input numerik di luar `resizable`, di luar `step`, sumbu `false`, atau `scale_mode: fixed`.**
   - Harapan: nilai di-clamp ke min/max dan dibulatkan ke step dari min. Sumbu terkunci tidak berubah.
   - Test: Task 4 `clampDims clamps, steps from min, and keeps locked axes`.
5. **Input tinggi dinding kosong, di luar 1000–12000, atau reset ke default.**
   - Harapan: ditolak inline dan tidak ada op terkirim. Tombol reset mengirim `height: null`.
   - Test: Task 8 `wall height rejects out-of-range input and resets with null`.

---

### Task 1: Reducer ops (non-geometri) + alokasi ID + `roomAt`

**Files:**
- Create: `web/src/editor/ops/reducer.ts`, `web/src/editor/ops/ids.ts`, `web/src/editor/lib/geom.ts`
- Test: `web/src/editor/ops/reducer.test.ts`, `web/src/editor/lib/geom.test.ts`

**Interfaces:**
- Consumes: `Spec` (`web/src/types/spec.ts`), `SpecOpsSchema` (`web/src/types/ops.ts`).
- Produces:
  - `export type EditorOp = SpecOpsSchema[number]`
  - `export interface OpFailure { index: number; op: string; message: string }`
  - `export interface ApplyResult { spec: Spec; failed: OpFailure[]; created: Record<string, number> }`. `created` memetakan ID baru ke indeks op yang membuatnya.
  - `applyOps(base: Spec, ops: EditorOp[]): ApplyResult`. Fungsi ini murni dan tidak memutasi `base`. Op yang gagal dilewati (bukan atomik seperti server), tetapi op berikutnya tetap diterapkan.
  - `ids.ts`:
    - `idKey(id: string): [string, number]`;
    - `seedIdSeq(spec: Spec): void`;
    - `takeId(spec: Spec, prefix: string): string`. Mirror persis `core/spec/ids.py`: `max(id_seq[prefix], semua nomor terpakai) + 1`.
  - `geom.ts`:
    - `pointInPolygon(p: [number, number], poly: [number, number][]): 'inside' | 'boundary' | 'outside'`;
    - `roomAt(spec: Spec, x: number, y: number): string | null`. Ruang pertama (urutan `spec.rooms`) yang *covers* titik: di dalam atau di batas outer, dan tidak *strictly inside* lubang mana pun.
  - `roundHalfEven(v: number): number`, sama dengan `round()` Python, dipakai di semua pembulatan mm.

- [ ] **Step 1: Tulis test yang gagal**

`reducer.test.ts` memuat GT dengan `import gt from '../../../../benchmarks/gatsu/gt_spec.json'`. Bila tsc menolak, aktifkan `resolveJsonModule` di `tsconfig.app.json` dan catat ruling.
- `add_object gets the next id and the room under its position`:
  - Op: `add_object` di `label_pos` R. MEETING.
  - Harapan: `objects[0].id === 'O1'`, `room_id` = ID R. MEETING, `created.O1 === 0`.
- `ids are never reused`: add (O1), delete O1, add lagi → `O2`.
- `set_wall_height "*" null clears overrides`: setelah `set_wall_height W1 4500` lalu `set_wall_height * null`, semua `walls[].height === null`.
- `set_default wall_height and unknown key`: `wall_height: 4500` diterapkan. `key: 'nope'` masuk `failed` dengan `index` 1.
- `rename_room / set_room_type / update_object apply only given fields`.
- `missing target fails that op only and base stays untouched`: snapshot `JSON.stringify(gt)` sama sebelum dan sesudah.

`geom.test.ts`:
- `roomAt matches server covers semantics (holes, boundary, outside)`. Buat persegi 0..1000 dengan lubang 400..600:
  - (500, 500) → `null`;
  - (400, 500), di batas lubang → ruang tersebut;
  - (0, 500) → ruang;
  - (−1, 0) → `null`;
  - dua ruang berbagi tepi: titik di tepi → ruang pertama.
- `roundHalfEven(2.5) === 2`, `roundHalfEven(3.5) === 4`, `roundHalfEven(-2.5) === -2`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- src/editor`
Expected: FAIL, modul tidak ditemukan.

- [ ] **Step 3: Implementasi `ids.ts`, `geom.ts`, dan `reducer.ts`**

Reducer bekerja di `structuredClone(base)`. Langkahnya:
1. Panggil `seedIdSeq` sekali.
2. `switch (op.op)` untuk: `add_object`, `update_object` (hanya field yang ada di op; `label: null` diizinkan), `delete_object`, `set_wall_height`, `set_default` (key harus ada di `Defaults`), `rename_room`, `set_room_type`.
3. Setiap `add_object` menghitung `room_id = roomAt(...)`. `update_object` dengan `position` juga menghitung ulang `room_id`.
4. Op lain (geometri) masuk `failed` dengan pesan `"unsupported"` sampai Task 2. `add_stair` masuk `failed` dengan pesan `"tidak tersedia di editor"`.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test -- src/editor && rtk npm run lint && rtk npm run build`
Expected: PASS, lint dan build bersih.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor web/tsconfig.app.json && rtk git commit -m "feat(editor): ops reducer with server id allocation and roomAt"
```

---

### Task 2: Reducer ops geometri + fixture paritas dari server

**Files:**
- Modify: `web/src/editor/ops/reducer.ts`
- Create: `tests/test_editor_parity.py`, `web/src/editor/ops/parity.fixture.json` (dibangkitkan), `web/src/editor/ops/parity.test.ts`

**Interfaces:**
- Consumes: `applyOps`, `takeId`, `idKey`, `roundHalfEven` (Task 1); `core.spec.ops.apply` (Python).
- Produces: `applyOps` mendukung `delete_wall` (cascade opening), `merge_walls`, `split_wall`, `move_wall`, `add_wall`, `set_door` (hanya pintu), `delete_opening`, `add_opening` (`sill` default dari `defaults.window_sill` untuk jendela, 0 untuk pintu), `set_stair`, dan `delete_stair`. Ruang tidak disentuh.
- Fixture: `{"cases": [{"name": str, "ops": [...], "expected": {"walls": [...], "openings": [...], "stairs": [...], "objects": [...], "defaults": {...}, "id_seq": {...}}}]}`. Semua elemen tanpa `provenance`. Field `room_id` objek ikut dibandingkan, tetapi `room_id` tangga tidak.

- [ ] **Step 1: Tulis generator paritas sebagai test pytest**

`tests/test_editor_parity.py::test_editor_parity_fixture_is_current` membangun kasus dari GT. ID dan offset dipilih dari GT oleh kode, tidak di-hardcode:
- `move_wall` (geser `a` W1 +100 mm X);
- `add_wall`;
- `split_wall` pada dinding yang punya pintu, di offset 100 mm setelah ujung pintu;
- split lalu `merge_walls` kedua potongan (reason "gabung");
- `delete_wall` pada dinding yang punya pintu (cascade);
- `set_door` (lebar +100, `hinge`);
- `add_opening` pintu dan jendela;
- `delete_opening`;
- `set_stair` yang menukar `start`/`end` semua flight dan `top_z` 4000;
- `delete_stair`;
- `add_object` lalu `update_object` (posisi baru);
- `set_default` lalu `set_wall_height`.

Untuk tiap kasus: `core.spec.ops.apply(gt, ops, "editor", 2)`, lalu ambil field di atas. Bila env `UPDATE_PARITY=1`, tulis fixture. Bila tidak, `assert` isi file sama dengan hasil.

Run: `UPDATE_PARITY=1 rtk uv run --env-file .env pytest -q tests/test_editor_parity.py`, lalu `rtk uv run --env-file .env pytest -q tests/test_editor_parity.py`
Expected: fixture tertulis, lalu PASS.

- [ ] **Step 2: Tulis test Vitest yang gagal**

`parity.test.ts`: untuk setiap kasus fixture, `applyOps(gt, case.ops)` harus menghasilkan `failed` kosong, dan `walls`, `openings`, `stairs`, `objects`, `meta.defaults`, serta `meta.id_seq` (tanpa provenance) sama persis dengan `expected` (`toEqual`).

Run: `cd web && rtk npm test -- parity`
Expected: FAIL, semua kasus geometri `unsupported`.

- [ ] **Step 3: Implementasi handler geometri di `reducer.ts`**

Port baris demi baris dari `core/spec/ops.py`:
- `_unit`;
- `_pt` dengan `roundHalfEven`;
- toleransi paralel 1.5°;
- `keep` = ID terkecil menurut `idKey`;
- remap opening dan cermin `hinge`/`swing` pada merge;
- split menolak offset di luar (0, panjang) atau yang memotong bukaan;
- `take_id('W' | 'D' | 'N')`.

Pesan error tidak perlu identik dengan server.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add tests/test_editor_parity.py web/src/editor/ops && rtk git commit -m "feat(editor): geometry ops in the client reducer, parity fixture from the server"
```

---

### Task 3: Komposisi ops lokal, undo/redo, rebase, dan store Zustand

**Files:**
- Modify: `web/package.json` (+`zustand@^5`)
- Create: `web/src/editor/ops/compose.ts`, `web/src/editor/store.ts`
- Test: `web/src/editor/ops/compose.test.ts`, `web/src/editor/store.test.ts`

**Interfaces:**
- Consumes: `applyOps`, `EditorOp`, `OpFailure` (Task 1).
- Produces:
  - `pushOp(base: Spec, ops: EditorOp[], op: EditorOp): { ops: EditorOp[] } | { error: string }`.
  - `targetIds(op: EditorOp): string[]`. Isinya `id`, atau `ids` untuk merge, atau `wall_id` untuk `add_opening`. `"*"` diabaikan.
  - `rebasePreview(head: Spec, ops: EditorOp[]): OpFailure[]`. Failure dihitung dengan `applyOps(head, ops)`, ditambah op yang target-nya tidak ada di `head`.
  - `useEditorStore` (zustand). State:
    - `projectId: string | null`, `baseVersion: number | null`, `base: Spec | null`;
    - `ops: EditorOp[]`, `past: EditorOp[][]`, `future: EditorOp[][]`;
    - `view: Spec | null`, `failed: OpFailure[]` (dihitung ulang setiap `ops` berubah);
    - `selection: string[]`;
    - `tool: 'select' | 'distance' | 'room-area' | 'area' | 'height' | 'add-wall'`;
    - `mode: 'orbit' | 'top' | 'walk'`;
    - `snap: boolean`;
    - `layers: Record<'walls' | 'columns' | 'doors' | 'objects' | 'labels' | 'grid' | 'axes', boolean>` (semua `true`, kecuali `axes`);
    - `cutaway: number | null` (mm);
    - `measurements: Measurement[]`;
    - `notice: { kind: 'error' | 'warning' | 'info'; text: string } | null`;
    - `saveIssues: Issue[]`.
  - Aksi store:
    - `load(projectId, spec)`, `apply(op): boolean`, `applyMany(ops): boolean` (satu langkah undo);
    - `undo()`, `redo()`;
    - `select(ids: string[], additive?: boolean)`, `setTool`, `setMode`, `toggleLayer`, `setSnap`, `setCutaway`;
    - `addMeasurement`, `removeMeasurement`, `clearMeasurements`;
    - `markSaved(spec: Spec)`, `acceptRebase(head: Spec, drop: number[])`, `setNotice`.
  - `Measurement = { id: string; kind: 'distance' | 'room-area' | 'area' | 'height'; points: [number, number, number][]; value: number; label: string }`.
  - `Issue = { code: string; severity: 'error' | 'warning' | 'info'; element_ids: string[]; message: string }`.

Aturan `pushOp`, berurutan:
1. Op tanpa target, atau semua target ada di `base` (atau bernilai `"*"`):
   - Bila op terakhir bertipe sama dengan target sama dan tipenya `update_object | move_wall | set_door | set_stair | set_wall_height`, gabungkan field-nya (op baru menang).
   - Selain itu, tambahkan op di akhir.
2. Target adalah ID prediksi. Cari indeks pembuatnya `k` lewat `applyOps(base, ops).created`, lalu:
   - `update_object` → gabungkan `position`, `rotation`, `dims`, `label` ke `add_object[k]`. Bila op berisi `locked`, kembalikan error `"Save dulu sebelum mengunci objek baru"`.
   - `delete_object` → hapus op `k`.
   - `move_wall` → gabungkan `a`, `b`, `thickness`, `kind` ke `add_wall[k]`.
   - `delete_wall` → hapus op `k`.
   - `set_door` → gabungkan ke `add_opening[k]`.
   - `delete_opening` → hapus op `k`.
   - Selain itu (split, merge, tinggi per dinding, bukaan baru di dinding baru, potongan hasil split) → error `"Save dulu: <id> belum disimpan"`.
3. Setelah op dihapus, ID prediksi berikutnya bisa bergeser. Store membuang ID yang tidak lagi ada di `view` dari `selection`.

- [ ] **Step 1: Tulis test yang gagal**

`compose.test.ts`, memakai GT:
- `folds edits of unsaved elements into their creation op`:
  - `add_object` (O1), lalu `update_object O1 {position}`, menghasilkan satu `add_object` dengan posisi baru.
  - `delete_object O1` → `ops` kosong.
  - `add_opening` lalu `set_door {width: 1000}`, menghasilkan satu `add_opening` dengan `width: 1000`.
  - `add_wall` lalu `move_wall {b}` → satu `add_wall`.
- `rejects ops that would reference a predicted id`:
  - `add_wall` (W78) lalu `split_wall W78` → error mengandung `"belum disimpan"`.
  - `update_object O1 {locked: true}` setelah add → error.
- `coalesces consecutive updates of the same base element`: dua `set_wall_height W1` berturut-turut → satu op dengan nilai terakhir.
- `no op in the list ever targets a predicted id`. Properti acak: 200 langkah acak dari `[add_object, update_object, delete_object]` pada ID yang terlihat di `view`. Pada setiap langkah, setiap `targetIds` di `ops` harus ada di `base`.

`store.test.ts`:
- `undo/redo walk the op list and cap at 100`: 105 kali `apply` → `past.length === 100`. Undo dua kali, lalu `ops.length === 103`. Redo sekali → 104. `apply` baru mengosongkan `future`.
- `apply returns false and sets a notice on a rejected op`.
- `rebase lists ops whose target vanished and never touches the other tab's new object`:
  - Base = GT. Ops lokal: `add_object` (prediksi O1), `set_door D1 {width}`, `update_object` dengan target yang tidak ada di head.
  - Head = GT + `add_object` milik tab lain (O1, posisi P) + `delete_opening D1`.
  - `rebasePreview` mendaftar op `set_door` (D1 hilang).
  - Setelah `acceptRebase(head, failedIdx)`: `view.objects` berisi O1 milik tab lain dengan posisi P yang tidak berubah, plus objek lokal sebagai `O2`.
  - Tanpa `acceptRebase`, `ops` tidak berubah.
- `markSaved clears ops, history and sets the new base`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm install zustand@^5 && rtk npm test -- src/editor`
Expected: FAIL pada test baru.

- [ ] **Step 3: Implementasi `compose.ts` dan `store.ts`**

`view` dan `failed` dihitung di dalam setiap aksi yang mengubah `ops` (bukan selector), supaya komponen membaca nilai jadi.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add web/package.json web/package-lock.json web/src/editor && rtk git commit -m "feat(editor): local op composition, undo/redo, rebase and the editor store"
```

---

### Task 4: Util geometri: sumbu, ukur, snap, resize, OBB

**Files:**
- Create: `web/src/editor/lib/coords.ts`, `measure.ts`, `snap.ts`, `resize.ts`, `obb.ts`
- Test: satu file `*.test.ts` per modul

**Interfaces:**
- Consumes: `Spec`, `roomAt`, `roundHalfEven` (Task 1); `Template` (`web/src/api/types.ts`). Tambahkan field kontrak `resizable`, `scale_mode`, `snap`, `clearance`, `allowed_room_types`, `tags`, `metadata` ke interface `Template`.
- Produces:
  - `coords.ts`: `toThree(p: [number, number, number?]): [number, number, number]`, `fromThree(v: { x: number; y: number; z: number }): [number, number, number]`, `rotToThree(deg: number): number`.
  - `measure.ts`:
    - `distance(a, b): { d: number; dx: number; dy: number; dz: number }` (mm);
    - `lockAxis(a, b): [number, number, number]`, mempertahankan komponen Δ terbesar;
    - `shoelaceM2(points: [number, number][]): number`;
    - `formatM(mm: number): string` (`"12.400 m"`), `formatM2(m2: number): string` (`"57.62 m²"`);
    - `nearestSnap<T extends { screen: [number, number] }>(cursor: [number, number], candidates: T[], maxPx = 10): T | null`;
    - `gridIntersections(spec: Spec): [number, number][]`, berisi semua pasangan sumbu vertical × horizontal (`offset` mm).
  - `snap.ts`: `snapPosition(p: [number, number], dims: [number, number, number], rotationDeg: number, snap: { grid_mm: number; align: 'edge' | 'center' }, enabled: boolean): [number, number]`.
  - `resize.ts`: `clampDims(dims: [number, number, number], t: Template): [number, number, number]`, `scaleOf(dims: [number, number, number], t: Template): [number, number, number]`. Hasil `scaleOf` berupa `[sx, sy, sz]` dalam sumbu three: `w/W`, `h/H`, `d/D`.
  - `obb.ts`:
    - `footprint(o: { position: [number, number, number]; rotation: number; dims: [number, number, number] }): [number, number][]` (4 titik CCW);
    - `overlaps(a, b): boolean`. Uji SAT dengan toleransi 1 mm, jadi tepi yang bersentuhan tidak dihitung tabrakan;
    - `collisions(spec: Spec): { a: string; b: string }[]`. Mencakup objek vs objek, objek vs tapak dinding (persegi panjang sepanjang a→b selebar `thickness`), dan objek vs kolom (kotak `size` terotasi).

- [ ] **Step 1: Tulis test yang gagal**

- `coords`:
  - `toThree([1000, 2000, 500])` → `[1, 0.5, -2]`, dan `fromThree` adalah inversnya.
  - Vektor depan +Y yang dirotasi `rotToThree(90)` di sekitar Y three mengarah ke −X spec.
- `measure`:
  - `distance` 3-4-5;
  - `lockAxis([0,0,0], [100, 900, 30])` → `[0, 900, 0]`;
  - `shoelaceM2` pada polygon R. MEETING (GT) cocok dengan `area_m2` ±0.01;
  - `formatM(12400) === '12.400 m'`;
  - `nearestSnap` memilih kandidat ≤ 10 px terdekat, `null` bila > 10 px;
  - `gridIntersections(gt).length` = jumlah sumbu vertical × horizontal.
- `snap`, grid 600, dims `[600, 1200, 2000]`, titik (1000, 1000):
  - edge rot 0 → `[900, 1200]`;
  - edge rot 90 → `[1200, 900]`;
  - center → `[1200, 1200]`;
  - rot 15 dengan edge → hasil sama dengan center;
  - `enabled: false` → titik asli.
- `resize` — `clampDims clamps, steps from min, and keeps locked axes`. Template `w: false`, `d: {min:1000, max:1200, step:100}`, `h: {min:1800, max:2400, step:100}`, dims 600/1200/2000:
  - `[700, 1349, 1750]` → `[600, 1200, 1800]`;
  - `[600, 1049, 2449]` → `[600, 1000, 2400]`;
  - `scale_mode: fixed` → selalu dims template.
  - `scaleOf([600, 1100, 2000])` → `[1, 1, 1100/1200]`.
- `obb`:
  - dua rack 600×1200 berdampingan dengan tepi menempel → tidak bertabrakan; digeser 10 mm saling masuk → bertabrakan;
  - rack yang memotong tapak dinding GT W1 → `{a: 'O1', b: 'W1'}`;
  - rotasi 45° terdeteksi lewat SAT (kasus yang lolos AABB tetapi tidak lolos OBB).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- src/editor/lib`
Expected: FAIL.

- [ ] **Step 3: Implementasi kelima modul**

Snap edge: hitung footprint terotasi kelipatan 90° (w dan d ditukar pada 90/270), snap sudut minimum ke grid dengan `roundHalfEven(v / g) * g`, lalu kembalikan pusatnya. Clamp: `min + roundHalfEven((v − min) / step) * step`, lalu dibatasi ke `[min, max]`.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor/lib web/src/api/types.ts && rtk git commit -m "feat(editor): axis conversion, measure, snap, resize and OBB utilities"
```

---

### Task 5: Data editor + kerangka layout tab Editor

**Files:**
- Create: `web/src/editor/EditorTab.tsx`, `web/src/editor/useEditorData.ts`, `web/src/editor/Toolbar.tsx`, `web/src/editor/StatusBar.tsx`
- Modify: `web/src/pages/ProjectDetailPage.tsx` (tab Editor), `web/src/api/hooks.ts` (`useSpecHead`), `web/src/index.scss`
- Test: `web/src/editor/EditorTab.test.tsx`

**Interfaces:**
- Consumes: `useEditorStore` (Task 3); `useOutputs`, `useTemplates`, `api` (M3).
- Produces:
  - `useSpecHead(projectId): UseQueryResult<Spec>` (`GET /api/projects/{id}/specs/HEAD`).
  - `useEditorData(projectId): { spec?: Spec; shellVersion: number | null; shellUrl: string | null; stale: boolean; templates: Template[]; loading: boolean }`. `shellVersion` = versi output terbesar ≤ HEAD yang berisi `shell.glb`. `stale` = `shellVersion !== HEAD`.
  - `<EditorTab projectId run />`, dengan prop `run: Run | null` dari ProjectDetailPage (dipakai Task 13).
  - CSS grid `.editor`: area `toolbar` / `library` / `viewport` / `props` / `status`. Kelas `.editor--no-left` dan `.editor--no-right` menyembunyikan panel. `min-width: 1056px`.
  - Slot `viewport` sementara berisi placeholder sampai Task 6.

- [ ] **Step 1: Tulis test yang gagal**

Mock `../api/client` dengan `vi.mock`. Bungkus dengan `QueryClientProvider`.
- `shows the stale shell banner`: HEAD v4, output hanya v3. Teks `"Shell dari v3; regenerate untuk memperbarui"` tampil.
- `shows an empty state without any shell`: tanpa output. Teks `"Belum ada shell. Regenerate dulu."` dan tombol "Regenerate" tampil.
- `toolbar shows version and unsaved count`: store dengan 3 ops. Teks `"v4 (unsaved: 3)"` tampil.
- `warns before unload with unsaved ops`: `window.dispatchEvent(new Event('beforeunload', { cancelable: true }))` → `defaultPrevented === true` saat ada ops, dan `false` saat ops kosong.
- `store loads HEAD once per project`: `load` dipanggil saat spec datang, dan tidak memuat ulang saat ada ops lokal (data refetch tidak menghapus ops).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- EditorTab`
Expected: FAIL.

- [ ] **Step 3: Implementasi**

Toolbar mengikuti 07 §2 dengan ikon Carbon:
- mode `[Orbit][Top][Walk]`;
- tool `[Select][Ukur jarak][Luas ruang][Luas bebas][Ukur tinggi]`;
- `Snap 600` (Checkbox);
- Undo/Redo, label versi;
- `[Save]` dan `[Regenerate]` dinonaktifkan dulu, aktif di Task 13.

StatusBar menampilkan `kursor X … m  Y … m | Ruang: … m² | … fps`, dari `useEditorStore` field `cursor`, `hoverRoom`, dan `fps`. Tambahkan ketiga field ini ke store. Hook debug `window.__editor` hanya di `import.meta.env.DEV`. Ganti placeholder tab Editor di ProjectDetailPage dengan `<EditorTab projectId={id} run={run} />`.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src && rtk git commit -m "feat(editor): editor tab layout, data loading and stale-shell banner"
```

---

### Task 6: Viewport, shell, mode Orbit/Top, layer, cutaway, dan seleksi

**Files:**
- Create: `web/src/editor/viewport/Viewport.tsx`, `Shell.tsx`, `SceneHelpers.tsx` (lampu, grid 600, sumbu grid, label ruang), `web/src/editor/viewport/shellIndex.ts`
- Test: `web/src/editor/viewport/shellIndex.test.ts`

**Interfaces:**
- Consumes: store (Task 3), `toThree`, `fromThree`, `roomAt` (Task 1, 4), `useEditorData` (Task 5).
- Produces (`shellIndex.ts`, murni, memakai `three` tanpa WebGL):
  - `buildShellIndex(root: Object3D): Map<string, Object3D[]>`. Kunci = `userData.spec_id`. Sebuah node tanpa `spec_id` mewarisi ID dari ancestor terdekat, misalnya `frame_*` di bawah `door_*`.
  - `specIdOf(obj: Object3D): string | null`.
  - `layerOf(specType: string): Layer | 'always'`: `wall` → walls, `column` → columns, `door`/`window` → doors, `room`/`slab`/`stair` → always.
  - `wallScale(view: Spec, wallId: string, bakedMm: number): number` = tinggi efektif (`height ?? defaults.wall_height`) dibagi `bakedMm` (`userData.height_mm`).
  - `hiddenIds(base: Spec, view: Spec): Set<string>`, berisi ID dinding, bukaan, atau tangga yang ada di base tetapi tidak ada di view.
- Viewport:
  - `<Canvas>` dengan `hemisphereLight` + `directionalLight`, tanpa bayangan.
  - `Shell` memuat `useGLTF(shellUrl)`, menerapkan visibilitas layer, menyembunyikan `hiddenIds`, dan menerapkan `scale.y = wallScale` pada mesh dinding. Bila ada skala ≠ 1, store `previewBanner` aktif dan EditorTab menampilkan `"Pratinjau: bukaan pintu belum akurat sampai regenerate"`.
  - Cutaway: `gl.localClippingEnabled = true`, plane horizontal di `cutaway/1000` m, hanya pada material dinding. Slider ada di panel Layer (Task 8).
  - Grid 600 memakai drei `<Grid cellSize={0.6} />` di y = 0 (layer `grid`). Sumbu grid struktur digambar sebagai garis + label dari `spec.grid.axes` (layer `axes`). Label ruang memakai drei `<Html>` di `label_pos` (layer `labels`).
  - Mode Orbit: `OrbitControls`, target di centroid `building_outline`. Mode Top: `OrthographicCamera makeDefault` dari atas + `MapControls` dengan `enableRotate={false}`, kamera di-fit ke bbox bangunan. Kamera tidak di-reset saat shell dimuat ulang.
  - Seleksi: `onClick` pada mesh → `specIdOf` → `store.select([id], e.shiftKey)`. Lantai ruang menyeleksi ruang. Outline biru `#0f62fe` berupa `lineSegments` + `EdgesGeometry` pada mesh yang terseleksi.
  - `onPointerMove` di lantai mengisi `cursor` (mm) dan `hoverRoom` di store. Komponen `<Stats>` internal menghitung rata-rata fps per detik ke `store.fps` dan mengisi `window.__editorStats` di dev.

- [ ] **Step 1: Tulis test yang gagal**

`shellIndex.test.ts` memakai pohon `Object3D` buatan:
- `index maps spec ids including children of door empties`: `door_D1` (userData D1) > `frame_D1` dan `leaf_D1_a` (tanpa userData). Ketiganya masuk kunci `D1`.
- `wallScale follows view height or default`: W1 baked 3000, view `set_wall_height W1 4500` → 1.5. `height: null` dengan default 4000 → 4000/3000.
- `hiddenIds lists locally deleted shell elements`.
- `layerOf maps every spec_type in shell.glb`: semua dari `wall`, `door`, `column`, `room`, `stair`, `slab` (data M3) punya layer.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- shellIndex`
Expected: FAIL.

- [ ] **Step 3: Implementasi `shellIndex.ts` dan komponen viewport**

- [ ] **Step 4: Jalankan test, lalu smoke di browser**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

Smoke: jalankan Uvicorn + Vite (lihat Task 15 Step 1) dengan project GT yang sudah di-regenerate. Lewat Playwright MCP, buka `?tab=editor`.
- `window.__editorStats.byType.wall === 77`.
- Klik sebuah dinding → `__editor.getState().selection` berisi ID dinding.
- Tombol Top mengubah kamera ke ortografik.
- Simpan screenshot ke `.playwright-mcp/m4-t6.png`.

Expected: semua butir terpenuhi.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor && rtk git commit -m "feat(editor): R3F viewport with shell mapping, orbit/top modes, layers, cutaway and selection"
```

---

### Task 7: Layer objek: template, transform, instancing

**Files:**
- Create: `web/src/editor/viewport/ObjectsLayer.tsx`, `web/src/editor/viewport/objectMatrix.ts`
- Test: `web/src/editor/viewport/objectMatrix.test.ts`

**Interfaces:**
- Consumes: `scaleOf`, `toThree`, `rotToThree` (Task 4); `templates` (Task 5); store.
- Produces:
  - `objectMatrix(o: PlacedObject, t: Template | undefined): Matrix4` = posisi `toThree(position)`, rotasi Y `rotToThree(rotation)`, skala `scaleOf(dims, t)`. Tanpa template, skala `dims/1000` diterapkan pada kotak satuan.
  - `shouldInstance(count: number): boolean` = `count > 20`.
  - `ObjectsLayer`:
    - mengelompokkan `view.objects` per `template_id@template_version`;
    - memuat `useGLTF(asset_url)` sekali per kunci;
    - untuk kelompok > 20 instance, membuat satu `InstancedMesh` per mesh template (matrix mesh dikalikan matrix objek);
    - untuk kelompok kecil, memakai `clone()` scene per objek;
    - template yang tidak ada di registry dirender sebagai kotak abu-abu seukuran `dims`, dan ID-nya masuk `store.missingTemplates` (ditampilkan di panel Masalah, Task 12);
    - klik instance (`e.instanceId`) atau klone → `select([objectId], shift)`;
    - objek terseleksi diberi kotak OBB wireframe `#0f62fe`.

- [ ] **Step 1: Tulis test yang gagal**

- `objectMatrix places, rotates and scales like the builder`: template rack 600×1200×2000, objek di (1000, 2000, 0), rot 90, dims (600, 1100, 2000). Hasil decompose: posisi (1, 0, −2), `quaternion` = rotasi Y π/2, skala (1, 1, 1100/1200).
- `shouldInstance(20) === false`, `shouldInstance(21) === true`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- objectMatrix`
Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan test, lalu smoke**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

Smoke: lewat `__editor.getState().apply(...)`, tambahkan 25 `rack-42u-600x1200` dan 1 `crac-unit-generic`. Scene harus memiliki ≥ 1 `InstancedMesh` dengan `count === 25`. Screenshot `.playwright-mcp/m4-t7.png`.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor && rtk git commit -m "feat(editor): objects layer with template assets and instancing above 20"
```

---

### Task 8: Panel Properties: info per tipe, tinggi dinding, ruang, layer

**Files:**
- Create: `web/src/editor/panels/PropertiesPanel.tsx`, `web/src/editor/panels/LayersPanel.tsx`
- Test: `web/src/editor/panels/PropertiesPanel.test.tsx`

**Interfaces:**
- Consumes: store (`view`, `selection`, `apply`, `applyMany`, `layers`, `cutaway`); `formatM` (Task 4).
- Produces: `<PropertiesPanel />` (kanan atas) dan `<LayersPanel />` (kanan bawah: toggle 7 layer, slider cutaway mati/1000–12000 mm, daftar Rooms yang bisa diklik untuk menyeleksi ruang dan dipakai teleport di Task 14). Isi panel per seleksi:
  - **Tanpa seleksi:**
    - NumberInput "Tinggi dinding default" (1000–12000) → `set_default {key: 'wall_height'}`;
    - Checkbox "Terapkan juga ke dinding yang tingginya diatur khusus" → op kedua `set_wall_height {id: '*', height: null}`, dikirim lewat `applyMany`.
  - **Dinding** (satu atau beberapa):
    - info ID, panjang (`formatM`), tebal, kind;
    - NumberInput tinggi → satu `set_wall_height` per dinding lewat `applyMany`;
    - tombol "Ikut default" → `height: null`.
  - **Ruang:**
    - TextInput nama → `rename_room` (saat blur atau Enter);
    - Dropdown tipe dari enum `RoomType` (salin dari `PRD/03` §6 ke konstanta `ROOM_TYPES`) → `set_room_type`;
    - info luas, keliling, dan daftar pintu;
    - NumberInput "Tinggi dinding ruang ini" → `set_wall_height` untuk setiap `bounding_walls`.
  - **Pintu, Tangga, Kolom:** info read-only sesuai 07 §4. Koreksi menyusul di Task 12.
  - **Objek:** info template, nama, dan `metadata`. Edit numerik menyusul di Task 10.
- Semua input tinggi menolak nilai kosong atau di luar 1000–12000 dengan teks invalid Carbon, tanpa op.

- [ ] **Step 1: Tulis test yang gagal**

Render dengan store berisi GT.
- `wall height rejects out-of-range input and resets with null`:
  - pilih W1, isi 500 → teks invalid tampil, `ops` kosong;
  - isi 4500 → `set_wall_height W1 4500`;
  - klik "Ikut default" → op digabung menjadi `height: null`.
- `global default with override checkbox emits set_default then set_wall_height *`: satu langkah undo.
- `room height sets every bounding wall`: pilih R. MEETING, isi 3500 → op `set_wall_height` sebanyak `bounding_walls.length`.
- `room type dropdown emits set_room_type and name emits rename_room`.
- `layers panel toggles layers and cutaway`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- PropertiesPanel`
Expected: FAIL.

- [ ] **Step 3: Implementasi, lalu pasang di area `props` EditorTab**

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor && rtk git commit -m "feat(editor): properties panel with wall heights, room edits and layers"
```

---

### Task 9: Library template + drag & drop

**Files:**
- Create: `web/src/editor/panels/LibraryPanel.tsx`, `web/src/editor/lib/drop.ts`, `web/src/editor/viewport/DropGhost.tsx`
- Test: `web/src/editor/lib/drop.test.ts`, `web/src/editor/panels/LibraryPanel.test.tsx`

**Interfaces:**
- Consumes: `snapPosition` (Task 4), `roomAt` (Task 1), store, `templates`.
- Produces:
  - `planDrop(view: Spec, t: Template, p: [number, number], snapOn: boolean): { op: EditorOp; warning?: string } | { error: string }`:
    - posisi = `snapPosition(p, [w, d, h], 0, t.snap, snapOn)`;
    - `room = roomAt(view, ...)`; bila `null`, kembalikan error `"Objek harus diletakkan di dalam ruang"`;
    - op = `add_object` dengan `template_id`, `template_version`, `position [x, y, 0]`, `rotation: 0`, `dims [w, d, h]`;
    - bila `allowed_room_types` tidak kosong dan tipe ruang tidak termasuk, tambahkan warning `"Template ini tidak dianjurkan untuk tipe ruang <tipe>"` tanpa memblokir.
  - LibraryPanel:
    - Search: cocokkan teks ke `name`, `id`, atau `tags`, tanpa membedakan huruf besar/kecil.
    - Filter kategori (enum 10 §2).
    - Kartu dengan thumbnail, nama, dan dims.
    - Kartu `draggable` dengan `dataTransfer.setData('application/x-template', 'id@version')`.
  - Viewport `onDragOver`:
    - raycast ke bidang y = 0, lalu tampilkan `DropGhost` (kotak semi-transparan seukuran template) di posisi snap;
    - `Alt` menonaktifkan snap;
    - `onDrop` → `planDrop` → `store.apply(op)` atau `setNotice` (error/warning). Notice ditampilkan EditorTab sebagai Carbon `ToastNotification`.

- [ ] **Step 1: Tulis test yang gagal**

- `drop.test.ts` — `planDrop snaps inside a room, rejects outside, warns on room type`:
  - titik di dalam R. MEETING → op dengan posisi hasil snap;
  - (−5000, −5000) → error;
  - template dengan `allowed_room_types: ['data_hall']` di R. MEETING → `warning` terisi.
- `LibraryPanel.test.tsx`:
  - `search filters by name, id and tags, category narrows`;
  - `cards carry id@version in dataTransfer` (picu `dragStart` dengan objek `dataTransfer` palsu).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- drop LibraryPanel`
Expected: FAIL.

- [ ] **Step 3: Implementasi, lalu pasang LibraryPanel di area `library`**

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor && rtk git commit -m "feat(editor): template library with drag and drop onto room floors"
```

---

### Task 10: Transform objek, multi-seleksi, dan edit numerik

**Files:**
- Create: `web/src/editor/lib/transform.ts`, `web/src/editor/viewport/TransformGizmo.tsx`, `web/src/editor/viewport/Marquee.tsx`, `web/src/editor/panels/ObjectProps.tsx`
- Modify: `PropertiesPanel.tsx` (objek memakai `ObjectProps`)
- Test: `web/src/editor/lib/transform.test.ts`, `web/src/editor/panels/ObjectProps.test.tsx`

**Interfaces:**
- Consumes: `snapPosition`, `clampDims`, `footprint` (Task 4); `roomAt`; store.
- Produces (`transform.ts`):
  - `groupCenter(objs: PlacedObject[]): [number, number]`;
  - `moveOps(objs, delta: [number, number], view: Spec, snapOn: boolean, templates): EditorOp[] | { error: string }`. Snap diterapkan ke objek pertama, lalu delta yang sama dipakai untuk grup. Bila ada objek yang keluar dari ruang, kembalikan error `"Objek harus tetap di dalam ruang"`;
  - `rotateOps(objs, deg: number): EditorOp[]`, rotasi grup di sekitar `groupCenter`, `rotation` dinormalisasi ke [0, 360);
  - `duplicateOps(objs, stepMm: number): EditorOp[]`, berupa `add_object` dengan offset +`stepMm` di X (`stepMm` = `snap.grid_mm` template objek pertama, atau 600);
  - `deleteOps(objs): EditorOp[]`.
  - Objek `locked` dikecualikan dari semua fungsi di atas, dan store memberi notice `"Objek terkunci"`.
- Perilaku:
  - **TransformGizmo** (drei `TransformControls`) dipasang ke proxy `Group` di pusat seleksi:
    - mode `translate`: `showY={false}`, artinya Z spec terkunci;
    - mode `rotate`: hanya sumbu Y, `rotationSnap` 15°, atau bebas saat `Alt`;
    - mode `scale`: hanya untuk satu objek; sumbu yang `resizable: false` disembunyikan.
  - Selama drag hanya pratinjau lokal. Saat `mouseUp`, op dibuat lewat `moveOps`/`rotateOps`, atau `update_object {dims: clampDims(...)}` untuk scale, lalu dikirim dengan `applyMany`. Bila hasilnya error, proxy dikembalikan dan notice ditampilkan.
  - Toggle mode gizmo tersedia di Properties (Pindah/Putar/Ubah ukuran).
  - **Marquee** (hanya mode Top + tool select): drag pada area kosong menggambar persegi. Objek yang `position`-nya di dalam persegi diseleksi (`Shift` = tambah).
  - **ObjectProps:**
    - NumberInput posisi x/y/z mm, rotasi derajat, dims w/d/h (`step` dari template, sumbu terkunci `disabled`, nilai di-clamp saat blur);
    - TextInput label (kosong → `label: null`);
    - Toggle `locked`;
    - semua edit lewat `store.apply`, sehingga objek yang belum disimpan otomatis digabung ke op pembuatnya oleh `pushOp`.

- [ ] **Step 1: Tulis test yang gagal**

`transform.test.ts`:
- `rotateOps turns a group about its center`: dua objek di (0, 0) dan (2000, 0), +90° → posisi (1000, −1000) dan (1000, 1000), rotation 90.
- `moveOps snaps the lead object and moves the group by the same delta`.
- `moveOps refuses to leave the room`.
- `duplicateOps offsets by one snap step`.
- `locked objects are excluded`.

`ObjectProps.test.tsx`:
- `dims input clamps to resizable bounds and disables locked axes`: `w` disabled; `d` diisi 1349 → op dengan `dims[1] = 1300` (step 100 dari min 1000).
- `label empty sends null`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- transform ObjectProps`
Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan test, lalu smoke**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

Smoke: drop rack, geser dengan gizmo, rotasi dengan R, ubah `d` lewat input. `__editor.getState().ops` harus berisi **satu** `add_object` dengan nilai akhir (hasil fold).

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor && rtk git commit -m "feat(editor): move/rotate/resize with gizmo and numeric input, multi-select and marquee"
```

---

### Task 11: Tool ukur

**Files:**
- Create: `web/src/editor/viewport/MeasureLayer.tsx`, `web/src/editor/panels/MeasurePanel.tsx`, `web/src/editor/lib/snapCandidates.ts`
- Test: `web/src/editor/lib/snapCandidates.test.ts`, `web/src/editor/panels/MeasurePanel.test.tsx`

**Interfaces:**
- Consumes: `distance`, `lockAxis`, `shoelaceM2`, `formatM`, `formatM2`, `nearestSnap`, `gridIntersections` (Task 4); store (`tool`, `measurements`).
- Produces:
  - `snapCandidates(hit: { object: Mesh; point: Vector3 }, spec: Spec, axesVisible: boolean): [number, number, number][]` (mm). Kandidat:
    - vertex mesh yang terkena (posisi dunia);
    - titik tengah setiap edge segitiga yang memuat titik hit;
    - persimpangan sumbu grid di z = 0, bila layer `axes` aktif;
    - ujung `a`/`b` dinding.
  - Viewport memproyeksikan kandidat ke layar, lalu memanggil `nearestSnap(cursor, …, 10)`.
  - Perilaku per tool (07 §5):
    - `distance`: klik A, lalu B. `Shift` = `lockAxis`. Hasil berupa garis + label Html `"d m (ΔX …, ΔY …, ΔZ …)"`.
    - `room-area`: klik lantai ruang. Polygon ruang di-highlight, label `formatM2(area_m2)` dari spec.
    - `area`: klik beberapa titik di lantai (snap ke ujung dinding dan persimpangan grid), klik dua kali untuk menutup, hasil dari `shoelaceM2`.
    - `height`: klik permukaan → Z titik. Bila yang diklik dinding, label juga menampilkan `height` spec.
    - `Esc` membatalkan ukuran yang sedang berjalan.
  - MeasurePanel (panel kanan saat tool ukur aktif): daftar ukuran dengan tombol hapus per baris dan "Hapus semua".

- [ ] **Step 1: Tulis test yang gagal**

`snapCandidates.test.ts`:
- mesh `BoxGeometry` 1×1×1 di (2, 0, −3), hit di (2.5, 0.2, −3) → kandidat berisi vertex dunia `[2500, 3500, 500]` mm (perhatikan `fromThree`);
- `axesVisible` menambah semua persimpangan grid GT.

`MeasurePanel.test.tsx`:
- `lists measurements and removes them`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- snapCandidates MeasurePanel`
Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan test, lalu smoke**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

Smoke: dengan layer `axes` aktif, ukur jarak dua persimpangan sumbu grid yang bersebelahan. `measurements[0].value` harus sama dengan selisih `offset` di spec (±1 mm). Klik lantai R. MEETING dengan `room-area` → label sama dengan `area_m2` spec.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor && rtk git commit -m "feat(editor): distance, room area, free area and height measuring tools"
```

---

### Task 12: Panel koreksi geometri, pratinjau 2D, validasi live, panel Masalah

**Files:**
- Create: `web/src/editor/panels/CorrectionPanel.tsx`, `web/src/editor/panels/IssuesPanel.tsx`, `web/src/editor/lib/geometryDiff.ts`, `web/src/editor/useValidate.ts`, `web/src/editor/viewport/GeometryPreview.tsx`, `web/src/editor/viewport/AddWallTool.tsx`
- Modify: `PropertiesPanel.tsx` (bagian "Koreksi" berupa Accordion yang terlipat secara default)
- Test: `geometryDiff.test.ts`, `CorrectionPanel.test.tsx`, `useValidate.test.tsx`, `IssuesPanel.test.tsx`

**Interfaces:**
- Consumes: store, `applyOps`, `api.post`, `snapPosition`, `gridIntersections`.
- Produces:
  - `geometryDiff(base: Spec, view: Spec): { walls: Diff<Wall>[]; openings: Diff<Opening>[]; stairs: Diff<Stair>[] }`, dengan `Diff<T> = { id: string; state: 'added' | 'moved' | 'deleted'; el: T }`. `moved` = `a`, `b`, `thickness`, `kind`, `offset`, `width`, atau `flights` berbeda.
  - `useValidate(projectId, baseVersion, ops): { issues: Issue[]; newIssues: Set<string>; error: string | null; pending: boolean }`:
    - debounce 500 ms, lalu `POST /api/projects/{id}/specs/validate {base_version, ops}`;
    - issue base diambil sekali (`ops: []`);
    - `newIssues` berisi kunci `code|element_ids` yang tidak ada di base;
    - balasan 400 `bad_op` → `error` berisi pesan + indeks op.
  - **CorrectionPanel** (07 §6b):
    - **Dinding terpilih:**
      - form `a.x`, `a.y`, `b.x`, `b.y`, `thickness`, `kind` → `move_wall` berisi field yang berubah saja;
      - "Pisah di offset (mm dari a)" → `split_wall`;
      - Hapus → `delete_wall` dengan dropdown alasan `garis anotasi | duplikat | bukan dinding | lainnya` (lainnya membuka TextInput wajib); tombol nonaktif tanpa alasan;
      - "Tambah pintu/jendela" (kategori, offset, lebar, tipe) → `add_opening`;
      - dua dinding atau lebih terpilih → "Gabung" → `merge_walls` dengan reason `"gabung dinding kolinear"`.
    - **Tanpa seleksi:**
      - "Tambah dinding" (a, b, tebal = `defaults.wall_thickness`, kind = `partition`) → `add_wall`;
      - tombol "Klik dua titik" mengaktifkan tool `add-wall` (hanya mode Top): `AddWallTool` mengisi a/b dari dua klik, dengan snap ke persimpangan sumbu grid, ujung dinding (≤ 10 px), lalu grid 100 mm; pengguna menekan "Tambah" untuk mengirim op.
    - **Pintu terpilih:**
      - tipe, lebar, tinggi, offset, engsel, arah → `set_door` (field berubah saja);
      - Hapus + alasan → `delete_opening`.
      - Jendela hanya bisa dihapus, karena `set_door` khusus pintu.
    - **Tangga terpilih:**
      - tanjakan per flight (`risers`), lebar (semua flight), `top_z` → `set_stair {flights, top_z}`;
      - "Balik arah naik" → `set_stair` dengan `start`/`end` setiap flight ditukar;
      - Hapus + alasan → `delete_stair`.
    - Error `pushOp` (elemen belum disimpan) tampil sebagai notice.
  - **GeometryPreview:** dari `geometryDiff`, garis `#ff832b` di y = 0.01 m:
    - tapak dinding added/moved solid, deleted putus-putus;
    - segmen bukaan di dinding;
    - garis flight dengan panah arah naik.
    - Bila diff tidak kosong, EditorTab menampilkan banner `"Geometri berubah: Save + Regenerate untuk melihat hasil 3D"`.
  - **IssuesPanel:**
    - menggabungkan issue validasi, `saveIssues` (Task 13), `missingTemplates` (Task 7), dan tabrakan (Task 14);
    - setiap baris berisi ikon severity, kode, pesan, dan ID elemen yang bisa diklik (→ `select`);
    - tag "baru" untuk `newIssues`.

- [ ] **Step 1: Tulis test yang gagal**

- `geometryDiff.test.ts` — `geometryDiff classifies added, moved and deleted`: `move_wall`, `add_wall`, `delete_opening`, `set_stair` dibandingkan dengan GT.
- `CorrectionPanel.test.tsx`:
  - `wall form sends only changed fields`;
  - `delete needs a reason`;
  - `stair flip swaps every flight`;
  - `door form edits width` (op `set_door {id, width}`);
  - `editing a wall created by split shows the save-first notice`.
- `useValidate.test.tsx` (fake timers, mock `api.post`) — `debounces to one request per 500 ms and marks new issues`: tiga perubahan ops dalam 300 ms → satu POST validasi (di luar panggilan base). Issue `V008` yang tidak ada di base masuk `newIssues`.
- `IssuesPanel.test.tsx` — `clicking an element id selects it`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- geometryDiff CorrectionPanel useValidate IssuesPanel`
Expected: FAIL.

- [ ] **Step 3: Implementasi, lalu pasang IssuesPanel di bawah Properties**

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor && rtk git commit -m "feat(editor): geometry correction panel with 2D preview, live validation and issues"
```

---

### Task 13: Save (201/409/422), rebase, dan Regenerate

**Files:**
- Create: `web/src/editor/useSave.ts`, `web/src/editor/RebaseDialog.tsx`, `web/src/editor/useRegenerateFlow.ts`
- Modify: `Toolbar.tsx`, `EditorTab.tsx`
- Test: `web/src/editor/useSave.test.tsx`, `web/src/editor/useRegenerateFlow.test.tsx`

**Interfaces:**
- Consumes: store (`ops`, `baseVersion`, `markSaved`, `acceptRebase`, `saveIssues`); `rebasePreview` (Task 3); `api`; `run` prop (Task 5); `useRegenerate` dan `useOutputs` (M3).
- Produces:
  - `useSave(projectId): { save(message?: string): Promise<void>; saving: boolean; conflict: { head: Spec; failed: OpFailure[] } | null; resolve(accept: boolean): void }`. Respons ditangani sebagai berikut:
    - `POST /specs {base_version, ops, message}`, dengan message default `"Edit editor: <n> op"`;
    - **201** → `markSaved(spec)`, toast `"Tersimpan sebagai v<N>"`. Bila `localStorage['editor.autoRegenerate'] === '1'`, regenerate langsung dipanggil; bila tidak, toast menawarkan tombol Regenerate.
    - **409 `spec_conflict`** → `GET /specs/HEAD`, `rebasePreview`, lalu buka RebaseDialog yang mendaftar op gagal (op, target, pesan) dengan pilihan "Terapkan ke v<HEAD>" atau "Batal". `resolve(true)` → `acceptRebase(head, failedIdx)`. `resolve(false)` tidak mengubah apa pun.
    - **409 `run_in_progress`** → notice.
    - **422** → `saveIssues = details.issues`, ops tetap ada.
    - **400 `bad_op`** → notice `"Op #<index> (<op>) ditolak: <pesan>"`.
  - `useRegenerateFlow(projectId, run)`:
    - `regenerate()` → `POST /regenerate {version: baseVersion}`;
    - `progress: number | null` dari tahap 7–10 run aktif;
    - `stage: string | null`;
    - saat output versi itu tersedia (`useOutputs` di-invalidate oleh SSE `output.ready`), `shellUrl` berganti ke versi baru. `Canvas` tidak di-remount (kamera tetap) dan `selection` dipertahankan.
  - Toolbar: Save (aktif bila ada ops, `Ctrl+S` di Task 14), Regenerate + `ProgressBar` kecil saat berjalan, Checkbox "Regenerate otomatis setelah Save" (localStorage).

- [ ] **Step 1: Tulis test yang gagal**

`useSave.test.tsx`, dengan mock `api`:
- `201 clears ops and moves the base`;
- `422 keeps ops and shows issues`;
- `409 opens the rebase dialog with failed ops; cancel keeps everything; accept drops only failed ops`;
- `auto regenerate after save follows localStorage`.

`useRegenerateFlow.test.tsx`:
- `progress follows stages 7-10 and the shell url switches when the new output appears`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- useSave useRegenerateFlow`
Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor && rtk git commit -m "feat(editor): save with conflict rebase and validation issues, regenerate with live progress"
```

---

### Task 14: Pintasan keyboard, tabrakan + clearance, mode Walk

**Files:**
- Create: `web/src/editor/lib/keys.ts`, `web/src/editor/useShortcuts.ts`, `web/src/editor/viewport/Clearance.tsx`, `web/src/editor/viewport/WalkControls.tsx`, `web/src/editor/lib/walk.ts`
- Modify: `ObjectsLayer.tsx` (outline merah), `IssuesPanel.tsx` (tabrakan), `LayersPanel.tsx` (teleport)
- Test: `keys.test.ts`, `walk.test.ts`, `IssuesPanel.test.tsx` (tambahan)

**Interfaces:**
- Consumes: `collisions` (Task 4), `transform.ts` (Task 10), `useSave` (Task 13), store.
- Produces:
  - `keyAction(e: { key: string; shiftKey: boolean; ctrlKey: boolean; metaKey: boolean }): Action | null`. Peta persis 07 §10:

    | Tombol | Action |
    |---|---|
    | `1` / `2` / `3` | `mode:orbit` / `mode:top` / `mode:walk` |
    | `v` | `tool:select` |
    | `m` | `tool:distance` |
    | `a` | `tool:area` |
    | `h` | `tool:height` |
    | `g` | `snap:toggle` |
    | `r` / `Shift+R` | `rotate:+90` / `rotate:-90` |
    | `Ctrl/Meta+D` | `duplicate` |
    | `Delete` | `delete` |
    | `Ctrl/Meta+Z` | `undo` |
    | `Ctrl/Meta+Shift+Z` | `redo` |
    | `Ctrl/Meta+S` | `save` |
    | `Escape` | `cancel` |

  - `useShortcuts()`: listener `keydown` di `window` hanya saat tab Editor tampil. Event diabaikan bila target berada di `input`, `textarea`, `select`, atau `[contenteditable]`, atau bila ada modal Carbon terbuka. Untuk `save`, `undo`, `redo`, dan `duplicate`, panggil `preventDefault`.
  - **Tabrakan (P1):** `collisions(view)` di-memo per `view`. Objek yang bertabrakan diberi outline `#fa4d56`. IssuesPanel menampilkan baris warning `"Tabrakan <a> ↔ <b>"` (kode `V017`). Save tetap diizinkan.
  - **Clearance:** untuk objek terseleksi, kotak transparan depan dan belakang sesuai `template.clearance` dalam frame lokal objek (depan = +Y spec).
  - **Walk (P1):** `walkStep(pos: [number, number], yawRad: number, input: { f: number; r: number }, dtS: number, run: boolean, blocked: (from, to) => boolean): [number, number]`. Kecepatan 1.4 m/s, atau 3 m/s saat run. Gerakan berhenti bila `blocked`.
    - `WalkControls` memakai `PointerLockControls` dengan tinggi mata 1.6 m.
    - `blocked` = raycast horizontal 0.3 m ke mesh dinding.
    - `Esc` keluar ke mode Orbit.
    - Daftar Rooms di LayersPanel: klik → teleport ke `label_pos` (mode Walk), atau fokus kamera (mode lain).

- [ ] **Step 1: Tulis test yang gagal**

- `keys.test.ts`:
  - `maps every shortcut of PRD 07 §10` (tabel di atas);
  - `ignores plain letters with ctrl except the mapped ones`.
- `walk.test.ts`:
  - `walks 1.4 m/s, runs 3 m/s, stops when blocked`.
- `IssuesPanel.test.tsx`:
  - `lists collisions as V017 warnings` (dua rack yang saling masuk).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- keys walk IssuesPanel`
Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src/editor && rtk git commit -m "feat(editor): keyboard shortcuts, collision warnings with clearance, walk mode"
```

---

### Task 15: Verifikasi end-to-end, performa, dan penutupan M4

- [ ] **Step 1: Siapkan data dan server**

```bash
rtk uv run --env-file .env python -m core.templates.make_placeholders --out data/templates
rtk uv run --env-file .env uvicorn server.app:app --port 8000        # background
cd web && rtk npm run dev -- --port 5173 --strictPort                 # background
```

Lewat API: buat project baru "Gatsu Editor", impor GT, lalu Regenerate v1 dan tunggu selesai.

- [ ] **Step 2: Alur kriteria selesai lewat Playwright MCP**

Simpan screenshot tiap langkah di `.playwright-mcp/m4-*.png`.
1. Buka `?tab=editor`. Shell v1 tampil, tanpa banner stale.
2. Tool `room-area` pada R. MEETING → label sama dengan `area_m2` spec. Tool `height` pada dinding → label menampilkan tinggi spec.
3. Pilih ruang data hall, lalu "Tinggi dinding ruang ini" = 4500. Banner pratinjau tampil.
4. Drop `rack-42u-600x1200`, `crac-unit-generic`, dan `ups-cabinet-generic` ke data hall. Resize masing-masing lewat input dims atau gizmo.
5. Koreksi: hapus satu dinding partisi (alasan "duplikat"), tambah satu dinding lewat "Klik dua titik", dan ubah lebar satu pintu +100 mm. Garis oranye dan banner geometri tampil. Panel Masalah menampilkan hasil validasi.
6. Save → v2. Regenerate dan amati progress di toolbar. Shell dimuat ulang dengan kamera tetap.
7. Lewat API/Python, pastikan:
   - `outputs/v2/layout_full.glb` memiliki node `obj_O*` sebanyak objek (pygltflib);
   - `outputs/v2/report.html` mencantumkan ketiga template di tabel objek;
   - `layout.blend` ditulis ulang (mtime) dan log build menyebut jumlah objek;
   - dinding yang dihapus tidak lagi ada di `shell.glb` v2.

- [ ] **Step 3: Presisi ukur**

Dengan layer `axes` aktif, ukur jarak dua persimpangan sumbu grid. `__editor.getState().measurements[0].value` harus sama dengan selisih `offset` di spec, dengan galat ≤ 1 mm.

- [ ] **Step 4: Performa (NFR-PF-04)**

- Lewat `POST /specs`, tambahkan 500 `rack-42u-600x1200` (grid 600 di data hall dan ruang lain yang cukup luas), simpan sebagai versi baru, lalu buka editor.
- Orbit kamera 5 s lewat `browser_run_code_unsafe`.
- Catat rata-rata `window.__editorStats.fps`. Expected: ≥ 45 fps di Chromium headed pada laptop ini.
- Bila Chromium jatuh ke software rendering (SwiftShader), catat angkanya dan ulangi di Chrome dengan GPU. Hasil dan jenis renderer ditulis di ROADMAP.

- [ ] **Step 5: Konflik dua tab**

1. Tab A dan B membuka editor pada versi yang sama.
2. A memindah rack lalu Save.
3. B mengubah lebar pintu yang sama dengan yang dihapus A (siapkan dulu: A menghapus pintu itu), menambah satu rack, lalu Save → dialog rebase menampilkan op pintu sebagai gagal.
4. "Terapkan" → Save berhasil. Rack milik B ada di versi baru, dan rack milik A tidak berubah.

- [ ] **Step 6: Suite + lint**

Run: `rtk uv run --env-file .env pytest -q` dan `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: semua hijau.

- [ ] **Step 7: Tutup M4 di ROADMAP, lalu commit**

Centang hanya tugas yang benar-benar selesai. Tulis blok "Status M4" yang memuat:
- hasil alur;
- presisi ukur;
- fps dan renderer;
- konflik dua tab;
- penyimpangan: SSAO tidak dibuat; snap ke dinding (P1) dan origin grid per ruang (P2) tidak dibuat; template "perbarui ke versi terbaru" (P2) tidak dibuat.

```bash
rtk git add ROADMAP.md && rtk git commit -m "docs: close M4"
```
