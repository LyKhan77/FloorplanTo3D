# Set augmentasi — m7a-augment-t4

**Skor ketahanan: 0.408** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.4981, wall_precision 0.5483, wall_iou 0.3104, door_recall 0.2719, room_match 0.0132, gross_area_err 0.5946

**Lolos: 0/29 varian (0%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: door_width_ok (23), door_recall (22), gross_area_err (21), door_dir_ok (20), wall_pos_median_mm (13), wall_pos_p95_mm (13). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.690 | 0.751 | 0.435 | 0.474 | 0.000 | 0.050 | [0, 0] | 41.7 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.941 | [0, 0] | 81.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, scale_err, stair_dir_ok, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.039 | 0.042 | 0.026 | 0.053 | 0.000 | 0.760 | [0, 0] | 87.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.735 | 0.748 | 0.422 | 0.421 | 0.021 | 0.565 | [0, 0] | 87.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.709 | 0.726 | 0.468 | 0.368 | 0.000 | 0.042 | [0, 0] | 102.0 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, stair_dir_ok |
| a05 | jpeg_q=40 | tidak | 0.769 | 0.725 | 0.468 | 0.368 | 0.042 | 0.026 | [0, 0] | 119.1 | metrics below 0.9 x a00: door_recall, door_width_ok, stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.752 | 0.792 | 0.507 | 0.368 | 0.021 | 0.041 | [0, 0] | 113.1 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.763 | 0.774 | 0.506 | 0.474 | 0.021 | 0.588 | [0, 0] | 126.2 | metrics below 0.9 x a00: gross_area_err, wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.691 | 0.747 | 0.448 | 0.421 | 0.021 | 0.736 | [0, 0] | 112.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err |
| a09 | rotate_deg=-1.0 | tidak | 0.600 | 0.739 | 0.401 | 0.263 | 0.000 | 0.779 | [0, 0] | 96.0 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_pos_median_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.669 | 0.766 | 0.376 | 0.474 | 0.000 | 0.706 | [-50, 100] | 108.0 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, wall_iou, wall_pos_median_mm |
| a11 | rotate_deg=0.5 | tidak | 0.546 | 0.689 | 0.322 | 0.368 | 0.042 | 0.763 | [0, -100] | 108.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.511 | 0.691 | 0.330 | 0.263 | 0.021 | 0.787 | [0, 0] | 98.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.574 | 0.729 | 0.417 | 0.316 | 0.021 | 0.838 | [0, 0] | 110.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_recall |
| a14 | margin_px=-40 | tidak | 0.764 | 0.784 | 0.475 | 0.474 | 0.021 | 0.056 | [0, 0] | 90.3 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, wall_pos_p95_mm |
| a15 | margin_px=80 | tidak | 0.769 | 0.780 | 0.479 | 0.368 | 0.021 | 0.037 | [0, 0] | 109.7 | metrics below 0.9 x a00: door_recall, door_width_ok |
| a16 | blur=0.6 | tidak | 0.736 | 0.773 | 0.471 | 0.421 | 0.021 | 0.018 | [0, 0] | 106.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok |
| a17 | blur=1.0 | tidak | 0.657 | 0.566 | 0.274 | 0.158 | 0.000 | 0.379 | [0, 0] | 150.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision |
| a18 | noise=4.0 | tidak | 0.767 | 0.754 | 0.493 | 0.474 | 0.021 | 0.439 | [0, 0] | 123.2 | metrics below 0.9 x a00: gross_area_err, stair_dir_ok, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.616 | 0.700 | 0.413 | 0.316 | 0.021 | 0.760 | [0, 0] | 128.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_recall |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | [0, 0] | 41.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.821 | [0, 0] | 102.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — |  | 16.3 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.055 | 0.070 | 0.052 | 0.000 | 0.000 | 0.752 | [0, 0] | 92.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.534 | 0.685 | 0.293 | 0.158 | 0.021 | 0.834 | [0, -150] | 101.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — |  | 4.8 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.581 | 0.707 | 0.356 | 0.368 | 0.042 | 0.734 | [0, 0] | 103.1 | metrics below 0.9 x a00: door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.680 | 0.777 | 0.395 | 0.421 | 0.021 | 0.696 | [0, 0] | 95.8 | metrics below 0.9 x a00: door_recall, gross_area_err, stair_dir_ok, wall_pos_median_mm, wall_pos_p95_mm |
| a28 | kombinasi | tidak | — | — | — | — | — | — |  | 13.7 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.767 | 0.435 | 0.368 | 0.000 | 0.692 | [0, 0] | 43.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err |
