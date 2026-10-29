# M10 — Celah pintu sebagai pemisah ruang: gagal gerbang, di-revert

## Temuan sebelum kode

Hipotesis awal: pintu yang terdeteksi menempel di ujung dinding yang menggantung, dan celah di sebelahnya terbuka. Hipotesis ini tidak terbukti. Di prediksi Gatsu, tidak ada tugas celah yang punya pintu dalam 300 mm dari ujungnya.

Enam kebocoran `door_gap` di Gatsu ternyata punya dua pola:

1. **Dua potongan dinding segaris berhenti sekitar 1.4 m terpisah**, di sekitar pintu yang tidak terdeteksi. Contohnya R29/R33: W64 dan W66 dengan pintu GT D16 di antaranya. `close_ends` hanya menyambung sampai 1.2 m.
2. **Potongan dinding di antara dua pintu hilang**, sehingga bentang yang kosong sekitar 2 m. Contohnya R25/R29 di sekitar D9 dan D10. Pola ini tidak aman ditutup otomatis, dan ditangani dengan garis bantu di kanvas review (M8).

## Percobaan

`close_ends` boleh menyambung ujung yang berhadapan dengan potongan segaris dari dinding yang sama sampai 2.0 m. Ujung tanpa pasangan segaris tetap dibatasi 1.2 m. Kodenya ada di `3b60f35`, di-revert oleh `c585a4d`.

## Gerbang (pembanding: run M9)

| Set | `room_match` | Kebocoran | Lainnya |
|---|---|---|---|
| Gatsu | 0.083 → 0.083 | `door_gap` 6 → 5 | `wall_precision` 0.7725 → 0.7701; ruang 41 → 42; koreksi 22.1 → 22.2 menit |
| Augmentasi (30) | 0.028 → 0.028 | — | `gross_area_err` 0.291 → 0.296 (tepat di batas toleransi) |
| Sintetis (20) | 0.047 → 0.047 | 144 → 135 pasangan | metrik lain sama |

**Gagal:** metrik target (`room_match`) tidak naik di set mana pun.

Menutup satu celah tidak cukup untuk membuat ruang cocok dengan GT (IoU ≥ 0.5), karena ruang yang sama juga bocor lewat dinding yang hilang dan sambungan lain.

## Kesimpulan

Kebocoran ruang di Gatsu adalah gabungan beberapa celah per ruang. Perbaikan satu jenis celah secara otomatis hanya menggeser beberapa pasangan, sehingga jalur yang efektif tetap koreksi manusia di kanvas review (M8).

Langkah otomatis berikutnya yang lebih menjanjikan ada di tahap 3: deteksi potongan dinding pendek dan dinding bergaris tunggal. Perubahan seperti ini sebaiknya diuji dengan denah nyata lain, bukan hanya Gatsu.
