# Set augmentasi — m10-augment

**Skor ketahanan: 0.511** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.5009, wall_precision 0.5564, wall_iou 0.3159, door_recall 0.2754, room_match 0.0278, gross_area_err 0.2960, correction_min 29.7000, correction_min_bulk 19.0000

**Lolos: 1/29 varian (3%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: room_match (18), gross_area_err (17), wall_recall (15), wall_iou (14), door_dir_ok (13), wall_pos_p95_mm (13). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | koreksi (menit) | koreksi massal (menit) | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.750 | 0.764 | 0.464 | 0.316 | 0.062 | 0.005 | 24.4 | 16.4 | [0, 0] | 39.9 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.824 | 39.0 | 24.1 | [0, 0] | 50.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.063 | 0.068 | 0.033 | 0.105 | 0.000 | 0.001 | 39.0 | 24.1 | [0, 0] | 60.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match, wall_iou, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.743 | 0.748 | 0.422 | 0.421 | 0.083 | 0.009 | 23.9 | 15.9 | [0, 0] | 53.7 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.727 | 0.768 | 0.470 | 0.421 | 0.062 | 0.003 | 24.9 | 16.2 | [0, 0] | 65.8 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a05 | jpeg_q=40 | tidak | 0.769 | 0.723 | 0.467 | 0.368 | 0.083 | 0.006 | 26.2 | 17.2 | [0, 0] | 76.0 | metrics below 0.9 x a00: gross_area_err, stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.752 | 0.789 | 0.506 | 0.368 | 0.062 | 0.002 | 24.1 | 16.0 | [0, 0] | 63.9 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.763 | 0.769 | 0.503 | 0.474 | 0.062 | 0.001 | 23.6 | 15.8 | [0, 0] | 68.3 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.691 | 0.738 | 0.444 | 0.421 | 0.021 | 0.315 | 25.9 | 17.2 | [0, 0] | 61.7 | metrics below 0.9 x a00: gross_area_err, room_match |
| a09 | rotate_deg=-1.0 | tidak | 0.602 | 0.737 | 0.400 | 0.263 | 0.000 | 0.005 | 30.6 | 19.9 | [0, 0] | 60.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.674 | 0.768 | 0.378 | 0.474 | 0.062 | 0.004 | 26.1 | 16.9 | [-50, 100] | 67.1 | metrics below 0.9 x a00: wall_iou, wall_pos_median_mm, wall_recall |
| a11 | rotate_deg=0.5 | tidak | 0.552 | 0.691 | 0.324 | 0.368 | 0.042 | 0.116 | 28.9 | 18.4 | [0, -100] | 65.9 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.516 | 0.690 | 0.331 | 0.263 | 0.000 | 0.300 | 29.2 | 18.6 | [0, 0] | 63.0 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.574 | 0.717 | 0.413 | 0.316 | 0.021 | 0.428 | 30.4 | 19.5 | [0, 0] | 64.4 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_iou, wall_recall |
| a14 | margin_px=-40 | tidak | 0.767 | 0.764 | 0.468 | 0.474 | 0.042 | 0.000 | 23.3 | 14.8 | [0, 0] | 56.7 | metrics below 0.9 x a00: room_match, stair_dir_ok, wall_pos_p95_mm |
| a15 | margin_px=80 | ya | 0.769 | 0.775 | 0.476 | 0.368 | 0.062 | 0.003 | 23.6 | 15.6 | [0, 0] | 64.1 |  |
| a16 | blur=0.6 | tidak | 0.736 | 0.773 | 0.471 | 0.421 | 0.021 | 0.004 | 23.5 | 15.5 | [0, 0] | 64.1 | metrics below 0.9 x a00: room_match |
| a17 | blur=1.0 | tidak | 0.662 | 0.782 | 0.420 | 0.421 | 0.000 | 0.325 | 25.5 | 16.7 | [0, 0] | 79.2 | metrics below 0.9 x a00: gross_area_err, room_match, wall_recall |
| a18 | noise=4.0 | tidak | 0.735 | 0.750 | 0.492 | 0.368 | 0.062 | 0.005 | 26.9 | 17.7 | [0, 0] | 63.9 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.616 | 0.695 | 0.412 | 0.316 | 0.021 | 0.027 | 30.1 | 18.6 | [0, 0] | 67.7 | metrics below 0.9 x a00: door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_recall |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | 39.0 | 24.1 | [0, 0] | 15.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.559 | 39.0 | 24.1 | [0, 0] | 54.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — | 39.0 | 24.1 |  | 6.4 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.055 | 0.070 | 0.052 | 0.000 | 0.000 | 0.198 | 39.0 | 24.1 | [0, 0] | 52.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.532 | 0.682 | 0.293 | 0.158 | 0.021 | 0.434 | 30.6 | 19.5 | [0, -150] | 60.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — | 39.0 | 24.1 |  | 1.5 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.557 | 0.727 | 0.360 | 0.368 | 0.021 | 0.445 | 26.8 | 17.3 | [0, -50] | 62.7 | metrics below 0.9 x a00: gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.686 | 0.773 | 0.396 | 0.421 | 0.021 | 0.458 | 25.3 | 16.4 | [0, 0] | 56.0 | metrics below 0.9 x a00: gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm |
| a28 | kombinasi | tidak | — | — | — | — | — | — | 39.0 | 24.1 |  | 4.5 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.765 | 0.433 | 0.368 | 0.000 | 0.403 | 24.5 | 16.2 | [0, 0] | 41.1 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_recall |
