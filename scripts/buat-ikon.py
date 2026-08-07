#!/usr/bin/env python3
"""Menghasilkan ikon aplikasi (.icns) tanpa perlu pustaka gambar.

PNG ditulis langsung dengan zlib dan struct, lalu dirakit jadi .icns memakai
`iconutil` bawaan macOS. Alasannya sama seperti foto placeholder: satu gambar
tidak sepadan dengan menambah Pillow sebagai dependensi.

Gambarnya: kotak membulat merah dengan panah putih masuk ke dalam wadah --
"input otomatis". Digambar per piksel dengan anti-alias sederhana supaya tepinya
tidak bergerigi di ukuran kecil.

    python3 scripts/buat-ikon.py [tujuan.icns]
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

UKURAN_ICNS = (16, 32, 128, 256, 512)

MERAH = (176, 33, 51)
PUTIH = (255, 255, 255)

# Semua koordinat dalam satuan 0..1 supaya bisa digambar di ukuran mana pun.
RADIUS_SUDUT = 0.22
PANAH_LEBAR = 0.13
PANAH_ATAS = 0.17
PANAH_BATANG_BAWAH = 0.46
PANAH_KEPALA_LEBAR = 0.19
PANAH_KEPALA_BAWAH = 0.66
WADAH_KIRI, WADAH_KANAN = 0.24, 0.76
WADAH_ATAS, WADAH_BAWAH = 0.70, 0.82
WADAH_TEBAL = 0.055


def _di_kotak_membulat(x: float, y: float) -> bool:
    r = RADIUS_SUDUT
    dx = min(x, 1 - x)
    dy = min(y, 1 - y)
    if dx >= r or dy >= r:
        return 0 <= x <= 1 and 0 <= y <= 1
    return (dx - r) ** 2 + (dy - r) ** 2 <= r * r


def _di_panah(x: float, y: float) -> bool:
    tengah = 0.5
    if PANAH_ATAS <= y <= PANAH_BATANG_BAWAH:
        return abs(x - tengah) <= PANAH_LEBAR / 2
    if PANAH_BATANG_BAWAH < y <= PANAH_KEPALA_BAWAH:
        # Segitiga yang menyempit ke bawah.
        bagian = (y - PANAH_BATANG_BAWAH) / (PANAH_KEPALA_BAWAH - PANAH_BATANG_BAWAH)
        lebar = PANAH_KEPALA_LEBAR * (1 - bagian)
        return abs(x - tengah) <= lebar
    return False


def _di_wadah(x: float, y: float) -> bool:
    if not (WADAH_KIRI <= x <= WADAH_KANAN and WADAH_ATAS <= y <= WADAH_BAWAH):
        return False
    di_dinding = (
        x <= WADAH_KIRI + WADAH_TEBAL
        or x >= WADAH_KANAN - WADAH_TEBAL
        or y >= WADAH_BAWAH - WADAH_TEBAL
    )
    return di_dinding


def _warna(x: float, y: float):
    """Kembalikan (r, g, b, a) untuk satu titik dalam satuan 0..1."""
    if not _di_kotak_membulat(x, y):
        return (0, 0, 0, 0)
    if _di_panah(x, y) or _di_wadah(x, y):
        return PUTIH + (255,)
    return MERAH + (255,)


def _piksel(sisi: int, contoh: int = 3) -> bytearray:
    """Baris RGBA dengan supersampling sederhana untuk menghaluskan tepi."""
    baris = bytearray()
    bagi = contoh * contoh
    for py in range(sisi):
        baris.append(0)  # filter None
        for px in range(sisi):
            total = [0, 0, 0, 0]
            for sy in range(contoh):
                for sx in range(contoh):
                    x = (px + (sx + 0.5) / contoh) / sisi
                    y = (py + (sy + 0.5) / contoh) / sisi
                    w = _warna(x, y)
                    for i in range(4):
                        total[i] += w[i]
            baris.extend(n // bagi for n in total)
    return baris


def _potongan(jenis: bytes, data: bytes) -> bytes:
    isi = jenis + data
    return struct.pack(">I", len(data)) + isi + struct.pack(">I", zlib.crc32(isi))


def tulis_png(path: Path, sisi: int) -> Path:
    ihdr = struct.pack(">IIBBBBB", sisi, sisi, 8, 6, 0, 0, 0)  # 8-bit RGBA
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _potongan(b"IHDR", ihdr)
        + _potongan(b"IDAT", zlib.compress(bytes(_piksel(sisi)), 9))
        + _potongan(b"IEND", b"")
    )
    return path


def buat_icns(tujuan: Path) -> Path:
    """Rakit .icns lewat iconutil. Melempar RuntimeError bila macOS-nya tanpa itu."""
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "ikon.iconset"
        iconset.mkdir()
        for sisi in UKURAN_ICNS:
            tulis_png(iconset / f"icon_{sisi}x{sisi}.png", sisi)
            tulis_png(iconset / f"icon_{sisi}x{sisi}@2x.png", sisi * 2)

        tujuan.parent.mkdir(parents=True, exist_ok=True)
        hasil = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(tujuan)],
            capture_output=True, text=True,
        )
        if hasil.returncode != 0:
            raise RuntimeError(f"iconutil gagal: {hasil.stderr.strip()}")
    return tujuan


def main(argv: list[str]) -> int:
    tujuan = Path(argv[1]) if len(argv) > 1 else Path("ikon.icns")
    try:
        path = buat_icns(tujuan)
    except (RuntimeError, FileNotFoundError) as error:
        print(f"Ikon dilewati: {error}", file=sys.stderr)
        return 1
    print(f"Ikon dibuat: {path} ({path.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
