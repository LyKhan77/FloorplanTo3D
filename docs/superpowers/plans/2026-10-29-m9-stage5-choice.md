# M9 — Pemilihan Kandidat Tahap 5 yang Stabil Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tahap 5 tidak lagi memilih kandidat yang membaca kedua muka dinding sebagai dua dinding. Pada denah garis ganda, kandidat S1 menghasilkan panjang dinding melebihi taksiran garis dinding gambar.

**Architecture:** `core/extraction/select.choose` mengeluarkan kandidat dengan `coverage` > `MAX_COVERAGE` (1.05). Kandidat seperti itu membaca lebih banyak dinding daripada yang tergambar, kecuali bila semua kandidat lolos begitu. Aturan relatif 60 % dan tie-break tetap.

**Bukti** (`benchmarks/.cache/*/runs/r/stages/05_validate/scores.json`, 2026-10-29):
- **Varian yang salah pilih:** s01, s04, s14 (sintetis) dan a17 (augmentasi) memilih S1 dengan `coverage` 1.12–1.37.
- **Kandidat yang benar:** S2 di varian yang sama ada di 0.73–0.91.
- **Pembanding:** di Gatsu dan varian lain, S1 hanya 0.1–0.4, dan S2 tidak pernah > 0.96.

**Tech Stack:** Python 3.12, pytest.

**Spec:**
- `PRD/04-extraction.md` Tahap 5 (pemilihan kandidat);
- `benchmarks/reports/m7b-final.md` mode gagal 3;
- `benchmarks/reports/m7d-final.md` (ketidakstabilan kandidat).

## Global Constraints

- **Lingkungan kerja:**
  - semua perintah shell diawali `rtk`;
  - jangan membaca `server-info.txt` atau `.env`.
- **Gerbang M7a** (gagal → revert dan ledger ruling):
  - metrik target: rata-rata `wall_iou` dan `gross_area_err` sintetis membaik;
  - tidak ada regresi di luar toleransi (0.005 rasio, 5 mm, 0.5 menit) pada Gatsu, rata-rata augmentasi, dan rata-rata sintetis.
- Commit dalam bahasa Inggris dan diakhiri `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Semua kandidat ber-`coverage` > 1.05:** `choose` tetap memilih (tidak `None`). Test di Task 1.
2. **Kandidat over-reading yang punya skor tertinggi** tidak memengaruhi batas 60 %, yang kini dihitung dari kandidat yang tersisa. Test di Task 1.

---

### Task 1: Aturan `MAX_COVERAGE` di `choose`

**Files:**
- Modify: `core/extraction/select.py`
- Test: `tests/extraction/test_select.py` (atau berkas test `choose` yang ada)

- [ ] **Step 1: Test yang gagal:**
  - `test_over_reading_candidate_is_left_out`: S1 skor 0.89 dengan coverage 1.26, S2 skor 0.878 dengan coverage 0.91 → S2 terpilih;
  - `test_all_over_reading_still_chooses`;
  - `test_coverage_cut_uses_the_remaining_candidates`.
- [ ] **Step 2–4: RED, implementasi, GREEN.** Snapshot Gatsu yang berubah: periksa, lalu perbarui dengan ledger ruling.
- [ ] **Step 5: Gerbang.**
  - `failure_modes --fresh --out benchmarks/reports/m9-gatsu`;
  - `run_augment_bench --fresh --out benchmarks/reports/m9-augment`;
  - `run_synth_bench --out benchmarks/reports/m9-synth`.

  Bandingkan dengan `m8-gatsu`, `m7a3-augment`, dan `m7d-synth-leaks`.
- [ ] **Step 6: Commit** `fix(extraction): stage 5 leaves out candidates that read both wall faces`.

### Task 2: Laporan dan status

- [ ] `benchmarks/reports/m9-final.md` (tabel gerbang), ROADMAP "Status M9", suite penuh.
- [ ] **Commit** `docs: M9 status`.
