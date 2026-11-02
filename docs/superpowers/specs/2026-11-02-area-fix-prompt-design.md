# Desain: perbaiki area dengan prompt (asisten LLM di review)

Tanggal: 2026-11-02 · Status: draf untuk disetujui user

## 1. Maksud dan alasan

Koreksi layout sekarang dikerjakan manual dengan alat editor: hapus, Garis bantu, Tutup celah, Pintu, tipe ruang. Ada
kesalahan yang merepotkan dikerjakan satu per satu, tetapi mudah dijelaskan dengan kalimat. Contoh dari user:

1. "Bagian tersebut dindingnya kurang logis dan tidak realistis; rekonstruksi bagian yang dianotasi agar menjadi ruangan
   tangga saja."
2. "Dinding ini sepertinya tidak digunakan; hapus saja."
3. "Di bagian yang dianotasi ada dua dinding duplikat atau berdempetan; rekonstruksi agar menyatu dan logis."

Fitur ini: user menandai area, menulis instruksi, lalu LLM (Strata) mengusulkan perbaikan. LLM boleh bertanya balik kalau
instruksinya ambigu. User melihat usulan sebagai pratinjau, lalu menerima (ditimpa) atau menolak (dibatalkan).

**Uji coba 2026-11-02** (project test-2, Strata Qwen3.8-Flash-Next di DGX, satu panggilan JSON per kasus):

| Kasus | Hasil | Waktu |
|---|---|---|
| "dinding duplikat" | gabung W70+W73, benar | 19–24 s |
| "hapus dinding ini" | bertanya "dinding mana?" (6 dinding di area) | 6–21 s |
| "jadikan ruang tangga" | dengan gambar: masuk akal, tapi koordinat dinding baru dikarang; teks saja: menghapus dinding asli | 35 s |

Kesimpulan dari uji itu:
- gambar dan daftar elemen dikirim bersama;
- koordinat dari LLM tidak dipakai langsung;
- review accept/reject wajib;
- progres harus terlihat.

## 2. Tujuan, non-tujuan, anti-tujuan

**Tujuan (versi 1)**
- **Alat "Perbaiki area" (`A`)** di kanvas review 2D layout: tarik kotak, lalu panel chat terbuka.
- **Konteks yang dikirim ke LLM:**
  - instruksi bebas;
  - daftar elemen di area;
  - **dinding yang sedang terpilih** sebagai rujukan "dinding ini";
  - crop gambar denah dengan dinding saat ini digambar berwarna dan diberi label ID.
- **Pertanyaan balik** kalau instruksi ambigu. User menjawab di chat, lalu percakapan berlanjut (sesi yang sama).
- **Aksi yang didukung:** hapus dinding, gabung dinding (kolinear maupun sejajar berdempetan), tambah dinding (rough line
  yang di-snap ke gambar), hapus bukaan, tipe ruang, dan nama ruang.
- **Validasi dan satu putaran koreksi:** usulan divalidasi (dry-run) sebelum ditampilkan. Kalau ada error, LLM mendapat
  hasilnya dan merevisi sekali.
- **Pratinjau di kanvas:** elemen yang dihapus dicoret merah, dinding baru atau hasil gabungan hijau. Tombol **Terima** /
  **Tolak**. Terima menambahkan op ke perubahan yang belum disimpan (satu langkah undo), lalu user Save seperti biasa.
  Tolak membuang semuanya.
- **Chat streaming:** setiap langkah tampil saat terjadi (membaca area, LLM berpikir, rencana, menerapkan, validasi,
  usulan siap).
- **Log setiap sesi** (instruksi, rencana, usulan, keputusan) untuk mengukur tingkat penerimaan.

**Non-tujuan (versi 1)**
- Lapisan instalasi (tray, rack). Polanya sama dan bisa menyusul.
- Generate interior: fitur kedua, dibangun di atas fondasi ini (§9).
- Menambah atau memindah pintu, dan mengedit tangga atau kolom.
- Agen tool-calling bertahap (pendekatan B).

**Anti-tujuan**
- LLM mengubah sesuatu di luar area, atau elemen yang tidak ada di daftarnya.
- Perubahan tanpa review.
- Geometri dari koordinat karangan LLM yang tidak menempel ke gambar tanpa diberi tanda.
- Fitur ini membuat alur review manual lebih lambat atau berubah.

## 3. Batasan

- Strata lewat `core/llm_review/client.py` (`ask_json`, gambar `png_part`). API key tetap di server.
- Strata opsional: kalau mati, alat ini menjawab "Strata tidak tersedia" dan alur lain tidak terpengaruh.
- Waktu yang diterima user: 20–40 detik per usulan, dengan progres terlihat.
- Op mengikuti `core/spec/ops.py` dan aturan editor: pending ops, `pushOp`, undo, dan validasi dry-run.
- UI berbahasa Indonesia. Prompt sistem LLM berbahasa Inggris; jawaban LLM ke user berbahasa Indonesia.

## 4. Pendekatan

| | Pendekatan | Trade-off | Keputusan |
|---|---|---|---|
| **A** | **Rencana JSON + satu putaran koreksi.** LLM membalas satu rencana terstruktur; server menerjemahkannya ke op lewat alat deterministik, memvalidasi, lalu merevisi sekali bila perlu. | Terbukti di uji coba; cepat (1–2 panggilan); mudah diukur. Rekonstruksi besar bertahap terbatas. | **dipilih user** |
| B | Agen tool-calling bertahap | Luwes, tapi lambat (1–3 menit) dan sulit dikendalikan; T4 dulu menghasilkan 0 perbaikan | ditolak |
| C | Browser memanggil Strata langsung | API key bocor ke klien | dicoret |

## 5. Alur

1. User menekan `A` (atau tombol "Perbaiki area"), lalu menarik kotak di kanvas. Panel chat terbuka di kanan. Elemen yang
   sedang terpilih ikut dicatat.
2. User menulis instruksi, lalu Kirim.
3. Server, dengan progres di-stream ke chat:
   1. Bangun **spec kerja** = HEAD + op lokal yang belum disimpan (dikirim klien), seperti dry-run validasi.
   2. Kumpulkan **konteks area** (§6.1).
   3. Panggil LLM. Hasilnya **pertanyaan** (langkah 4) atau **rencana** (langkah 5).
4. Pertanyaan tampil di chat. User menjawab, dan jawabannya ditambahkan ke percakapan. Kembali ke 3.3. Maksimal 3
   pertanyaan per sesi; setelah itu LLM wajib memberi rencana atau menyatakan tidak bisa.
5. Rencana diterjemahkan ke op (§6.3), lalu divalidasi:
   - op ditolak, atau ada issue `error` baru dibanding sebelum usulan → kirim balik ke LLM sekali (§6.4);
   - tetap gagal → usulan ditampilkan dengan tanda error dan tombol Terima nonaktif. User bisa Tolak atau memperjelas
     instruksi.
6. Usulan tampil: ringkasan aksi dan penjelasan LLM di chat, pratinjau di kanvas.
7. **Terima** → op masuk ke pending editor (`applyMany`, satu langkah undo); kotak dan panel tetap terbuka untuk
   instruksi lanjutan. **Tolak** → pratinjau hilang. Keputusan dicatat ke log sesi.

## 6. Detail

### 6.1 Konteks area

- **Elemen:**
  - dinding yang memotong kotak: id, a, b, tebal, panjang, kind, dan bukaan di dinding itu (id, kategori, offset, lebar);
  - ruang yang poligonnya memotong kotak: id, nama, tipe, luas;
  - tangga dan kolom di dalam kotak, hanya id dan posisi (konteks, tidak bisa diubah di v1).
- **Rujukan:** id dinding yang sedang terpilih, dengan kalimat "elemen yang dimaksud user (terpilih): …".
- **Gambar:** crop `page.png` dari run terbaru (frame `grid.json` px_to_mm, sama dengan `/backdrop` dan `/snap`), kotak +
  15% margin, sisi terpanjang 900 px.
  - Dinding saat ini digambar 2 px berwarna bergantian, dengan label ID di tengahnya.
  - Dinding terpilih ditebalkan.
  - Tanpa run (spec impor): tanpa gambar, dan chat memberi tahu bahwa LLM hanya membaca daftar elemen.

### 6.2 Skema rencana

```
{ "question": str | null,
  "actions": [
    {"type": "delete_wall", "id": "W12"},
    {"type": "merge_walls", "ids": ["W70", "W73"]},
    {"type": "add_wall", "a": [x, y], "b": [x, y]},
    {"type": "delete_opening", "id": "D3"},
    {"type": "set_room_type", "room": "R5", "value": "stair"},
    {"type": "rename_room", "room": "R5", "name": "Tangga"} ],
  "explanation": str }
```

- Kalau `question` diisi, `actions` harus kosong.
- **ID di luar daftar area** membuat rencana ditolak dan masuk putaran koreksi, dengan pesan "id X tidak ada di area".
- **Nilai tipe ruang** mengikuti enum `Room.type` di spec. Yang tidak dikenal → `other`, dengan catatan di chat.

### 6.3 Penerjemahan ke op (deterministik)

- **`delete_wall`** → op `delete_wall` dengan alasan `"asisten: <instruksi, dipotong 60 karakter>"`.
- **`merge_walls`:**
  - kolinear dan bersambung → op `merge_walls` yang sudah ada;
  - sejajar (sudut ≤ 3°) dan berjarak ≤ tebal terbesar + 100 mm → hapus semua, lalu tambah satu dinding di **garis
    tengah** rentang gabungan, dengan tebal terbesar, lalu di-snap ke gambar seperti `add_wall`;
  - selain itu → ditolak ("tidak sejajar atau terlalu jauh").
  - Bukaan pada dinding yang digabung: offset diproyeksikan ke dinding baru (op `add_opening` dengan field yang sama).
    Kalau keluar dari dinding baru, bukaan itu tidak dibawa, dan chat menyebutnya.
- **`add_wall`:**
  - garis kasar dari LLM → `snap_wall` (`core/extraction/snap.py`, sama seperti Garis bantu) pada `bin.png` run terbaru;
  - menempel → dipakai;
  - tidak menempel → garis kasar dipakai dengan tebal default HEAD, ditandai **"tidak menempel ke gambar"** di chat dan
    pratinjau (kuning).
- **`delete_opening`** → op `delete_opening` dengan alasan.
- **`set_room_type` / `rename_room`** (keputusan user: opsi b, satu langkah): perubahan dinding membangun ulang ruang
  dengan ID baru, jadi aksi ruang diterjemahkan ke **op baru berbasis titik**:
  - `set_room_type_at {at: [x, y], type}` dan `rename_room_at {at: [x, y], name}`;
  - titiknya = titik representatif ruang yang dimaksud LLM, atau pusat area kalau ruangnya hilang.

  Kedua op ini **dijalankan setelah ruang dibangun ulang** di `core/spec/ops.apply` (ruang yang memuat titik itu
  sesudah rebuild). Reducer web (`web/src/editor/ops/reducer.ts`) melakukan hal yang sama, dan fixture paritas
  (`tests/test_editor_parity.py`) ikut diperbarui. Titik di luar semua ruang → `OpError` "tidak ada ruang di titik ini",
  yang masuk putaran koreksi. Op ini juga tersedia untuk editor manual, tapi tidak dipakai di UI v1.
- **Urutan op:** penghapusan → gabungan → tambahan → ruang.

### 6.4 Validasi dan putaran koreksi

- Dry-run seperti `POST /specs/validate`: spec kerja + op usulan.
- **Pemicu revisi** (hanya satu kali):
  - `OpError`;
  - issue `error` baru dibanding spec kerja sebelum usulan;
  - aksi yang ditolak penerjemah.

  LLM menerima rencana sebelumnya dan daftar masalahnya, lalu membalas rencana baru.
- **Issue `warning` dan tugas review baru** (misalnya celah) tidak memicu revisi, tapi ditampilkan di ringkasan usulan.

### 6.5 Streaming dan API

- `POST /api/projects/{pid}/assist/area`, dengan body:
  `{session_id?, base_version, ops, box: [x0, y0, x1, y1], selection: [ids], message}`.
- **Respons:** `text/event-stream` langsung, dalam request yang sama, tidak lewat EventBus project; event asisten tidak
  perlu masuk `events.jsonl`. Event:

  | Event | Isi |
  |---|---|
  | `session` | `{session_id}` |
  | `step` | `{text}`, contoh "membaca 9 dinding dan 2 ruang di area…", "menunggu Strata…" |
  | `question` | `{text}` |
  | `proposal` | `{ops, deleted: [ids], added: [{a, b, thickness, snapped}], explanation, issues, valid}` |
  | `error` | `{text}` |
  | `done` | — |

- **Sesi** disimpan di server (memori + `data/projects/<id>/assist/<session_id>.json`): percakapan, konteks, rencana,
  usulan. Jawaban atas pertanyaan dikirim dengan `session_id` yang sama.
- `POST /assist/area/{session_id}/decision {accepted: bool}` mencatat keputusan.
- **Batas waktu:** satu panggilan Strata 120 s. Strata mati atau timeout → event `error` "Strata tidak tersedia, coba
  lagi atau perbaiki manual".

### 6.6 Web

- **Alat `A` "Perbaiki area"** di toolbar review (Pilih V, Garis bantu L, Dinding baru W, Perbaiki area A). Tarik kotak,
  lalu kotak tetap tergambar (garis putus-putus ungu).
- **Panel chat** menggantikan panel kanan selama alat aktif:
  - riwayat pesan (user, langkah, pertanyaan, usulan);
  - kotak input dengan tombol Kirim (Enter);
  - tombol Terima / Tolak pada usulan terakhir;
  - Esc menutup sesi.
- **Pratinjau usulan:** lapisan SVG di atas kanvas, tidak masuk store sampai Terima.
- **Terima:** `useEditorStore.applyMany(proposal.ops)`. Kalau ditolak oleh `pushOp` (misalnya op lokal sudah berubah),
  muncul pesan "usulan usang, kirim ulang".

### 6.7 Prompt sistem (inti)

- **Peran:** perbaiki denah data center di area yang ditandai.
- **Aturan:**
  - hanya pakai ID di daftar;
  - jangan sentuh dinding luar bangunan kecuali diminta;
  - koordinat dinding baru cukup kasar (akan di-snap);
  - bertanya kalau instruksi ambigu, atau kalau "ini" tidak jelas dan tidak ada elemen terpilih;
  - jawab `explanation` dan `question` dalam bahasa Indonesia.
- **Format:** skema §6.2, `effort` medium, temperatur 0.
- Prompt disimpan berversi di `core/llm_review/prompts/AF/v1.md`, seperti T0–T4.

## 7. Ukuran keberhasilan

- **Tiga kasus uji** jadi tes regresi dengan Strata (`@pytest.mark.strata`). Data test-2 tidak ada di repo, jadi kasusnya
  dibangun dari file yang ter-commit: GT Gatsu (`benchmarks/gatsu/gt_spec.json`) + `floorplan/plan.jpeg` lewat
  `preprocess`.
  - **Duplikat:** salinan sejajar sebuah dinding GT, digeser 120 mm.
  - **"Hapus ini":** dinding nyasar yang ditambahkan ke GT.
  - **"Ruang tangga":** area tangga S1 GT dengan kotak dinding tambahan di dalamnya.

  Kotak area dan pilihan ditulis di tes. Harapannya:
  - duplikat → satu dinding gabungan;
  - "hapus ini" dengan W terpilih → hapus W itu; tanpa pilihan → bertanya;
  - "ruang tangga" → tidak menghapus dinding luar.
- **Log sesi:** tingkat Terima per jenis instruksi, dipantau saat denah PM masuk.

## 8. Yang diputuskan user

- Alur: tandai area → prompt → LLM memperbaiki → review → Terima (timpa) / Tolak (batal).
- LLM boleh bertanya balik kalau ambigu.
- Chat dengan progres streaming.
- 20–40 detik per usulan diterima.
- Pendekatan A.
- Generate interior: fitur berikutnya, dengan LLM bertanya dulu objek apa yang diinginkan.
- Tipe dan nama ruang ikut dalam usulan yang sama (opsi b), lewat op berbasis titik yang dijalankan setelah rebuild ruang.
- Fitur ini dikerjakan di branch baru (`area-assist`).

## 9. Keputusan saya (bisa dikoreksi)

- **Cakupan v1:** layout di kanvas review 2D saja. Instalasi dan generate interior menyusul dengan fondasi yang sama
  (chat streaming, rencana JSON, pratinjau, terima/tolak).
- **Terima** masuk ke pending ops (bukan langsung Save), dan menjadi satu langkah undo.
- **Streaming:** respons SSE langsung per request, tidak lewat EventBus project.
- **Batas:** maksimal 3 pertanyaan per sesi dan 1 putaran koreksi.
- **Tidak ada aksi pintu di v1.**
- **Dinding yang tidak menempel ke gambar** tetap boleh diterima, tapi diberi tanda kuning di pratinjau. Setelah Save,
  tandanya tidak hilang: cek kecocokan gambar di tahap 8 (`core/verify/fit.py`) sudah menyebut dinding yang tidak berada
  di atas garis gambar. Provenance op tetap `editor`; jejak LLM ada di log sesi `assist/`, tanpa mengubah kontrak
  ops/commit.

## 10. Diserahkan ke builder

- Gaya visual panel chat dan pratinjau, dalam pola Carbon yang ada.
- Cara menyimpan sesi di memori server (dict per project dengan TTL, misalnya 1 jam).
- Struktur modul (`core/assist/…`, `server/routes/assist.py`, `web/src/editor/assist/…`).
