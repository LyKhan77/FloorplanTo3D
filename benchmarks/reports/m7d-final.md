# M7d — Ruang bocor: hasil

## Atribusi kebocoran (Task 1, diperbaiki setelah review akhir)

`failure_modes.classify_leaks` mencatat setiap pasangan ruang GT yang menyatu dalam satu ruang prediksi.

**Pasangan yang dihitung:** hanya yang bertetangga, yaitu berbagi tepi lebih dari 300 mm. Ruang yang hanya bersentuhan di sudut tidak dihitung.

**Cara menentukan penyebab:**
- Pemisahnya adalah semua garis tengah dinding GT di sepanjang tepi bersama itu.
- Kebocorannya adalah bentang terpanjang pemisah itu yang tidak tertutup dinding prediksi (toleransi 150 mm, sama dengan `wall_recall`).
- Penyebabnya:
  - `door_gap`: ada pusat pintu GT di bentang itu;
  - `wall_missing`: bentangnya ≥ 300 mm tanpa pintu;
  - `other`: tidak ada celah di garis tengah pemisah (bocor lewat sambungan atau jalur lain).

| Set | `door_gap` | `wall_missing` | `other` | Sumber |
|---|---|---|---|---|
| Gatsu (11 pasangan) | 6 | 4 | 1 | `m7d-baseline.json` |
| Sintetis `s01…s20` (122 pasangan) | 32 | 43 | 47 | `m7d-synth-leaks.json` |

Di Gatsu, `wall_missing` hanya berasal dari 5 dinding: W13 dan W14 (dinding luar, ruang `outdoor`), W68, W69, dan W72. Sementara `door_gap` tersebar di banyak pintu, terutama deretan WC, pantry, dan ruang-ruang di sisi timur.

**Koreksi:** versi pertama Task 1 menghitung kontak sudut sebagai kebocoran, dan menilai pemisah dari satu dinding saja. Hasilnya `wall_missing` 9 / `door_gap` 2, dan kesimpulan "bukan lewat celah pintu". Kesimpulan itu salah. Dengan atribusi yang benar, celah pintu adalah penyebab terbesar di Gatsu (6/11) dan sepertiga dari kasus sintetis yang terdiagnosis.

## Dinding sintetis penutup kebocoran, PRD/04 §6b (Task 2): gagal gerbang, di-revert

**Cara kerja:**
- Ruang yang memuat label bertipe berbeda dipotong oleh perpanjangan sebuah ujung dinding yang menggantung.
- Dinding baru diterima hanya bila skor validator naik.

Laporan: `m7d-t2`, `m7d-augment`, `m7d-synth` (dihasilkan sebelum atribusi diperbaiki, sehingga angka kebocoran di `m7d-t2` memakai cara hitung lama).

| Set | Metrik | Sebelum | Sesudah |
|---|---|---|---|
| Gatsu | ruang (GT 48) | 41 | 44 |
| Gatsu | `room_match` | 0.083 | 0.083 |
| Gatsu | `wall_precision` | 0.7725 | 0.7694 |
| Gatsu | koreksi / massal (menit) | 22.1 / 14.4 | 21.0 / 13.3 |
| Augmentasi (rata-rata 30) | `room_match` | 0.028 | 0.031 |
| Augmentasi (rata-rata 30) | varian lolos | 2 | 1 |
| Sintetis (rata-rata 21) | `room_match` | 0.040 | 0.042 |
| Sintetis (rata-rata 21) | `door_recall` | 0.362 | 0.354 |
| Sintetis (rata-rata 21) | `door_width_ok` | 0.283 | 0.273 |
| Sintetis (rata-rata 21) | `door_dir_ok` | 0.327 | 0.315 |

**Gerbang gagal, dengan dua alasan:**
1. `room_match` Gatsu tidak naik.
2. Tiga metrik pintu sintetis turun melebihi toleransi 0.005. Penurunannya berasal dari `s08` dan `s13`, tempat tahap 5 memilih kandidat ekstraksi lain setelah skor validator berubah.

Di augmentasi, ketidakstabilan yang sama terlihat jelas: `a00`, `a02`, `a15`, dan `a19` berubah pintu atau ruangnya. Misalnya `a00` `door_recall` 0.316 → 0.474, sedangkan `a02` 0.105 → 0.053.

Ada juga batas bawaan aturan PRD. Menutup kebocoran sering menghasilkan ruang tanpa pintu, karena `door_recall` hanya sekitar 0.4. Penalti V012 untuk ruang tanpa pintu (0.12) lebih besar daripada keuntungan V004 (0.15 × rasio ujung menggantung), sehingga syarat "skor naik" jarang terpenuhi.

Kode percobaan ada di commit `9f4e123` (di-revert oleh `f76a2b9`). Jumlah dinding sintetis yang diterima tidak dicatat di laporan run; di Gatsu ruang bertambah 3 (41 → 44).

## Lainnya

- `failure_modes --fresh` menjalankan ulang cache default. Bila `--cache` menunjuk folder kerja atau induknya, perintah ditolak.
- Cache Gatsu default sudah diregenerasi di HEAD. Metrik kembali sama dengan `m7a3-gatsu`: 41 ruang, `room_match` 0.083.

## Implikasi untuk milestone berikutnya

1. **Pemilihan kandidat tahap 5 harus stabil dulu.** Setiap perubahan yang menggeser skor validator bisa membalik pilihan kandidat dan membuat gerbang berisik. Ini sudah terjadi di M7a-2, M7b (S1/S2), dan M7d (sintetis dan augmentasi).
2. **Celah pintu adalah penyebab kebocoran terbesar di Gatsu.** Dinding prediksi berhenti di kusen dan tidak menyambung melintasi bukaan. Menutup bukaan pintu yang terdeteksi tidak menghasilkan ruang tanpa pintu, karena pintunya ada di pemisah itu. Jadi pendekatan ini tidak terkena masalah V012 seperti §6b, dan layak dicoba setelah no. 1.
3. **Dinding hilang** di Gatsu terbatas pada 5 dinding, dua di antaranya dinding luar. Kasus `other` di sintetis (47) belum terdiagnosis.
