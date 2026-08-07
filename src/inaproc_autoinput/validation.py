"""Pemeriksaan baris produk sebelum dijalankan ke portal.

Semua yang bisa diketahui tanpa membuka portal diperiksa di sini. Mengisi satu
produk lewat form makan waktu setengah sampai satu menit; menemukan kategori
yang salah ketik di detik ke-50 itu pemborosan yang bisa dihindari.

Yang diperiksa hanya isi baris Excel. Berkas -- foto, video, dokumen PDF --
diperiksa terpisah di `assets.py`, karena berlaku untuk semua baris sekaligus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import (
    TIPE_BARANG,
    Field,
    all_fields,
    attribute_pairs,
    incomplete_pairs,
    split_category,
)

# Kolom yang wajib diisi hanya bila kolom pemicunya bernilai tertentu.
CONDITIONAL = {"pre_order_hari": ("pre_order", "Aktif")}

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    key: str
    label: str
    message: str
    blocking: bool = True

    def __str__(self) -> str:
        return f"{self.label}: {self.message}"


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


# Form membatasi desimal maksimal dua digit ("Maks. 2 digit di belakang koma").
# Lebih dari dua digit setelah titik hampir pasti pemisah ribuan, bukan desimal.
_ANGKA_SAH = re.compile(r"\d+([.,]\d{1,2})?$")
# Diawali angka bukan nol: "0,055" itu desimal tiga digit, bukan ribuan.
_RIBUAN = re.compile(r"^[1-9]\d{0,2}([.,]\d{3})+$")


def _periksa_angka(text: str, key: str) -> list[str]:
    """Periksa satu nilai numerik.

    Yang paling berbahaya bukan angka yang jelas salah, tapi '1.000'. Ditulis
    orang Indonesia untuk seribu, dibaca portal sebagai satu. Kalau dibiarkan
    lewat, stok meleset seribu kali lipat tanpa ada yang menyadarinya -- jadi
    pola pemisah ribuan ditolak dengan pesan yang menyebut angka benarnya.
    """
    if _RIBUAN.fullmatch(text):
        polos = re.sub(r"[.,]", "", text)
        utuh = re.split(r"[.,]", text)[0]
        return [f"'{text}' terbaca portal sebagai {utuh}, bukan {polos}. "
                f"Tulis tanpa pemisah ribuan: {polos}"]
    if not _ANGKA_SAH.fullmatch(text):
        return [f"'{text}' harus angka polos, tanpa pemisah ribuan atau 'Rp'. "
                "Desimal maksimal dua digit"]
    if key == "harga_produk" and float(text.replace(",", ".")) == 0:
        return ["harga tidak boleh 0"]
    return []


def _check_field(fld: Field, row: dict, tipe: str) -> list[Issue]:
    issues: list[Issue] = []

    def add(message: str, blocking: bool = True) -> None:
        issues.append(Issue(fld.key, fld.label, message, blocking))

    value = row.get(fld.key)

    if not fld.applies_to(tipe):
        # Bagian Pengiriman, PPnBM, dan TKDN memang tidak muncul di form untuk
        # kategori Jasa dan Digital, jadi isinya pasti terabaikan.
        if not _blank(value):
            add(f"tidak dipakai untuk produk tipe {tipe}, akan diabaikan",
                blocking=False)
        return issues

    if _blank(value):
        if fld.required:
            add("wajib diisi")
        elif fld.key == "berat_gram" and tipe == TIPE_BARANG:
            add("produk tipe Barang wajib mengisi berat")
        elif fld.key in CONDITIONAL:
            pemicu, nilai = CONDITIONAL[fld.key]
            if str(row.get(pemicu, "")).strip() == nilai:
                add(f"wajib diisi karena {pemicu} bernilai {nilai}")
        return issues

    text = str(value).strip()

    if fld.options and text not in fld.options:
        add(f"'{text}' tidak sah; pilihan: {', '.join(fld.options)}")

    if fld.min_len and len(text) < fld.min_len:
        add(f"panjang {len(text)} karakter, minimum {fld.min_len}")
    if fld.max_len and len(text) > fld.max_len:
        add(f"panjang {len(text)} karakter, maksimum {fld.max_len}")

    if fld.numeric:
        add_numerik = _periksa_angka(text, fld.key)
        for pesan in add_numerik:
            add(pesan)

    return issues


def _check_category(row: dict, catalog) -> tuple[list[Issue], str]:
    """Cocokkan jalur kategori dengan daftar resmi portal.

    Mengembalikan (temuan, tipe_produk). Tipe hasil pencocokan dipakai untuk
    menentukan apakah bagian Pengiriman, PPnBM, dan TKDN berlaku -- lebih bisa
    dipercaya daripada kolom Tipe Produk yang diisi tangan.
    """
    jalur = row.get("kategori", "")
    node, pesan = catalog.resolve_path(jalur)
    if node is None:
        return [Issue("kategori", "Kategori", pesan)], ""

    issues: list[Issue] = []
    level1 = split_category(jalur)[0]
    if level1 and not catalog.in_scope(level1):
        issues.append(Issue(
            "kategori", "Kategori",
            f"'{level1}' di luar bidang yang dilayani, jadi tidak ada di sheet "
            "'Daftar Kategori'. Kategorinya sah — pastikan ini memang disengaja.",
            blocking=False,
        ))

    return issues, node.tipe_produk


def _check_pairs(row: dict, assets=None) -> list[Issue]:
    """Blok atribut: slot harus terisi lengkap atau kosong sama sekali.

    Kecuali bila nilainya bisa diambil dari dokumen bernama sama yang sudah
    dipilih di panel Berkas -- itu bukan kekurangan, cuma pengisian dari sumber
    lain.
    """
    issues: list[Issue] = []
    for _, nama, nilai in incomplete_pairs(row):
        if nama:
            dari_berkas = assets.nilai_atribut(nama) if assets is not None else ""
            if dari_berkas:
                issues.append(Issue(
                    nama, f"Atribut '{nama}'",
                    f"diisi dari dokumen: {dari_berkas}", blocking=False,
                ))
                continue
            issues.append(Issue(nama, f"Atribut '{nama}'", "nilainya belum diisi"))
        else:
            issues.append(Issue(
                "atribut", "Atribut", f"'{nilai}' diisi tapi nama atributnya kosong"
            ))
    return issues


def validate(
    row: dict, fields: tuple[Field, ...] | None = None, catalog=None, assets=None
) -> list[Issue]:
    fields = fields or all_fields()
    issues: list[Issue] = []
    # Tipe produk hanya datang dari katalog portal. Tidak ada kolomnya di Excel
    # karena portal yang menentukan, dan menyalinnya ke spreadsheet cuma
    # membuka peluang penyedia menulis sesuatu yang bertentangan.
    tipe = ""

    if catalog is not None and not catalog.kosong:
        temuan, tipe = _check_category(row, catalog)
        issues.extend(temuan)

    for fld in fields:
        if fld.group.startswith("Atribut"):
            continue  # blok berpasangan diperiksa terpisah
        issues.extend(_check_field(fld, row, tipe))

    issues.extend(_check_pairs(row, assets))

    if _blank(row.get("kbki")):
        # Portal tetap mewajibkannya. Kalau dilewati diam-diam, produk baru
        # ketahuan tidak bisa disimpan setelah seluruh form terisi.
        issues.append(Issue(
            "kbki", "Kode KBKI",
            "kosong — aplikasi melewatinya; pilih sendiri di portal sebelum menyimpan",
            blocking=False,
        ))

    if not attribute_pairs(row):
        issues.append(Issue(
            "atribut_1_nama", "Atribut Khusus Kategori",
            "belum ada atribut diisi — hampir semua kategori mewajibkan beberapa",
            blocking=False,
        ))

    return issues


def summarize(issues: list[Issue]) -> str:
    blocking = sum(1 for i in issues if i.blocking)
    return f"{blocking} error, {len(issues) - blocking} peringatan"


__all__ = ["Issue", "validate", "summarize"]
