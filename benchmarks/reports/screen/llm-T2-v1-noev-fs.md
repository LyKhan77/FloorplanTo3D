# Benchmark Strata — llm-T2-v1-noev-fs

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 1, evidence False, few-shot True.

| Metrik | Nilai |
|---|---|
| n | 24 |
| accuracy | 0.875 |
| baseline_accuracy | 0.125 |
| invalid_rate | 0.000 |
| passes | False |

**per_field:** `{"is_door": 0.9583333333333334, "door_type": 1.0, "hinge": 0.6, "swing": 0.8}`

**baseline_per_field:** `{"is_door": 0.20833333333333334, "door_type": 1.0, "hinge": 0.8, "swing": 0.8}`

**latency:** `{"calls": 24, "mean_ms": 5679, "p90_ms": 5780}`

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
   "right": 4
  },
  "left": {
   "right": 1
  }
 }
}
```
