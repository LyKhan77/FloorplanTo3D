# M7a — Laporan akhir ketahanan & akurasi ekstraksi

Kode akhir = Task 4 + Task 5 + fix pass review akhir (Task 3 dan 6 di-revert). Angka Gatsu dari `m7a-baseline` → `m7a-final-fix`, set augmentasi dari `m7a-augment-baseline` → `m7a-augment-final`.

## Gatsu (run tahap 0–5 pada `floorplan/plan.jpeg`)

| Metrik | Baseline | Akhir | Target NFR | Lolos NFR |
|---|---|---|---|---|
| scale_err | 0.001 | 0.001 | 0.005 | ya |
| wall_recall | 0.766 | 0.772 | 0.950 | tidak |
| wall_precision | 0.800 | 0.773 | 0.950 | tidak |
| wall_pos_median_mm | 18.000 | 17.000 | 50 | ya |
| wall_pos_p95_mm | 113.000 | 113.000 | 150 | ya |
| door_recall | 0.421 | 0.474 | 0.900 | tidak |
| door_width_ok | 0.316 | 0.368 | 0.900 | tidak |
| door_dir_ok | 0.167 | 0.222 | 0.800 | tidak |
| room_match | 0.021 | 0.083 | 0.900 | tidak |
| rooms_pred | 22 | 42 | — | — |
| rooms_gt | 48 | 48 | — | — |
| wall_iou | 0.511 | 0.485 | 0.850 | tidak |
| stair_risers_ok | 0.333 | 0.000 | 1.000 | tidak |
| stair_dir_ok | 1.000 | 1.000 | 1.000 | ya |
| gross_area_err | 0.030 | 0.038 | 0.010 | tidak |

Ruang: dalam 8/23 → 7/23 cocok; outdoor 3/25 → 10/25.
Dinding GT terlewat: 20 → 16; dinding palsu: 67 → 68.

## Set augmentasi (30 varian: a00 + 19 satu-faktor + 10 kombinasi)

| Rata-rata (run berhenti = nilai terburuk) | Baseline | Akhir |
|---|---|---|
| wall_recall | 0.4912 | 0.4994 |
| wall_precision | 0.5521 | 0.5512 |
| wall_iou | 0.3096 | 0.3115 |
| door_recall | 0.2579 | 0.2667 |
| room_match | 0.0104 | 0.0278 |
| gross_area_err | 0.6377 | 0.6070 |

Skor ketahanan relatif (porsi metrik ≥ 0.9 × a00): 0.432 → 0.480. Varian lolos penuh (setiap metrik ≥ 0.9 × a00): 0/29 → 1/29.

## Perbaikan

| Task | Aturan | Hasil |
|---|---|---|
| 3 | Dinding satu sisi (garis tunggal yang kedua ujungnya bertemu garis tegak lurus) | **di-revert**: recall +3.2 poin tetapi presisi −6 poin (potongan sumbu grid, tepi tangga, jalur kabel); hanya 1 dari 9 dinding sasaran pulih karena garis mukanya sudah berpasangan |
| 4 | Pasangan garis ganda yang terputus (overlap absolut ≥ 300 mm) | **dipertahankan**: Gatsu recall 0.766 → 0.779; rata-rata augmentasi `gross_area_err` 0.638 → 0.595 |
| 4 | Muka dinding mempertahankan tebalnya | **di-revert**: kontur bangunan runtuh (`gross_area_err` 0.03 → 0.59) |
| 5 | Ruang dipecah di leher < 300 mm (`form_rooms`, hanya ruang di kontur luar sesudah fix pass) | **dipertahankan, menunggu keputusan pengguna**: outdoor 3 → 10, ruang 22 → 41 (GT 48), `room_match` 0.021 → 0.083; tahap 5 berpindah ke kandidat lain (skor 0.871 vs 0.855): presisi dinding −2 poin |
| fix pass | Leher dipotong tanpa membungkus partisi tipis; pemecahan dibatasi ke kontur luar; pasangan silang antar-partisi ditolak; exception tahap jadi varian gagal | dinding identik dengan Task 5, `room_match` 0.042 → 0.083 |
| 6 | Cable ladder (garis ganda ≥ 200 mm dengan rung) | **di-revert**: presisi +1.2 poin di Gatsu, tetapi pita luar bersirip ikut terbuang dan kontur runtuh (`gross_area_err` sampai 0.59) |

## Mode gagal yang tersisa

1. **Kontur bangunan rapuh.** Satu dinding pita yang hilang memutus kontur luar dan `gross_area_err` melonjak (rata-rata augmentasi ~0.6, sedangkan a00 0.05). Ini masalah ketahanan terbesar dan perlu task tersendiri: kontur yang toleran celah, bukan penyaringan dinding.
2. **Resolusi rendah (skala ≤ 0.75).** `wall_recall` turun ke 0.02–0.06, dan sebagian varian berhenti di tahap 2 (skala tidak terbaca).
3. **Pemilihan kandidat tahap 5 tidak stabil.** Perubahan kecil pada skor validator membuat tahap 5 berpindah di antara kandidat yang skornya hampir sama.
4. **Ruang dalam bocor menjadi satu ruang besar** (316 m²) lewat dinding yang terlewat, misalnya dinding bawah R. MEETING yang berimpit dengan sumbu grid 2.
5. **Dinding pita bagian dalam (W11/W13) berpasangan salah** dengan garis 400 mm, dan pasangan salah itu justru ikut menutup kontur.
6. **Dinding palsu:** cable tray, tepi tangga, dan partisi bilik toilet. Tidak ada aturan penghapusan yang aman selama kontur masih rapuh.

## Kriteria selesai M7 (dari ROADMAP)

- **Kriteria 1 (Gatsu memenuhi NFR-AC): belum.** Lihat kolom "Lolos NFR" pada tabel Gatsu.
- **Kriteria 2 (≥ 80% varian augmentasi mencapai ≥ 0.9 × a00): belum.** Hanya 2/29 varian lolos.

Sisa galat Gatsu dikoreksi lewat panel koreksi editor (M4).
