# Spike Strata — Probe Kemampuan Server (M6 Task 1)

Tanggal: 2026-10-27. Model `qwen3.8-flash-next-iq2_xs` di `http://192.168.2.142:8081/v1`. Script: `benchmarks/spike/probe_strata.py`. Data mentah ada di `benchmarks/spike/out/probe.json`, yang tidak di-commit.

Spike M0 ditunda karena Strata mati (2026-10-26). Probe ini hanya mengukur **kemampuan server**. Akurasi T1/T2 dalam 4 varian (± bukti teks, ± few-shot) diukur di M6 Task 9 dengan set benchmark Gatsu ≥ 40 item, yang menggantikan 20 crop manual §8.

## Hasil

| Probe | Hasil |
|---|---|
| a. `/health`, `/status`, `/v1/models` | 200. Body `/health`: `{"status": "ok", "images": true, "loaded": true, ...}`. Body `/status`: `{"busy": false, "queued": 0}`. Field `status` (idle/processing) tidak ada; yang ada `busy`. |
| b. JSON tanpa `response_format` (5×) | 5/5 lolos `json.loads`. Tidak ada `<think>` dan tidak ada code fence. Median 567 ms. |
| c. `response_format` `json_schema` strict (5×) | Diterima (tanpa 4xx) dan ditaati: 5/5 JSON valid. Median 348 ms. |
| d. `extra_body.reasoning_effort` | `none`, `low`, dan `medium` diterima, semuanya 3/3 JSON valid. Median 108 / 547 / 487 ms. |
| e. Teks kecil dalam gambar | 768²: keenam kata terbaca, sampai tinggi huruf 6 px. 1536²: keenam kata terbaca, sampai 6 px. Tidak ada indikasi gambar diperkecil sampai teks hilang. Latensi 3.8 s / 5.7 s untuk transkripsi. |
| f. Tool calling | `tool_calls` terisi dan argumennya JSON valid. Dengan prompt "delete W3, it is a dimension line" tanpa bukti, model memilih `finish` dan menolak menghapus tanpa verifikasi. Model berhati-hati, sesuai harapan untuk T4. Latensi 9.8 s (`medium`). |
| g. Latensi `low` (5×) | Teks saja: median 653 ms, p90 1419 ms. 768²: median 633 ms, p90 2575 ms. 768² + 384²: median 516 ms, p90 2630 ms. |

## Keputusan untuk M6 Task 2–6

- `USE_RESPONSE_FORMAT = True`. Klien mengirim `response_format={"type": "json_schema", ...}` dari schema pydantic, tetapi tetap memvalidasi dan me-retry sendiri, karena jaminan server tidak menggantikan validasi.
- `reasoning_effort` dikirim lewat `extra_body={"reasoning_effort": effort}`. Nilai `none` / `low` / `medium` sesuai PRD/05 §2.
- `T4_OVERLAY_MAX_PX = 1536`, karena teks 6 px masih terbaca di 1536².
- `/status` mengembalikan `busy`, bukan `status`. `GET /api/health` (M3) membaca `status`, sehingga mode Strata di dashboard selalu `—`. Ini diperbaiki di Task 7: `status = "processing" if busy else "idle"`, dengan fallback ke field `status` bila ada.
- **Estimasi waktu tahap 6:** 60 elemen × ~2.3 suara (vote 3 dilewati bila vote 1–2 sepakat) × ~0.6–2.6 s ≈ 85–360 s, ditambah T4 ≤ 5 × ~10 s. Hasilnya berada di bawah batas 600 s. Batas waktu di harness tetap dipasang untuk kasus server sibuk.
