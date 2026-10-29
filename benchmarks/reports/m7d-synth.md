# Denah sintetis — m7d-synth

**Lolos: 0/20 varian (0%); target ≥ 70 % belum tercapai.** Lolos = setiap metrik ringkasan ≥ 80 % target NFR (≤ ambang / 0.8 untuk metrik lower-is-better); run yang berhenti gagal. s00 = GT tanpa perubahan, dirender dengan gaya yang sama (pembanding).

**Rata-rata absolut (s01…, run berhenti = nilai terburuk):** wall_recall 0.8710, wall_precision 0.9270, wall_iou 0.5637, door_recall 0.3536, room_match 0.0421, gross_area_err 0.1263, correction_min 20.2000, correction_min_bulk 14.5000

Metrik yang paling sering gagal: wall_iou (20), door_recall (20), room_match (20), gross_area_err (16). Run yang berhenti: —.

| Varian | perubahan | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | koreksi (menit) | koreksi massal (menit) | geser terbaik (mm, diagnostik) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s00 | bay 6/6/4/6/6/6/6 | tidak | 0.902 | 0.951 | 0.643 | 0.368 | 0.042 | 0.021 | 17.8 | 13.3 | [0, 0] | 55.4 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s01 | bay 6/7/3/7/5/6/7, cermin, -2 partisi, +1 partisi, tangga (-300, 250) | tidak | 0.761 | 0.910 | 0.308 | 0.053 | 0.000 | 0.383 | 30.8 | 21.9 | [0, 0] | 39.2 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s02 | bay 5/5/4/5/6/6/5, cermin, -2 partisi, 1 tipe pintu, tangga (100, -150) | tidak | 0.860 | 0.931 | 0.611 | 0.368 | 0.062 | 0.022 | 20.5 | 14.1 | [0, 0] | 60.1 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s03 | bay 5/5/4/6/5/6/6, cermin, -2 partisi, +2 partisi, tangga (-250, -50) | tidak | 0.842 | 0.892 | 0.552 | 0.316 | 0.000 | 0.341 | 21.6 | 15.2 | [0, 0] | 55.8 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s04 | bay 7/6/5/4/6/5/7, cermin, -2 partisi, +2 partisi, 1 tipe pintu, tangga (50, -100) | tidak | 0.782 | 0.903 | 0.299 | 0.211 | 0.021 | 0.453 | 29.9 | 21.6 | [0, -100] | 44.1 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s05 | bay 7/7/4/5/4/5/5, cermin, tangga (300, -200) | tidak | 0.935 | 0.928 | 0.646 | 0.471 | 0.128 | 0.006 | 17.9 | 13.6 | [0, 0] | 52.6 | below 80% of target: wall_iou, door_recall, room_match |
| s06 | bay 6/5/3/5/7/6/6, cermin, -2 partisi, +2 partisi, 2 tipe pintu, tangga (-250, 100) | tidak | 0.861 | 0.941 | 0.599 | 0.421 | 0.041 | 0.097 | 18.9 | 13.2 | [0, 0] | 59.2 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s07 | bay 6/7/4/5/5/7/4, +2 partisi, tangga (0, 200) | tidak | 0.922 | 0.884 | 0.608 | 0.333 | 0.020 | 0.005 | 19.6 | 14.8 | [0, 0] | 61.6 | below 80% of target: wall_iou, door_recall, room_match |
| s08 | bay 5/7/3/7/7/5/6, cermin, 3 tipe pintu, tangga (0, 300) | tidak | 0.895 | 0.931 | 0.621 | 0.368 | 0.021 | 0.020 | 18.2 | 12.8 | [0, 0] | 36.7 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s09 | bay 7/5/4/7/6/7/7, 4 tipe pintu, tangga (-50, 150) | tidak | 0.904 | 0.956 | 0.618 | 0.421 | 0.042 | 0.018 | 16.2 | 12.0 | [0, 0] | 34.9 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s10 | bay 7/5/4/5/6/5/6, +1 partisi, 3 tipe pintu, tangga (300, -150) | tidak | 0.879 | 0.895 | 0.593 | 0.474 | 0.042 | 0.248 | 16.8 | 11.7 | [0, 0] | 53.8 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s11 | bay 5/6/4/4/5/7/4, cermin, -3 partisi, +2 partisi, 5 tipe pintu, tangga (100, 250) | tidak | 0.921 | 0.912 | 0.613 | 0.389 | 0.041 | 0.004 | 16.2 | 11.6 | [0, 0] | 49.5 | below 80% of target: wall_iou, door_recall, room_match |
| s12 | bay 5/7/3/5/5/5/6, cermin, +2 partisi, 1 tipe pintu, tangga (250, 200) | tidak | 0.861 | 0.930 | 0.602 | 0.316 | 0.040 | 0.021 | 22.0 | 15.8 | [0, 0] | 52.2 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s13 | bay 7/7/4/5/4/7/6, cermin, -3 partisi, +2 partisi, tangga (300, 250) | tidak | 0.907 | 0.958 | 0.621 | 0.353 | 0.085 | 0.002 | 17.8 | 13.3 | [0, 0] | 56.1 | below 80% of target: wall_iou, door_recall, room_match |
| s14 | bay 7/5/4/7/6/6/7, -3 partisi, +1 partisi, 4 tipe pintu, tangga (50, 250) | tidak | 0.791 | 0.902 | 0.318 | 0.105 | 0.044 | 0.443 | 29.4 | 21.1 | [0, -100] | 32.2 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s15 | bay 6/7/3/4/6/5/6, cermin, -2 partisi, +1 partisi, 1 tipe pintu, tangga (300, -200) | tidak | 0.856 | 0.968 | 0.622 | 0.421 | 0.000 | 0.022 | 19.4 | 13.7 | [0, 0] | 50.1 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s16 | bay 6/6/3/5/6/4/7, -3 partisi, tangga (200, -300) | tidak | 0.883 | 0.940 | 0.611 | 0.526 | 0.045 | 0.350 | 18.0 | 12.6 | [0, 0] | 47.0 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s17 | bay 7/5/4/5/5/5/6, +2 partisi, tangga (-300, 50) | tidak | 0.890 | 0.949 | 0.616 | 0.316 | 0.040 | 0.022 | 20.3 | 15.2 | [0, 0] | 49.3 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s18 | bay 5/6/3/4/7/6/6, -3 partisi, +1 partisi, 2 tipe pintu, tangga (-250, 200) | tidak | 0.895 | 0.953 | 0.623 | 0.632 | 0.106 | 0.025 | 15.0 | 10.7 | [0, 0] | 49.9 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s19 | bay 6/7/3/4/5/6/7, -3 partisi, 2 tipe pintu, tangga (250, -200) | tidak | 0.880 | 0.923 | 0.576 | 0.316 | 0.022 | 0.021 | 18.3 | 13.1 | [0, 0] | 44.1 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s20 | bay 5/6/3/6/5/4/5, -3 partisi, +2 partisi, 5 tipe pintu, tangga (-50, 50) | tidak | 0.895 | 0.937 | 0.618 | 0.263 | 0.042 | 0.023 | 17.5 | 12.7 | [0, 0] | 33.6 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
