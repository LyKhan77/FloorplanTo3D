# M7a-2 — Upaya koreksi, kontur toleran celah, pemilihan kandidat

Kode akhir = Task 1 (metrik) + Task 2 (kontur per massa) + fix pass review akhir; Task 3 (medoid) di-revert. Angka dari `m7a2-baseline` → `m7a2-final-fix` (Gatsu) dan `m7a2-augment-baseline` → `m7a2-augment-final`. Menit koreksi dibatasi oleh menit gambar ulang (39.0 untuk Gatsu).

## Kriteria MVP #2: koreksi ≤ 15 menit

**Gatsu: 22.1 → 22.1 menit, belum terpenuhi.** Sebagai pembanding, menggambar ulang dari nol butuh 39.0 menit. Rata-rata set augmentasi: 29.9 → 30.0 menit.

| Operasi | detik/op | Baseline | Akhir | Menit (akhir) |
|---|---|---|---|---|
| delete_wall | 5 | 68 | 68 | 5.7 |
| add_wall | 20 | 16 | 16 | 5.3 |
| delete_opening | 5 | 9 | 9 | 0.8 |
| add_opening | 15 | 10 | 10 | 2.5 |
| set_door | 10 | 5 | 5 | 0.8 |
| set_room_type | 8 | 31 | 31 | 4.1 |
| rename_room | 8 | 14 | 14 | 1.9 |
| set_stair | 20 | 3 | 3 | 1.0 |

Tiga penyumbang terbesar: delete_wall (5.7 menit), add_wall (5.3 menit), set_room_type (4.1 menit). Model biaya ini **batas bawah**: jendela, dinding yang tertutup 50–99%, dan jenis dinding yang salah tidak dihitung.

## Gatsu

| Metrik | Baseline | Akhir |
|---|---|---|
| wall_recall | 0.772 | 0.772 |
| wall_precision | 0.773 | 0.773 |
| wall_iou | 0.485 | 0.485 |
| door_recall | 0.474 | 0.474 |
| room_match | 0.083 | 0.083 |
| rooms_pred | 42 | 41 |
| rooms_gt | 48 | 48 |
| gross_area_err | 0.038 | 0.003 |

**`gross_area_err` 0.038 → 0.003: NFR ≤ 0.01 terpenuhi.** Jumlah ruang tidak berubah (41), karena ruang hanya dibentuk dari dinding yang digambar.

## Set augmentasi (rata-rata, run berhenti = nilai terburuk)

| Metrik | Baseline | Akhir |
|---|---|---|
| wall_recall | 0.4994 | 0.4994 |
| wall_precision | 0.5512 | 0.5512 |
| wall_iou | 0.3115 | 0.3115 |
| door_recall | 0.2667 | 0.2667 |
| room_match | 0.0278 | 0.0278 |
| gross_area_err | 0.607 | 0.2973 |
| correction_min (dibatasi gambar ulang) | 29.9 | 30.0 |

## Perubahan

| Task | Perubahan | Hasil |
|---|---|---|
| 1 | Metrik menit koreksi (operasi editor × waktu standar, dibatasi menit gambar ulang) | baseline Gatsu 22.1 menit, augmentasi 29.9 menit |
| 2 | Kontur bangunan: celah ≤ 3 m ditutup per massa (massa harus melingkupi ruang). Kontur hanya untuk luas kotor dan slab; ruang tetap dari dinding yang digambar. | Gatsu `gross_area_err` 0.038 → 0.003; augmentasi 0.607 → 0.297 |
| 3 | Pemilihan kandidat medoid | **di-revert**: tidak ada perbaikan |
| fix pass | Tidak ada ruang karangan di ceruk atau teras < 3 m; cincin yang putus di dua tempat tetap tertutup; menit dibatasi gambar ulang | sesudah fix, Task 2 menaikkan jumlah ruang 42 → 50 hanya karena ruang karangan; kenaikan itu dibatalkan |

## Langkah berikutnya untuk mencapai ≤ 15 menit

Kontur dan akurasi ekstraksi tidak lagi menjadi tuas utama: menit koreksi tidak bergerak di M7a-2. Waktu koreksi yang tersisa didominasi tiga operasi berulang:
1. Menghapus 68 dinding palsu satu per satu.
2. Menyetel tipe 31 ruang satu per satu.
3. Menambah 16 dinding.

Fitur editor yang langsung memangkas waktu:
- **hapus massal** dinding dalam satu seleksi atau di bawah ambang keyakinan;
- **set tipe massal** untuk beberapa ruang sekaligus;
- **gambar dinding berantai** dengan snap.

Model waktu sebaiknya dikalibrasi dengan satu sesi koreksi nyata di editor.
