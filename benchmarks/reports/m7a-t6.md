# Atribusi galat Gatsu — m7a-t6

| Metrik | Nilai |
|---|---|
| wall_recall | 0.772 |
| wall_precision | 0.775 |
| wall_iou | 0.487 |
| door_recall | 0.474 |
| room_match | 0.042 |
| rooms_pred | 40 |
| rooms_gt | 48 |
| gross_area_err | 0.594 |

**Dinding GT terlewat:** 16 (94.4 m)

| Mode | Jumlah | Panjang (m) |
|---|---|---|
| single | 6 | 41.7 |
| double | 5 | 18.5 |
| faint | 4 | 26.7 |
| erased | 1 | 7.5 |

**Dinding palsu:** 67 (98.1 m)

| Wilayah | Jumlah | Panjang (m) |
|---|---|---|
| other | 59 | 87.0 |
| free_end | 6 | 5.4 |
| hatch | 1 | 0.3 |
| text | 1 | 5.2 |

**Ruang:** dalam 5/23 cocok, outdoor 10/25 cocok; ruang prediksi yang menelan ≥ 2 ruang GT: 5 (R14+R27, R32+R34, R38+R42+R46, R37+R41, R43+R47).

Rincian dinding terlewat (id, jenis, tebal, panjang, mode, tinta binary/clean [kiri, tengah, kanan]):

- W11 exterior 150 mm, 13020 mm: **single** [0.12, 0.05, 1.0] / [0.12, 0.05, 1.0]
- W13 exterior 150 mm, 12830 mm: **single** [0.03, 0.03, 1.0] / [0.03, 0.03, 1.0]
- W14 exterior 150 mm, 13880 mm: **faint** [0.1, 0.1, 0.57] / [0.1, 0.1, 0.57]
- W15 exterior 150 mm, 4610 mm: **single** [1.0, 0.03, 0.28] / [1.0, 0.03, 0.28]
- W16 exterior 150 mm, 4780 mm: **single** [1.0, 0.05, 0.28] / [1.0, 0.05, 0.28]
- W22 exterior 150 mm, 360 mm: **double** [1.0, 0.23, 1.0] / [1.0, 0.23, 1.0]
- W30 low 130 mm, 6650 mm: **faint** [0.28, 0.07, 0.28] / [0.25, 0.07, 0.25]
- W38 exterior 150 mm, 770 mm: **single** [1.0, 0.17, 0.2] / [1.0, 0.17, 0.2]
- W41 interior 100 mm, 5690 mm: **single** [0.95, 0.95, 0.23] / [0.95, 0.95, 0.23]
- W47 interior 210 mm, 1590 mm: **double** [1.0, 0.0, 1.0] / [1.0, 0.0, 1.0]
- W53 interior 150 mm, 7010 mm: **double** [1.0, 0.07, 0.97] / [1.0, 0.07, 0.97]
- W59 partition 130 mm, 4180 mm: **faint** [0.38, 0.3, 0.38] / [0.38, 0.3, 0.38]
- W62 interior 210 mm, 4950 mm: **double** [0.78, 0.1, 0.82] / [0.78, 0.1, 0.82]
- W64 interior 100 mm, 1950 mm: **faint** [0.12, 0.55, 0.55] / [0.12, 0.55, 0.55]
- W67 interior 120 mm, 7540 mm: **erased** [0.9, 0.1, 0.8] / [0.55, 0.1, 0.35]
- W72 interior 130 mm, 4630 mm: **double** [0.88, 0.23, 0.88] / [0.62, 0.12, 0.62]
