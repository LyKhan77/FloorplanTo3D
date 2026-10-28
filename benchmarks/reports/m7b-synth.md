# Denah sintetis — m7b-synth

**Lolos: 0/20 varian (0%); target ≥ 70 % belum tercapai.** Lolos = setiap metrik ringkasan ≥ 80 % target NFR (≤ ambang / 0.8 untuk metrik lower-is-better); run yang berhenti gagal. s00 = GT tanpa perubahan, dirender dengan gaya yang sama (pembanding).

**Rata-rata absolut (s01…, run berhenti = nilai terburuk):** wall_recall 0.8677, wall_precision 0.8989, wall_iou 0.5598, door_recall 0.3614, room_match 0.0475, gross_area_err 0.0998, correction_min 20.6000, correction_min_bulk 14.8000

Metrik yang paling sering gagal: wall_iou (20), door_recall (20), room_match (20), gross_area_err (17), wall_recall (3), wall_precision (1). Run yang berhenti: —.

| Varian | perubahan | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | koreksi (menit) | koreksi massal (menit) | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s00 | bay 6/6/4/6/6/6/6 | tidak | 0.902 | 0.951 | 0.643 | 0.368 | 0.042 | 0.021 | 17.8 | 13.3 | [0, 0] | 58.5 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s01 | bay 6/7/3/7/5/6/7, cermin, -2 partisi, +1 partisi, tangga (-300, 250) | tidak | 0.700 | 0.780 | 0.286 | 0.105 | 0.000 | 0.246 | 32.5 | 22.4 | [0, -100] | 45.1 | below 80% of target: wall_recall, wall_iou, door_recall, room_match, gross_area_err |
| s02 | bay 5/5/4/5/6/6/5, cermin, -2 partisi, 1 tipe pintu, tangga (100, -150) | tidak | 0.901 | 0.907 | 0.598 | 0.421 | 0.000 | 0.021 | 20.5 | 15.1 | [0, 0] | 59.9 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s03 | bay 5/5/4/6/5/6/6, cermin, -2 partisi, +2 partisi, tangga (-250, -50) | tidak | 0.859 | 0.882 | 0.562 | 0.316 | 0.040 | 0.301 | 21.2 | 15.4 | [0, 0] | 59.9 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s04 | bay 7/6/5/4/6/5/7, cermin, -2 partisi, +2 partisi, 1 tipe pintu, tangga (50, -100) | tidak | 0.702 | 0.762 | 0.274 | 0.105 | 0.000 | 0.397 | 33.4 | 23.2 | [0, -100] | 45.0 | below 80% of target: wall_recall, wall_iou, door_recall, room_match, gross_area_err |
| s05 | bay 7/7/4/5/4/5/5, cermin, tangga (300, -200) | tidak | 0.926 | 0.928 | 0.644 | 0.412 | 0.085 | 0.006 | 17.0 | 12.7 | [0, 0] | 52.8 | below 80% of target: wall_iou, door_recall, room_match |
| s06 | bay 6/5/3/5/7/6/6, cermin, -2 partisi, +2 partisi, 2 tipe pintu, tangga (-250, 100) | tidak | 0.878 | 0.929 | 0.591 | 0.579 | 0.041 | 0.018 | 16.5 | 11.3 | [0, 0] | 59.6 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s07 | bay 6/7/4/5/5/7/4, +2 partisi, tangga (0, 200) | tidak | 0.919 | 0.889 | 0.608 | 0.333 | 0.020 | 0.005 | 19.6 | 14.8 | [0, 0] | 62.3 | below 80% of target: wall_iou, door_recall, room_match |
| s08 | bay 5/7/3/7/7/5/6, cermin, 3 tipe pintu, tangga (0, 300) | tidak | 0.876 | 0.954 | 0.637 | 0.474 | 0.106 | 0.022 | 17.1 | 12.2 | [0, 0] | 34.7 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s09 | bay 7/5/4/7/6/7/7, 4 tipe pintu, tangga (-50, 150) | tidak | 0.909 | 0.956 | 0.627 | 0.316 | 0.083 | 0.018 | 16.0 | 12.1 | [0, 0] | 38.3 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s10 | bay 7/5/4/5/6/5/6, +1 partisi, 3 tipe pintu, tangga (300, -150) | tidak | 0.893 | 0.907 | 0.594 | 0.368 | 0.000 | 0.019 | 20.4 | 15.1 | [0, 0] | 55.5 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s11 | bay 5/6/4/4/5/7/4, cermin, -3 partisi, +2 partisi, 5 tipe pintu, tangga (100, 250) | tidak | 0.912 | 0.886 | 0.600 | 0.333 | 0.041 | 0.004 | 19.9 | 14.2 | [0, 0] | 52.6 | below 80% of target: wall_iou, door_recall, room_match |
| s12 | bay 5/7/3/5/5/5/6, cermin, +2 partisi, 1 tipe pintu, tangga (250, 200) | tidak | 0.889 | 0.897 | 0.580 | 0.263 | 0.040 | 0.021 | 21.1 | 15.4 | [0, 0] | 56.2 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s13 | bay 7/7/4/5/4/7/6, cermin, -3 partisi, +2 partisi, tangga (300, 250) | tidak | 0.909 | 0.951 | 0.615 | 0.412 | 0.043 | 0.365 | 18.0 | 13.7 | [0, 0] | 59.9 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s14 | bay 7/5/4/7/6/6/7, -3 partisi, +1 partisi, 4 tipe pintu, tangga (50, 250) | tidak | 0.671 | 0.715 | 0.269 | 0.158 | 0.044 | 0.430 | 32.3 | 22.4 | [0, -100] | 31.4 | below 80% of target: wall_recall, wall_precision, wall_iou, door_recall, room_match, gross_area_err |
| s15 | bay 6/7/3/4/6/5/6, cermin, -2 partisi, +1 partisi, 1 tipe pintu, tangga (300, -200) | tidak | 0.915 | 0.942 | 0.626 | 0.579 | 0.087 | 0.020 | 14.7 | 10.2 | [0, 0] | 51.2 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s16 | bay 6/6/3/5/6/4/7, -3 partisi, tangga (200, -300) | tidak | 0.892 | 0.950 | 0.620 | 0.579 | 0.068 | 0.020 | 15.2 | 10.9 | [0, 0] | 48.1 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s17 | bay 7/5/4/5/5/5/6, +2 partisi, tangga (-300, 50) | tidak | 0.913 | 0.942 | 0.636 | 0.263 | 0.060 | 0.021 | 19.8 | 14.5 | [0, 0] | 51.8 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s18 | bay 5/6/3/4/7/6/6, -3 partisi, +1 partisi, 2 tipe pintu, tangga (-250, 200) | tidak | 0.910 | 0.941 | 0.619 | 0.526 | 0.064 | 0.021 | 17.6 | 12.7 | [0, 0] | 52.6 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s19 | bay 6/7/3/4/5/6/7, -3 partisi, 2 tipe pintu, tangga (250, -200) | tidak | 0.893 | 0.926 | 0.592 | 0.368 | 0.044 | 0.019 | 18.3 | 13.3 | [0, 0] | 45.0 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
| s20 | bay 5/6/3/6/5/4/5, -3 partisi, +2 partisi, 5 tipe pintu, tangga (-50, 50) | tidak | 0.887 | 0.935 | 0.615 | 0.316 | 0.083 | 0.024 | 20.1 | 14.7 | [0, 0] | 31.8 | below 80% of target: wall_iou, door_recall, room_match, gross_area_err |
