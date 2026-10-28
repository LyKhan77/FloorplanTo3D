# Set augmentasi — m7a2-augment-baseline

**Skor ketahanan: 0.480** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.4994, wall_precision 0.5512, wall_iou 0.3115, door_recall 0.2667, room_match 0.0278, gross_area_err 0.6070, correction_min 31.1000

**Lolos: 1/29 varian (3%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: gross_area_err (21), room_match (18), wall_iou (15), wall_recall (15), wall_pos_p95_mm (14), door_dir_ok (13). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | koreksi (menit) | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.750 | 0.766 | 0.464 | 0.316 | 0.062 | 0.049 | 24.2 | [0, 0] | 57.7 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.941 | 40.4 | [0, 0] | 111.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.063 | 0.069 | 0.033 | 0.105 | 0.000 | 0.439 | 50.1 | [0, 0] | 126.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.735 | 0.748 | 0.422 | 0.421 | 0.083 | 0.565 | 23.7 | [0, 0] | 116.8 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.727 | 0.771 | 0.472 | 0.421 | 0.062 | 0.048 | 24.9 | [0, 0] | 139.8 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a05 | jpeg_q=40 | tidak | 0.769 | 0.725 | 0.468 | 0.368 | 0.083 | 0.026 | 26.2 | [0, 0] | 163.3 | metrics below 0.9 x a00: stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.752 | 0.792 | 0.507 | 0.368 | 0.062 | 0.041 | 24.1 | [0, 0] | 157.5 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.763 | 0.774 | 0.505 | 0.474 | 0.062 | 0.588 | 23.1 | [0, 0] | 174.5 | metrics below 0.9 x a00: gross_area_err, wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.691 | 0.747 | 0.448 | 0.421 | 0.021 | 0.736 | 25.7 | [0, 0] | 153.4 | metrics below 0.9 x a00: gross_area_err, room_match |
| a09 | rotate_deg=-1.0 | tidak | 0.600 | 0.739 | 0.401 | 0.263 | 0.000 | 0.779 | 30.8 | [0, 0] | 135.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.669 | 0.766 | 0.376 | 0.474 | 0.062 | 0.706 | 25.9 | [-50, 100] | 145.4 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_pos_median_mm, wall_recall |
| a11 | rotate_deg=0.5 | tidak | 0.546 | 0.689 | 0.322 | 0.368 | 0.042 | 0.763 | 28.9 | [0, -100] | 146.9 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.516 | 0.693 | 0.332 | 0.263 | 0.000 | 0.786 | 29.0 | [0, 0] | 137.1 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.574 | 0.724 | 0.415 | 0.316 | 0.021 | 0.831 | 30.2 | [0, 0] | 141.7 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_iou, wall_recall |
| a14 | margin_px=-40 | tidak | 0.762 | 0.768 | 0.467 | 0.474 | 0.042 | 0.485 | 23.4 | [0, 0] | 122.6 | metrics below 0.9 x a00: gross_area_err, room_match, stair_dir_ok, wall_pos_p95_mm |
| a15 | margin_px=80 | ya | 0.769 | 0.780 | 0.479 | 0.368 | 0.062 | 0.037 | 23.6 | [0, 0] | 147.4 |  |
| a16 | blur=0.6 | tidak | 0.736 | 0.775 | 0.472 | 0.421 | 0.021 | 0.018 | 23.4 | [0, 0] | 149.5 | metrics below 0.9 x a00: room_match |
| a17 | blur=1.0 | tidak | 0.657 | 0.566 | 0.274 | 0.158 | 0.000 | 0.379 | 35.8 | [0, 0] | 191.3 | metrics below 0.9 x a00: door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a18 | noise=4.0 | tidak | 0.730 | 0.748 | 0.490 | 0.368 | 0.062 | 0.702 | 26.4 | [0, 0] | 144.5 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.616 | 0.700 | 0.413 | 0.316 | 0.021 | 0.760 | 29.9 | [0, 0] | 164.3 | metrics below 0.9 x a00: door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_recall |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | 39.2 | [0, 0] | 59.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.821 | 50.5 | [0, 0] | 134.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 30.3 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.055 | 0.071 | 0.052 | 0.000 | 0.000 | 0.753 | 50.9 | [0, 0] | 117.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.531 | 0.684 | 0.292 | 0.158 | 0.021 | 0.834 | 30.6 | [0, -150] | 123.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 5.7 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.553 | 0.731 | 0.361 | 0.368 | 0.021 | 0.736 | 26.8 | [0, -50] | 128.7 | metrics below 0.9 x a00: gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.680 | 0.777 | 0.395 | 0.421 | 0.021 | 0.696 | 25.1 | [0, 0] | 119.8 | metrics below 0.9 x a00: gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm |
| a28 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 15.7 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.768 | 0.435 | 0.368 | 0.000 | 0.692 | 24.4 | [0, 0] | 67.3 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_recall |
