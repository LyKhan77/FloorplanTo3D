# M9 — Pemilihan kandidat tahap 5: hasil

## Aturan

`core/extraction/select.choose` mengeluarkan kandidat dengan `coverage` > 1.05, yaitu yang membaca dinding lebih panjang daripada taksiran garis dinding di gambar. Pada denah garis ganda, kandidat S1 membaca kedua muka dinding sebagai dua dinding, sehingga `coverage`-nya 1.12–1.38. Kandidat S2 yang benar tidak pernah di atas 0.96. Bila semua kandidat ber-`coverage` > 1.05, aturan tidak berlaku.

## Gerbang M7a (lolos)

| Set | `wall_recall` | `wall_precision` | `wall_iou` | `door_recall` | `room_match` | `gross_area_err` | koreksi massal (menit) |
|---|---|---|---|---|---|---|---|
| Gatsu (`m8-gatsu` → `m9-gatsu`) | 0.772 → 0.772 | 0.773 → 0.773 | 0.485 → 0.485 | 0.474 → 0.474 | 0.083 → 0.083 | 0.003 → 0.003 | 14.4 → 14.4 |
| Augmentasi, rata-rata 30 (`m7a3-augment` → `m9-augment`) | 0.4994 → 0.4989 | 0.551 → 0.557 | 0.312 → 0.316 | 0.267 → 0.270 | 0.028 → 0.028 | 0.297 → 0.291 | 19.2 → 19.0 |
| Sintetis, rata-rata s01–s20 (`m7d-synth-leaks` → `m9-synth`) | 0.870 → 0.886 | 0.926 → 0.934 | 0.562 → 0.608 | 0.362 → 0.386 | 0.040 → 0.047 | 0.126 → 0.064 | 14.6 → 13.2 |

Varian yang berubah hanya yang memilih S1 sebelumnya:
- s01: `wall_iou` 0.31 → 0.60;
- s04: `wall_iou` 0.30 → 0.60;
- s14: `wall_iou` 0.32 → 0.63;
- a17: `wall_iou` 0.27 → 0.41.

Penurunan `wall_recall` augmentasi (−0.0005) masih dalam toleransi 0.005.

## Sisa

Kontur bangunan yang pecah (M7b mode gagal 4) dan pintu yang terlewat tetap ada. Di sintetis, `gross_area_err` turun ke 0.064, tapi masih di atas batas lolos 0.0125.
