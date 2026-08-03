"""Objek inti: satu baris produk beserta status eksekusinya."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum

from .schema import attachment_pairs, attribute_pairs, split_category


class Status(str, Enum):
    MENUNGGU = "menunggu"
    BERJALAN = "berjalan"
    SUKSES = "sukses"
    GAGAL = "gagal"
    DILEWATI = "dilewati"

    @property
    def label(self) -> str:
        return {
            Status.MENUNGGU: "Menunggu",
            Status.BERJALAN: "Proses",
            Status.SUKSES: "Sukses",
            Status.GAGAL: "Gagal",
            Status.DILEWATI: "Dilewati",
        }[self]

    @property
    def symbol(self) -> str:
        return {
            Status.MENUNGGU: "○",
            Status.BERJALAN: "⟳",
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

    @property
    def tipe_produk(self) -> str:
        return self.data.get("tipe_produk", "")

    @property
    def atribut(self) -> dict[str, str]:
        return attribute_pairs(self.data)

    @property
    def lampiran(self) -> dict[str, str]:
        return attachment_pairs(self.data)

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


__all__ = ["ProductRow", "Status", "rows_from_records"]
