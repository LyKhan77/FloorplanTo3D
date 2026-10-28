# Benchmark Strata — llm-T2-v1-ev-fs

Model `Qwen3.8-Flash-Next`, prompt `v1`, votes 3, evidence True, few-shot True.

| Metrik | Nilai |
|---|---|
| n | 24 |
| accuracy | 0.500 |
| baseline_accuracy | 0.125 |
| invalid_rate | 0.000 |
| passes | False |

**per_field:** `{"is_door": 0.625, "door_type": 1.0, "hinge": 0.6, "swing": 0.8}`

**baseline_per_field:** `{"is_door": 0.20833333333333334, "door_type": 1.0, "hinge": 0.8, "swing": 0.8}`

**latency:** `{"calls": 51, "mean_ms": 24667, "p90_ms": 27608}`

Matriks kebingungan (label → jawaban):

```json
{
 "hinge": {
  "end": {
   "end": 1,
   "start": 2
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
   "right": 3,
   "left": 1
  },
  "left": {
   "left": 1
  }
 }
}
```
