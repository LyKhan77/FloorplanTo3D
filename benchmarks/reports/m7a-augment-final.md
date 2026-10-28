# Set augmentasi — m7a-augment-final

**Skor ketahanan: 0.480** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.4994, wall_precision 0.5512, wall_iou 0.3115, door_recall 0.2667, room_match 0.0278, gross_area_err 0.6070

**Lolos: 1/29 varian (3%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: gross_area_err (21), room_match (18), wall_iou (15), wall_recall (15), wall_pos_p95_mm (14), door_dir_ok (13). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.750 | 0.766 | 0.464 | 0.316 | 0.062 | 0.049 | [0, 0] | 42.9 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.941 | [0, 0] | 87.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.063 | 0.069 | 0.033 | 0.105 | 0.000 | 0.439 | [0, 0] | 99.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.735 | 0.748 | 0.422 | 0.421 | 0.083 | 0.565 | [0, 0] | 91.1 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.727 | 0.771 | 0.472 | 0.421 | 0.062 | 0.048 | [0, 0] | 110.9 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a05 | jpeg_q=40 | tidak | 0.769 | 0.725 | 0.468 | 0.368 | 0.083 | 0.026 | [0, 0] | 127.7 | metrics below 0.9 x a00: stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.752 | 0.792 | 0.507 | 0.368 | 0.062 | 0.041 | [0, 0] | 120.5 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.763 | 0.774 | 0.505 | 0.474 | 0.062 | 0.588 | [0, 0] | 136.1 | metrics below 0.9 x a00: gross_area_err, wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.691 | 0.747 | 0.448 | 0.421 | 0.021 | 0.736 | [0, 0] | 120.0 | metrics below 0.9 x a00: gross_area_err, room_match |
| a09 | rotate_deg=-1.0 | tidak | 0.600 | 0.739 | 0.401 | 0.263 | 0.000 | 0.779 | [0, 0] | 102.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.669 | 0.766 | 0.376 | 0.474 | 0.062 | 0.706 | [-50, 100] | 110.7 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_pos_median_mm, wall_recall |
| a11 | rotate_deg=0.5 | tidak | 0.546 | 0.689 | 0.322 | 0.368 | 0.042 | 0.763 | [0, -100] | 112.8 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.516 | 0.693 | 0.332 | 0.263 | 0.000 | 0.786 | [0, 0] | 104.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.574 | 0.724 | 0.415 | 0.316 | 0.021 | 0.831 | [0, 0] | 118.7 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_iou, wall_recall |
| a14 | margin_px=-40 | tidak | 0.762 | 0.768 | 0.467 | 0.474 | 0.042 | 0.485 | [0, 0] | 95.6 | metrics below 0.9 x a00: gross_area_err, room_match, stair_dir_ok, wall_pos_p95_mm |
| a15 | margin_px=80 | ya | 0.769 | 0.780 | 0.479 | 0.368 | 0.062 | 0.037 | [0, 0] | 119.7 |  |
| a16 | blur=0.6 | tidak | 0.736 | 0.775 | 0.472 | 0.421 | 0.021 | 0.018 | [0, 0] | 119.0 | metrics below 0.9 x a00: room_match |
| a17 | blur=1.0 | tidak | 0.657 | 0.566 | 0.274 | 0.158 | 0.000 | 0.379 | [0, 0] | 160.9 | metrics below 0.9 x a00: door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a18 | noise=4.0 | tidak | 0.730 | 0.748 | 0.490 | 0.368 | 0.062 | 0.702 | [0, 0] | 125.4 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.616 | 0.700 | 0.413 | 0.316 | 0.021 | 0.760 | [0, 0] | 138.2 | metrics below 0.9 x a00: door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_recall |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | [0, 0] | 50.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.821 | [0, 0] | 116.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — |  | 22.2 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.055 | 0.071 | 0.052 | 0.000 | 0.000 | 0.753 | [0, 0] | 99.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.531 | 0.684 | 0.292 | 0.158 | 0.021 | 0.834 | [0, -150] | 103.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — |  | 4.9 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.553 | 0.731 | 0.361 | 0.368 | 0.021 | 0.736 | [0, -50] | 103.1 | metrics below 0.9 x a00: gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.680 | 0.777 | 0.395 | 0.421 | 0.021 | 0.696 | [0, 0] | 98.1 | metrics below 0.9 x a00: gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm |
| a28 | kombinasi | tidak | — | — | — | — | — | — |  | 11.4 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.768 | 0.435 | 0.368 | 0.000 | 0.692 | [0, 0] | 49.6 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_recall |
