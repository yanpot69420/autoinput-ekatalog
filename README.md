# INAPROC Autoinput

Aplikasi jendela (Python + PySide6) untuk menginput produk ke **Katalog
Elektronik v6** lewat halaman *tambah produk*, dari satu template Excel yang
diisi penyedia.

Penyedia mengisi satu lembar Excel. Aplikasi membacanya, memeriksa tiap baris,
lalu mengisikannya ke portal satu per satu — sambil menandai baris mana yang
sedang diproses dan mana yang sudah berhasil.

## Kenapa lewat halaman tambah produk, bukan unggah massal

Panduan resmi INAPROC menyatakan fitur unggah massal **tidak mencakup**: produk
varian, harga grosir, layanan tambahan, serta informasi TKDN, SNI, dan Merek.
Produk yang punya salah satu dari itu tetap harus diisi lewat halaman penyedia.

Selain itu, unggah massal menuntut satu file terpisah untuk **setiap Kategori
Level 3** — Bina Marga saja 68 file, Cipta Karya 66 file, dengan susunan kolom
yang berbeda-beda. Template universal di sini menggantikan semuanya dengan satu
lembar.

## Status: Tahap 2 selesai

| Tahap | Isi | Status |
|---|---|---|
| 1 | Jendela, template Excel, baca file, validasi, penanda baris | **Selesai** |
| 2 | Isi satu baris ke portal | **Selesai** |
| 3 | Jalankan semua, lanjutkan sisanya, berhenti di tengah | Belum |
| 4 | Varian, harga grosir, TKDN/SNI/Merek | Belum |

## Menjalankan ke portal

Aplikasi tidak pernah menyimpan kata sandi. Kamu menjalankan Chrome dengan port
debug terbuka, login sendiri, lalu aplikasi menempel ke sesi itu:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/.inaproc-chrome"
```

Profil terpisah dipakai supaya Chrome sehari-harimu tidak perlu ditutup. Login
sekali di jendela itu; sesinya bertahan.

Lalu di aplikasi: **Uji koneksi browser** → pilih satu baris → **Jalankan baris
ini**.

### Tiga tingkat tindakan

Pilihan *Setelah terisi* menentukan sejauh mana aplikasi boleh bertindak:

| Mode | Yang dilakukan |
|---|---|
| **Isi saja, jangan simpan** (bawaan) | Form diisi, aplikasi berhenti. Kamu yang memeriksa dan menekan tombol |
| Simpan sebagai draf | Menekan *Simpan Draf Produk* |
| Simpan (produk diajukan) | Menekan *Simpan* |

Dua mode terakhir mengubah data di akun penyedia, jadi selalu ada konfirmasi
lebih dulu. Untuk produk pertama, pakai mode bawaan.

Panel rincian menampilkan langkah demi langkah apa yang diisi, plus peringatan
untuk atribut atau dokumen yang tidak ada di kategori tersebut.

## Menjalankan

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/inaproc-autoinput
```

Alur pemakaian:

1. **Buat template kosong…** → simpan, kirim ke penyedia untuk diisi.
2. Penyedia mengisi mulai baris 5, satu baris satu produk. Sheet *Petunjuk*
   berisi aturan pengisian.
3. **Buka template terisi…** → tiap baris diperiksa dan diberi status.
4. Klik satu baris untuk melihat rinciannya: kategori, atribut khusus, dan
   daftar hal yang harus diperbaiki.
5. Perbaiki di Excel, lalu **Muat ulang**.

## Daftar kategori

Portal menyediakan seluruh pohon kategori lewat satu panggilan GraphQL publik,
tanpa login:

```
POST https://katalog.inaproc.id/graphql
query { allMinifiedProductCategory(input: {}) { ... } }
```

Hasilnya **57 kategori level 1 → 456 level 2 → 2.934 level 3**, lengkap dengan
UUID. UUID itu terbukti sama dengan `Category ID` di baris 2 template unggah
massal resmi — misalnya `1.2 Mobilisasi` sama-sama
`5136f692-9c21-49e2-9cfa-fa4c93c6de5b`.

Aplikasi mengunduhnya sekali dan menyimpannya di `~/.inaproc-autoinput/`.

### Bidang yang dilayani

Dari 57 kategori level 1, hanya **21 bidang konstruksi dan pertanian** yang
dipakai — menyisakan **1.277 dari 2.934** kategori level 3. Template dan
dropdown hanya memuat bidang ini; sisanya tidak ikut.

Konstruksi: Bina Marga, Bina Marga 2025, Cipta Karya, Sumber Daya Air,
Perumahan dan Kawasan Permukiman, Bidang Umum, SMKK, Komponen Struktur,
Material Dasar Utama, Material Olahan Utama, Pesawat/Peralatan Konstruksi
Lainnya, dan enam kategori alat berat (Pesawat Angkat/Angkut/Tenaga dan
Produksi beserta Jasa Sewa masing-masing).

Pertanian: Pekerjaan Cetak Sawah, Tanaman dan Sarana Pendukung, Hewan dan
Ternak.

Daftarnya ada di `categories.BIDANG_DEFAULT`, dan bisa diubah tanpa menyentuh
kode dengan menulis `~/.inaproc-autoinput/bidang.json`:

```json
{ "bidang": ["Bidang Bina Marga", "Bidang Cipta Karya"] }
```

Katalog **penuh** tetap dipakai saat memvalidasi. Kategori yang sah tapi di
luar bidang terpilih dilaporkan sebagai *peringatan* — bukan diblokir, dan
bukan dibilang "tidak ada", yang akan menyesatkan.

Dengan daftar itu aplikasi:

- memeriksa jalur Kategori Level 1 → 2 → 3 yang ditulis penyedia, dan
  menyarankan ejaan terdekat bila salah ketik;
- memastikan Tipe Produk cocok dengan tipe kategorinya (kategori Jasa tidak
  bisa diisi produk Barang);
- menempelkan seluruh daftar kategori sebagai sheet **Daftar Kategori** di
  template kosong, supaya penyedia menyalin nama, bukan mengarang.

UUID-nya nanti dipakai Tahap 2 untuk memilih kategori langsung di form.

## Isi template

Skemanya disusun dari pembacaan langsung form `penyedia.inaproc.id/products/add`
— lihat [docs/form-tambah-produk.md](docs/form-tambah-produk.md). Ini berbeda
cukup jauh dari template unggah massal, jadi jangan pakai yang itu sebagai acuan.

**35 kolom inti** — kategori (satu kolom jalur lengkap), Daftar Produk
Sektoral, nama, deskripsi, foto & video, saklar Merek/SNI/TKDN, KBKI,
self-declare PDN, PPN, PPnBM, kuantitas desimal, harga, stok, pre-order, serta
bagian Pengiriman (berat, dimensi, ongkir) yang hanya berlaku untuk kategori
bertipe Barang.

**8 pasang `Atribut n` / `Nilai n`** — untuk bagian *Spesifikasi Produk →
Informasi Utama*, yang isinya berbeda tiap Kategori Level 3. Di form bentuknya
array berindeks (`productInformations.mainInformations.<n>.value`), bukan field
bernama tetap — karena itu kolomnya dibiarkan bebas: penyedia menulis nama
atributnya, aplikasi mencocokkannya dengan label di halaman.

Termasuk di sini: Satuan Pengukuran, Kode Produk, Lingkup Kegiatan, Lokasi
Layanan (Kecamatan), SBU Konstruksi. Semuanya milik kategori, bukan milik semua
produk — karena itu tidak jadi kolom inti.

**5 pasang `Dokumen n` / `Berkas n`** — lampiran PDF, mengikuti pola yang sama
karena daftar dokumen yang diminta juga berbeda tiap kategori.

Foto, video, dan dokumen diisi dengan **alamat berkas di komputer**, bukan
tautan — form mengunggah berkas. Aplikasi memeriksa berkasnya benar-benar ada,
formatnya benar, dan ukurannya tidak melebihi batas sebelum baris dijalankan.

Pembacaan mengikuti **judul kolom di baris 2**, bukan posisinya — penyedia boleh
menggeser kolom atau menyisipkan catatan sendiri tanpa merusak apa pun.

### Yang belum didukung

Varian, harga grosir, harga zonasi, layanan tambahan, serta rincian merek, SNI,
dan TKDN. Saklarnya sudah ada di template, tapi isinya belum bisa dimasukkan —
untuk sekarang diedit manual di portal setelah produk tayang.

## Status eksekusi

Status **tidak** ditulis balik ke file Excel penyedia: kalau file itu sedang
dibuka di Excel, penulisan akan gagal dan hasil kerja berjam-jam bisa hilang.
Status disimpan di berkas pendamping `<nama>.status.json` di folder yang sama.

Dua perlindungan di dalamnya:

- Baris yang isinya **berubah** sejak terakhir dijalankan dikembalikan ke
  *menunggu* — status suksesnya tidak lagi mewakili isi file.
- Baris yang tercatat *berjalan* saat aplikasi berhenti mendadak juga
  dikembalikan ke *menunggu*, karena proses itu tidak pernah selesai.

## Isi paket

| Modul | Tugas |
|---|---|
| `schema.py` | Definisi kolom template universal |
| `references.py` | Daftar pilihan yang dibaca dari form, sumber dropdown |
| `categories.py` | Mengambil, menyimpan, dan menelusuri pohon kategori portal |
| `workbook.py` | Membuat template kosong, membaca template terisi |
| `validation.py` | Memeriksa baris sebelum dijalankan |
| `model.py` | `ProductRow` dan status eksekusinya |
| `state.py` | Menyimpan dan memulihkan status per baris |
| `runner.py` | Menyambung ke Chrome lewat CDP dan mengisi form di portal |
| `ui/` | Jendela dan model tabel (PySide6) |

## Uji

```bash
.venv/bin/python -m pytest tests -q
```

Uji pengisi form berjalan terhadap `tests/mock_form.html` — halaman tiruan
dengan `id`, `name`, dan perilaku dropdown yang sama seperti form asli. Uji itu
dilewati bila Chrome dengan port debug belum berjalan:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/.inaproc-chrome-uji"
```

## Catatan

Bagian **Pengiriman**, **PPnBM**, dan **Sertifikat TKDN** hanya muncul di form
untuk kategori bertipe Barang. Validasi menentukan tipe dari kategori di portal,
bukan dari kolom Tipe Produk yang diisi tangan — jadi penyedia tidak perlu tahu
aturan ini.

Tiga hal tidak bisa jadi dropdown tetap karena isinya berbeda tiap kategori:
**Kode KBKI**, **Daftar Produk Sektoral**, dan **Satuan Pengukuran**. Ketiganya
diperiksa saat baris dijalankan, setelah kategori dipilih di portal.

Portal juga menolak kategori yang tidak cocok dengan izin usaha penyedia
(*"Anda tidak memiliki KBLI yang sesuai"*). Ini tidak bisa diperiksa dari luar.
