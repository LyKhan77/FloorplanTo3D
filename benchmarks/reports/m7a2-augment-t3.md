# Set augmentasi — m7a2-augment-t3

**Skor ketahanan: 0.500** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.5014, wall_precision 0.5505, wall_iou 0.3092, door_recall 0.2702, room_match 0.0354, gross_area_err 0.3020, correction_min 30.6000

**Lolos: 1/29 varian (3%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: gross_area_err (19), wall_recall (17), room_match (15), wall_pos_p95_mm (15), wall_iou (14), door_dir_ok (12). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | koreksi (menit) | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.750 | 0.766 | 0.464 | 0.316 | 0.062 | 0.003 | 23.7 | [0, 0] | 49.4 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.830 | 40.4 | [0, 0] | 98.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.039 | 0.041 | 0.026 | 0.053 | 0.000 | 0.019 | 51.3 | [0, 0] | 111.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.735 | 0.748 | 0.422 | 0.421 | 0.083 | 0.009 | 23.7 | [0, 0] | 105.0 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.727 | 0.771 | 0.472 | 0.421 | 0.062 | 0.003 | 24.3 | [0, 0] | 119.5 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a05 | jpeg_q=40 | tidak | 0.769 | 0.725 | 0.468 | 0.368 | 0.083 | 0.006 | 25.7 | [0, 0] | 137.6 | metrics below 0.9 x a00: gross_area_err, stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.752 | 0.792 | 0.507 | 0.368 | 0.062 | 0.002 | 23.7 | [0, 0] | 132.1 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.727 | 0.781 | 0.499 | 0.211 | 0.083 | 0.003 | 24.9 | [0, 0] | 150.1 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.655 | 0.731 | 0.442 | 0.368 | 0.042 | 0.002 | 27.4 | [0, 0] | 135.2 | metrics below 0.9 x a00: door_dir_ok, room_match, stair_dir_ok, wall_recall |
| a09 | rotate_deg=-1.0 | tidak | 0.624 | 0.755 | 0.397 | 0.316 | 0.000 | 0.118 | 27.8 | [0, 50] | 106.4 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_iou, wall_pos_p95_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.641 | 0.728 | 0.321 | 0.421 | 0.000 | 0.471 | 27.9 | [-50, 150] | 111.6 | metrics below 0.9 x a00: gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a11 | rotate_deg=0.5 | tidak | 0.546 | 0.689 | 0.322 | 0.368 | 0.062 | 0.423 | 28.3 | [0, -100] | 113.7 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.554 | 0.721 | 0.354 | 0.368 | 0.042 | 0.436 | 25.4 | [0, 0] | 110.7 | metrics below 0.9 x a00: gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.640 | 0.751 | 0.421 | 0.421 | 0.042 | 0.001 | 26.9 | [0, 0] | 118.3 | metrics below 0.9 x a00: door_dir_ok, room_match, stair_dir_ok, wall_pos_median_mm, wall_recall |
| a14 | margin_px=-40 | tidak | 0.762 | 0.768 | 0.467 | 0.474 | 0.042 | 0.006 | 23.1 | [0, 0] | 98.1 | metrics below 0.9 x a00: gross_area_err, room_match, stair_dir_ok, wall_pos_p95_mm |
| a15 | margin_px=80 | ya | 0.769 | 0.780 | 0.479 | 0.368 | 0.083 | 0.003 | 23.4 | [0, 0] | 116.3 |  |
| a16 | blur=0.6 | tidak | 0.733 | 0.776 | 0.477 | 0.316 | 0.000 | 0.004 | 23.6 | [0, 0] | 112.5 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, room_match |
| a17 | blur=1.0 | tidak | 0.657 | 0.566 | 0.274 | 0.158 | 0.000 | 0.190 | 35.4 | [0, 0] | 156.8 | metrics below 0.9 x a00: door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a18 | noise=4.0 | tidak | 0.759 | 0.760 | 0.482 | 0.474 | 0.062 | 0.002 | 24.6 | [0, 0] | 121.3 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.657 | 0.742 | 0.432 | 0.421 | 0.000 | 0.194 | 25.1 | [0, 0] | 134.3 | metrics below 0.9 x a00: gross_area_err, room_match, wall_recall |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | 39.2 | [0, 0] | 42.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.620 | 50.5 | [0, 0] | 107.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 18.6 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.051 | 0.064 | 0.042 | 0.000 | 0.021 | 0.510 | 52.0 | [0, 0] | 99.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.551 | 0.742 | 0.296 | 0.316 | 0.083 | 0.531 | 26.2 | [0, -150] | 106.0 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 4.1 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.580 | 0.707 | 0.356 | 0.368 | 0.062 | 0.277 | 24.2 | [0, 0] | 107.3 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.627 | 0.705 | 0.395 | 0.421 | 0.000 | 0.369 | 27.9 | [-50, 0] | 101.8 | metrics below 0.9 x a00: gross_area_err, room_match, stair_dir_ok, wall_iou, wall_recall |
| a28 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 12.9 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.736 | 0.412 | 0.368 | 0.083 | 0.027 | 24.3 | [0, 0] | 54.6 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_recall |
