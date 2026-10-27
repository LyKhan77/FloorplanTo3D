# Benchmark Strata — llm-T1-v1-ev-nofs

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 3, evidence True, few-shot False.

| Metrik | Nilai |
|---|---|
| n | 96 |
| accuracy | 0.656 |
| baseline_accuracy | 0.531 |
| delete_precision | 1.000 |
| f1_annotation | 0.476 |
| invalid_rate | 0.000 |
| passes | True |

**latency:** `{"calls": 202, "mean_ms": 4500, "p90_ms": 4793}`

Matriks kebingungan (label → jawaban):

```json
{
 "wall": {
  "wall": 48
 },
 "annotation": {
  "wall": 33,
  "annotation": 15
 }
}
```
