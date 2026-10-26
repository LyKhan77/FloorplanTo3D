# 05 — Review LLM (Tahap 6) & Peran Strata

## 1. Posisi LLM dalam Sistem

Strata (`qwen3.8-flash-next-iq2_xs`, ±2-bit, multimodal, 128K context, tool calling OpenAI) adalah model lokal dengan kemampuan terbatas. Desain mengikuti tiga prinsip:

1. **Lantai terjamin.** Hasil terburuk tahap 6 sama dengan hasil tahap 5. Strata tidak pernah bisa memperburuk spec, karena ada gerbang skor.
2. **Tugas kecil dan tertutup.** Satu elemen, satu pertanyaan, jawaban enum atau JSON berskema. Tidak ada generasi kode.
3. **Diaktifkan berdasarkan bukti.** Setiap jenis tugas punya flag. Flag hanya boleh aktif bila tugas itu lolos benchmark (§7).

### 1.1 Tiga tingkat peran LLM

| Tingkat | Kapan | Interaksi | Status MVP |
|---|---|---|---|
| **1 — Otomatis** | Setiap run, tahap 6 | Harness memanggil Strata dengan tugas terdefinisi, tanpa chat | **P0** |
| **2 — Eskalasi** | Run berstatus `needs_attention` atau skor tetap di bawah ambang | Manusia berdiskusi dengan Strata lewat panel chat di dashboard. Strata memakai tool spec yang sama dan render headless sebagai "mata". | P2 (post-MVP) |
| **3 — Developer** | Gaya denah baru gagal, atau butuh fitur baru | Coding agent (Pi / Claude Code ke endpoint Strata) mengubah **kode** di repo, bukan data project | Di luar runtime; dipakai tim |

**Blender MCP** tidak dipakai di jalur utama. Blender MCP hanya opsional untuk Tingkat 2 (inspeksi read-only) atau untuk developer. Perubahan langsung ke `.blend` lewat MCP akan tertimpa saat regenerate (lihat ADR-1, ADR-2).

## 2. Daftar Tugas LLM

| ID | Tugas | Input | Output (schema) | `reasoning_effort` | Voting |
|---|---|---|---|---|---|
| **T0** | Parse prompt menjadi parameter | teks prompt | `PromptParams` | `low` | tidak |
| **T1** | Verifikasi elemen: "apakah elemen ini dinding?" | crop zoom + konteks + fitur teks | `{"id", "verdict": "wall"\|"annotation"\|"unsure"}` | `low` | 3 |
| **T2** | Verifikasi pintu dan arahnya | crop zoom pintu + fitur | `{"id", "is_door": bool, "door_type", "hinge", "swing"}` | `low` | 3 |
| **T3** | Tipe ruang dari label | teks label OCR + daftar enum + luas | `{"id", "type", "name_normalized"}` | `none` | 3 |
| **T4** | Perbaikan masalah validator lewat tool | overlay bernomor + daftar masalah + tool | `tool_calls` (lihat §4) | `medium` | tidak |

Tugas T1–T3 tergolong **klasifikasi**. T4 tergolong **aksi**. T4 adalah tugas paling berisiko, sehingga paling akhir diaktifkan.

### 2.1 Pemilihan elemen untuk review (routing)

Hanya elemen berikut yang dikirim ke Strata:
- `provenance.confidence < 0.6`,
- elemen yang dirujuk oleh masalah validator berseverity `warning`/`error`,
- ruang bertipe `other` atau tanpa nama (T3).

Batas per run: maksimal 60 elemen untuk T1/T2 (diurutkan dari keyakinan terendah) dan `LLM_MAX_ITER` iterasi T4 (default 5).

## 3. Format Input ke Strata

### 3.1 Crop zoom (T1, T2)

- Crop persegi berpusat pada elemen, dengan ukuran = panjang elemen × 1.6 (min 2 m, maks 8 m). Crop diambil dari `page.png` resolusi kerja, lalu di-resize ke **768×768**.
- Elemen yang ditanya digambar dengan **outline magenta 3 px** dan label ID besar di pojok. Elemen lain digambar tipis abu-abu.
- Ditambah **thumbnail konteks 384×384** dari seluruh denah, dengan kotak merah di posisi crop.

### 3.2 Bukti teks (wajib)

Contoh untuk T1:

```
Element W7
- length: 4200 mm, thickness: 90 mm (stroke 3.1 px), orientation: horizontal
- connects to walls at ends: start=none, end=W12
- passes through dense-hatch area: yes (62% of length)
- nearest text within 600 mm: "NYY 4x1Cx185mm" (annotation class)
- parallel partner line found: no
- CV confidence: 0.41
```

### 3.3 Few-shot

Per tugas, 3–5 contoh dari benchmark Gatsu (crop + bukti + jawaban benar), mencakup kasus positif, kasus negatif, dan kasus jebakan (jalur kabel yang mirip dinding). Contoh disimpan di `benchmarks/gatsu/fewshot/<task>/`.

### 3.4 System prompt (kerangka)

```
You are a floor plan verification assistant for data center drawings.
Answer ONLY with JSON matching the given schema. No explanation outside JSON.
Architectural walls are drawn as thick lines or pairs of parallel lines 80–600 mm apart.
Cable routes, dimension lines, leaders and MEP annotations are NOT walls.
If unsure, answer "unsure".
```

Prompt sistem ditulis dalam bahasa Inggris dan diberi versi (`prompts/<task>/v<n>.md`). Versi prompt dicatat di transkrip.

## 4. Tool untuk T4

Tool dipetakan 1:1 ke ops spec (`03-layout-spec.md` §11) dan dibatasi:

| Tool | Parameter | Batas |
|---|---|---|
| `delete_wall` | `id`, `reason` | Hanya dinding dengan `confidence < 0.8` |
| `merge_walls` | `ids[]`, `reason` | Hanya dinding kolinear yang berdekatan (≤ tebal) |
| `set_door` | `id`, `door_type?`, `hinge?`, `swing?` | — |
| `delete_opening` | `id`, `reason` | Hanya `confidence < 0.8` |
| `set_room_type` | `id`, `type` | — |
| `rename_room` | `id`, `name` | — |
| `finish` | `summary` | Mengakhiri loop |

Tool geometri bebas (`add_wall`, `move_wall`) **tidak** diberikan ke Strata, karena model 2-bit tidak andal untuk koordinat.

## 5. Harness Loop

```
spec = spec_v1
score = validate(spec).score
queue = select_for_review(spec)              # §2.1

# Fase A: klasifikasi (T1, T2, T3), per elemen
for el in queue:
    answers = [ask(task_for(el), el) for _ in range(VOTES)]   # self-consistency
    verdict = majority(answers, min_agree=2)                  # tidak sepakat → abaikan
    if verdict and verdict != current(el):
        candidate = apply(spec, op_from(verdict))
        new = validate(candidate).score
        if no_errors(candidate) and new >= score - 0.005:     # gerbang (toleransi kecil untuk label)
            spec, score = candidate, new; log(accepted)
        else:
            log(rejected, reason="score_drop")

# Fase B: perbaikan (T4), loop tool calling
for i in range(LLM_MAX_ITER):
    issues = validate(spec).issues
    if not issues: break
    call = ask_tools(overlay_ids(spec), issues, TOOLS)
    if call.name == "finish" or call is None: break
    candidate = apply(spec, call)
    if no_errors(candidate) and validate(candidate).score > score:   # harus NAIK
        spec, score = candidate, validate(candidate).score; log(accepted)
    else:
        log(rejected); feed_back_rejection(call)   # beri tahu model bahwa aksi ditolak

if spec != spec_v1: save(spec, source="llm")   # spec.v2
```

Aturan tambahan:
- **Gerbang Fase A** memakai toleransi −0.005. Perubahan label atau tipe ruang bisa netral terhadap skor, tetapi tetap bernilai.
- **Gerbang Fase B** mensyaratkan skor naik secara ketat.
- Output yang tidak valid JSON/schema di-retry maksimal 2 kali dengan pesan error parsing, lalu elemen dilewati.
- Panggilan memakai `temperature: 0` untuk percobaan pertama. Untuk suara voting ke-2 dan ke-3 dipakai `temperature: 0.4` dengan variasi crop (zoom ×1.3) agar suaranya independen.
- Timeout per panggilan: `STRATA_TIMEOUT_S`. Batas total tahap 6: 10 menit. Bila lewat, hasil yang sudah diterima tetap dipakai.

## 6. Ketersediaan & Fallback

1. Sebelum tahap 6, jalankan `GET /health` ke Strata (timeout 3 s).
2. Bila gagal, tahap 6 = `skipped` (reason `strata_unavailable`) dan pipeline lanjut ke tahap 7 dengan `spec.v1`.
3. Bila `LLM_TASKS_ENABLED` kosong, tahap 6 = `skipped` (reason `disabled`).
4. Dashboard menampilkan status Strata dari `GET /health` dan `GET /status` (idle/processing) setiap 15 detik.

## 7. Benchmark & Gerbang Aktivasi

### 7.1 Dataset

- **Sumber**: ground truth Gatsu (`benchmarks/gatsu/gt_spec.json`), ditambah GT denah lain saat tersedia.
- **Pembuatan item**: jalankan tahap 1–5 dengan beberapa kandidat sweep, lalu cocokkan elemen hasil CV dengan GT (IoU tapak ≥ 0.5 untuk dinding, ≤ 300 mm untuk pintu). Hasilnya item berlabel:
  - T1: elemen CV yang **benar dinding** dan yang **sebenarnya anotasi** (false positive), target ≥ 40 item seimbang;
  - T2: pintu dengan tipe, engsel, dan arah GT, target ≥ 20 item;
  - T3: label ruang beserta tipe GT, target ≥ 20 item (boleh ditambah label sintetis dengan variasi typo OCR).
- Item few-shot **dikeluarkan** dari set evaluasi.

### 7.2 Metrik & ambang

| Tugas | Baseline | Metrik | Syarat aktif |
|---|---|---|---|
| T1 | Ambang keyakinan CV (≥ 0.5 = dinding) | Akurasi, F1 kelas "annotation" | Akurasi ≥ baseline + 5 poin **dan** presisi pada keputusan "hapus" ≥ 90% |
| T2 | Hasil CV | Akurasi per field | Akurasi `swing`/`hinge` ≥ baseline + 10 poin |
| T3 | Leksikon (§4.3 dok 04) | Akurasi tipe | ≥ leksikon + 5 poin, atau leksikon gagal ≥ 20% |
| T4 | Tanpa T4 | Δ skor validator dan Δ metrik akurasi GT di akhir run | Δ akurasi GT ≥ 0 di **semua** denah benchmark, dan Δ > 0 di minimal satu |

### 7.3 Prosedur

- Script `benchmarks/run_llm_bench.py --task T1 --prompt v2 --votes 3` menghasilkan laporan Markdown + JSON di `benchmarks/reports/`. Isinya akurasi, matriks kebingungan, latensi rata-rata, dan tingkat output invalid.
- Benchmark wajib dijalankan ulang ketika model, kuantisasi, versi prompt, atau format crop berubah.
- Keputusan aktivasi dicatat di `benchmarks/DECISIONS.md` (tanggal, tugas, hasil, keputusan).

## 8. Spike Awal (sebelum M6)

Tujuan: mengukur kemampuan nyata Strata sedini mungkin, dengan biaya rendah.

1. Nyalakan Strata di gspe-ai2.
2. Ambil 20 crop Gatsu secara manual: 10 dinding asli, 6 jalur kabel/garis dimensi, 4 pintu.
3. Jalankan T1/T2 dengan format §3 (dengan dan tanpa bukti teks, dengan dan tanpa few-shot).
4. Catat akurasi, latensi per panggilan, tingkat JSON invalid, dan apakah gambar diperkecil oleh server (uji dengan crop berisi teks kecil).
5. Hasil spike menentukan urutan aktivasi tugas dan menjadi bahan rekomendasi kuantisasi (lihat `12-risks.md` R-06).

## 9. Transkrip & Observabilitas

`runs/<id>/stages/06_review/transcript.jsonl`, satu baris per panggilan:

```jsonc
{ "ts": "...", "task": "T1", "element": "W7", "prompt_version": "v2", "vote": 1,
  "request": { "messages_ref": "crops/W7_v1.png", "effort": "low" },
  "response": { "raw": "{\"id\":\"W7\",\"verdict\":\"annotation\"}", "parsed": {...}, "valid": true },
  "latency_ms": 2140, "tokens": { "prompt": 1830, "completion": 22 } }
```

`decisions.json` berisi keputusan akhir per elemen: `accepted` / `rejected(score_drop)` / `no_consensus` / `invalid_output`, beserta skor sebelum dan sesudah. Dashboard menampilkan keduanya di tab Review.

## 10. Panel Chat Eskalasi (Tingkat 2, post-MVP, ringkas)

- Panel chat di tab Review untuk run `needs_attention`.
- Strata mendapat tool yang sama dengan T4, ditambah `render_view(camera)` (render headless, read-only) dan `show_overlay(ids[])`.
- Setiap aksi tetap lewat ops, gerbang validasi, dan versi spec baru. Bedanya, manusia dapat menyetujui aksi yang menurunkan skor, dengan konfirmasi eksplisit.
