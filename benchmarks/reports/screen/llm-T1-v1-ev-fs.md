# Benchmark Strata — llm-T1-v1-ev-fs

Model `qwen3.8-flash-next-iq2_xs`, prompt `v1`, votes 1, evidence True, few-shot True.

| Metrik | Nilai |
|---|---|
| n | 96 |
| accuracy | 0.750 |
| baseline_accuracy | 0.531 |
| delete_precision | 0.722 |
| f1_annotation | 0.765 |
| invalid_rate | 0.000 |
| passes | False |

**latency:** `{"calls": 96, "mean_ms": 5643, "p90_ms": 5807}`

Matriks kebingungan (label → jawaban):

```json
{
 "wall": {
  "annotation": 15,
  "wall": 33
 },
 "annotation": {
  "wall": 9,
  "annotation": 39
 }
}
```
