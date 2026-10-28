# Set augmentasi — m7a2-augment-t2

**Skor ketahanan: 0.500** (rata-rata porsi metrik yang ≥ 0.9 × a00 per varian; run yang berhenti = 0).

**Rata-rata absolut (gerbang M7a, run berhenti = nilai terburuk):** wall_recall 0.5022, wall_precision 0.5506, wall_iou 0.3132, door_recall 0.2719, room_match 0.0368, gross_area_err 0.2001, correction_min 30.8000

**Lolos: 1/29 varian (3%)** (a00 = gambar asli, pembanding; lolos = setiap metrik ≥ 0.9 × a00, atau ≤ a00 / 0.9 untuk metrik lower-is-better).

Metrik yang paling sering gagal: room_match (16), wall_recall (16), gross_area_err (15), door_dir_ok (14), door_width_ok (13), wall_iou (13). Run yang berhenti: stage 2 needs_attention (2), stage 4 failed (1).

| Varian | faktor | lolos | wall_recall | wall_precision | wall_iou | door_recall | room_match | gross_area_err | koreksi (menit) | geser (mm) | s | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a00 | identitas | ya | 0.750 | 0.766 | 0.464 | 0.316 | 0.062 | 0.005 | 23.7 | [0, 0] | 71.7 |  |
| a01 | scale=0.6 | tidak | 0.025 | 0.111 | 0.021 | 0.000 | 0.000 | 0.824 | 40.4 | [0, 0] | 142.9 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_precision, wall_recall |
| a02 | scale=0.75 | tidak | 0.063 | 0.069 | 0.033 | 0.105 | 0.000 | 0.001 | 50.1 | [0, 0] | 171.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, room_match, wall_iou, wall_pos_p95_mm, wall_precision, wall_recall |
| a03 | scale=1.5 | tidak | 0.735 | 0.748 | 0.422 | 0.421 | 0.083 | 0.009 | 23.7 | [0, 0] | 152.1 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, scale_err, wall_pos_median_mm, wall_pos_p95_mm |
| a04 | scale=2.0 | tidak | 0.727 | 0.771 | 0.472 | 0.421 | 0.062 | 0.003 | 24.3 | [0, 0] | 185.7 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a05 | jpeg_q=40 | tidak | 0.769 | 0.725 | 0.468 | 0.368 | 0.083 | 0.006 | 25.7 | [0, 0] | 214.4 | metrics below 0.9 x a00: gross_area_err, stair_dir_ok, wall_pos_p95_mm |
| a06 | jpeg_q=60 | tidak | 0.752 | 0.792 | 0.507 | 0.368 | 0.062 | 0.003 | 23.7 | [0, 0] | 205.4 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a07 | jpeg_q=80 | tidak | 0.763 | 0.774 | 0.505 | 0.474 | 0.062 | 0.001 | 23.0 | [0, 0] | 226.4 | metrics below 0.9 x a00: wall_pos_p95_mm |
| a08 | rotate_deg=-2.0 | tidak | 0.650 | 0.776 | 0.466 | 0.316 | 0.042 | 0.003 | 25.6 | [0, 0] | 210.0 | metrics below 0.9 x a00: door_width_ok, room_match, wall_recall |
| a09 | rotate_deg=-1.0 | tidak | 0.600 | 0.739 | 0.401 | 0.263 | 0.042 | 0.005 | 29.4 | [0, 0] | 181.2 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a10 | rotate_deg=-0.5 | tidak | 0.669 | 0.766 | 0.376 | 0.474 | 0.062 | 0.004 | 25.6 | [-50, 100] | 186.7 | metrics below 0.9 x a00: wall_iou, wall_pos_median_mm, wall_recall |
| a11 | rotate_deg=0.5 | tidak | 0.546 | 0.689 | 0.322 | 0.368 | 0.083 | 0.025 | 28.3 | [0, -100] | 182.9 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_recall |
| a12 | rotate_deg=1.0 | tidak | 0.516 | 0.693 | 0.332 | 0.263 | 0.021 | 0.298 | 27.8 | [0, 0] | 170.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_recall |
| a13 | rotate_deg=2.0 | tidak | 0.640 | 0.751 | 0.421 | 0.421 | 0.042 | 0.001 | 26.9 | [0, 0] | 183.0 | metrics below 0.9 x a00: door_dir_ok, room_match, stair_dir_ok, wall_pos_median_mm, wall_recall |
| a14 | margin_px=-40 | tidak | 0.762 | 0.768 | 0.467 | 0.474 | 0.042 | 0.000 | 23.1 | [0, 0] | 156.3 | metrics below 0.9 x a00: room_match, stair_dir_ok, wall_pos_p95_mm |
| a15 | margin_px=80 | ya | 0.769 | 0.780 | 0.479 | 0.368 | 0.083 | 0.003 | 23.4 | [0, 0] | 179.9 |  |
| a16 | blur=0.6 | tidak | 0.736 | 0.775 | 0.472 | 0.421 | 0.021 | 0.004 | 23.2 | [0, 0] | 193.2 | metrics below 0.9 x a00: room_match |
| a17 | blur=1.0 | tidak | 0.657 | 0.566 | 0.274 | 0.158 | 0.000 | 0.190 | 35.4 | [0, 0] | 245.2 | metrics below 0.9 x a00: door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a18 | noise=4.0 | tidak | 0.730 | 0.748 | 0.490 | 0.368 | 0.062 | 0.005 | 26.8 | [0, 0] | 185.6 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, wall_pos_p95_mm |
| a19 | noise=8.0 | tidak | 0.701 | 0.734 | 0.439 | 0.421 | 0.062 | 0.007 | 26.8 | [0, 0] | 211.6 | metrics below 0.9 x a00: gross_area_err |
| a20 | kombinasi | tidak | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.999 | 39.2 | [0, 0] | 80.8 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a21 | kombinasi | tidak | 0.036 | 0.055 | 0.027 | 0.000 | 0.000 | 0.240 | 50.5 | [0, 0] | 163.3 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, scale_err, wall_iou, wall_pos_median_mm, wall_precision, wall_recall |
| a22 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 41.9 | stage 4 failed: tidak ada kandidat yang bisa dirakit menjadi spec |
| a23 | kombinasi | tidak | 0.040 | 0.055 | 0.045 | 0.000 | 0.000 | 0.284 | 52.2 | [0, 0] | 148.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_p95_mm, wall_precision, wall_recall |
| a24 | kombinasi | tidak | 0.531 | 0.684 | 0.292 | 0.158 | 0.021 | 0.020 | 30.1 | [0, -150] | 156.7 | metrics below 0.9 x a00: door_dir_ok, door_recall, door_width_ok, gross_area_err, room_match, wall_iou, wall_pos_median_mm, wall_pos_p95_mm, wall_precision, wall_recall |
| a25 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 7.9 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a26 | kombinasi | tidak | 0.597 | 0.710 | 0.372 | 0.421 | 0.042 | 0.025 | 25.8 | [0, 0] | 161.1 | metrics below 0.9 x a00: door_dir_ok, door_width_ok, gross_area_err, room_match, stair_dir_ok, wall_iou, wall_pos_median_mm, wall_recall |
| a27 | kombinasi | tidak | 0.627 | 0.705 | 0.395 | 0.421 | 0.021 | 0.023 | 27.9 | [-50, 0] | 147.7 | metrics below 0.9 x a00: gross_area_err, room_match, stair_dir_ok, wall_iou, wall_recall |
| a28 | kombinasi | tidak | — | — | — | — | — | — | 39.0 |  | 25.5 | stage 2 needs_attention: Skala tidak dapat ditentukan, isi skala manual |
| a29 | kombinasi | tidak | 0.674 | 0.768 | 0.435 | 0.368 | 0.042 | 0.013 | 23.7 | [0, 0] | 90.1 | metrics below 0.9 x a00: door_dir_ok, gross_area_err, room_match, wall_recall |
