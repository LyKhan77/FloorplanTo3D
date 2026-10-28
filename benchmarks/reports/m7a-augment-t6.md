# Set augmentasi — m7a-augment-t6

**Skor ketahanan: 0.425** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.4970, wall_precision 0.5498, wall_iou 0.3120, door_recall 0.2667, room_match 0.0222, gross_area_err 0.6548

**Lolos: 0/29 varian (0%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: door_recall (23), door_width_ok (23), door_dir_ok (21), gross_area_err (18), wall_pos_p95_mm (14), wall_recall (12). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.690 | 0.757 | 0.438 | 0.474 | 0.021 | 0.535 | [0, 0] | 41.6 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.941 | [0, 0] | 88.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, stair_dir_ok, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.039 | 0.042 | 0.026 | 0.053 | 0.000 | 0.761 | [0, 0] | 100.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.735 | 0.748 | 0.422 | 0.421 | 0.083 | 0.565 | [0, 0] | 93.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.709 | 0.732 | 0.470 | 0.368 | 0.000 | 0.042 | [0, 0] | 115.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match, stair_dir_ok |
| a05 | jpeg_q=40 | tidak | 0.769 | 0.727 | 0.469 | 0.368 | 0.083 | 0.026 | [0, 0] | 137.1 | metrics below 0.9 x a00: door_recall, door_width_ok, stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.752 | 0.798 | 0.510 | 0.368 | 0.062 | 0.655 | [0, 0] | 122.1 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.763 | 0.779 | 0.507 | 0.474 | 0.062 | 0.589 | [0, 0] | 142.5 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.691 | 0.747 | 0.448 | 0.421 | 0.021 | 0.736 | [0, 0] | 124.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err |
| a09 | rotate_deg=-1.0 | tidak | 0.600 | 0.739 | 0.401 | 0.263 | 0.000 | 0.779 | [0, 0] | 112.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_pos_median_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.669 | 0.771 | 0.379 | 0.474 | 0.042 | 0.708 | [-50, 100] | 121.1 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, wall_iou, wall_pos_median_mm |
| a11 | rotate_deg=0.5 | tidak | 0.546 | 0.690 | 0.323 | 0.368 | 0.042 | 0.763 | [0, -100] | 122.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.544 | 0.698 | 0.367 | 0.211 | 0.000 | 0.803 | [0, -50] | 113.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_p95_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.574 | 0.733 | 0.419 | 0.316 | 0.021 | 0.839 | [0, 0] | 122.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_recall |
| a14 | margin_px=-40 | tidak | 0.762 | 0.770 | 0.469 | 0.474 | 0.021 | 0.486 | [0, 0] | 103.1 | metrics below 0.9 x a00: stair_dir_ok, wall_pos_p95_mm |
| a15 | margin_px=80 | tidak | 0.769 | 0.783 | 0.480 | 0.368 | 0.042 | 0.037 | [0, 0] | 123.7 | metrics below 0.9 x a00: door_recall, door_width_ok |
| a16 | blur=0.6 | tidak | 0.736 | 0.773 | 0.471 | 0.421 | 0.021 | 0.018 | [0, 0] | 117.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok |
| a17 | blur=1.0 | tidak | 0.657 | 0.566 | 0.274 | 0.158 | 0.000 | 0.379 | [0, 0] | 147.1 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision |
| a18 | noise=4.0 | tidak | 0.730 | 0.751 | 0.491 | 0.368 | 0.062 | 0.700 | [0, 0] | 112.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.616 | 0.700 | 0.413 | 0.316 | 0.021 | 0.760 | [0, 0] | 121.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_recall |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | [0, 0] | 45.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.821 | [0, 0] | 102.0 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — |  | 18.3 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.055 | 0.070 | 0.052 | 0.000 | 0.000 | 0.753 | [0, 0] | 87.0 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.534 | 0.685 | 0.293 | 0.158 | 0.021 | 0.834 | [0, -150] | 95.1 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — |  | 5.6 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.553 | 0.724 | 0.358 | 0.368 | 0.021 | 0.729 | [0, -50] | 94.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.680 | 0.777 | 0.395 | 0.421 | 0.021 | 0.696 | [0, 0] | 87.2 | metrics below 0.9 x a00: door_recall, gross_area_err, stair_dir_ok, wall_pos_median_mm, wall_pos_p95_mm |
| a28 | kombinasi | tidak | — | — | — | — | — | — |  | 9.9 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.767 | 0.435 | 0.368 | 0.000 | 0.692 | [0, 0] | 48.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match |
