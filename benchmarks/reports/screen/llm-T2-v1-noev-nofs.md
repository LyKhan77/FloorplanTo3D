# Benchmark Strata — llm-T2-v1-noev-nofs

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 1, evidence False, few-shot False.

| Metrik | Nilai |
|---|---|
| n | 24 |
| accuracy | 0.375 |
| baseline_accuracy | 0.125 |
| invalid_rate | 0.000 |
| passes | False |

**per_field:** `{"is_door": 0.5416666666666666, "door_type": 1.0, "hinge": 0.8, "swing": 0.2}`

**baseline_per_field:** `{"is_door": 0.20833333333333334, "door_type": 1.0, "hinge": 0.8, "swing": 0.8}`

**latency:** `{"calls": 24, "mean_ms": 4708, "p90_ms": 4767}`

Matriks kebingungan (label → jawaban):

```json
{
 "hinge": {
  "end": {
   "end": 2,
   "start": 1
  },
  "start": {
   "start": 1
  },
  "both": {
   "both": 1
  }
 },
 "swing": {
  "right": {
   "left": 3,
   "right": 1
  },
  "left": {
   "right": 1
  }
 }
}
```
