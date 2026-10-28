# M7b — Denah sintetis: hasil dan analisis

Set: 21 varian (`benchmarks/reports/m7b-synth.md`, `.json`).
- `s00` adalah GT Gatsu tanpa perubahan yang dirender dengan gaya CAD sintetis.
- `s01…s20` adalah GT yang diubah acak per seed, lalu dirender dengan gaya yang sama:
  - lebar bay 0.75×–1.25× (lebar tangga ikut menyempit bila bay-nya menyempit);
  - cermin kiri-kanan;
  - −0…3 partisi, +0…2 partisi;
  - tipe pintu diundi ulang di antara tipe yang cocok dengan lebarnya (daun 500–1300 mm, PRD/04 §3.4);
  - tangga digeser ≤ 300 mm, diperkecil bila anak tangga akan masuk ke dinding.

Metrik dihitung di frame varian sendiri, tanpa penyelarasan. Kolom "geser terbaik" hanya diagnostik.

Contoh gambar: `m7b-synth-s00.png` dan `m7b-synth-s01.png` (s01 dicerminkan, bay diubah, −2/+1 partisi).

## Hasil terhadap kriteria PRD/01 §3

**Lolos 0/20 varian (target ≥ 70 % belum tercapai).** Lolos berarti setiap metrik ringkasan ≥ 80 % target NFR. Kriteria ini tidak memblokir MVP.

| | `wall_recall` | `wall_precision` | `wall_iou` | `door_recall` | `room_match` | `gross_area_err` | koreksi (menit) | koreksi massal (menit) |
|---|---|---|---|---|---|---|---|---|
| Batas lolos (80 % target) | ≥ 0.76 | ≥ 0.76 | ≥ 0.68 | ≥ 0.72 | ≥ 0.72 | ≤ 0.0125 | | |
| Gatsu asli (`plan.jpeg`) | 0.772 | 0.773 | 0.485 | 0.474 | 0.083 | 0.003 | 22.1 | 14.4 |
| `s00` (render GT apa adanya) | 0.902 | 0.951 | 0.643 | 0.368 | 0.042 | 0.021 | 17.8 | 13.3 |
| Rata-rata `s01…s20` | 0.870 | 0.926 | 0.562 | 0.362 | 0.040 | 0.126 | 20.2 | 14.6 |

Metrik yang gagal per varian:
- `wall_iou`, `door_recall`, `room_match`: 20/20;
- `gross_area_err`: 16/20;
- `wall_recall` dan `wall_precision`: 0/20.

Pembacaan grid dan skala selalu benar: galat skala ≤ 0.06 %, dan semua sumbu A–F dan 1–3 terbaca, termasuk pada varian yang dicerminkan.

## Efek gaya render (`s00` vs Gatsu asli)

- **Dinding jauh lebih baik:** recall 0.90 vs 0.77, presisi 0.95 vs 0.77. Gambar sintetis bersih: tanpa hatch, tanpa garis kabel berwarna padat, dan tanpa simbol sanitair.
- **Pintu dan ruang tidak lebih baik.**
- **Luas kotor lebih buruk:** 0.021 vs 0.003.
- Kesimpulan: renderer ini lebih mudah dibaca daripada `plan.jpeg` untuk dinding. Angka dinding sintetis adalah batas atas, bukan perkiraan untuk denah nyata (R-19).

## Efek perubahan geometri (`s01…s20` vs `s00`)

- **17/20 varian tetap dekat `s00`:** recall 0.84–0.94, presisi 0.89–0.97, `wall_iou` 0.55–0.65, galat posisi median 6–9 mm.
- **Penurunan besar datang dari dua mode gagal** (no. 3 dan 4 di bawah).
- Cermin, partisi, tipe pintu, dan tangga sendiri tidak menurunkan dinding secara berarti.

## Mode gagal teratas (kandidat perbaikan umum milestone berikutnya)

1. **Ruang menyatu (`room_match` ≈ 0.04).**
   - Ruang yang terbentuk hanya 12–32, sedangkan GT punya 44–50, dan pola ini muncul di semua varian.
   - Celah pintu tidak ditutup, sehingga ruang-ruang bersebelahan melebur.
   - Ini kandidat terbesar: menutup bukaan pintu sebagai pemisah ruang (PRD/04 §6b).
2. **Pintu terlewat (`door_recall` rata-rata 0.36, rentang 0.05–0.63; arah benar 0.32).**
   - Busur pintu sintetis tergambar lengkap dan ukuran daunnya realistis, tapi ekstraktor tetap melewatkan sekitar 2 dari 3 pintu.
   - Pada Gatsu asli recall 0.47, jadi kegagalannya ada di deteksi pintu, bukan di kualitas gambar.
3. **Pemilihan kandidat stage 5 tidak stabil.**
   - Pada `s01`, `s04`, dan `s14`, stage 5 memilih strategi S1 (garis tunggal) alih-alih S2.
   - Dinding jatuh di salah satu muka dinding: galat posisi median 64–69 mm, `wall_iou` 0.30–0.32, recall 0.76–0.79.
   - Pada `s04` dan `s14`, geser terbaik (0, −100) menunjukkan pergeseran yang sama.
   - Masalah serupa sudah tercatat di M7a-2 (pilihan medoid di-revert). Skor validator saja tidak cukup membedakan S1 dari S2 pada denah garis ganda.
4. **Kontur bangunan pecah atau menyusut.**
   - Pada 7/20 varian, kontur prediksi terbelah menjadi 2–4 massa atau kehilangan sebagian bangunan, sehingga `gross_area_err` 0.10–0.45:
     - `s01`, `s04`, `s14`: bersama S1;
     - `s03`, `s06`, `s10`, `s16`: dengan S2.
   - Closing 1500 mm per massa (M7a-2) tidak cukup bila partisi tambahan, bay sempit, atau dinding di muka luar membuat celah pada pita luar.
   - 9 varian lain gagal tipis (0.018–0.025), setara `s00` (0.021). Itu galat sistematis kecil pada render ini, bukan efek perubahan geometri.

## Menit koreksi

- Rata-rata model satu-per-satu: 20.2 menit.
- **Model aksi massal: rata-rata 14.6 menit, median 13.6. 14/20 varian ≤ 15 menit.**
- Seperti Gatsu (14.4), angka ini menunggu kalibrasi (`docs/calibration-correction.md`).

## Batasan

- Gaya render adalah asumsi kita sendiri (R-19). Set ini menguji ketahanan terhadap perubahan geometri, bukan keragaman gaya denah nyata.
- Panel terisi kadang menutupi label ruang, dan label bisa bertabrakan setelah bay menyempit. GT tetap menyimpan nama itu, sehingga model koreksi menghitung rename untuknya.
- Varian berasal dari satu bangunan. Denah nyata lain dari PM tetap dibutuhkan.
