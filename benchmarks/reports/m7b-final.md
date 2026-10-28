# M7b — Denah sintetis: hasil dan analisis

Set: 21 varian (`benchmarks/reports/m7b-synth.md`, `.json`).
- `s00` adalah GT Gatsu tanpa perubahan yang dirender dengan gaya CAD sintetis.
- `s01…s20` adalah GT yang diubah acak per seed, lalu dirender dengan gaya yang sama:
  - lebar bay 0.75×–1.25×;
  - cermin kiri-kanan;
  - −0…3 partisi, +0…2 partisi;
  - tipe pintu diundi ulang;
  - tangga digeser ≤ 300 mm.

Contoh gambar: `m7b-synth-s00.png` dan `m7b-synth-s01.png` (s01 dicerminkan, bay diubah, −2/+1 partisi).

## Hasil terhadap kriteria PRD/01 §3

**Lolos 0/20 varian (target ≥ 70 % belum tercapai).** Lolos berarti setiap metrik ringkasan ≥ 80 % target NFR. Kriteria ini tidak memblokir MVP.

| | `wall_recall` | `wall_precision` | `wall_iou` | `door_recall` | `room_match` | `gross_area_err` | koreksi (menit) | koreksi massal (menit) |
|---|---|---|---|---|---|---|---|---|
| Batas lolos (80 % target) | ≥ 0.76 | ≥ 0.76 | ≥ 0.68 | ≥ 0.72 | ≥ 0.72 | ≤ 0.0125 | | |
| Gatsu asli (`plan.jpeg`) | 0.772 | 0.773 | 0.485 | 0.474 | 0.083 | 0.003 | 22.1 | 14.4 |
| `s00` (render GT apa adanya) | 0.902 | 0.951 | 0.643 | 0.368 | 0.042 | 0.021 | 17.8 | 13.3 |
| Rata-rata `s01…s20` | 0.868 | 0.899 | 0.560 | 0.361 | 0.048 | 0.100 | 20.6 | 14.8 |

Metrik yang gagal per varian:
- `wall_iou`, `door_recall`, `room_match`: 20/20;
- `gross_area_err`: 17/20;
- `wall_recall`: 3/20;
- `wall_precision`: 1/20.

Pembacaan grid dan skala selalu benar: galat skala ≤ 0.06 %, dan semua sumbu A–F dan 1–3 terbaca, termasuk pada varian yang dicerminkan.

## Efek gaya render (`s00` vs Gatsu asli)

- **Dinding jauh lebih baik:** recall 0.90 vs 0.77, presisi 0.95 vs 0.77. Gambar sintetis bersih: tanpa hatch, tanpa garis kabel berwarna padat, dan tanpa simbol sanitair.
- **Pintu dan ruang tidak lebih baik.** Kegagalannya tidak disebabkan oleh noise gambar asli.
- Kesimpulan: renderer ini lebih mudah dibaca daripada `plan.jpeg`. Angka sintetis adalah batas atas untuk dinding, bukan perkiraan untuk denah nyata (R-19).

## Efek perubahan geometri (`s01…s20` vs `s00`)

Sebagian besar varian (14/20) tetap dekat `s00`: recall 0.86–0.93, presisi 0.88–0.96, `wall_iou` 0.56–0.64. Penurunan besar hanya datang dari dua mode gagal (no. 3 dan 4 di bawah).

## Mode gagal teratas (kandidat perbaikan umum milestone berikutnya)

1. **Ruang menyatu (`room_match` ≈ 0.05).**
   - Ruang yang terbentuk hanya 7–27, sedangkan GT punya 44–50.
   - Celah pintu tidak ditutup, sehingga ruang-ruang bersebelahan melebur menjadi satu.
   - Polanya sama dengan Gatsu asli (41 ruang; 22 sebelum pemecahan leher di M7a), dan muncul di semua varian.
   - Ini kandidat terbesar: menutup bukaan pintu sebagai pemisah ruang (PRD/04 §6b).
2. **Pintu terlewat (`door_recall` ≈ 0.36, arah benar 0.33).**
   - Busur pintu sintetis tergambar lengkap, tapi ekstraktor tetap melewatkan 2 dari 3 pintu.
   - Pada Gatsu asli recall 0.47, jadi kegagalannya ada di deteksi pintu sendiri, bukan di kualitas gambar.
3. **Pemilihan kandidat stage 5 tidak stabil.**
   - Pada `s01`, `s04`, dan `s14`, stage 5 memilih strategi S1 (garis tunggal) alih-alih S2.
   - Dinding lalu jatuh di salah satu muka dinding, bukan di garis tengahnya: galat posisi median 44–68 mm, `wall_iou` 0.27–0.31, recall 0.67–0.70.
   - Masalah serupa sudah tercatat di M7a-2 (pilihan medoid di-revert). Skor validator saja tidak cukup membedakan S1 dari S2 pada denah garis ganda.
4. **Kontur bangunan pecah.**
   - Pada `s03` dan `s13`, kontur utama terbelah menjadi dua massa (prediksi 364/406 m² vs GT 521/639 m²), sehingga `gross_area_err` 0.30–0.37.
   - Closing 1500 mm per massa (M7a-2) tidak cukup bila partisi tambahan atau bay sempit membuat celah pada pita luar.

## Menit koreksi

- Rata-rata model satu-per-satu: 20.6 menit.
- **Model aksi massal: rata-rata 14.8 menit, median 14.4. 13/20 varian ≤ 15 menit.**
- Seperti Gatsu (14.4), menit koreksi massal di sekitar batas MVP #2. Angka ini menunggu kalibrasi (`docs/calibration-correction.md`).

## Batasan

- Gaya render adalah asumsi kita sendiri (R-19). Set ini menguji ketahanan terhadap perubahan geometri, bukan keragaman gaya denah nyata.
- Varian berasal dari satu bangunan. Denah nyata lain dari PM tetap dibutuhkan.
