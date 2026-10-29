# Set augmentasi — m7d-augment

**Skor ketahanan: 0.399** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.5005, wall_precision 0.5503, wall_iou 0.3114, door_recall 0.2737, room_match 0.0312, gross_area_err 0.2922, correction_min 29.8000, correction_min_bulk 19.0000

**Lolos: 0/29 varian (0%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: door_recall (23), door_width_ok (23), door_dir_ok (22), room_match (22), gross_area_err (16), wall_pos_median_mm (13). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | koreksi (menit) | koreksi massal (menit) | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.695 | 0.748 | 0.437 | 0.474 | 0.083 | 0.005 | 22.5 | 14.5 | [0, 0] | 51.8 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.824 | 39.0 | 24.1 | [0, 0] | 60.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, stair_dir_ok, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.039 | 0.041 | 0.026 | 0.053 | 0.000 | 0.006 | 39.0 | 24.1 | [0, 0] | 69.0 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.735 | 0.748 | 0.422 | 0.421 | 0.083 | 0.009 | 23.9 | 15.9 | [0, 0] | 60.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.727 | 0.771 | 0.472 | 0.421 | 0.062 | 0.003 | 24.9 | 16.2 | [0, 0] | 82.1 | metrics below 0.9 x a00: door_dir_ok, door_recall, room_match, stair_dir_ok |
| a05 | jpeg_q=40 | tidak | 0.771 | 0.718 | 0.466 | 0.368 | 0.083 | 0.006 | 25.9 | 16.6 | [0, 0] | 101.3 | metrics below 0.9 x a00: door_recall, door_width_ok, gross_area_err, stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.758 | 0.791 | 0.509 | 0.368 | 0.083 | 0.002 | 23.7 | 15.6 | [0, 0] | 89.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.763 | 0.774 | 0.505 | 0.474 | 0.062 | 0.001 | 23.5 | 15.7 | [0, 0] | 76.6 | metrics below 0.9 x a00: room_match, wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.691 | 0.747 | 0.448 | 0.421 | 0.021 | 0.367 | 25.9 | 17.2 | [0, 0] | 67.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match |
| a09 | rotate_deg=-1.0 | tidak | 0.600 | 0.739 | 0.401 | 0.263 | 0.000 | 0.005 | 30.8 | 19.9 | [0, 0] | 67.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match, wall_pos_median_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.669 | 0.766 | 0.376 | 0.474 | 0.062 | 0.004 | 26.1 | 16.9 | [-50, 100] | 73.6 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, room_match, wall_iou, wall_pos_median_mm |
| a11 | rotate_deg=0.5 | tidak | 0.546 | 0.689 | 0.322 | 0.368 | 0.042 | 0.116 | 28.9 | 18.4 | [0, -100] | 79.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.516 | 0.693 | 0.332 | 0.263 | 0.000 | 0.311 | 29.2 | 18.6 | [0, 0] | 75.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.574 | 0.724 | 0.415 | 0.316 | 0.021 | 0.481 | 30.4 | 19.5 | [0, 0] | 71.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_recall |
| a14 | margin_px=-40 | tidak | 0.766 | 0.785 | 0.476 | 0.474 | 0.042 | 0.004 | 22.4 | 14.8 | [0, 0] | 69.5 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, room_match, wall_pos_p95_mm |
| a15 | margin_px=80 | tidak | 0.769 | 0.774 | 0.477 | 0.368 | 0.083 | 0.003 | 23.7 | 15.6 | [0, 0] | 75.4 | metrics below 0.9 x a00: door_recall, door_width_ok |
| a16 | blur=0.6 | tidak | 0.741 | 0.763 | 0.470 | 0.421 | 0.021 | 0.004 | 22.5 | 14.3 | [0, 0] | 79.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match |
| a17 | blur=1.0 | tidak | 0.666 | 0.569 | 0.277 | 0.158 | 0.000 | 0.190 | 35.4 | 22.1 | [0, 0] | 105.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision |
| a18 | noise=4.0 | tidak | 0.730 | 0.748 | 0.490 | 0.368 | 0.062 | 0.005 | 26.9 | 17.7 | [0, 0] | 73.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.704 | 0.726 | 0.437 | 0.421 | 0.062 | 0.007 | 26.9 | 17.3 | [0, 0] | 84.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | 39.0 | 24.1 | [0, 0] | 17.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.559 | 39.0 | 24.1 | [0, 0] | 64.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — | 39.0 | 24.1 |  | 9.1 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.055 | 0.071 | 0.052 | 0.000 | 0.000 | 0.198 | 39.0 | 24.1 | [0, 0] | 61.5 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.531 | 0.684 | 0.292 | 0.158 | 0.021 | 0.341 | 30.6 | 19.5 | [0, -150] | 65.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — | 39.0 | 24.1 |  | 2.6 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.553 | 0.731 | 0.361 | 0.368 | 0.021 | 0.451 | 26.8 | 17.3 | [0, -50] | 69.0 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.680 | 0.777 | 0.395 | 0.421 | 0.021 | 0.459 | 25.3 | 16.4 | [0, 0] | 65.5 | metrics below 0.9 x a00: door_recall, gross_area_err, room_match, stair_dir_ok, wall_pos_median_mm, wall_pos_p95_mm |
| a28 | kombinasi | tidak | — | — | — | — | — | — | 39.0 | 24.1 |  | 5.2 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.768 | 0.435 | 0.368 | 0.000 | 0.403 | 24.5 | 16.2 | [0, 0] | 48.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match |
