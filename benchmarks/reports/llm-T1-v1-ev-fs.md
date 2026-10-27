# Benchmark Strata — llm-T1-v1-ev-fs

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 3, evidence True, few-shot True.

| Metrik | Nilai |
|---|---|
| n | 96 |
| accuracy | 0.760 |
| baseline_accuracy | 0.531 |
| delete_precision | 0.755 |
| f1_annotation | 0.763 |
| invalid_rate | 0.000 |
| passes | False |

**latency:** `{"calls": 217, "mean_ms": 4982, "p90_ms": 5635}`

Matriks kebingungan (label → jawaban):

```json
{
 "wall": {
  "annotation": 12,
  "wall": 36
 },
 "annotation": {
  "wall": 11,
  "annotation": 37
 }
}
```
