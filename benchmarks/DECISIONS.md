# Keputusan Aktivasi Tugas Strata (PRD/05 §7)

Setiap tugas LLM hanya aktif bila lolos syarat §7.2 pada benchmark Gatsu. Benchmark wajib diulang bila model, kuantisasi, versi prompt, atau format crop berubah (§7.3).

Model: `qwen3.8-flash-next-iq2_xs` (Strata, `192.168.2.142:8081`). Item: `benchmarks/gatsu/llm_items/` (`python -m benchmarks.llm_items`). Laporan: `benchmarks/reports/llm-*.md` (voting 3) dan `benchmarks/reports/screen/` (saringan varian, 1 suara).

## 2026-10-27 — M6

| Tugas | Varian dan prompt | n eval | Hasil | Pembanding | Syarat §7.2 | Keputusan |
|---|---|---|---|---|---|---|
| T0 parse prompt | v1, `low` (diukur sebelum budget 512 ditambahkan; latensi 2.8 s, jadi tidak terdampak) | 20 prompt × 5 field | akurasi field 0.99 | parser aturan 0.78 | ≥ aturan + 5 poin | **aktif** |
| T1 verifikasi dinding | v1, bukti teks, **tanpa** few-shot, `none`, 3 suara | 96 (48 dinding / 48 anotasi) | akurasi 0.656, presisi "hapus" **1.00** (15/15) | ambang CV ≥ 0.5: 0.531 | ≥ +5 poin **dan** presisi hapus ≥ 0.90 | **aktif** |
| T1 (varian lain) | v1, bukti teks + few-shot, 3 suara | 96 | akurasi 0.760, presisi hapus 0.755 | 0.531 | presisi hapus < 0.90 | ditolak: menghapus 12 dari 48 dinding asli |
| T2 verifikasi pintu | v1, bukti teks + few-shot, 1 suara (saringan) | 24 (5 pintu asli + 19 deteksi palsu) | engsel 0.80, arah 0.80; is_door 0.83 (tanpa bukti teks: 0.96) | CV: engsel 0.80, arah 0.80; is_door 0.21 | engsel dan arah masing-masing ≥ +10 poin | **nonaktif** |
| T3 tipe ruang | v1, bukti teks + few-shot, `none`, 3 suara | 20 (7 label + 13 varian typo) | akurasi tipe 0.85 | leksikon 0.75 | ≥ leksikon + 5 poin | **aktif** |
| T4 perbaikan via tool | v1, `medium` + budget 2048 | Gatsu end-to-end | _diisi setelah run_ | T1+T3 tanpa T4 | Δ akurasi GT ≥ 0 semua metrik, > 0 minimal satu | _diisi_ |

### Catatan

- **Thinking dibatasi.** Strata berpikir tanpa batas secara default (`thinking_budget: null`). Satu pertanyaan T1 bergambar menghasilkan lebih dari 10.000 token penalaran (> 75 s) pada `reasoning_effort: low`. T1/T2/T3 memakai `none`: jawaban sama pada item uji, sekitar 5 s per panggilan. T0 dan T4 memakai `reasoning_budget_tokens` 512 dan 2048.
- **Few-shot per tugas** (`FEWSHOT_TASKS = T2, T3`). Few-shot menaikkan akurasi T1 (0.66 → 0.76), tetapi menurunkan presisi hapus dari 1.00 ke 0.76. Gerbang §7.2 mementingkan presisi hapus, jadi T1 berjalan tanpa few-shot.
- **T1 berhati-hati.** Pada varian aktif, Strata menandai 15 dari 48 anotasi (recall 0.31) dan tidak pernah menandai dinding asli. Selebihnya tetap ditangani gerbang skor validator di tahap 6.
- **T2 punya sinyal berguna di luar syarat PRD.** Strata mengenali deteksi pintu palsu jauh lebih baik dari CV (is_door 0.96 vs 0.21 tanpa bukti teks). Namun syarat §7.2 untuk T2 adalah engsel dan arah, dan di sana Strata tidak lebih baik dari CV pada 5 pintu asli. Mengaktifkan T2 hanya untuk menghapus pintu palsu butuh syarat baru, yang menjadi keputusan pemilik produk.
- **n kecil.** GT Gatsu punya 19 pintu, dan CV hanya menemukan sekitar 8 pada jarak ≤ 300 mm, sehingga target T2 ≥ 20 tidak tercapai. T3 tepat 20 item setelah label yang bukan nama ruang dibuang.
