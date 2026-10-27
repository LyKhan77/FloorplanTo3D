# Benchmark Strata — llm-T4-v1-T1-T3

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 3, evidence True, few-shot True.

| Metrik | Nilai |
|---|---|
| passes | False |

**improvement:** `{"scale_err": 0.0, "wall_recall": 0.008, "wall_precision": 0.0007, "wall_pos_median_mm": -1.0, "wall_pos_p95_mm": 0.0, "door_recall": 0.0, "door_width_ok": 0.0, "door_dir_ok": 0.0, "room_match": 0.0, "rooms_pred": 2, "rooms_gt": 0, "area_err_max": 0.103, "wall_iou": 0.0013, "stair_risers_ok": 0.0, "stair_dir_ok": 0.0, "stair_pos_ok": 0.0, "gross_area_err": 0.5699}`

**base:** `{"seconds": 588.8, "accepted": 14, "score_before": 0.8836, "score_after": 0.8825, "timed_out": false, "ops": [{"op": "delete_wall", "id": "W82", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W58", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W102", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W52", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W3", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W101", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W96", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W122", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W100", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W72", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W6", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W8", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W38", "reason": "strata: annotation"}, {"op": "rename_room", "id": "R20", "name": "DUTE"}]}`

**test:** `{"seconds": 612.1, "accepted": 12, "score_before": 0.8836, "score_after": 0.8862, "timed_out": true, "ops": [{"op": "delete_wall", "id": "W58", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W102", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W52", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W3", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W101", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W122", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W100", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W72", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W6", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W8", "reason": "strata: annotation"}, {"op": "delete_wall", "id": "W38", "reason": "strata: annotation"}, {"op": "rename_room", "id": "R20", "name": "DUTE"}]}`
