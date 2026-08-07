"""Definisi template Excel universal yang diisi penyedia.

Disusun dari pembacaan langsung form `penyedia.inaproc.id/products/add` untuk
kategori Jasa (3.1 Galian) dan Barang (Meja Kerja) -- lihat
`docs/form-tambah-produk.md`.

Tiga bagian:

* **Kolom inti** -- selalu ada, apa pun kategorinya.
* **Kolom khusus Barang** -- bagian Pengiriman, TKDN, dan PPnBM hanya muncul
  bila kategorinya bertipe Barang. Untuk Jasa dan Digital dikosongkan.
* **Blok atribut** -- pasangan Atribut/Nilai untuk `Spesifikasi Produk >
  Informasi Utama`, yang isinya berbeda tiap Kategori Level 3. Di form
  bentuknya array berindeks, bukan field bernama tetap.

Foto, video, dan dokumen PDF sengaja tidak ada di sini -- semuanya dipilih
lewat panel Berkas di aplikasi. Lihat `assets.py`.

Kategori ditulis sebagai **satu kolom berisi jalur lengkap**, mengikuti bentuk
pemilihnya di portal: satu kotak pencarian bertingkat, bukan tiga dropdown.
Ini juga menghilangkan ambiguitas 71 nama Level 3 yang dipakai lebih dari
sekali di seluruh katalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import references as ref

TIPE_BARANG = "Barang"
TIPE_JASA = "Jasa"
TIPE_DIGITAL = "Digital"
TIPE_PRODUK = (TIPE_BARANG, TIPE_JASA, TIPE_DIGITAL)

JUMLAH_SLOT_ATRIBUT = 8

PEMISAH_KATEGORI = " > "

FOTO_EXT = (".jpg", ".jpeg", ".png")
VIDEO_EXT = (".mp4", ".mov")
DOKUMEN_EXT = (".pdf",)

BATAS_VIDEO_MB = 50
BATAS_DOKUMEN_MB = 10


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    group: str
    required: bool = False
    options: tuple[str, ...] = ()
    hint: str = ""
    numeric: bool = False
    url: bool = False
    file_ext: tuple[str, ...] = ()
    max_mb: int = 0
    min_len: int = 0
    max_len: int = 0
    # Kosong berarti berlaku untuk semua tipe produk.
    only_for: tuple[str, ...] = field(default_factory=tuple)
    # Nama daftar di sheet rujukan, dipakai bila pilihannya terlalu panjang
    # untuk ditulis langsung di sel (batas Excel 255 karakter).
    lookup: str = ""
    width: int = 22

    @property
    def is_file(self) -> bool:
        return bool(self.file_ext)

    def applies_to(self, tipe: str) -> bool:
        return not self.only_for or not tipe or tipe in self.only_for


G_KATEGORI = "Kategori"
G_PRODUK = "Informasi Produk"
G_PDN = "KBKI & PDN"
G_PAJAK = "Pajak"
G_HARGA = "Harga & Stok"
G_KIRIM = "Pengiriman (khusus Barang)"
G_ATRIBUT = "Atribut Khusus Kategori"

CORE_FIELDS: tuple[Field, ...] = (
    # --- Kategori: satu kolom jalur lengkap, seperti kotak pencarian di portal.
    Field("kategori", "Kategori", G_KATEGORI, required=True,
          hint="Salin dari sheet 'Daftar Kategori'. Format: Level 1 > Level 2 > Level 3",
          width=64),

    # --- Informasi produk
    Field("produk_sektoral", "Daftar Produk Sektoral", G_PRODUK, required=True,
          hint="Dipilih dari daftar baku milik kategori tersebut", width=30),
    Field("nama_produk", "Nama Produk", G_PRODUK, required=True,
          min_len=5, max_len=250, width=44),
    Field("deskripsi", "Deskripsi", G_PRODUK, max_len=2000, width=44),

    # --- KBKI & PDN
    # Wajib di portal, tapi bukan di sini: daftar kode yang sah berbeda tiap
    # kategori dan tidak bisa ditebak dari luar, jadi lebih sering dipilih
    # sendiri di form. Dikosongkan berarti aplikasi melewatinya dan kamu yang
    # memilih di portal sebelum menyimpan -- diingatkan, bukan diblokir.
    Field("kbki", "Kode KBKI", G_PDN,
          hint="Boleh kosong; kalau kosong dipilih manual di portal", width=16),
    Field("pdn_klasifikasi", "Klasifikasi Produk", G_PDN, required=True,
          options=ref.KLASIFIKASI_PDN, width=18),
    # Tiga pertanyaan self-declare PDN tidak bertanda Wajib di form -- portal
    # sudah mengisinya dengan jawaban bawaan. Dibiarkan opsional supaya baris
    # tidak diblokir untuk sesuatu yang portal sendiri tidak wajibkan.
    Field("pdn_lokasi_produksi", "Lokasi Produksi", G_PDN,
          options=ref.LOKASI_PRODUKSI, lookup="Lokasi Produksi",
          hint="Kosong berarti memakai jawaban bawaan portal", width=32),
    Field("pdn_tenaga_kerja", "Tenaga Kerja dalam Proses Produksi", G_PDN,
          options=ref.TENAGA_KERJA, lookup="Tenaga Kerja", width=32),
    Field("pdn_bahan_baku", "Bahan Baku dalam Proses Produksi", G_PDN,
          options=ref.BAHAN_BAKU, lookup="Bahan Baku", width=32),

    # --- Pajak
    Field("ppn", "PPN", G_PAJAK, required=True, options=ref.PPN, width=12),

    # --- Harga & stok
    Field("minimum_pembelian", "Minimum Pembelian", G_HARGA, numeric=True,
          hint="Kosong berarti 1", width=18),
    Field("harga_produk", "Harga Produk", G_HARGA, required=True, numeric=True,
          hint="Angka polos, di luar pajak & ongkir, tidak boleh 0", width=18),
    Field("stok", "Jumlah Stok", G_HARGA, required=True, numeric=True, width=14),
    Field("satuan_produk", "Satuan Produk", G_HARGA, required=True,
          options=ref.SATUAN_PRODUK, lookup="Satuan Produk", width=18),
    Field("pre_order", "Pre Order", G_HARGA, options=ref.AKTIF, width=14),
    Field("pre_order_hari", "Pre Order - Hari", G_HARGA, numeric=True,
          hint="Wajib bila Pre Order aktif", width=16),

    # --- Pengiriman: bagian ini hanya muncul untuk kategori bertipe Barang.
    Field("berat_gram", "Berat Produk (gram)", G_KIRIM, numeric=True,
          only_for=(TIPE_BARANG,),
          hint="Berat setelah dikemas. 1 kg = 1000 gram", width=20),
    Field("panjang_cm", "Panjang (cm)", G_KIRIM, numeric=True,
          only_for=(TIPE_BARANG,), width=14),
    Field("lebar_cm", "Lebar (cm)", G_KIRIM, numeric=True,
          only_for=(TIPE_BARANG,), width=14),
    Field("tinggi_cm", "Tinggi (cm)", G_KIRIM, numeric=True,
          only_for=(TIPE_BARANG,), width=14),
)


def perlu_kuantitas_desimal(row: dict) -> bool:
    """Apakah saklar Kuantitas Desimal perlu dinyalakan untuk baris ini.

    Disimpulkan, bukan ditanyakan: stok 332,35 jelas butuh desimal, stok 1
    tidak. Menanyakannya lewat kolom cuma menambah satu hal yang bisa salah
    tanpa menambah keputusan.
    """
    for kunci in ("stok", "minimum_pembelian"):
        teks = str(row.get(kunci, "") or "").strip().replace(",", ".")
        if "." in teks:
            try:
                if float(teks) != int(float(teks)):
                    return True
            except ValueError:
                continue
    return False


def attribute_fields(slots: int = JUMLAH_SLOT_ATRIBUT) -> tuple[Field, ...]:
    """Pasangan Atribut/Nilai untuk Spesifikasi Produk > Informasi Utama."""
    out: list[Field] = []
    for i in range(1, slots + 1):
        hint = (
            "Tulis nama atribut persis seperti di form, mis. Satuan Pengukuran"
            if i == 1 else ""
        )
        out.append(Field(f"atribut_{i}_nama", f"Atribut {i}", G_ATRIBUT,
                         hint=hint, width=26))
        out.append(Field(f"atribut_{i}_nilai", f"Nilai {i}", G_ATRIBUT, width=26))
    return tuple(out)


def all_fields(slots: int = JUMLAH_SLOT_ATRIBUT) -> tuple[Field, ...]:
    return CORE_FIELDS + attribute_fields(slots)


def by_key(fields: tuple[Field, ...] = ()) -> dict[str, Field]:
    return {f.key: f for f in (fields or all_fields())}


def split_category(value: str) -> tuple[str, str, str]:
    """'A > B > C' -> ('A', 'B', 'C'). Bagian yang kurang jadi string kosong."""
    bagian = [b.strip() for b in str(value or "").split(">")]
    bagian += [""] * (3 - len(bagian))
    return bagian[0], bagian[1], bagian[2]


def join_category(*bagian: str) -> str:
    return PEMISAH_KATEGORI.join(b for b in bagian if b)


def _pairs(row: dict, prefix: str, kedua: str, slots: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for i in range(1, slots + 1):
        nama = str(row.get(f"{prefix}_{i}_nama", "") or "").strip()
        nilai = str(row.get(f"{prefix}_{i}_{kedua}", "") or "").strip()
        if nama or nilai:
            out.append((nama, nilai))
    return out


def attribute_pairs(row: dict, slots: int = JUMLAH_SLOT_ATRIBUT) -> dict[str, str]:
    return {n: v for n, v in _pairs(row, "atribut", "nilai", slots) if n}


def incomplete_pairs(row: dict) -> list[tuple[str, str, str]]:
    """Slot atribut yang hanya terisi separuh -- (jenis, nama, nilai)."""
    return [
        ("atribut", nama, nilai)
        for nama, nilai in _pairs(row, "atribut", "nilai", JUMLAH_SLOT_ATRIBUT)
        if not nama or not nilai
    ]


__all__ = [
    "CORE_FIELDS",
    "DOKUMEN_EXT",
    "FOTO_EXT",
    "Field",
    "JUMLAH_SLOT_ATRIBUT",
    "PEMISAH_KATEGORI",
    "TIPE_BARANG",
    "TIPE_DIGITAL",
    "TIPE_JASA",
    "TIPE_PRODUK",
    "VIDEO_EXT",
    "all_fields",
    "perlu_kuantitas_desimal",
    "attribute_fields",
    "attribute_pairs",
    "by_key",
    "incomplete_pairs",
    "join_category",
    "split_category",
]
