# Benchmark Strata — llm-T1-v1-noev-nofs

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 1, evidence False, few-shot False.

| Metrik | Nilai |
|---|---|
| n | 96 |
| accuracy | 0.583 |
| baseline_accuracy | 0.531 |
| delete_precision | 0.786 |
| f1_annotation | 0.355 |
| invalid_rate | 0.000 |
| passes | False |

**latency:** `{"calls": 96, "mean_ms": 4651, "p90_ms": 4713}`

Matriks kebingungan (label → jawaban):

```json
{
 "wall": {
  "annotation": 3,
  "wall": 45
 },
 "annotation": {
  "wall": 37,
  "annotation": 11
 }
}
```
