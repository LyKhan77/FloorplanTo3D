# Benchmark ekstraksi: m5c-spec.json

| Metrik | Nilai | Ambang | Lulus |
|---|---|---|---|
| scale_err | 0.0013 | 0.0050 | ✓ |
| wall_recall | 0.7662 | 0.9500 | ✗ |
| wall_precision | 0.7943 | 0.9500 | ✗ |
| wall_pos_median_mm | 18.0000 | 50 | ✓ |
| wall_pos_p95_mm | 113.0000 | 150 | ✓ |
| door_recall | 0.4211 | 0.9000 | ✗ |
| door_width_ok | 0.3158 | 0.9000 | ✗ |
| door_dir_ok | 0.1667 | 0.8000 | ✗ |
| room_match | 0.0208 | 0.9000 | ✗ |
| rooms_pred | 23 | — | — |
| rooms_gt | 48 | — | — |
| area_err_max | 0.7457 | — | — |
| wall_iou | 0.5105 | 0.8500 | ✗ |
| stair_risers_ok | 0.3333 | 1.0000 | ✗ |
| stair_dir_ok | 1.0000 | 1.0000 | ✓ |
| stair_pos_ok | 0.0000 | 1.0000 | ✗ |
| gross_area_err | 0.0301 | 0.0100 | ✗ |
