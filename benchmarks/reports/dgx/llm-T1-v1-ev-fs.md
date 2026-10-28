# Benchmark Strata — llm-T1-v1-ev-fs

Model `Qwen3.8-Flash-Next`, prompt `v1`, votes 3, evidence True, few-shot True.

| Metrik | Nilai |
|---|---|
| n | 96 |
| accuracy | 0.771 |
| baseline_accuracy | 0.583 |
| delete_precision | 0.814 |
| f1_annotation | 0.769 |
| invalid_rate | 0.010 |
| passes | False |

**latency:** `{"calls": 206, "mean_ms": 13764, "p90_ms": 25447}`

Matriks kebingungan (label → jawaban):

```json
{
 "wall": {
  "wall": 39,
  "annotation": 8,
  "invalid": 1
 },
 "annotation": {
  "wall": 13,
  "annotation": 35
 }
}
```
