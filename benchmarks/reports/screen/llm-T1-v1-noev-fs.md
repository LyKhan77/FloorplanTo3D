# Benchmark Strata — llm-T1-v1-noev-fs

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 1, evidence False, few-shot True.

| Metrik | Nilai |
|---|---|
| n | 96 |
| accuracy | 0.740 |
| baseline_accuracy | 0.531 |
| delete_precision | 0.780 |
| f1_annotation | 0.719 |
| invalid_rate | 0.000 |
| passes | False |

**latency:** `{"calls": 96, "mean_ms": 5581, "p90_ms": 5714}`

Matriks kebingungan (label → jawaban):

```json
{
 "wall": {
  "annotation": 9,
  "wall": 39
 },
 "annotation": {
  "wall": 16,
  "annotation": 32
 }
}
```
