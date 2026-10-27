# M6 — Review Strata: Ringkasan Benchmark

Tanggal 2026-10-27, model `qwen3.8-flash-next-iq2_xs`. Keputusan per tugas dan alasannya ada di `benchmarks/DECISIONS.md`. Probe kemampuan server ada di `spike-strata.md`.

**Set aktif: `LLM_TASKS_ENABLED=T0,T3`.** T0 berjalan di tahap 0, T3 di tahap 6. T1, T2, dan T4 nonaktif.

| Tugas | Hasil | Pembanding | Lolos §7.2 | Gatsu end-to-end |
|---|---|---|---|---|
| T0 parse prompt | 0.99 | aturan 0.78 | ya | — (tahap 0) |
| T1 verifikasi dinding | 0.656, presisi hapus 1.00 | CV 0.531 | ya | **turun** (`wall_recall` −4.8 poin) |
| T2 verifikasi pintu | engsel/arah 0.80/0.80 | CV 0.80/0.80 | tidak | — |
| T3 tipe ruang | 0.85 | leksikon 0.75 | ya | sama (0 perubahan) |
| T4 perbaikan via tool | 0 perubahan diterima | tanpa T4 | tidak | sama |

**Gatsu dengan set aktif vs tanpa Strata:** semua metrik sama (Δ 0), jadi kriteria "dengan Strata ≥ tanpa Strata" terpenuhi. Waktu tahap 6 adalah 5.8 s (batas 600 s). Dengan T1 aktif, tahap 6 butuh 591.6 s, sudah di batas waktu.

Metrik Gatsu (tahap 5 = tahap 6): `wall_recall` 0.766, `wall_precision` 0.800, `door_recall` 0.421, `room_match` 0.021, `wall_iou` 0.511, `gross_area_err` 0.030, `rooms_typed_ok` 4.

Strata tidak menaikkan akurasi Gatsu. Penyebab utama galat masih berasal dari tahap 3–4 (dinding terputus, 22 vs 48 ruang). Tugas klasifikasi per elemen tidak bisa menambah dinding yang hilang, karena tool geometri bebas memang tidak diberikan ke model 2-bit (PRD/05 §4).
