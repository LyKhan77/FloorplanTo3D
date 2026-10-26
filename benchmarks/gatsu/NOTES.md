# Ground Truth MSC Gatsu L1 — Catatan Interpretasi

Sumber: `floorplan/plan.jpeg` (1600×945 px, ≈ 25.81 mm/px). Pengukuran dilakukan dalam piksel di `gt_px.py`, lalu dikonversi ke `gt.yaml` (mm). Untuk mengubah GT, edit `gt_px.py`, jalankan ulang, lalu jalankan `gt_author`.

```
uv run python -m benchmarks.gatsu.gt_px
uv run python -m benchmarks.tools.gt_author benchmarks/gatsu/gt.yaml
```

## Kalibrasi

- Posisi sumbu grid diambil dari garis leader magenta di bawah dan di kiri bulatan grid:
  - sumbu X: A=198.5, B=431.0, D=818.5, E=1050.5, F=1283.0 px;
  - sumbu Y: 1=133.0, 2=365.0, 3=598.0 px;
  - sumbu **C = 663.0 px hasil interpolasi**, karena leader C tidak tertangkap segmentasi warna.
- Fit affine least squares atas 18 perpotongan menghasilkan RMS 7.6 mm (< 1 px).
- Koordinat dalam radius 150 mm dari sumbu grid di-snap ke sumbu. Tebal dinding dibulatkan ke 10 mm.

## Tingkat detail (keputusan pengguna 2026-10-26)

Yang dimodelkan 1:1 adalah elemen denah umum: dinding, lantai, tangga, pintu, kolom, termasuk pita luar dan blok-blok di sekelilingnya. Furnitur dan perangkat tidak dimodelkan. Kondisinya existing.

## Interpretasi

| Elemen | Keputusan | Alasan / risiko |
|---|---|---|
| Pita luar | `skin` exterior t=110 (garis terluar) + rail `low` t=130 di dalamnya + garis dalam pita (muka bangunan) exterior t=150 | Ketiganya digambar sebagai garis ganda. Rail ditafsirkan sebagai tepi planter/pagar rendah dengan **tinggi 1000 mm (asumsi; tidak terbaca dari denah)**. Dinding `low` tidak ikut membagi ruang. |
| Sel pita luar | Sel di antara sirip diberi tipe `outdoor` (25 ruang tanpa nama) | PRD/04 tahap 4 langkah 2b. |
| Blok sirip | `column kind: pilaster`: baris utara/selatan di setiap sumbu grid dan tengah bentang (20×51 px), 4 di barat, 1 di timur | Sesuai jawaban pengguna: blok kecil di sekeliling bangunan dimodelkan. |
| Pier | Kotak antara garis dalam pita dan kolom baris 1/3 dimodelkan sebagai pilaster yang sedikit overlap dengan kolom | Di gambar pier menyatu dengan kolom; celah 1 px membuat ruang bocor. |
| Bay C–D | Tonjolan utara (R. Meeting) dan selatan antara sumbu C dan D | Dibentuk garis 653–829 px. |
| Glazing | Garis ganda dengan mullion di depan bentang A–B, B–C, D–E (utara), A–B, B–C (selatan), dan barat → `glass` t=150 | Ujungnya ditaruh di garis tengah elemen tetangga agar fasad tertutup. |
| Pintu masuk barat | Dinding x≈141 px dengan pintu ganda membuka keluar | Celah skin di barat (y 272–456 px) adalah teras. |
| Keluar tangga timur (S2) | Dinding x≈1350 px diperpanjang menutup celah, dengan bukaan `opening` (tanpa daun) 382–408 px | Konvensi spec: dinding menerus di bukaan. Tanpa ini, seluruh koridor terhubung ke luar dan tidak membentuk ruang. |
| Cable trench | Garis ganda y≈598–613 px di bawah Battery/AHU/MDF dan antara bangunan utama–Capasitor Room **bukan dinding** | Garis itu jalur kabel (hatch tangga). Ruang selatan dibatasi garis dalam pita (y≈641 px). |
| Garis leader | Garis vertikal panjang ke label "ROUTE CABLE" (mis. x≈1007 px) diabaikan | Anotasi. |
| Battery Room + Ex Mushola | **Satu ruang**, berlabel BATTERY ROOM | Tidak ada dinding tergambar di antaranya. Catatan "PROPOSED PANEL EXISTING AFTER DISMANTLE THE WALL" menyiratkan ada dinding existing yang akan dibongkar, tetapi posisinya tidak tergambar, jadi tidak dikarang. **Perlu konfirmasi pengguna.** |
| Galery | Satu ruang besar: galery + koridor sepanjang sumbu 2 + area tangga S1 + vestibule barat | Semua terbuka satu sama lain di gambar. |
| Ruang tanpa label | Ruang di timur Gudang (D–E, pintu sendiri), ruang servis di timur MDF, dan celah sempit di antara glazing dan muka bangunan dibiarkan tanpa nama (`other`, 7 ruang) | Tidak ada teks di gambar. |
| Tangga S1 (U, antara A–B) | Flight 1 naik ke utara (x≈392 px), bordes utara, flight 2 ke selatan; 15 tanjakan per flight dari hitungan garis injakan; arah dari teks "NK" + walking line | Dengan default `floor_to_floor` 4000, tanjakan = 133 mm (V019 warning). Tinggi lantai sebenarnya kemungkinan 4.5–5 m. **Perlu konfirmasi tinggi lantai.** |
| Tangga S2 (timur) | Satu flight 1.4 m, 10 tanjakan, diasumsikan naik ke utara | Tidak ada teks arah. Garis tengah ditafsirkan sebagai railing. 10 tanjakan tidak cukup untuk satu lantai (V019), jadi kemungkinan ini tangga keluar ke level tanah. **Arah dan tujuan belum pasti.** |
| Lift | Shaft dinding t=210 di tengah tangga S1, ruang `lift` | Simbol silang dalam kotak. |
| Toilet | Partisi bilik, dinding depan bilik dengan 4 pintu, 2 pintu masuk di dinding timur | Fixture (kloset, wastafel) tidak dimodelkan. |

## Warning validator yang tersisa (skor 0.993)

- **V005**: tebal shaft lift (210), dinding barat tangga S2 (210), bangku toilet (190), dan dinding x≈1283 (180) berbeda > 30% dari median `interior`. Nilai ini memang hasil ukur.
- **V019**: lihat baris tangga S1/S2 di atas.

## Perlu review pengguna

1. Batas Battery Room dan Ex Mushola (dinding yang akan dibongkar).
2. Tinggi lantai ke lantai (mempengaruhi tanjakan S1).
3. Arah dan tujuan tangga timur S2.
4. Penafsiran rail di pita luar sebagai dinding rendah.
