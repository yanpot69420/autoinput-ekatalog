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

## Status: Tahap 3 selesai

| Tahap | Isi | Status |
|---|---|---|
| 1 | Jendela, template Excel, baca file, validasi, penanda baris | **Selesai** |
| 2 | Isi satu baris ke portal | **Selesai** |
| 3 | Jalankan semua, lanjutkan sisanya, berhenti di tengah | **Selesai** |
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

## Menjalankan banyak baris

| Tombol | Yang dikerjakan |
|---|---|
| **Jalankan baris ini** | Hanya baris yang dipilih |
| **Jalankan semua** | Semua baris siap, dari atas — termasuk mengulang yang **Gagal** |
| **Lanjutkan sisanya** | Sama, tapi baris **Gagal** dilewati |
| **Berhenti** | Hentikan antrean |

Dua hal tidak pernah masuk antrean, apa pun tombolnya. Baris **Sukses**:
mengulangnya membuat produk *kedua* di portal, bukan memperbarui yang pertama,
dan itu tidak bisa dibatalkan dari sini. Baris yang masih punya **error**: sudah
pasti ditolak, dan menghabiskan setengah menit masing-masing untuk
membuktikannya.

Bedanya dua tombol antrean cuma pada baris yang gagal. Baris gagal umumnya perlu
diperbaiki dulu — mengulangnya apa adanya menghasilkan kegagalan yang sama.
Baris **Terisi** ikut di keduanya, karena belum ada apa pun yang masuk ke portal.

Satu sambungan browser dipakai untuk seluruh antrean, dan **status disimpan tiap
baris selesai**, bukan di akhir. Aplikasi yang mati di baris ke-40 tidak
menghapus 39 baris sebelumnya.

### Berhenti di tengah

Playwright versi sinkron tidak bisa diputus dari luar, jadi berhentinya
diperiksa di sela-sela langkah: jedanya paling lama satu langkah, bukan satu
baris penuh. Form di portal tertinggal separuh terisi — tidak apa-apa, tidak ada
yang tersimpan dan baris berikutnya memuat ulang halamannya.

Baris yang diputus dikembalikan ke **Menunggu**, bukan Gagal. Tidak ada yang
salah dengan barisnya, dan menandainya gagal akan membuat "Lanjutkan sisanya"
melewatinya. Berhenti yang datang sedetik sebelum tombol Simpan diklik tetap
membatalkan kliknya.

### Berhenti sendiri

Tiga baris gagal berturut-turut menghentikan antrean. Kegagalan sebanyak itu
hampir selalu berarti sesinya yang rusak — logout, portal bermasalah, halaman
berubah — bukan tiga baris yang kebetulan buruk. Meneruskannya cuma menambah 48
kegagalan yang sama sambil menghabiskan setengah menit per baris. Kegagalan yang
diselingi keberhasilan tidak dihitung beruntun.

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

Sudah dijalankan di Windows 10 (Python 3.12, Chrome 151): seluruh uji lulus,
termasuk uji pengisi form yang menempel ke Chrome sungguhan lewat port debug.
Dua lapisan yang perilakunya berbeda dari macOS ikut terbukti di sana — deteksi
lokasi Chrome, dan cara melepas prosesnya supaya tidak ikut mati saat aplikasi
ditutup (`creationflags`, karena `start_new_session` diabaikan diam-diam di
Windows).

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

### Membuka Chrome sendiri, di luar aplikasi

Aplikasi tidak harus yang menjalankan Chrome. Buat pintasan terpisah:

```bash
./scripts/buat-shortcut-chrome.sh
```

Hasilnya **Chrome Portal INAPROC.app** — klik dua kali, Chrome terbuka dengan
port debug dan profil yang sama seperti pilihan di aplikasi. Login sekali, lalu
biarkan terbuka berhari-hari. Di aplikasi cukup klik **Uji koneksi browser**;
tombol "Buka Chrome portal" tidak perlu disentuh sama sekali.

Enaknya begini: umur Chrome tidak lagi terikat pada aplikasi. Aplikasi boleh
ditutup dan dibuka berkali-kali tanpa mengganggu sesi yang sedang berjalan, dan
tidak ada satu pun tindakan aplikasi yang bisa menutup browsermu.

Di Windows, jalankan `scripts\buka-chrome-windows.bat`. Kalau Chrome ternyata
masih berjalan, keduanya menolak dengan penjelasan — bukan gagal diam-diam.

### Dua pilihan profil Chrome

Pilih di kotak **Profil Chrome** pada bilah atas. Pilihannya tersimpan di
`~/.inaproc-autoinput/chrome.json`.

| | Profil terpisah (bawaan) | Profil Chrome harian |
|---|---|---|
| Lokasi | `~/.inaproc-chrome` | profil Chrome biasamu |
| Chrome harian | tidak perlu ditutup | **harus ditutup sepenuhnya dulu** |
| Sesi portal | dua sesi satu akun — saling menendang | satu sesi, tidak ada konflik |
| Tab lain | tidak ada | semuanya ikut terlihat di port debug |

Profil terpisah lebih tidak mengganggu, tapi punya satu kelemahan yang baru
terasa setelah dipakai: portal melihat dua sesi untuk satu akun, dan karena
hanya satu yang diizinkan, yang satunya ditendang dengan kotak "Akun Telah
Keluar". Kalau kamu sering membuka portal di Chrome harian juga, profil harian
menghilangkan konflik itu sama sekali.

Harganya: port debug hanya bisa dibuka saat Chrome mulai dijalankan, jadi
Chrome harus benar-benar ditutup lebih dulu — semua jendela, lalu *Keluar* dari
menu Chrome. Aplikasi memeriksanya dan menolak dengan penjelasan kalau kamu
lupa, karena Chrome yang dijalankan di atas profil terpakai cuma menyerahkan
alamatnya ke jendela yang sudah ada lalu keluar diam-diam.

Dengan profil harian aplikasi tidak pernah mengambil alih tab yang sedang
terbuka: kalau belum ada tab portal, tab baru yang dibuka.

### Mengukur, bukan menebak

Kalau portal terasa berat, jalankan ini **tepat saat itu**:

```bash
.venv/bin/python -m inaproc_autoinput.periksa_portal
```

Keluarannya angka, bukan kesan: berapa lama server menjawab, berapa lama form
siap dipakai, dan permintaan mana yang menahan. Saat portal sehat, form siap
sekitar **0,7 detik**. Halaman yang sedang kamu buka tidak diganggu —
pengukuran memakai tab tersendiri yang ditutup lagi.

Bedanya penting. Portal yang lambat tidak bisa dipercepat dari aplikasi.
Halaman yang tidak pernah siap padahal servernya cepat menunjuk ke hal lain
sama sekali: sesi yang mati, atau modal yang menutupi halaman.

### Kalau portal terasa berhenti merespons

Dua sebab yang sudah pernah terjadi, dan keduanya tidak terlihat seperti apa
adanya:

**Kotak "Akun Telah Keluar".** Portal menutupi seluruh halaman dengan overlay
ber-`z-index` 99999 saat sesimu berakhir — biasanya karena akun yang sama
dipakai masuk dari browser lain, dan portal hanya mengizinkan satu sesi.
Halaman di bawahnya tetap terlihat normal, tapi semua klik dan ketikan ditelan
overlay itu, jadi rasanya seperti lag parah — sementara tab dan kolom URL tetap
lancar, karena itu bagian browser, bukan halaman. Aplikasi sekarang mengenalinya
dan menyebutkannya, bukan menunggu sampai batas waktunya habis.

Kalau ini berulang, ganti **Profil Chrome** ke *harian* (lihat di bawah) —
penyebabnya memang dua profil memakai satu akun.

**Proses perender Chrome yang tersangkut.** Ini penyebab paling sering, dan
paling menyesatkan: Chrome kadang meninggalkan proses perender yatim yang terus
berputar tanpa halaman apa pun. Terukur membakar **72% CPU dengan satu tab
`about:blank`**, dan yang melambat jadi *semua* situs — bukan cuma portal, jadi
gampang dikira portalnya yang berat.

Angkanya, diukur pada halaman lokal yang sama sebelum dan sesudah Chrome
dijalankan ulang:

| | tersangkut | setelah dijalankan ulang | sehat |
|---|---|---|---|
| Membangun DOM | 237 ms | 77 ms | 75 ms |
| Kecepatan JS | 3,77 juta | 8,20 juta | 8,14 juta |
| Waktu per frame | 16,7 ms | 8,3 ms | 8,3 ms |

Hal yang sama terlihat di rangkaian uji: 100 detik jadi 29 detik.

Obatnya menjalankan ulang Chrome. Butuh sekitar satu detik, dan sesi loginmu
tetap ada karena profilnya permanen:

```bash
.venv/bin/python -m inaproc_autoinput.buka_chrome --mulai-ulang
```

`periksa_portal` mengenali kondisi ini sendiri dan menyebutkan perintahnya.

Chrome ditutup lewat protokolnya sendiri (`Browser.close`), bukan dimatikan
paksa. Bedanya penting: Chrome menuliskan cookie dan sesi ke profil saat keluar
normal, sedangkan kalau dibunuh yang tertulis belum tentu lengkap — dan itu
persis yang membuat login hilang.

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

Sebagian atribut berpasangan dengan lampiran berjudul persis sama — *Masa
Berlaku SBU Konstruksi* dan *Komponen Struktur Biaya Tayang* punya kolom teks
sekaligus unggahan PDF. Untuk keduanya kolom `Nilai n` boleh dikosongkan:
aplikasi mengisinya dengan nama berkas yang kamu pilih di tab **Berkas**, jadi
tidak perlu diketik ulang di Excel. Yang lain tetap harus diisi.

### Berkas tidak ada di Excel

Foto, video, dan dokumen PDF dipilih lewat tab **Berkas** di aplikasi, bukan
diketik sebagai path di spreadsheet. Tiga alasan: path yang diketik tangan
rawan salah dan tidak bisa diperiksa saat mengetik; dokumen perusahaan seperti
SBU sama untuk seluruh baris sehingga menuliskannya puluhan kali cuma
pengulangan; dan spreadsheet bukan tempat yang wajar untuk memilih berkas.

Dua tingkat: **dokumen dan foto umum** berlaku untuk semua baris, **foto per
baris** menimpa foto umum untuk produk yang punya foto sendiri.

Semua yang dipilih bisa dilepas lagi. Dokumen dan video punya tombol **Hapus**
masing-masing; URL video juga. Foto tampil sebagai daftar — pilih satu atau
beberapa lalu **Hapus terpilih**, jadi salah pilih satu dari lima tidak memaksa
memilih ulang kelimanya. **Kosongkan semua berkas…** melepas semuanya sekaligus
(dengan konfirmasi), berguna saat berpindah penyedia atau kompetisi.

Yang dilepas cuma kaitannya — berkasnya sendiri tidak pernah dihapus dari
komputer. *Masa Berlaku SBU* memang tidak punya tombol sendiri: ia selalu
mengikuti berkas SBU.

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

Di Windows, cara paling ringkas adalah memakai pembuka milik aplikasi sendiri —
sekalian menguji deteksi lokasi Chrome di mesin itu:

```bash
.venv\Scripts\python -c "from inaproc_autoinput import chrome; print(chrome.launch())"
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
