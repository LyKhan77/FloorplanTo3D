# M7a-2 — Upaya koreksi, kontur toleran celah, pemilihan kandidat

Kode akhir = Task 1 (metrik) + Task 2 (kontur per massa); Task 3 (medoid) di-revert. Angka dari `m7a2-baseline` → `m7a2-t2` (Gatsu) dan `m7a2-augment-baseline` → `m7a2-augment-t2`.

## Kriteria MVP #2: koreksi ≤ 15 menit

**Gatsu: 22.1 → 21.8 menit, belum terpenuhi.** Sebagai pembanding, menggambar ulang dari nol butuh 39.0 menit. Rata-rata set augmentasi: 31.1 → 30.6 menit.

| Operasi | detik/op | Baseline | Akhir | Menit (akhir) |
|---|---|---|---|---|
| delete_wall | 5 | 68 | 68 | 5.7 |
| add_wall | 20 | 16 | 16 | 5.3 |
| delete_opening | 5 | 9 | 9 | 0.8 |
| add_opening | 15 | 10 | 10 | 2.5 |
| set_door | 10 | 5 | 5 | 0.8 |
| set_room_type | 8 | 31 | 30 | 4.0 |
| rename_room | 8 | 14 | 13 | 1.7 |
| set_stair | 20 | 3 | 3 | 1.0 |

Tiga penyumbang terbesar: delete_wall (5.7 menit), add_wall (5.3 menit), set_room_type (4.0 menit).

## Gatsu

| Metrik | Baseline | Akhir | Target NFR |
|---|---|---|---|
| wall_recall | 0.772 | 0.772 | 0.950 |
| wall_precision | 0.773 | 0.773 | 0.950 |
| wall_iou | 0.485 | 0.485 | 0.850 |
| door_recall | 0.474 | 0.474 | 0.900 |
| door_width_ok | 0.368 | 0.368 | 0.900 |
| door_dir_ok | 0.222 | 0.222 | 0.800 |
| room_match | 0.083 | 0.083 | 0.900 |
| rooms_pred | 42 | 50 | — |
| rooms_gt | 48 | 48 | — |
| gross_area_err | 0.038 | 0.003 | 0.010 |

Ruang: dalam 7/23 → 9/23, outdoor 10/25 → 11/25. **`gross_area_err` 0.038 → 0.003: NFR ≤ 0.01 terpenuhi.**

## Set augmentasi (rata-rata, run berhenti = nilai terburuk)

| Metrik | Baseline | Akhir |
|---|---|---|
| wall_recall | 0.4994 | 0.5024 |
| wall_precision | 0.5512 | 0.5529 |
| wall_iou | 0.3115 | 0.3116 |
| door_recall | 0.2667 | 0.2754 |
| room_match | 0.0278 | 0.0347 |
| gross_area_err | 0.607 | 0.2906 |
| correction_min | 31.1 | 30.6 |

Skor relatif 0.480 → 0.491.

## Perubahan

| Task | Perubahan | Hasil |
|---|---|---|
| 1 | Metrik menit koreksi (operasi editor × waktu standar) | baseline Gatsu 22.1 menit, augmentasi 31.1 menit |
| 2 | Kontur bangunan: celah ≤ 3 m ditutup per massa bangunan | Gatsu `gross_area_err` 0.038 → 0.003, ruang 42 → 50; augmentasi 0.607 → 0.291. Versi closing seluruh gabungan (0.200) menyatukan annex Capacitor Room ke bangunan utama, jadi diganti versi per massa. |
| 3 | Pemilihan kandidat medoid | **di-revert**: Gatsu tidak berubah, augmentasi tidak membaik, `gross_area_err` +0.011 |

## Langkah berikutnya untuk mencapai ≤ 15 menit

Upaya koreksi Gatsu yang tersisa (21.8 menit) didominasi tiga operasi:
1. Menghapus dinding palsu satu per satu.
2. Menyetel tipe ruang satu per satu, terutama ruang pita `outdoor`.
3. Menambah dinding yang terlewat.

Fitur editor yang langsung memangkas waktu:
- **hapus massal** dinding berkeyakinan rendah atau dinding dalam satu seleksi;
- **set tipe massal** untuk beberapa ruang sekaligus;
- **gambar dinding berantai** dengan snap ke dinding yang ada.

Contoh: hapus massal memangkas sekitar 4.5 menit dari 5.7 menit, dan set tipe massal sekitar 3.0 menit. Dengan itu target ≤ 15 menit realistis. Model waktu ini sebaiknya dikalibrasi dengan satu sesi koreksi nyata di editor.
