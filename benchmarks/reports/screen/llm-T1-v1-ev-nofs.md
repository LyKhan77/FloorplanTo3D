# Benchmark Strata — llm-T1-v1-ev-nofs

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 1, evidence True, few-shot False.

| Metrik | Nilai |
|---|---|
| n | 96 |
| accuracy | 0.646 |
| baseline_accuracy | 0.531 |
| delete_precision | 0.889 |
| f1_annotation | 0.485 |
| invalid_rate | 0.000 |
| passes | False |

**latency:** `{"calls": 96, "mean_ms": 4699, "p90_ms": 4767}`

Matriks kebingungan (label → jawaban):

```json
{
 "wall": {
  "annotation": 2,
  "wall": 46
 },
 "annotation": {
  "wall": 32,
  "annotation": 16
 }
}
```
