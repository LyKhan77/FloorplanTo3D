# M7d — Ruang bocor: hasil

## Atribusi kebocoran (Task 1)

`failure_modes` kini menghitung pasangan ruang GT bertetangga yang menyatu di satu ruang prediksi, beserta pemisahnya di GT:
- `wall_missing`: dinding pemisah tercakup < 50 %;
- `door_gap`: dinding ada, tapi bukaan pintunya terbuka;
- `other`: lainnya.

| Set | `wall_missing` | `door_gap` | `other` |
|---|---|---|---|
| Gatsu (`m7d-baseline`) | 9 | 2 | 1 |
| Sintetis `s00…s20` (M7b) | 49 | 7 | 78 |

Pada 78 kasus `other` di sintetis, pemisahnya hampir utuh: cakupan ≥ 0.95 pada 45 kasus. Celah yang tersisa ada di ujung atau sambungan dinding (24), di tengah (24), atau tidak terlihat di garis tengah sama sekali (30).

**Koreksi atas M7b:** ruang menyatu terutama karena dinding hilang (Gatsu) dan sambungan dinding yang tidak tertutup (sintetis), bukan "lewat celah pintu". Celah pintu hanya penyebab kecil.

## Dinding sintetis penutup kebocoran, PRD/04 §6b (Task 2): gagal gerbang, di-revert

Ruang yang memuat label bertipe berbeda dipotong oleh perpanjangan sebuah ujung dinding yang menggantung. Dinding baru diterima hanya bila skor validator naik. Laporan: `m7d-t2`, `m7d-augment`, `m7d-synth`.

| Set | Metrik | Sebelum | Sesudah |
|---|---|---|---|
| Gatsu | pasangan bocor | 12 | 7 |
| Gatsu | ruang (GT 48) | 41 | 44 |
| Gatsu | `room_match` | 0.083 | 0.083 |
| Gatsu | `wall_precision` | 0.7725 | 0.7694 |
| Gatsu | koreksi / massal (menit) | 22.1 / 14.4 | 21.0 / 13.3 |
| Augmentasi (rata-rata 30) | `room_match` | 0.028 | 0.031 |
| Augmentasi (rata-rata 30) | lainnya | — | dalam toleransi |
| Sintetis (rata-rata 21) | `room_match` | 0.040 | 0.042 |
| Sintetis (rata-rata 21) | `door_recall` | 0.362 | 0.354 (−0.008) |

**Gerbang gagal, dengan dua alasan:**
1. `room_match` Gatsu tidak naik. Ruang hasil potongan belum cukup mirip ruang GT (IoU < 0.5), karena dinding lain di sekitarnya juga masih hilang.
2. `door_recall` sintetis turun melebihi toleransi. Skor validator yang berubah membuat tahap 5 memilih kandidat ekstraksi lain di `s08` dan `s13`, dan pintunya ikut hilang. Ini ketidakstabilan pemilihan kandidat yang sama dengan M7a-2 dan M7b.

Ada juga batas bawaan aturan PRD. Menutup kebocoran sering menghasilkan ruang tanpa pintu, karena `door_recall` hanya sekitar 0.4. Penalti V012 untuk ruang tanpa pintu (0.12) lebih besar daripada keuntungan menyambung ujung dinding (V004, 0.15 × rasio), sehingga "skor naik" jarang terpenuhi.

Kode percobaan ada di commit `9f4e123` (di-revert oleh `f76a2b9`). Percobaan ini bisa dipakai lagi bila pemilihan kandidat stabil.

## Lainnya

- `failure_modes --fresh` kini juga menjalankan ulang cache default (Task 3).

## Implikasi untuk milestone berikutnya

1. **Pemilihan kandidat tahap 5 harus stabil dulu.** Setiap perubahan yang menggeser skor validator bisa membalik pilihan kandidat dan membuat gerbang berisik. Ini sudah tiga kali terjadi: M7a-2, M7b (S1/S2), dan M7d.
2. **Dinding hilang adalah penyebab kebocoran terbesar di Gatsu**, yaitu dinding interior 5–7 m yang tidak terdeteksi. Masalah ini ada di deteksi dinding (tahap 3), bukan di pembentukan ruang.
3. **Sambungan dinding yang tidak tertutup** adalah penyebab terbesar di sintetis, jadi `close_ends` (reach 1200 mm) layak diperiksa.
