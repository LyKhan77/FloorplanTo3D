# Benchmark Strata — llm-T3-v1-ev-fs

Model `Qwen3.8-Flash-Next`, prompt `v1`, votes 3, evidence True, few-shot True.

| Metrik | Nilai |
|---|---|
| n | 20 |
| accuracy | 0.850 |
| baseline_accuracy | 0.750 |
| lexicon_fail_rate | 0.250 |
| invalid_rate | 0.000 |
| passes | True |

**latency:** `{"calls": 41, "mean_ms": 19803, "p90_ms": 37481}`

Matriks kebingungan (label → jawaban):

```json
{
 "meeting": {
  "meeting": 2
 },
 "storage": {
  "storage": 3
 },
 "mdf": {
  "mdf": 4
 },
 "ahu_room": {
  "ahu_room": 4
 },
 "lobby": {
  "other": 2,
  "corridor": 1
 },
 "capacitor_room": {
  "capacitor_room": 4
 }
}
```
