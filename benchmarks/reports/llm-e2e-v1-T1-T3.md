# Benchmark Strata — llm-e2e-v1-T1-T3

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 3, evidence True, few-shot True.

| Metrik | Nilai |
|---|---|
| passes | False |

**improvement:** `{"scale_err": 0.0, "wall_recall": -0.0476, "wall_precision": 0.0189, "wall_pos_median_mm": 0.0, "wall_pos_p95_mm": 11.0, "door_recall": 0.0, "door_width_ok": 0.0, "door_dir_ok": 0.0, "room_match": 0.0208, "rooms_pred": -2, "rooms_gt": 0, "area_err_max": 0.0293, "wall_iou": -0.004, "stair_risers_ok": 0.0, "stair_dir_ok": 0.0, "stair_pos_ok": 0.0, "gross_area_err": -0.004}`

**base:** `{"seconds": 0.0, "accepted": 0}`

**test:** `{"seconds": 591.6, "accepted": 17, "score_before": 0.8836, "score_after": 0.8913, "timed_out": false, "ops": [{"op": "delete_wall", "id": "W56", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W23", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W58", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W102", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W52", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W3", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W101", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W96", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W122", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W100", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W74", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W72", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W6", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W8", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W38", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W54", "reason": "strata: annotation"}, {"op": "rename_room", "id": "R20", "name": "DUTE"}]}`
