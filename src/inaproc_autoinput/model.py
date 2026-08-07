"""Objek inti: satu baris produk beserta status eksekusinya."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum

from .schema import attribute_pairs, split_category


class Status(str, Enum):
    MENUNGGU = "menunggu"
    BERJALAN = "berjalan"
    # Form sudah terisi tapi belum disimpan -- hasil mode "Isi saja". Bukan
    # sukses: tidak ada apa pun yang masuk ke portal, jadi baris ini masih
    # harus dikerjakan. Menyamakannya dengan sukses akan membuat "Lanjutkan
    # sisanya" melewatinya diam-diam.
    TERISI = "terisi"
    SUKSES = "sukses"
    GAGAL = "gagal"
    DILEWATI = "dilewati"

    @property
    def label(self) -> str:
        return {
            Status.MENUNGGU: "Menunggu",
            Status.BERJALAN: "Proses",
            Status.TERISI: "Terisi",
            Status.SUKSES: "Sukses",
            Status.GAGAL: "Gagal",
            Status.DILEWATI: "Dilewati",
        }[self]

    @property
    def symbol(self) -> str:
        return {
            Status.MENUNGGU: "○",
            Status.BERJALAN: "⟳",
            Status.TERISI: "◐",
            Status.SUKSES: "✓",
            Status.GAGAL: "✗",
            Status.DILEWATI: "–",
        }[self]


@dataclass
class ProductRow:
    """Satu baris produk dari template, plus hasil eksekusinya."""

    excel_row: int
    data: dict
    status: Status = Status.MENUNGGU
    message: str = ""
    produk_id: str = ""  # id produk di INAPROC setelah berhasil dibuat
    issues: list = field(default_factory=list)

    @property
    def nama(self) -> str:
        return self.data.get("nama_produk", "")

    @property
    def kategori(self) -> str:
        return self.data.get("kategori", "")

    @property
    def kategori_3(self) -> str:
        """Bagian paling spesifik dari jalur kategori, untuk ditampilkan di tabel."""
        return split_category(self.data.get("kategori", ""))[2]

    # Diisi saat baris dibaca, dari katalog portal -- bukan dari kolom Excel.
    # Portal yang menentukan tipe dari kategorinya, jadi penyedia tidak perlu
    # menuliskannya dan tidak bisa menuliskannya keliru.
    tipe_portal: str = ""

    @property
    def tipe_produk(self) -> str:
        return self.tipe_portal

    @property
    def atribut(self) -> dict[str, str]:
        return attribute_pairs(self.data)

    @property
    def blocking_issues(self) -> list:
        return [i for i in self.issues if i.blocking]

    @property
    def siap(self) -> bool:
        """Baris boleh dijalankan bila belum sukses dan tidak punya error."""
        return self.status != Status.SUKSES and not self.blocking_issues

    def fingerprint(self) -> str:
        """Sidik jari isi baris, untuk mendeteksi data yang berubah sejak dijalankan.

        Kalau penyedia mengubah harga sebuah produk setelah baris itu sukses,
        status suksesnya tidak lagi mewakili apa yang ada di file -- dan aplikasi
        harus tahu itu, bukan diam-diam menganggapnya masih selesai.
        """
        payload = {k: v for k, v in sorted(self.data.items()) if k != "_row"}
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def rows_from_records(records: list[dict]) -> list[ProductRow]:
    return [ProductRow(excel_row=r.get("_row", 0), data=r) for r in records]


def antrean(rows: list[ProductRow], lewati_gagal: bool = False) -> list[int]:
    """Posisi baris yang akan dikerjakan sebuah antrean.

    Dua hal selalu dilewati, apa pun tombolnya:

    * **Sukses** -- mengulangnya membuat produk *kedua* di portal, bukan
      memperbarui yang pertama. Ini tidak bisa dibatalkan dari sini.
    * **Baris ber-error** -- sudah pasti ditolak, dan menghabiskan setengah
      menit masing-masing untuk membuktikannya.

    `lewati_gagal` yang membedakan dua tombol: "Jalankan semua" mengulang baris
    yang gagal, "Lanjutkan sisanya" tidak. Baris yang gagal umumnya perlu
    diperbaiki dulu -- mengulangnya apa adanya cuma menghasilkan kegagalan yang
    sama. Baris **Terisi** ikut di keduanya: belum ada apa pun yang masuk ke
    portal, jadi pekerjaannya belum selesai.
    """
    return [
        i for i, row in enumerate(rows)
        if row.siap and not (lewati_gagal and row.status is Status.GAGAL)
    ]


__all__ = ["ProductRow", "Status", "antrean", "rows_from_records"]
