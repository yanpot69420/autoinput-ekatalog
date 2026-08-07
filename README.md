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

## Tiga tingkat tindakan

Pilihan *Setelah terisi* menentukan sejauh mana aplikasi boleh bertindak:

| Mode | Yang dilakukan | Status baris |
|---|---|---|
| **Isi saja, jangan simpan** (bawaan) | Form diisi, aplikasi berhenti. Kamu yang memeriksa dan menekan tombol | **Terisi** |
| Simpan sebagai draf | Menekan *Simpan Draf Produk* | Sukses |
| Simpan (produk diajukan) | Menekan *Simpan* | Sukses |

Baris yang cuma **Terisi** tidak dianggap selesai: tidak ada apa pun yang masuk
ke portal, jadi baris itu tetap dihitung sebagai perlu dikerjakan. Menyamakannya
dengan sukses akan membuat "Lanjutkan sisanya" melewatinya diam-diam.

Dua mode terakhir mengubah data di akun penyedia, jadi selalu ada konfirmasi
lebih dulu. Untuk produk pertama, pakai mode bawaan.

Panel rincian menampilkan langkah demi langkah apa yang diisi, plus peringatan
untuk atribut atau dokumen yang tidak ada di kategori tersebut.

## Menjalankan

Siapkan sekali:

```bash
python3 -m venv .venv && .venv/bin/pip install -e . playwright
```

Lalu buat pintasan yang bisa diklik dua kali dari Finder atau Dock:

```bash
./scripts/buat-shortcut.sh
```

Menghasilkan **INAPROC Autoinput.app** lengkap dengan ikonnya. Beri argumen
untuk menaruhnya di tempat lain, misalnya `./scripts/buat-shortcut.sh ~/Applications`
supaya muncul di Launchpad dan Spotlight.

Bundle-nya hanya penunjuk ke folder proyek, bukan salinan — setiap perbaikan
kode langsung ikut terpakai tanpa perlu dibuat ulang. Karena memuat path
absolut mesin pembuatnya, bundle itu sendiri tidak ikut ke repositori.

Atau jalankan langsung dari terminal:

```bash
.venv/bin/inaproc-autoinput
```

### Windows

Siapkan lingkungannya, lalu pakai `scripts\jalankan-windows.bat` — klik dua
kali, atau klik kanan → *Send to* → *Desktop (create shortcut)*.

```
python -m venv .venv
.venv\Scripts\pip install -e . playwright
```

Berkas `.bat` itu memakai `pythonw.exe` supaya jendela Command Prompt tidak
ikut muncul, dan path-nya relatif terhadap letak berkasnya sendiri — folder
proyek boleh dipindah tanpa mengubah apa pun.

Yang **belum diuji di Windows**: seluruh aplikasi ini dikembangkan dan
dijalankan di macOS. Lapisan yang berbeda perilakunya sudah ditangani —
lokasi Chrome termasuk pemasangan per-pengguna di `%LOCALAPPDATA%`, dan cara
melepas proses Chrome supaya tidak ikut mati (`creationflags`, karena
`start_new_session` diabaikan diam-diam di Windows). Tapi keduanya baru diuji
lewat simulasi, bukan di mesin Windows sungguhan.

Ikon `.app` hanya untuk macOS; `.bat` di Windows memakai ikon bawaan.

### Menyambung ke portal

Aplikasi tidak pernah menyimpan kata sandi. Klik **Buka Chrome portal** di
jendela aplikasi — Chrome terbuka dengan port debug dan profil terpisah di
`~/.inaproc-chrome`, jadi Chrome sehari-harimu tidak perlu ditutup. Login
sendiri di jendela itu, sekali saja, lalu klik **Uji koneksi browser**.

Chrome selalu dibuka dengan alamat halaman tambah produk. Ini bukan kenyamanan
belaka: Chrome yang dibuka tanpa alamat hanya menampilkan tab baru, dan tab itu
tidak muncul sebagai target di `/json/list` — port debug hidup tapi tidak ada
yang bisa dikendalikan, dengan pesan galat yang menyesatkan.

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

UUID-nya dipakai saat mengisi form untuk memastikan kategori yang terpilih benar.

## Isi template

Skemanya disusun dari pembacaan langsung form `penyedia.inaproc.id/products/add`
— lihat [docs/form-tambah-produk.md](docs/form-tambah-produk.md). Ini berbeda
cukup jauh dari template unggah massal, jadi jangan pakai yang itu sebagai acuan.

**20 kolom inti** — kategori (satu kolom jalur lengkap), Daftar Produk
Sektoral, nama, deskripsi, KBKI, self-declare PDN, PPN, minimum pembelian,
harga, stok, satuan, pre-order, serta berat dan dimensi yang hanya berlaku
untuk kategori bertipe Barang.

### Yang sengaja tidak jadi kolom

Sembilan kolom dibuang setelah diuji terhadap file 51 pekerjaan nyata, di mana
21 dari 45 kolom sama sekali tidak terisi:

| Kolom | Kenapa dibuang |
|---|---|
| Punya Merek, Punya SNI, Punya TKDN, Harga Zonasi, Aktifkan PPnBM | Menyalakannya memunculkan isian lain di form yang belum didukung, jadi form justru jadi tidak lengkap. Saklar yang jawabannya cuma boleh "Tidak" bukan pilihan |
| Atur Ongkir Produk | Pilihannya cuma satu, `Standar`. Tidak ada keputusan di sini |
| Tipe Produk | Portal menentukannya dari kategori; menyalinnya ke Excel cuma membuka peluang bertentangan |
| Kuantitas Desimal | Disimpulkan dari angka stok: 332,35 butuh desimal, 1 tidak |
| URL Video Produk | Pindah ke tab Berkas, berdampingan dengan berkas videonya |

**8 pasang `Atribut n` / `Nilai n`** — untuk bagian *Spesifikasi Produk →
Informasi Utama*, yang isinya berbeda tiap Kategori Level 3. Di form bentuknya
array berindeks (`productInformations.mainInformations.<n>.value`), bukan field
bernama tetap — karena itu kolomnya dibiarkan bebas: penyedia menulis nama
atributnya, aplikasi mencocokkannya dengan label di halaman.

Termasuk di sini: Satuan Pengukuran, Kode Produk, Lingkup Kegiatan, Lokasi
Layanan (Kecamatan), SBU Konstruksi. Semuanya milik kategori, bukan milik semua
produk — karena itu tidak jadi kolom inti.

### Berkas tidak ada di Excel

Foto, video, dan dokumen PDF dipilih lewat tab **Berkas** di aplikasi, bukan
diketik sebagai path di spreadsheet. Tiga alasan: path yang diketik tangan
rawan salah dan tidak bisa diperiksa saat mengetik; dokumen perusahaan seperti
SBU sama untuk seluruh baris sehingga menuliskannya puluhan kali cuma
pengulangan; dan spreadsheet bukan tempat yang wajar untuk memilih berkas.

Dua tingkat: **dokumen dan foto umum** berlaku untuk semua baris, **foto per
baris** menimpa foto umum untuk produk yang punya foto sendiri.

Portal meminta unggahan terpisah untuk *Masa Berlaku SBU* padahal isinya
dokumen yang sama dengan *SBU* — panel mengikutkannya otomatis, cukup pilih
sekali.

Pilihan berkas disimpan di `<nama>.berkas.json` di sebelah workbook, jadi file
Excel penyedia tidak pernah ditulisi. Aplikasi memeriksa berkasnya ada,
formatnya benar, dan ukurannya di bawah batas sebelum baris dijalankan.

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
| `assets.py` | Foto, video, dan dokumen PDF beserta pemeriksaannya |
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
