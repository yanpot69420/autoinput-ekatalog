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

    # --- penggunaan ---------------------------------------------------------

    def foto_untuk(self, excel_row: int) -> list[str]:
        """Foto khusus baris bila ada, selain itu foto umum."""
        khusus = self.foto_baris.get(excel_row)
        return list(khusus) if khusus else list(self.foto_umum)

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
        if not foto and not (excel_row is None and self.foto_baris):
            # Tanpa nomor baris, foto khusus per baris ikut dihitung -- kalau
            # tidak, ringkasan akan terus mengeluh "belum ada foto" padahal
            # setiap baris sudah punya fotonya masing-masing.
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
        if not self.dokumen:
            return ["Belum ada dokumen dipilih. Kategori konstruksi biasanya "
                    "mewajibkan SBU dan sertifikat standar."]
        return []

    # --- penyimpanan --------------------------------------------------------

    def save(self, workbook: str | Path) -> Path:
        path = state_path(workbook)
        payload = {
            "dokumen": self.dokumen,
            "foto_umum": self.foto_umum,
            "foto_baris": {str(k): v for k, v in self.foto_baris.items()},
            "video": self.video,
            "video_url": self.video_url,
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
        )


__all__ = [
    "Assets",
    "DOKUMEN_LAZIM",
    "IKUT_BERKAS",
    "MAKS_FOTO",
    "periksa",
    "state_path",
]
