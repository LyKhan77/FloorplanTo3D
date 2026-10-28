# Set augmentasi — m7a-augment-t5

**Skor ketahanan: 0.497** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.4979, wall_precision 0.5485, wall_iou 0.3110, door_recall 0.2632, room_match 0.0229, gross_area_err 0.6173

**Lolos: 2/29 varian (7%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: gross_area_err (21), wall_iou (15), wall_recall (15), door_dir_ok (14), wall_pos_median_mm (13), wall_pos_p95_mm (13). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.750 | 0.763 | 0.463 | 0.316 | 0.021 | 0.049 | [0, 0] | 43.8 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.941 | [0, 0] | 90.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.039 | 0.042 | 0.026 | 0.053 | 0.000 | 0.760 | [0, 0] | 100.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.735 | 0.748 | 0.422 | 0.421 | 0.083 | 0.565 | [0, 0] | 94.6 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.709 | 0.726 | 0.468 | 0.368 | 0.000 | 0.042 | [0, 0] | 114.2 | metrics below 0.9 x a00: door_dir_ok, room_match, stair_dir_ok |
| a05 | jpeg_q=40 | tidak | 0.769 | 0.725 | 0.468 | 0.368 | 0.083 | 0.026 | [0, 0] | 131.4 | metrics below 0.9 x a00: stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.752 | 0.792 | 0.507 | 0.368 | 0.062 | 0.041 | [0, 0] | 126.6 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.763 | 0.774 | 0.506 | 0.474 | 0.062 | 0.588 | [0, 0] | 139.7 | metrics below 0.9 x a00: gross_area_err, wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.691 | 0.747 | 0.448 | 0.421 | 0.021 | 0.736 | [0, 0] | 125.5 | metrics below 0.9 x a00: gross_area_err |
| a09 | rotate_deg=-1.0 | tidak | 0.600 | 0.739 | 0.401 | 0.263 | 0.000 | 0.779 | [0, 0] | 104.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.669 | 0.766 | 0.376 | 0.474 | 0.042 | 0.706 | [-50, 100] | 113.4 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_pos_median_mm, wall_recall |
| a11 | rotate_deg=0.5 | tidak | 0.546 | 0.689 | 0.322 | 0.368 | 0.042 | 0.763 | [0, -100] | 115.5 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.511 | 0.691 | 0.330 | 0.263 | 0.021 | 0.787 | [0, 0] | 107.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.574 | 0.729 | 0.417 | 0.316 | 0.021 | 0.838 | [0, 0] | 114.0 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, wall_iou, wall_recall |
| a14 | margin_px=-40 | tidak | 0.762 | 0.768 | 0.467 | 0.474 | 0.021 | 0.485 | [0, 0] | 95.2 | metrics below 0.9 x a00: gross_area_err, stair_dir_ok, wall_pos_p95_mm |
| a15 | margin_px=80 | ya | 0.769 | 0.780 | 0.479 | 0.368 | 0.042 | 0.037 | [0, 0] | 116.9 |  |
| a16 | blur=0.6 | ya | 0.736 | 0.773 | 0.471 | 0.421 | 0.021 | 0.018 | [0, 0] | 111.2 |  |
| a17 | blur=1.0 | tidak | 0.657 | 0.566 | 0.274 | 0.158 | 0.000 | 0.379 | [0, 0] | 141.3 | metrics below 0.9 x a00: door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a18 | noise=4.0 | tidak | 0.730 | 0.745 | 0.489 | 0.368 | 0.062 | 0.699 | [0, 0] | 109.3 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.616 | 0.700 | 0.413 | 0.316 | 0.021 | 0.760 | [0, 0] | 117.8 | metrics below 0.9 x a00: door_width_ok, gross_area_err, stair_dir_ok, wall_iou, wall_recall |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | [0, 0] | 43.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.821 | [0, 0] | 99.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — |  | 17.4 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.055 | 0.070 | 0.052 | 0.000 | 0.000 | 0.752 | [0, 0] | 85.1 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.534 | 0.685 | 0.293 | 0.158 | 0.021 | 0.834 | [0, -150] | 92.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — |  | 4.6 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.553 | 0.724 | 0.358 | 0.368 | 0.021 | 0.729 | [0, -50] | 91.7 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.680 | 0.777 | 0.395 | 0.421 | 0.021 | 0.696 | [0, 0] | 86.0 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_pos_median_mm, wall_pos_p95_mm |
| a28 | kombinasi | tidak | — | — | — | — | — | — |  | 9.8 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.767 | 0.435 | 0.368 | 0.000 | 0.692 | [0, 0] | 45.9 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_recall |
