# Set augmentasi — m7a2-augment-t2

**Skor ketahanan: 0.491** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.5024, wall_precision 0.5529, wall_iou 0.3116, door_recall 0.2754, room_match 0.0347, gross_area_err 0.2906, correction_min 30.6000

**Lolos: 1/29 varian (3%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: gross_area_err (18), wall_recall (16), door_dir_ok (15), room_match (15), wall_iou (13), wall_pos_p95_mm (13). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | koreksi (menit) | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.750 | 0.766 | 0.464 | 0.316 | 0.062 | 0.003 | 23.7 | [0, 0] | 49.3 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.830 | 40.4 | [0, 0] | 101.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.063 | 0.069 | 0.033 | 0.105 | 0.000 | 0.001 | 50.1 | [0, 0] | 116.4 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match, wall_iou, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.735 | 0.748 | 0.422 | 0.421 | 0.083 | 0.009 | 23.7 | [0, 0] | 107.0 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.727 | 0.771 | 0.472 | 0.421 | 0.062 | 0.003 | 24.3 | [0, 0] | 128.1 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a05 | jpeg_q=40 | tidak | 0.769 | 0.725 | 0.468 | 0.368 | 0.083 | 0.006 | 25.7 | [0, 0] | 146.1 | metrics below 0.9 x a00: gross_area_err, stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.752 | 0.792 | 0.507 | 0.368 | 0.062 | 0.002 | 23.7 | [0, 0] | 141.9 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.763 | 0.774 | 0.505 | 0.474 | 0.062 | 0.001 | 23.0 | [0, 0] | 157.5 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.655 | 0.731 | 0.442 | 0.368 | 0.042 | 0.002 | 27.4 | [0, 0] | 145.7 | metrics below 0.9 x a00: door_dir_ok, room_match, stair_dir_ok, wall_recall |
| a09 | rotate_deg=-1.0 | tidak | 0.600 | 0.739 | 0.401 | 0.263 | 0.000 | 0.026 | 29.7 | [0, 0] | 122.6 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.669 | 0.766 | 0.376 | 0.474 | 0.062 | 0.004 | 25.6 | [-50, 100] | 128.9 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_pos_median_mm, wall_recall |
| a11 | rotate_deg=0.5 | tidak | 0.546 | 0.689 | 0.322 | 0.368 | 0.062 | 0.423 | 28.3 | [0, -100] | 134.0 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.516 | 0.693 | 0.332 | 0.263 | 0.021 | 0.336 | 27.7 | [0, 0] | 124.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.640 | 0.751 | 0.421 | 0.421 | 0.042 | 0.001 | 26.9 | [0, 0] | 132.4 | metrics below 0.9 x a00: door_dir_ok, room_match, stair_dir_ok, wall_pos_median_mm, wall_recall |
| a14 | margin_px=-40 | tidak | 0.762 | 0.768 | 0.467 | 0.474 | 0.042 | 0.006 | 23.1 | [0, 0] | 109.3 | metrics below 0.9 x a00: gross_area_err, room_match, stair_dir_ok, wall_pos_p95_mm |
| a15 | margin_px=80 | ya | 0.769 | 0.780 | 0.479 | 0.368 | 0.083 | 0.003 | 23.4 | [0, 0] | 131.2 |  |
| a16 | blur=0.6 | tidak | 0.736 | 0.775 | 0.472 | 0.421 | 0.021 | 0.004 | 23.2 | [0, 0] | 128.3 | metrics below 0.9 x a00: room_match |
| a17 | blur=1.0 | tidak | 0.657 | 0.566 | 0.274 | 0.158 | 0.000 | 0.190 | 35.4 | [0, 0] | 162.4 | metrics below 0.9 x a00: door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a18 | noise=4.0 | tidak | 0.730 | 0.748 | 0.490 | 0.368 | 0.062 | 0.005 | 26.8 | [0, 0] | 124.2 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.701 | 0.734 | 0.439 | 0.421 | 0.062 | 0.007 | 26.8 | [0, 0] | 134.6 | metrics below 0.9 x a00: gross_area_err |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | 39.2 | [0, 0] | 48.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.620 | 50.5 | [0, 0] | 113.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 20.8 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.055 | 0.071 | 0.052 | 0.000 | 0.000 | 0.355 | 50.8 | [0, 0] | 98.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.551 | 0.742 | 0.296 | 0.316 | 0.083 | 0.531 | 26.2 | [0, -150] | 105.2 | metrics below 0.9 x a00: gross_area_err, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 4.3 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.597 | 0.710 | 0.372 | 0.421 | 0.042 | 0.471 | 26.1 | [0, 0] | 104.6 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.590 | 0.745 | 0.358 | 0.316 | 0.000 | 0.471 | 26.5 | [0, 0] | 98.0 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a28 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 11.3 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.768 | 0.435 | 0.368 | 0.000 | 0.410 | 23.7 | [0, 0] | 52.0 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_recall |
