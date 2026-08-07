"""Berkas yang diunggah ke portal: foto, video, dan dokumen PDF.

Dulu semuanya jadi kolom di Excel berisi path. Itu keliru karena tiga hal:
path yang diketik tangan rawan salah dan tidak bisa diperiksa saat mengetik;
dokumen perusahaan seperti SBU sama untuk seluruh baris sehingga menuliskannya
puluhan kali cuma pengulangan; dan spreadsheet bukan tempat yang wajar untuk
memilih berkas.

Sekarang berkas dipilih lewat panel di aplikasi, dan disimpan di berkas
pendamping `<nama>.berkas.json` di sebelah workbook -- sama seperti status,
supaya file Excel penyedia tidak pernah ditulisi.

Dua tingkat:

* **Dokumen** dan **foto umum** berlaku untuk semua baris. Ini yang lazim:
  satu SBU, satu sertifikat standar, satu foto perusahaan.
* **Foto per baris** menimpa foto umum, untuk produk yang punya foto sendiri.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .placeholder import PLACEHOLDER_PATH, adalah_placeholder, pastikan
from .schema import (
    BATAS_DOKUMEN_MB,
    BATAS_VIDEO_MB,
    DOKUMEN_EXT,
    FOTO_EXT,
    VIDEO_EXT,
)

SUFFIX = ".berkas.json"
MAKS_FOTO = 5

# Empat dokumen yang diminta kategori konstruksi. Dipakai sebagai saran awal di
# panel Berkas, bukan sebagai aturan -- daftar sebenarnya dibaca dari form saat
# baris dijalankan, karena tiap kategori bisa berbeda.
DOKUMEN_LAZIM = (
    "Sertifikat Badan Usaha (SBU) Konstruksi",
    "Masa Berlaku Sertifikat Badan Usaha (SBU) Konstruksi",
    "Sertifikat Standar",
    "Komponen Struktur Biaya Tayang",
)

# Portal meminta berkas terpisah untuk masa berlaku SBU, padahal isinya dokumen
# yang sama. Panel Berkas memakai ini untuk mengikutkan otomatis.
IKUT_BERKAS = {
    "Masa Berlaku Sertifikat Badan Usaha (SBU) Konstruksi":
        "Sertifikat Badan Usaha (SBU) Konstruksi",
}


def state_path(workbook: str | Path) -> Path:
    workbook = Path(workbook)
    return workbook.with_name(workbook.stem + SUFFIX)


def periksa(path_teks: str, ekstensi: tuple[str, ...], maks_mb: int = 0) -> str:
    """Kembalikan pesan masalah, atau string kosong bila berkasnya sehat."""
    if not str(path_teks or "").strip():
        return "belum dipilih"
    path = Path(path_teks).expanduser()
    if path.suffix.lower() not in ekstensi:
        return f"format harus {' atau '.join(ekstensi)}, bukan '{path.suffix or '?'}'"
    if not path.exists():
        return f"berkas tidak ditemukan: {path}"
    if not path.is_file():
        return f"bukan berkas: {path}"
    if maks_mb and path.stat().st_size / (1024 * 1024) > maks_mb:
        ukuran = path.stat().st_size / (1024 * 1024)
        return f"ukuran {ukuran:.1f} MB, batasnya {maks_mb} MB"
    return ""


@dataclass
class Assets:
    """Berkas untuk satu workbook."""

    dokumen: dict[str, str] = field(default_factory=dict)
    foto_umum: list[str] = field(default_factory=list)
    foto_baris: dict[int, list[str]] = field(default_factory=dict)
    video: str = ""
    video_url: str = ""
    # Baris tanpa foto tidak bisa dijalankan sama sekali karena form mewajibkan
    # minimal satu. Placeholder membuka jalan, tapi pemakaiannya selalu
    # dilaporkan -- lihat catatan().
    pakai_placeholder: bool = True

    # --- penggunaan ---------------------------------------------------------

    def foto_untuk(self, excel_row: int) -> list[str]:
        """Foto khusus baris bila ada, lalu foto umum, lalu placeholder."""
        khusus = self.foto_baris.get(excel_row)
        if khusus:
            return list(khusus)
        if self.foto_umum:
            return list(self.foto_umum)
        return [str(pastikan())] if self.pakai_placeholder else []

    def baris_pakai_placeholder(self, excel_row: int) -> bool:
        foto = self.foto_untuk(excel_row)
        return bool(foto) and adalah_placeholder(foto[0])

    def nilai_atribut(self, nama: str) -> str:
        """Nilai atribut yang bisa diambil dari dokumen bernama sama.

        Beberapa atribut di form berpasangan dengan lampiran berjudul persis
        sama -- "Masa Berlaku SBU Konstruksi" dan "Komponen Struktur Biaya
        Tayang" punya kolom teks sekaligus unggahan PDF. Kalau dokumennya sudah
        dipilih, nama berkasnya dipakai sebagai isi kolom teksnya, jadi tidak
        perlu diketik ulang di Excel.
        """
        berkas = self.dokumen.get(str(nama or "").strip())
        return Path(berkas).stem if berkas else ""

    def baris_berfoto_sendiri(self) -> list[int]:
        return sorted(self.foto_baris)

    def set_foto_baris(self, excel_row: int, berkas: list[str]) -> None:
        if berkas:
            self.foto_baris[excel_row] = list(berkas[:MAKS_FOTO])
        else:
            self.foto_baris.pop(excel_row, None)

    def set_dokumen(self, nama: str, path_teks: str) -> None:
        """Pasang dokumen, sekaligus yang mengikutinya (masa berlaku SBU)."""
        if path_teks:
            self.dokumen[nama] = path_teks
        else:
            self.dokumen.pop(nama, None)
        for pengikut, sumber in IKUT_BERKAS.items():
            if sumber == nama:
                if path_teks:
                    self.dokumen[pengikut] = path_teks
                else:
                    self.dokumen.pop(pengikut, None)

    @property
    def kosong(self) -> bool:
        return not (self.dokumen or self.foto_umum or self.foto_baris
                    or self.video or self.video_url)

    # --- pemeriksaan --------------------------------------------------------

    def masalah(self, excel_row: int | None = None) -> list[str]:
        """Daftar masalah berkas. Bila `excel_row` diberi, foto dicek per baris."""
        pesan: list[str] = []

        foto = self.foto_untuk(excel_row) if excel_row is not None else self.foto_umum
        # Tanpa nomor baris, foto khusus per baris ikut dihitung -- kalau tidak,
        # ringkasan akan terus mengeluh "belum ada foto" padahal setiap baris
        # sudah punya fotonya masing-masing. Placeholder juga menutup celah ini,
        # dan pemakaiannya dilaporkan lewat catatan(), bukan sebagai masalah.
        ada_foto = bool(foto) or self.pakai_placeholder or (
            excel_row is None and bool(self.foto_baris)
        )
        if not ada_foto:
            pesan.append("Foto: belum ada foto dipilih; produk wajib punya minimal satu")
        for berkas in foto:
            galat = periksa(berkas, FOTO_EXT)
            if galat:
                pesan.append(f"Foto {Path(berkas).name}: {galat}")

        if self.video:
            galat = periksa(self.video, VIDEO_EXT, BATAS_VIDEO_MB)
            if galat:
                pesan.append(f"Video: {galat}")

        if self.video_url and not self.video_url.lower().startswith(("http://", "https://")):
            pesan.append("URL Video: harus diawali http:// atau https://")

        for nama, berkas in sorted(self.dokumen.items()):
            galat = periksa(berkas, DOKUMEN_EXT, BATAS_DOKUMEN_MB)
            if galat:
                pesan.append(f"Dokumen '{nama}': {galat}")
        return pesan

    def siap(self, excel_row: int | None = None) -> bool:
        return not self.masalah(excel_row)

    def catatan(self) -> list[str]:
        """Hal yang perlu diperhatikan, tapi belum tentu salah.

        Dokumen wajib berbeda tiap kategori dan baru diketahui setelah form
        terbuka -- kategori Barang seperti Meja Kerja bisa jadi tidak minta
        satu pun. Karena itu "belum ada dokumen" cuma diingatkan, bukan
        dihitung sebagai masalah yang memblokir.
        """
        pesan = []
        if not self.foto_umum and self.pakai_placeholder:
            khusus = len(self.foto_baris)
            sisa = " kecuali {} baris berfoto sendiri".format(khusus) if khusus else ""
            pesan.append(
                f"Semua baris{sisa} akan memakai foto placeholder. Produk yang "
                "tayang dengan gambar ini terlihat jelas belum berfoto — ganti "
                "sebelum menyimpan ke portal."
            )
        if not self.dokumen:
            pesan.append("Belum ada dokumen dipilih. Kategori konstruksi biasanya "
                         "mewajibkan SBU dan sertifikat standar.")
        return pesan

    # --- penyimpanan --------------------------------------------------------

    def save(self, workbook: str | Path) -> Path:
        path = state_path(workbook)
        payload = {
            "dokumen": self.dokumen,
            "foto_umum": self.foto_umum,
            "foto_baris": {str(k): v for k, v in self.foto_baris.items()},
            "video": self.video,
            "video_url": self.video_url,
            "pakai_placeholder": self.pakai_placeholder,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
        return path

    @classmethod
    def load(cls, workbook: str | Path) -> "Assets":
        path = state_path(workbook)
        if not path.exists():
            return cls()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()

        baris: dict[int, list[str]] = {}
        for kunci, nilai in (payload.get("foto_baris") or {}).items():
            try:
                baris[int(kunci)] = list(nilai)
            except (TypeError, ValueError):
                continue
        return cls(
            dokumen=dict(payload.get("dokumen") or {}),
            foto_umum=list(payload.get("foto_umum") or []),
            foto_baris=baris,
            video=payload.get("video", "") or "",
            video_url=payload.get("video_url", "") or "",
            pakai_placeholder=bool(payload.get("pakai_placeholder", True)),
        )


__all__ = [
    "Assets",
    "PLACEHOLDER_PATH",
    "DOKUMEN_LAZIM",
    "IKUT_BERKAS",
    "MAKS_FOTO",
    "periksa",
    "state_path",
]
