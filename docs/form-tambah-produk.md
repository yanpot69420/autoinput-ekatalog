# Peta form Tambah Produk — penyedia.inaproc.id

Hasil pembacaan langsung halaman `https://penyedia.inaproc.id/products/add`
pada 3 Agustus 2026, dengan akun penyedia yang sudah login.

Kategori uji: **Bidang Bina Marga › Divisi 3 Pekerjaan Tanah dan Geosintetik ›
3.1 Galian** (Produk Jasa).

Dokumen ini jadi acuan Tahap 2. Selektor di bawah adalah `id` atau `name`
elemen — keduanya stabil dan lebih tahan perubahan tata letak daripada koordinat.

## Pemilih kategori

Kotak pencarian dengan penelusuran bertingkat, bukan tiga dropdown terpisah.

```
input[placeholder="Pilih Kategori"]
```

Mengetik kata kunci menyaring seluruh tingkat sekaligus, lalu hasilnya muncul
sebagai tiga kolom berdampingan: Level 1 → Level 2 → Level 3. Setelah level 3
diklik, kotak pencarian berisi jalur lengkapnya:

```
Bidang Bina Marga > Divisi 3 Pekerjaan Tanah dan Geosintetik
```

Begitu kategori terpilih, muncul keterangan **"Kategori ini termasuk jenis
Produk Jasa"** — konfirmasi tipe produk langsung dari portal.

Memilih kategori **mengubah isi form**: beberapa bagian baru bermunculan
(Daftar Produk Sektoral, Spesifikasi Produk, Pengaturan Kuantitas Desimal,
Harga Zonasi, Lampiran), dan PPN otomatis terisi 12%.

## Field tetap

| Bagian | Field | Selektor | Tipe | Wajib |
|---|---|---|---|---|
| Kategori | Pilih Kategori | `input[placeholder="Pilih Kategori"]` | pencarian bertingkat | ✓ |
| Merek | Merek aktif/tidak | `#form-product-brand-isActive-switch` — `brand.isActive` | switch | |
| Informasi Produk | Daftar Produk Sektoral | `#react-select-_r_1u_-input` | dropdown | ✓ |
| | Nama Produk | `#form-product-name-input` — `name` | teks, min 5, **maks 250** | ✓ |
| | Foto Utama … Foto 5 | `#product-image-input-0` … `-4` | **file** | ✓ (min 1) |
| | Video Produk | `#videoInput` — `video` | file .mp4/.mov, maks 50 MB | |
| | URL Video Produk | `#form-product-video-url-input` — `videoUrl` | teks, URL YouTube | |
| | Deskripsi | `textarea[name=description]` | **maks 2000** | |
| Kode KBKI | Pilih kode KBKI | dropdown | dropdown | ✓ |
| PDN | Klasifikasi Produk | `#react-select-_r_1l_-input` | dropdown (Lokal) | ✓ |
| | Lokasi Produksi | `#react-select-_r_1m_-input` | dropdown | |
| | Tenaga Kerja | `#react-select-_r_1n_-input` | dropdown | |
| | Bahan Baku | `#react-select-_r_1o_-input` | dropdown | |
| Sertifikat SNI | SNI ada/tidak | `#form-product-sni-switch` — `sni.isActive` | switch | |
| Pajak | PPN | `#react-select-ppnPercentage-select-input` | dropdown | ✓ |
| | Kuantitas Desimal | `#form-product-decimal-qty-switch` — `hasDecimalQuantity` | switch | |
| Varian | Tambah Varian | tombol | bagian berulang | |
| Harga | Minimum Pembelian | `#form-product-min-purchase-input` | teks (bawaan 1) | |
| | Harga Produk | `#form-product-price-input` — `priceAndVariantField.variants.0.price` | teks | ✓ |
| | Harga tayang termasuk pajak | (hanya baca, terhitung sendiri) | | |
| | Harga Grosir | tombol | bagian berulang | |
| | Harga Zonasi | `priceAndVariantField.isRegionPriceActive` | switch | |
| Informasi stok | Jumlah Stok | `#stockUnit-value-input` — `priceAndVariantField.variants.0.stock` | teks | ✓ |
| | Satuan Produk | `#react-select-_r_1t_-input` → `stockUnit.primaryUnit` | dropdown | ✓ |
| Pre Order | Pre Order aktif | `#form-product-preorder-isActive-switch` — `preOrder.isActive` | switch | |
| Layanan Tambahan | Tambah Layanan | tombol | bagian berulang | |

## Atribut khusus kategori

Inilah yang berbeda tiap Kategori Level 3. Bentuknya **array berindeks**, bukan
nama field yang berbeda-beda:

```
productInformations.mainInformations.<n>.value
productInformations.additionalInformations.<n>.value
```

Untuk kategori **3.1 Galian**, indeksnya:

| n | Label | Selektor | Tipe |
|---|---|---|---|
| 0 | Satuan Pengukuran | `#react-select-_r_21_-input` | dropdown |
| 1 | Kode Produk | `#form-product-productInformations-mainInformations-1-input` | teks |
| 2 | Lingkup Kegiatan | `…-mainInformations-2-input` | teks |
| 3 | Lokasi Layanan (Kecamatan) | `…-mainInformations-3-input` | teks |
| 4 | Sertifikat Badan Usaha (SBU) Konstruksi | `#react-select-_r_26_-input` | dropdown |
| 5 | Masa Berlaku SBU Konstruksi | `…-mainInformations-5-input` | teks |
| 6 | Sertifikat Standar | `#react-select-_r_29_-input` | dropdown |
| 7 | Komponen Struktur Biaya Tayang | `…-mainInformations-7-input` | teks |

`additionalInformations.0.value` = **Informasi Lainnya** (opsional).

Urutan ini sama persis dengan urutan kolom grup "Informasi Utama" dan
"Informasi Lainnya" pada template unggah massal — jadi pemetaan dari kedua
sumber saling mengonfirmasi.

**Cara aplikasi memakainya:** setelah kategori dipilih, baca label tiap indeks
dari halaman, lalu cocokkan dengan kolom `Atribut n` / `Nilai n` di template
Excel berdasarkan namanya. Tidak perlu daftar atribut yang di-hardcode.

## Lampiran dokumen

Semua `input[type=file]` dengan `id="document-field-input"`, format **.pdf
maks 10 MB**, dibedakan hanya oleh urutan kemunculannya:

1. Sertifikat Badan Usaha (SBU) Konstruksi — Wajib
2. Masa Berlaku Sertifikat Badan Usaha (SBU) Konstruksi — Wajib
3. Sertifikat Standar — Wajib
4. Komponen Struktur Biaya Tayang — Wajib
5. Informasi Lainnya — opsional

Ini menjawab teka-teki lama: kolom bernama sama yang muncul dua kali di template
unggah massal (grup "Informasi Utama" dan grup "Dokumen") ternyata **nilai
pernyataan** versus **berkas PDF-nya**.

## Pilihan Satuan Pengukuran

39 pilihan, terbaca langsung dari dropdown:

```
M2, M3, Jam, Meter, Pcs, kg, Paket, Pekerjaan, Pasang, Unit, Orang, ton,
Liter, Ha/Bulan, Tunggul Pohon, LS, orang/bulan, orang/jam, orang/kegiatan,
Lump Sum, Titik, Titik Lokasi, Roll, Hektare, set, Buah, 1 x, Pohon, cm,
Pola, sampel, Rupiah/Jam, M3/Km, Buah Jembatan, Kegiatan, Lembar, Pengujian,
Lokasi, Per potong
```

## Tombol simpan

```
Batal · Simpan Draf Produk · Simpan & Tambah Produk Lagi · Simpan
```

**Simpan & Tambah Produk Lagi** cocok untuk pengisian beruntun: form kembali
kosong tanpa memuat ulang halaman.

## Selisih dengan template unggah massal

| Hal | Unggah massal | Form tambah produk |
|---|---|---|
| Nama produk | min 10, maks 100 | **min 5, maks 250** |
| Deskripsi | min 10, maks 100 | **maks 2000** |
| Foto | tautan publik `.png` | **unggah berkas** .jpg/.jpeg/.png, 300×300–2048×2048 |
| Dokumen | tautan Google Drive | **unggah berkas** .pdf maks 10 MB |
| Varian, Harga Grosir, Layanan Tambahan | tidak didukung | **didukung** |
| Merek, SNI | tidak didukung | **didukung** (switch) |
| Daftar Produk Sektoral | tidak ada | **ada, wajib** |
| Harga Zonasi | tidak ada | **ada** |
| Kuantitas Desimal | kolom biasa | switch, muncul setelah kategori dipilih |

## Perbedaan kategori Barang

Diperiksa dengan `Peralatan Kantor > Furnitur Kantor > Meja Kerja`. Yang
**muncul** hanya untuk Barang:

| Bagian | Field |
|---|---|
| Sertifikat TKDN(%) | saklar, sejajar dengan Merek dan SNI |
| Pengaturan Pajak | **Aktifkan PPnBM** (Pajak Penjualan Barang Mewah) |
| Pengiriman | **Berat Produk** (Wajib, gram/kg) |
| | **Ukuran Produk** — panjang x lebar x tinggi, satuan CM, opsional |
| | **Atur Ongkir Produk** — pilihan "Standar" |

Yang **hilang** pada kategori Barang ini: Daftar Produk Sektoral, Harga Zonasi,
dan Pengaturan Kuantitas Desimal. Ketiganya ternyata tidak universal.

Portal juga menolak lebih awal bila izin usaha penyedia tidak cocok:
*"Anda tidak memiliki KBLI yang sesuai dengan kategori tersebut."* Ini tidak
bisa diperiksa dari luar, jadi tetap muncul saat baris dijalankan.

Catatan ketidakpastian: blok `Informasi Utama` pada kategori Meja Kerja masih
menampilkan atribut konstruksi (SBU, Lingkup Kegiatan). Kemungkinan sisa
keadaan dari kategori sebelumnya, karena penyedia ini tidak berizin untuk
kategori tersebut. Perlu dipastikan ulang dengan akun yang berizin.

## Daftar pilihan yang sudah dibaca

| Dropdown | Isi |
|---|---|
| Satuan Produk | 82 pilihan, sama untuk semua kategori |
| Satuan Pengukuran | 39 pilihan untuk Bina Marga; berbeda per kategori |
| Klasifikasi Produk PDN | `Lokal`, `Import` — portal menulis "Import", bukan "Impor" |
| SBU Konstruksi | `Memiliki`, `Tidak Memiliki` |
| Sertifikat Standar | `Memiliki`, `Tidak Memiliki` |
| PPN | `0%`, `12%` |
| Kode KBKI | per kategori; ditampilkan sebagai `54310 - Jasa pembongkaran` |
| Daftar Produk Sektoral | per kategori; 3.1 Galian punya 8 produk baku |

Tiga yang terakhir tidak bisa dijadikan dropdown tetap di Excel karena isinya
bergantung kategori — diperiksa saat baris dijalankan.

## Yang belum terjawab

- Field turunan saat saklar **Merek**, **SNI**, atau **TKDN** dinyalakan.
- Isi bagian **Varian**, **Harga Grosir**, **Harga Zonasi**, dan **Layanan
  Tambahan** setelah tombol "Tambah" ditekan.
