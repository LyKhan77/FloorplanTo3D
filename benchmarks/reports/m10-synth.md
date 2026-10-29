# Denah sintetis — m10-synth

**Lolos: 0/20 varian (0%); target ≥ 70 % belum tercapai.** Lolos = setiap metrik ringkasan ≥ 80 % target NFR (≤ ambang / 0.8 untuk metrik lower-is-better); run yang berhenti gagal. s00 = GT tanpa perubahan, dirender dengan gaya yang sama (pembanding).

**Rata-rata absolut (s01…, run berhenti = nilai terburuk):** wall_recall 0.8865, wall_precision 0.9336, wall_iou 0.6078, door_recall 0.3855, room_match 0.0467, gross_area_err 0.0644, correction_min 18.3000, correction_min_bulk 13.1000

**Kebocoran ruang (jumlah pasangan, s01…):** door_gap 41, wall_missing 48, other 46

Metrik yang paling sering gagal: wall_iou (20), door_recall (20), room_match (20), gross_area_err (15). Run yang berhenti: —.

| Varian | perubahan | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | koreksi (menit) | koreksi massal (menit) | geser terbaik (mm, diagnostik) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s00 | bay 6/6/4/6/6/6/6 | tidak | 0.902 | 0.951 | 0.643 | 0.368 | 0.042 | 0.021 | 17.8 | 13.3 | [0, 0] | 53.0 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s01 | bay 6/7/3/7/5/6/7, cermin, -2 partisi, +1 partisi, tangga (-300, 250) | tidak | 0.892 | 0.945 | 0.601 | 0.316 | 0.091 | 0.003 | 16.6 | 11.8 | [0, 0] | 34.1 | below 80% of target: wall_iou, door_recall, room_match |
| s02 | bay 5/5/4/5/6/6/5, cermin, -2 partisi, 1 tipe pintu, tangga (100, -150) | tidak | 0.853 | 0.939 | 0.610 | 0.368 | 0.042 | 0.022 | 20.8 | 14.6 | [0, 0] | 54.4 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s03 | bay 5/5/4/6/5/6/6, cermin, -2 partisi, +2 partisi, tangga (-250, -50) | tidak | 0.842 | 0.892 | 0.552 | 0.316 | 0.000 | 0.341 | 21.6 | 15.2 | [0, 0] | 53.5 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s04 | bay 7/6/5/4/6/5/7, cermin, -2 partisi, +2 partisi, 1 tipe pintu, tangga (50, -100) | tidak | 0.873 | 0.969 | 0.603 | 0.263 | 0.043 | 0.022 | 17.7 | 12.6 | [0, 0] | 37.7 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s05 | bay 7/7/4/5/4/5/5, cermin, tangga (300, -200) | tidak | 0.935 | 0.928 | 0.646 | 0.471 | 0.128 | 0.006 | 17.9 | 13.6 | [0, 0] | 49.7 | below 80% of target: wall_iou, door_recall, room_match |
| s06 | bay 6/5/3/5/7/6/6, cermin, -2 partisi, +2 partisi, 2 tipe pintu, tangga (-250, 100) | tidak | 0.861 | 0.941 | 0.599 | 0.421 | 0.041 | 0.097 | 18.9 | 13.2 | [0, 0] | 54.7 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s07 | bay 6/7/4/5/5/7/4, +2 partisi, tangga (0, 200) | tidak | 0.919 | 0.886 | 0.607 | 0.333 | 0.020 | 0.005 | 19.7 | 14.8 | [0, 0] | 53.3 | below 80% of target: wall_iou, door_recall, room_match |
| s08 | bay 5/7/3/7/7/5/6, cermin, 3 tipe pintu, tangga (0, 300) | tidak | 0.887 | 0.913 | 0.607 | 0.474 | 0.043 | 0.019 | 18.5 | 13.0 | [0, 0] | 31.2 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s09 | bay 7/5/4/7/6/7/7, 4 tipe pintu, tangga (-50, 150) | tidak | 0.904 | 0.956 | 0.618 | 0.421 | 0.042 | 0.018 | 16.2 | 12.0 | [0, 0] | 33.2 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s10 | bay 7/5/4/5/6/5/6, +1 partisi, 3 tipe pintu, tangga (300, -150) | tidak | 0.879 | 0.895 | 0.593 | 0.474 | 0.042 | 0.248 | 16.8 | 11.7 | [0, 0] | 45.0 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s11 | bay 5/6/4/4/5/7/4, cermin, -3 partisi, +2 partisi, 5 tipe pintu, tangga (100, 250) | tidak | 0.921 | 0.912 | 0.613 | 0.389 | 0.041 | 0.004 | 16.2 | 11.6 | [0, 0] | 43.0 | below 80% of target: wall_iou, door_recall, room_match |
| s12 | bay 5/7/3/5/5/5/6, cermin, +2 partisi, 1 tipe pintu, tangga (250, 200) | tidak | 0.861 | 0.930 | 0.602 | 0.316 | 0.040 | 0.021 | 22.0 | 15.8 | [0, 0] | 46.7 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s13 | bay 7/7/4/5/4/7/6, cermin, -3 partisi, +2 partisi, tangga (300, 250) | tidak | 0.896 | 0.946 | 0.605 | 0.412 | 0.064 | 0.000 | 17.2 | 12.3 | [0, 0] | 50.7 | below 80% of target: wall_iou, door_recall, room_match |
| s14 | bay 7/5/4/7/6/6/7, -3 partisi, +1 partisi, 4 tipe pintu, tangga (50, 250) | tidak | 0.902 | 0.956 | 0.632 | 0.263 | 0.067 | 0.019 | 17.0 | 12.4 | [0, 0] | 27.5 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s15 | bay 6/7/3/4/6/5/6, cermin, -2 partisi, +1 partisi, 1 tipe pintu, tangga (300, -200) | tidak | 0.858 | 0.969 | 0.624 | 0.421 | 0.000 | 0.022 | 19.4 | 13.7 | [0, 0] | 44.6 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s16 | bay 6/6/3/5/6/4/7, -3 partisi, tangga (200, -300) | tidak | 0.883 | 0.940 | 0.611 | 0.526 | 0.045 | 0.350 | 18.0 | 12.6 | [0, 0] | 43.1 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s17 | bay 7/5/4/5/5/5/6, +2 partisi, tangga (-300, 50) | tidak | 0.892 | 0.949 | 0.618 | 0.316 | 0.040 | 0.022 | 20.3 | 15.2 | [0, 0] | 45.3 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s18 | bay 5/6/3/4/7/6/6, -3 partisi, +1 partisi, 2 tipe pintu, tangga (-250, 200) | tidak | 0.895 | 0.953 | 0.623 | 0.632 | 0.106 | 0.025 | 15.0 | 10.7 | [0, 0] | 44.4 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s19 | bay 6/7/3/4/5/6/7, -3 partisi, 2 tipe pintu, tangga (250, -200) | tidak | 0.882 | 0.923 | 0.577 | 0.316 | 0.000 | 0.021 | 18.1 | 13.0 | [0, 0] | 39.4 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s20 | bay 5/6/3/6/5/4/5, -3 partisi, +2 partisi, 5 tipe pintu, tangga (-50, 50) | tidak | 0.895 | 0.933 | 0.615 | 0.263 | 0.042 | 0.023 | 17.5 | 12.7 | [0, 0] | 29.0 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
