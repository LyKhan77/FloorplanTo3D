# Benchmark Strata — llm-T1-v1-ev-fs

Model `Qwen3.8-Flash-Next`, prompt `v1`, votes 3, evidence True, few-shot True.

| Metrik | Nilai |
|---|---|
| n | 96 |
| accuracy | 0.833 |
| baseline_accuracy | 0.583 |
| delete_precision | 0.848 |
| f1_annotation | 0.830 |
| invalid_rate | 0.000 |
| passes | False |

**latency:** `{"calls": 207, "mean_ms": 13158, "p90_ms": 25272}`

Matriks kebingungan (label → jawaban):

```json
{
 "wall": {
  "wall": 41,
  "annotation": 7
 },
 "annotation": {
  "annotation": 39,
  "wall": 9
 }
}
```
