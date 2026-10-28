# Benchmark Strata — llm-T1-v1-ev-nofs

Model `Qwen3.8-Flash-Next`, prompt `v1`, votes 3, evidence True, few-shot False.

| Metrik | Nilai |
|---|---|
| n | 96 |
| accuracy | 0.552 |
| baseline_accuracy | 0.583 |
| delete_precision | 0.857 |
| f1_annotation | 0.218 |
| invalid_rate | 0.000 |
| passes | False |

**latency:** `{"calls": 201, "mean_ms": 3873, "p90_ms": 4101}`

Matriks kebingungan (label → jawaban):

```json
{
 "wall": {
  "wall": 47,
  "annotation": 1
 },
 "annotation": {
  "wall": 42,
  "annotation": 6
 }
}
```
