# Set augmentasi — m7a-augment-baseline

**Skor ketahanan: 0.432** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.4912, wall_precision 0.5521, wall_iou 0.3096, door_recall 0.2579, room_match 0.0104, gross_area_err 0.6377

**Lolos: 0/29 varian (0%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: gross_area_err (22), door_dir_ok (21), stair_dir_ok (19), stair_risers_ok (19), door_width_ok (17), room_match (14). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.664 | 0.755 | 0.424 | 0.368 | 0.021 | 0.076 | [0, 0] | 42.6 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.941 | [0, 0] | 88.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, stair_dir_ok, stair_risers_ok, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.063 | 0.071 | 0.033 | 0.053 | 0.000 | 0.038 | [0, 0] | 101.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match, stair_dir_ok, stair_risers_ok, wall_iou, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.716 | 0.738 | 0.413 | 0.316 | 0.021 | 0.560 | [0, 0] | 95.1 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, scale_err, stair_dir_ok, stair_risers_ok, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.702 | 0.726 | 0.466 | 0.368 | 0.000 | 0.043 | [0, 0] | 114.5 | metrics below 0.9 x a00: door_dir_ok, room_match, stair_dir_ok, stair_risers_ok |
| a05 | jpeg_q=40 | tidak | 0.674 | 0.745 | 0.462 | 0.316 | 0.021 | 0.706 | [0, 0] | 126.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_risers_ok |
| a06 | jpeg_q=60 | tidak | 0.738 | 0.784 | 0.499 | 0.368 | 0.021 | 0.687 | [0, 0] | 124.2 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.758 | 0.772 | 0.504 | 0.474 | 0.021 | 0.587 | [0, 0] | 140.5 | metrics below 0.9 x a00: gross_area_err, stair_risers_ok, wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.665 | 0.745 | 0.440 | 0.421 | 0.000 | 0.794 | [0, 0] | 125.2 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, room_match, stair_dir_ok, stair_risers_ok |
| a09 | rotate_deg=-1.0 | tidak | 0.654 | 0.761 | 0.426 | 0.474 | 0.000 | 0.656 | [0, 0] | 98.4 | metrics below 0.9 x a00: gross_area_err, room_match, stair_dir_ok, stair_risers_ok |
| a10 | rotate_deg=-0.5 | tidak | 0.634 | 0.764 | 0.367 | 0.474 | 0.000 | 0.780 | [-50, 100] | 103.7 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm |
| a11 | rotate_deg=0.5 | tidak | 0.529 | 0.708 | 0.302 | 0.211 | 0.021 | 0.816 | [0, -100] | 104.0 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, stair_risers_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.528 | 0.680 | 0.319 | 0.211 | 0.000 | 0.786 | [0, -100] | 95.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_risers_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.563 | 0.724 | 0.409 | 0.316 | 0.000 | 0.841 | [0, 0] | 99.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, gross_area_err, room_match, stair_dir_ok, stair_risers_ok, wall_recall |
| a14 | margin_px=-40 | tidak | 0.784 | 0.807 | 0.505 | 0.368 | 0.021 | 0.523 | [0, 0] | 83.6 | metrics below 0.9 x a00: door_width_ok, gross_area_err, wall_pos_p95_mm |
| a15 | margin_px=80 | tidak | 0.759 | 0.775 | 0.479 | 0.368 | 0.021 | 0.037 | [0, 0] | 99.8 | metrics below 0.9 x a00: stair_risers_ok |
| a16 | blur=0.6 | tidak | 0.727 | 0.766 | 0.467 | 0.421 | 0.021 | 0.018 | [0, 0] | 99.2 | metrics below 0.9 x a00: door_dir_ok, stair_dir_ok |
| a17 | blur=1.0 | tidak | 0.657 | 0.566 | 0.274 | 0.158 | 0.000 | 0.379 | [0, 0] | 124.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, stair_risers_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision |
| a18 | noise=4.0 | tidak | 0.706 | 0.747 | 0.483 | 0.368 | 0.021 | 0.740 | [0, 0] | 96.2 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, stair_dir_ok, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.612 | 0.698 | 0.413 | 0.316 | 0.021 | 0.763 | [0, 0] | 105.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, stair_risers_ok |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | [0, 0] | 37.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, stair_risers_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.040 | 0.062 | 0.030 | 0.000 | 0.000 | 0.822 | [0, 0] | 86.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, stair_dir_ok, stair_risers_ok, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — |  | 15.7 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.055 | 0.071 | 0.052 | 0.000 | 0.000 | 0.755 | [0, 0] | 80.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.532 | 0.724 | 0.294 | 0.211 | 0.042 | 0.775 | [0, -150] | 79.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, stair_dir_ok, stair_risers_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — |  | 2.9 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.592 | 0.715 | 0.374 | 0.368 | 0.000 | 0.742 | [0, 0] | 84.4 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, room_match, stair_dir_ok, stair_risers_ok, wall_iou, wall_recall |
| a27 | kombinasi | tidak | 0.690 | 0.778 | 0.397 | 0.421 | 0.042 | 0.580 | [0, 0] | 77.8 | metrics below 0.9 x a00: gross_area_err, stair_dir_ok, stair_risers_ok, wall_pos_median_mm |
| a28 | kombinasi | tidak | — | — | — | — | — | — |  | 10.2 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.667 | 0.773 | 0.434 | 0.368 | 0.000 | 0.685 | [0, 0] | 45.1 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, room_match, stair_dir_ok |
