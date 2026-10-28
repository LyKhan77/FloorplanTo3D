# Atribusi galat Gatsu — m7a-t4

| Metrik | Nilai |
|---|---|
| wall_recall | 0.779 |
| wall_precision | 0.794 |
| wall_iou | 0.510 |
| door_recall | 0.421 |
| room_match | 0.021 |
| rooms_pred | 23 |
| rooms_gt | 48 |
| gross_area_err | 0.030 |

**Dinding GT terlewat:** 19 (103.4 m)

| Mode | Jumlah | Panjang (m) |
|---|---|---|
| single | 9 | 44.3 |
| double | 5 | 24.9 |
| faint | 4 | 26.7 |
| erased | 1 | 7.5 |

**Dinding palsu:** 69 (84.3 m)

| Wilayah | Jumlah | Panjang (m) |
|---|---|---|
| other | 57 | 69.4 |
| free_end | 7 | 5.7 |
| hatch | 4 | 5.0 |
| text | 1 | 4.2 |

**Ruang:** dalam 9/23 cocok, outdoor 3/25 cocok; ruang prediksi yang menelan ≥ 2 ruang GT: 6 (R1+R6+R7, R10+R19+R21, R16+R2+R22+R25+R29+R3+R33+R43+R47+R48+R5, R32+R34, R37+R41, R38+R42+R46).

Rincian dinding terlewat (id, jenis, tebal, panjang, mode, tinta binary/clean [kiri, tengah, kanan]):

- W9 exterior 150 mm, 1460 mm: **single** [1.0, 0.15, 0.15] / [1.0, 0.15, 0.15]
- W10 exterior 150 mm, 1460 mm: **double** [0.93, 0.2, 1.0] / [0.93, 0.2, 1.0]
- W11 exterior 150 mm, 13020 mm: **single** [0.12, 0.05, 1.0] / [0.12, 0.05, 1.0]
- W13 exterior 150 mm, 12830 mm: **single** [0.03, 0.03, 1.0] / [0.03, 0.03, 1.0]
- W14 exterior 150 mm, 13880 mm: **faint** [0.1, 0.1, 0.57] / [0.1, 0.1, 0.57]
- W15 exterior 150 mm, 4610 mm: **single** [1.0, 0.03, 0.28] / [1.0, 0.03, 0.28]
- W16 exterior 150 mm, 4780 mm: **single** [1.0, 0.05, 0.28] / [1.0, 0.05, 0.28]
- W24 exterior 150 mm, 360 mm: **single** [0.0, 1.0, 0.23] / [0.0, 1.0, 0.23]
- W30 low 130 mm, 6650 mm: **faint** [0.28, 0.07, 0.28] / [0.25, 0.07, 0.25]
- W38 exterior 150 mm, 770 mm: **single** [1.0, 0.17, 0.2] / [1.0, 0.17, 0.2]
- W39 exterior 150 mm, 770 mm: **single** [0.17, 1.0, 0.35] / [0.17, 1.0, 0.35]
- W41 interior 100 mm, 5690 mm: **single** [0.95, 0.95, 0.23] / [0.95, 0.95, 0.23]
- W47 interior 210 mm, 1590 mm: **double** [1.0, 0.0, 1.0] / [1.0, 0.0, 1.0]
- W51 interior 100 mm, 10210 mm: **double** [0.85, 1.0, 0.85] / [0.85, 1.0, 0.85]
- W53 interior 150 mm, 7010 mm: **double** [1.0, 0.07, 0.97] / [1.0, 0.07, 0.97]
- W59 partition 130 mm, 4180 mm: **faint** [0.38, 0.3, 0.38] / [0.38, 0.3, 0.38]
- W64 interior 100 mm, 1950 mm: **faint** [0.12, 0.55, 0.55] / [0.12, 0.55, 0.55]
- W67 interior 120 mm, 7540 mm: **erased** [0.9, 0.1, 0.8] / [0.55, 0.1, 0.35]
- W72 interior 130 mm, 4630 mm: **double** [0.88, 0.23, 0.88] / [0.62, 0.12, 0.62]
