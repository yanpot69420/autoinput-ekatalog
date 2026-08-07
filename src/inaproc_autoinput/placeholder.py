"""Foto sementara untuk produk yang fotonya belum disiapkan.

Form mewajibkan minimal satu foto, jadi baris tanpa foto tidak bisa dijalankan
sama sekali. Placeholder membuka jalan supaya pengisian tidak tertahan hanya
karena fotonya belum ada -- tapi ia sengaja dibuat mencolok: kotak abu dengan
silang besar dan bingkai tebal. Produk yang tayang dengan gambar ini akan
langsung terlihat salah, dan itu memang tujuannya.

Gambarnya dihasilkan sendiri, bukan dibundel: PNG ditulis langsung dengan
`zlib` dan `struct` supaya paket ini tidak perlu Pillow hanya untuk satu
gambar. Ukurannya 700x700, persis ukuran optimal yang diminta portal (batasnya
300x300 sampai 2048x2048).
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

PLACEHOLDER_PATH = Path.home() / ".inaproc-autoinput" / "foto-placeholder.png"

SISI = 700
_LATAR = (232, 234, 237)
_GARIS = (154, 160, 166)
_SILANG = (196, 199, 197)
_TEBAL_BINGKAI = 10
_TEBAL_SILANG = 14


def _potongan(jenis: bytes, data: bytes) -> bytes:
    isi = jenis + data
    return struct.pack(">I", len(data)) + isi + struct.pack(">I", zlib.crc32(isi))


def _piksel(sisi: int) -> bytearray:
    """Baris piksel RGB, satu byte filter 0 di depan tiap baris."""
    baris = bytearray()
    for y in range(sisi):
        baris.append(0)  # filter None
        for x in range(sisi):
            di_bingkai = (
                x < _TEBAL_BINGKAI or y < _TEBAL_BINGKAI
                or x >= sisi - _TEBAL_BINGKAI or y >= sisi - _TEBAL_BINGKAI
            )
            # Dua diagonal, digambar dengan jarak titik ke garis y=x dan y=-x.
            di_silang = (
                abs(x - y) < _TEBAL_SILANG or abs(x + y - (sisi - 1)) < _TEBAL_SILANG
            )
            warna = _GARIS if di_bingkai else (_SILANG if di_silang else _LATAR)
            baris.extend(warna)
    return baris


def buat(path: Path | None = None, sisi: int = SISI) -> Path:
    """Tulis ulang berkas placeholder, menimpa yang lama."""
    path = path or PLACEHOLDER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    ihdr = struct.pack(">IIBBBBB", sisi, sisi, 8, 2, 0, 0, 0)  # 8-bit RGB
    isi = (
        b"\x89PNG\r\n\x1a\n"
        + _potongan(b"IHDR", ihdr)
        + _potongan(b"IDAT", zlib.compress(bytes(_piksel(sisi)), 9))
        + _potongan(b"IEND", b"")
    )
    path.write_bytes(isi)
    return path


def pastikan(path: Path | None = None) -> Path:
    """Kembalikan path placeholder, buat dulu bila belum ada."""
    path = path or PLACEHOLDER_PATH
    if not path.exists():
        return buat(path)
    return path


def adalah_placeholder(berkas: str, path: Path | None = None) -> bool:
    path = path or PLACEHOLDER_PATH
    try:
        return Path(berkas).resolve() == path.resolve()
    except OSError:
        return False


__all__ = ["PLACEHOLDER_PATH", "SISI", "adalah_placeholder", "buat", "pastikan"]
