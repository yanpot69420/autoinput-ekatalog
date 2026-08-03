"""Daftar pilihan yang dibaca langsung dari form tambah produk INAPROC.

Semuanya hasil membuka dropdown aslinya di `penyedia.inaproc.id/products/add`
pada 3 Agustus 2026. Dipakai untuk dua hal: membuat dropdown di template Excel,
dan memeriksa isian penyedia sebelum baris dijalankan.

Yang TIDAK ada di sini karena isinya berbeda tiap Kategori Level 3:

* **Kode KBKI** -- hanya kode yang berlaku untuk kategori itu yang muncul.
  Di form ditampilkan sebagai "54310 - Jasa pembongkaran".
* **Daftar Produk Sektoral** -- daftar produk baku milik kategori tersebut, dan
  tidak selalu ada. Kategori Jasa 3.1 Galian punya 8 pilihan; kategori Barang
  Meja Kerja tidak punya bagian ini sama sekali.
* **Satuan Pengukuran** -- ada di blok atribut, dan daftarnya berbeda per
  kategori. Yang di bawah adalah daftar untuk kategori Bina Marga.

Ketiganya baru bisa dipastikan setelah kategori dipilih di portal, jadi
diperiksa saat baris dijalankan, bukan di Excel.
"""

from __future__ import annotations

# --- pilihan tetap ----------------------------------------------------------

PPN = ("0%", "12%")
KLASIFIKASI_PDN = ("Lokal", "Import")  # portal menulis "Import", bukan "Impor"
LOKASI_PRODUKSI = (
    "Diproduksi di seluruh Indonesia",
    "Diproduksi sebagian di Indonesia",
    "Tidak ada yang diproduksi di Indonesia",
)
TENAGA_KERJA = (
    "Dibuat oleh seluruh tenaga kerja Indonesia di dalam negeri",
    "Sebagian tenaga kerja Indonesia",
    "Tidak ada tenaga kerja Indonesia",
)
BAHAN_BAKU = (
    "Seluruh bahan baku dalam negeri",
    "Sebagian bahan baku dalam negeri",
    "Tidak ada bahan baku dalam negeri",
)
KEPEMILIKAN = ("Memiliki", "Tidak Memiliki")
YA_TIDAK = ("Ya", "Tidak")
AKTIF = ("Aktif", "Tidak Aktif")
OPSI_ONGKIR = ("Standar",)

# --- Satuan Produk: 82 pilihan, sama untuk semua kategori -------------------

SATUAN_PRODUK = (
    "Ah", "Ampul", "Artikel", "Bal", "Barel", "Batang", "Blister", "Botol",
    "Buah", "Buah Jembatan", "Bulan", "Butir", "Canister", "Cartridges", "Cm",
    "Drum", "Dus", "Gelas", "Ha/Bulan", "Hari", "Hektare", "Ikat", "Jam",
    "Jam Terbang", "Jerigen", "Kaleng", "Kantong", "Kaplet", "Kapsul",
    "Karung", "Kegiatan", "Kilogram", "Kilometer", "Kotak", "LS", "Lembar",
    "Liter", "Lokasi", "Lump Sum", "Lusin", "M²", "M³", "M³/Km", "Meter",
    "Milimeter", "Minggu", "Orang", "Orang/Bulan", "Orang/Jam",
    "Orang/Kegiatan", "Pail", "Paket", "Pasang", "Pcs", "Pekerjaan",
    "Pengujian", "Per Potong", "Periode", "Pohon", "Pola", "Porsi", "Rim",
    "Ritase", "Roll", "Rupiah/Jam", "Sampel", "Satuan Ukur", "Set", "Tablet",
    "Tahun", "Titik", "Titik Lokasi", "Ton", "Trip", "Tube", "Tunggul Pohon",
    "Unit", "Vial", "Voyage", "Watt", "Zak", "1 X",
)

# --- Satuan Pengukuran: daftar untuk kategori Bina Marga --------------------
# Berbeda per kategori; ini dipakai sebagai rujukan, bukan aturan mengikat.

SATUAN_PENGUKURAN_BINA_MARGA = (
    "M2", "M3", "Jam", "Meter", "Pcs", "kg", "Paket", "Pekerjaan", "Pasang",
    "Unit", "Orang", "ton", "Liter", "Ha/Bulan", "Tunggul Pohon", "LS",
    "orang/bulan", "orang/jam", "orang/kegiatan", "Lump Sum", "Titik",
    "Titik Lokasi", "Roll", "Hektare", "set", "Buah", "1 x", "Pohon", "cm",
    "Pola", "sampel", "Rupiah/Jam", "M3/Km", "Buah Jembatan", "Kegiatan",
    "Lembar", "Pengujian", "Lokasi", "Per potong",
)

# --- kumpulan daftar panjang yang ditempel ke sheet rujukan Excel -----------

DAFTAR_RUJUKAN: dict[str, tuple[str, ...]] = {
    "Satuan Produk": SATUAN_PRODUK,
    "Satuan Pengukuran (Bina Marga)": SATUAN_PENGUKURAN_BINA_MARGA,
    "Lokasi Produksi": LOKASI_PRODUKSI,
    "Tenaga Kerja": TENAGA_KERJA,
    "Bahan Baku": BAHAN_BAKU,
}


__all__ = [
    "AKTIF",
    "BAHAN_BAKU",
    "DAFTAR_RUJUKAN",
    "KEPEMILIKAN",
    "KLASIFIKASI_PDN",
    "LOKASI_PRODUKSI",
    "OPSI_ONGKIR",
    "PPN",
    "SATUAN_PENGUKURAN_BINA_MARGA",
    "SATUAN_PRODUK",
    "TENAGA_KERJA",
    "YA_TIDAK",
]
