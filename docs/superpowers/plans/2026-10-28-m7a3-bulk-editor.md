# M7a-3 — Aksi Massal Editor untuk Memangkas Menit Koreksi Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menurunkan menit koreksi Gatsu dari 22.1 menuju ≤ 15 (kriteria sukses MVP #2) dengan memangkas tiga pekerjaan berulang yang mendominasi koreksi:
- menghapus 68 dinding palsu satu per satu (5.7 menit);
- menyetel tipe 31 ruang satu per satu (4.1 menit);
- menambah 16 dinding, yang masing-masing butuh tool, 2 klik, dan tombol (5.3 menit).

**Architecture:**
- Semua aksi baru memakai op yang sudah ada (`delete_wall`, `set_room_type`, `add_wall`) lewat `applyMany`, sehingga satu aksi = satu langkah undo, dan server memvalidasi seperti biasa saat simpan. Tidak ada op atau endpoint baru.
- **Seleksi:** marquee (mode top) ikut menyeleksi dinding yang kedua ujungnya ada di dalam kotak. Tombol "Pilih dinding ragu" menyeleksi dinding hasil CV berkeyakinan < 0.6.
- **Aksi:**
  - seleksi ≥ 2 dinding menampilkan "Hapus N dinding" dengan satu alasan;
  - seleksi ≥ 2 ruang menampilkan satu Dropdown tipe untuk semuanya;
  - tool tambah dinding mendapat mode berantai: Enter menyimpan dinding dan memulai dinding berikutnya dari titik akhir, Esc berhenti.
- **Pengukuran:** model biaya koreksi "massal" ditambahkan di samping model satu-per-satu, dan keduanya dilaporkan.

**Tech Stack:** React 18 + TypeScript, Zustand store, React Three Fiber, Carbon g100, Vitest + Testing Library; Python 3.12 untuk benchmark.

**Spec:**
- `PRD/07-web-editor.md` (seleksi, panel koreksi, tool tambah dinding);
- `PRD/03-layout-spec.md` §11 (ops);
- `ROADMAP.md` M7 Kriteria selesai 2 ("Sisa galat Gatsu terkoreksi lewat panel koreksi ≤ 15 menit");
- `benchmarks/reports/m7a2-final.md` (rincian menit per operasi).

Branch: `m7a3-bulk-editor` dari `main`.

## Model biaya massal (asumsi, dikalibrasi di Task 6)

| Pekerjaan | Satu-per-satu (sekarang) | Massal |
|---|---|---|
| Hapus N dinding palsu | 5 s × N | 10 s per aksi hapus + 2 s × N untuk menyeleksi |
| Set tipe N ruang (G tipe target berbeda) | 8 s × N | 10 s × G + 2 s × N |
| Tambah N dinding | 20 s × N | 10 s × N (satu klik + Enter, berantai) |
| Lainnya (pintu, nama, tangga) | tetap | tetap |

Perkiraan Gatsu dengan model massal: 22.1 → ~14 menit. Angka ini harus dikalibrasi sebelum dianggap memenuhi kriteria.

## Global Constraints

- **Lingkungan kerja:**
  - semua perintah shell diawali `rtk`;
  - jangan membaca atau meng-commit `server-info.txt`;
  - test Python: `rtk uv run --env-file .env pytest -q -m "not strata"`;
  - test web: `cd web && rtk npx vitest run && rtk npm run lint && rtk npm run build`.
- **Op dan undo:**
  - tidak ada op baru; aksi massal = `applyMany([...])`;
  - satu aksi massal = satu entri undo, sehingga satu Ctrl+Z membatalkan semuanya;
  - op yang gagal di reducer klien dilaporkan lewat notice yang sudah ada.
- **Elemen manusia:** "Pilih dinding ragu" hanya mengambil dinding dengan `provenance.source == "cv"` dan `confidence < 0.6`. Dinding hasil edit manusia tidak pernah ikut.
- **UI:**
  - copy dalam bahasa Indonesia, gaya Carbon g100 seperti panel yang ada;
  - semua tombol baru punya `aria-label` yang jelas;
  - aksi massal menyebut jumlah elemen ("Hapus 12 dinding").
- **Bahasa dan konvensi:**
  - dokumen dalam bahasa Indonesia dengan istilah teknis Inggris;
  - commit dalam bahasa Inggris dan diakhiri `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Seleksi campuran** (dinding + pintu + ruang). Aksi massal hanya muncul bila seluruh seleksi sejenis; tidak ada penghapusan diam-diam atas elemen lain. Test di Task 2 dan 3.
2. **Hapus massal dinding yang menjadi induk pintu.** Pintunya ikut terhapus (cascade server), dan notice menyebut jumlah pintu yang ikut hilang. Test di Task 2.
3. **Marquee di mode orbit atau walk:** tidak boleh aktif (perilaku sekarang hanya di mode top). Dinding yang hanya sebagian di dalam kotak tidak ikut terseleksi. Test di Task 1.
4. **Rantai dinding dengan titik akhir = titik awal** (dinding nol panjang), atau Enter tanpa titik b: tidak ada op yang dikirim. Esc menghapus draft. Test di Task 4.
5. **Undo setelah aksi massal:** satu Ctrl+Z mengembalikan semua elemen. Test di Task 2 dan 3.

---

### Task 1: Marquee menyeleksi dinding

**Files:**
- Create: `web/src/editor/lib/rectPick.ts`, `web/src/editor/lib/rectPick.test.ts`
- Modify: `web/src/editor/viewport/Marquee.tsx`

**Interfaces:**
- Produces: `idsInRect(view: Spec, rect: {xa: number; xb: number; ya: number; yb: number}, toScreen: (p: [number, number, number]) => [number, number]): string[]`. Hasilnya objek (posisi di dalam kotak, seperti sekarang) ditambah dinding (kedua ujung `a` dan `b` di dalam kotak), dalam urutan spec.

- [ ] **Step 1: Tulis test yang gagal** (`rectPick.test.ts`, proyeksi identitas `toScreen = ([x, y]) => [x, y]`):

```ts
it('picks walls with both ends inside and skips partial ones', () => {
  const view = spec({ walls: [wall('W1', [0, 0], [100, 0]), wall('W2', [0, 0], [500, 0])], objects: [obj('O1', [50, 50, 0])] })
  expect(idsInRect(view, { xa: -10, xb: 200, ya: -10, yb: 200 }, id2)).toEqual(['W1', 'O1'])
})
it('returns nothing for an empty rectangle', () => { ... toEqual([]) })
```

- [ ] **Step 2: Jalankan, pastikan gagal.** `cd web && rtk npx vitest run src/editor/lib/rectPick.test.ts` → FAIL.
- [ ] **Step 3: Implementasi** `idsInRect`. `Marquee.tsx` memakainya; syarat mode top dan tool select tetap.
- [ ] **Step 4: Jalankan, pastikan lolos.**
- [ ] **Step 5: Commit** `feat(editor): marquee selects walls fully inside the box`.

---

### Task 2: Hapus massal dinding + "Pilih dinding ragu"

**Files:**
- Create: `web/src/editor/panels/BulkWalls.tsx`, `web/src/editor/panels/BulkWalls.test.tsx`
- Modify: `web/src/editor/panels/CorrectionPanel.tsx`, `web/src/editor/store.ts` (`selectDoubtfulWalls(threshold = 0.6)`)

**Interfaces:**
- Produces:
  - `useEditorStore.selectDoubtfulWalls(threshold?: number): number`: menyeleksi dinding `source == "cv"` dengan `confidence < threshold`, lalu mengembalikan jumlahnya.
  - `<BulkWalls walls={Wall[]} />` untuk seleksi ≥ 2 dinding:
    - tombol "Gabung" yang sudah ada tetap tampil;
    - `DeleteWithReason` dengan label `Hapus ${n} dinding`, yang memanggil `applyMany(walls.map(w => ({op: 'delete_wall', id: w.id, reason})))`;
    - notice menyebut jumlah pintu yang ikut terhapus (pintu yang `wall_id`-nya ada di seleksi).
  - Tanpa seleksi, `CorrectionPanel` menampilkan tombol "Pilih dinding ragu (< 0.6)" di atas form tambah dinding.

- [ ] **Step 1: Tulis test yang gagal** (`BulkWalls.test.tsx` dengan store nyata dan spec kecil):

```tsx
it('deletes every selected wall in one undo step', async () => {
  // select W1, W2 -> choose reason -> click "Hapus 2 dinding"
  expect(view.walls.map(w => w.id)).not.toContain('W1'); expect(...).not.toContain('W2')
  useEditorStore.getState().undo(); expect(view.walls.map(w => w.id)).toEqual(expect.arrayContaining(['W1', 'W2']))
})
it('warns how many doors go with the walls', ...)            // W1 hosts D1 -> notice "1 pintu ikut terhapus"
it('mixed selection (wall + room) offers no bulk delete', ...)
it('selectDoubtfulWalls picks cv walls under 0.6 only', ...)  // editor-made and 0.8 walls stay unselected
```

- [ ] **Step 2: Jalankan, pastikan gagal.**
- [ ] **Step 3: Implementasi** sesuai Interfaces.
- [ ] **Step 4: Jalankan, lalu lint.**
- [ ] **Step 5: Commit** `feat(editor): delete many walls at once and select doubtful walls`.

---

### Task 3: Set tipe ruang massal

**Files:**
- Modify: `web/src/editor/panels/PropertiesPanel.tsx` (`pick`: jenis `rooms` untuk ≥ 2 ruang; komponen `RoomsBulk`)
- Test: `web/src/editor/panels/PropertiesPanel.test.tsx`

**Interfaces:**
- Produces: `pick()` mengembalikan `{kind: 'rooms', items: Room[]}` bila seleksi ≥ 2 dan semuanya ruang. `RoomsBulk` menampilkan "N ruang terseleksi" dan Dropdown tipe. Memilih tipe memanggil `applyMany` berisi `set_room_type` hanya untuk ruang yang tipenya berbeda.

- [ ] **Step 1: Tulis test yang gagal:**

```tsx
it('sets one type on every selected room in one undo step', ...)  // R1 other, R2 office -> "storage" -> both storage; one undo restores both
it('skips rooms already of that type', ...)                       // applyMany receives only the differing room
it('mixed selection shows no room bulk control', ...)
```

- [ ] **Step 2: Jalankan, pastikan gagal.**
- [ ] **Step 3: Implementasi.**
- [ ] **Step 4: Jalankan, lalu lint.**
- [ ] **Step 5: Commit** `feat(editor): set one room type on many rooms`.

---

### Task 4: Tambah dinding berantai

**Files:**
- Modify: `web/src/editor/store.ts` (`wallSpec: {thickness: number; kind: WallKind}`, `setWallSpec`, `commitWallDraft(): boolean`), `web/src/editor/viewport/AddWallTool.tsx` (Enter dan Esc), `web/src/editor/panels/CorrectionPanel.tsx` (`AddWallForm` memakai `wallSpec` dan `commitWallDraft`)
- Test: `web/src/editor/store.test.ts`, `web/src/editor/panels/CorrectionPanel.test.tsx`

**Interfaces:**
- Produces:
  - `commitWallDraft()`:
    - bila draft punya `a` dan `b` dengan `a != b`: `apply({op: 'add_wall', a, b, thickness, kind})`, lalu draft menjadi `{a: b}` dan tool tetap `add-wall` (berantai), dan fungsi mengembalikan `true`;
    - selain itu tidak mengirim op dan mengembalikan `false`.
  - `AddWallTool`: Enter memanggil `commitWallDraft()`; Esc mengosongkan draft dan kembali ke tool select (seperti sekarang).
  - Tombol panel "Tambah" memanggil `commitWallDraft()`. Tool tidak lagi otomatis kembali ke select setelah satu dinding.

- [ ] **Step 1: Tulis test yang gagal** (`store.test.ts`):

```ts
it('commitWallDraft adds the wall and starts the next one at b', () => {
  s.setWallDraft({ a: [0, 0], b: [3000, 0] }); expect(s.commitWallDraft()).toBe(true)
  expect(last(view.walls)).toMatchObject({ a: [0, 0], b: [3000, 0], thickness: 150 })
  expect(state.wallDraft).toEqual({ a: [3000, 0] }); expect(state.tool).toBe('add-wall')
})
it('no op for a zero-length or half draft', ...)   // {a,b equal} and {a only} -> false, ops unchanged
it('uses the chosen thickness and kind', ...)      // setWallSpec({thickness: 200, kind: 'exterior'})
```

- [ ] **Step 2: Jalankan, pastikan gagal.**
- [ ] **Step 3: Implementasi.**
- [ ] **Step 4: Jalankan, lalu lint.**
- [ ] **Step 5: Commit** `feat(editor): chained wall drawing (Enter adds and continues, Esc stops)`.

---

### Task 5: Model biaya massal di benchmark

**Files:**
- Modify: `benchmarks/correction_effort.py` (`correction_ops` menambah `room_type_groups`; `BULK_SECONDS`; `correction_minutes(ops, bulk: bool = False)`; `capped_minutes(..., bulk=False)`), `benchmarks/failure_modes.py` dan `benchmarks/run_augment_bench.py` (melaporkan kedua model)
- Test: `tests/benchmarks/test_correction_effort.py`

**Interfaces:**
- Produces:
  - `room_type_groups` = jumlah tipe target berbeda di antara ruang GT yang butuh `set_room_type`.
  - `correction_minutes(ops, bulk=True)` = Σ ops lainnya × SECONDS + biaya massal per tabel "Model biaya massal":
    - `delete_wall`: 10 bila N > 0, ditambah 2 × N;
    - `set_room_type`: 10 × groups + 2 × N;
    - `add_wall`: 10 × N.
  - `effort` di JSON berbentuk `{"ops", "minutes", "minutes_bulk"}`. Baris augmentasi mendapat `correction_min_bulk`, dan `absolute_means` ikut mencantumkannya.

- [ ] **Step 1: Tulis test yang gagal:**

```python
def test_bulk_model():
    ops = {"delete_wall": 68, "add_wall": 16, "set_room_type": 31, "room_type_groups": 5, "add_opening": 0, ...}
    assert correction_minutes(ops, bulk=True) == round((10 + 2 * 68 + 16 * 10 + 10 * 5 + 2 * 31) / 60, 1)
def test_room_type_groups_counted(): ...   # two GT rooms of the same wrong type -> groups 1
```

- [ ] **Step 2–4: RED, GREEN**, lalu jalankan `failure_modes` (`--out benchmarks/reports/m7a3-gatsu`) dan `run_augment_bench` (`--out benchmarks/reports/m7a3-augment`). Expected: menit massal Gatsu tercatat, perkiraannya ~14.
- [ ] **Step 5: Commit** `bench: bulk-editor correction model next to the one-by-one model`.

---

### Task 6: E2E, panduan kalibrasi, status

**Files:**
- Create: `docs/calibration-correction.md`
- Modify: `ROADMAP.md` (Status M7a-3)

- [ ] **Step 1: E2E Playwright** pada project Gatsu di server dev:
  - seleksi marquee pada area dinding palsu, lalu "Hapus N dinding";
  - "Pilih dinding ragu", lalu hapus;
  - pilih beberapa ruang `outdoor` dengan Shift-klik, lalu set tipe sekaligus;
  - gambar 3 dinding berantai dengan Enter;
  - simpan: server memvalidasi, dan versi baru muncul di Versions;
  - satu Ctrl+Z membatalkan aksi massal terakhir.
- [ ] **Step 2: Panduan kalibrasi** (`docs/calibration-correction.md`):
  - langkah sesi koreksi Gatsu berwaktu: project baru dari `plan.jpeg`, mulai stopwatch, koreksi sampai skor validator dan cek visual setara GT, lalu catat menit;
  - tabel pencatatan per jenis operasi;
  - cara memperbarui `SECONDS`/`BULK_SECONDS` dari hasil sesi.
- [ ] **Step 3: Suite penuh** (Python + web) hijau.
- [ ] **Step 4: ROADMAP.** "Status M7a-3": menit Gatsu untuk model satu-per-satu dan massal, status kriteria ≤ 15 (terpenuhi menurut model, menunggu kalibrasi), dan hasil E2E.
- [ ] **Step 5: Commit** `docs: M7a-3 status and correction calibration guide`.
