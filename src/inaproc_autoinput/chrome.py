"""Membuka Chrome dengan port debug, supaya aplikasi bisa menempel ke sesimu.

Port debug hanya bisa dibuka saat Chrome mulai dijalankan, dan Chrome menolak
membukanya bila profil yang sama sudah berjalan. Karena itu dipakai profil
terpisah di `~/.inaproc-chrome` -- Chrome sehari-harimu tidak perlu ditutup,
dan port debug tidak menempel ke profil pribadimu.

Login dilakukan sendiri di jendela itu, sekali saja; sesinya bertahan karena
profilnya permanen. Aplikasi tidak pernah menyentuh kata sandi.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

PORT_DEFAULT = 9222
PROFIL = Path.home() / ".inaproc-chrome"

# Chrome selalu dibuka dengan alamat ini supaya ada halaman yang bisa
# dikendalikan sejak awal -- lihat penjelasan di launch().
URL_AWAL = "https://penyedia.inaproc.id/products/add"

# Lokasi Chrome pada macOS, Linux, dan Windows -- dicoba berurutan.
KANDIDAT = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def find_chrome() -> Path | None:
    for kandidat in KANDIDAT:
        path = Path(kandidat)
        if path.exists():
            return path
    return None


def command(port: int = PORT_DEFAULT, chrome: Path | None = None) -> list[str]:
    """Perintah lengkap untuk membuka Chrome berport debug."""
    binary = chrome or find_chrome()
    return [
        str(binary or "google-chrome"),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={PROFIL}",
        "--no-first-run",
        "--no-default-browser-check",
    ]


def command_text(port: int = PORT_DEFAULT) -> str:
    """Perintah yang bisa disalin ke Terminal, dengan tanda kutip seperlunya."""
    bagian = []
    for arg in command(port):
        bagian.append(f'"{arg}"' if " " in arg else arg)
    return " ".join(bagian)


def is_listening(port: int = PORT_DEFAULT, timeout: float = 1.5) -> str:
    """Kembalikan versi browser bila port debug hidup, atau string kosong."""
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/json/version", timeout=timeout
        ) as response:
            payload = json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        return ""
    return payload.get("Browser", "Chrome")


def launch(port: int = PORT_DEFAULT, url: str = URL_AWAL) -> tuple[bool, str]:
    """Buka Chrome berport debug. Mengembalikan (berhasil, pesan).

    Bila port sudah hidup, tidak membuka jendela baru -- cukup melaporkannya.

    URL selalu diberikan, tidak pernah dikosongkan: Chrome yang dibuka tanpa
    alamat hanya menampilkan halaman tab baru, dan halaman itu tidak muncul
    sebagai target di `/json/list`. Akibatnya port debug hidup tapi tidak ada
    yang bisa dikendalikan, dan pesan galatnya menyesatkan ("tidak bisa
    menyambung", padahal sambungannya justru berhasil).
    """
    versi = is_listening(port)
    if versi:
        return True, f"Chrome sudah terbuka dengan port debug ({versi})."

    binary = find_chrome()
    if binary is None:
        return False, (
            "Chrome tidak ditemukan di lokasi yang biasa. Buka sendiri dengan:\n\n"
            + command_text(port)
        )

    argumen = command(port, binary) + [url or URL_AWAL]
    try:
        subprocess.Popen(
            argumen,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # jangan ikut mati saat aplikasi ditutup
        )
    except OSError as error:
        return False, f"Gagal menjalankan Chrome: {error}"

    return True, (
        "Chrome dibuka dengan profil terpisah. Login ke portal di jendela itu, "
        "lalu klik 'Uji koneksi'."
    )


__all__ = [
    "PORT_DEFAULT",
    "PROFIL",
    "URL_AWAL",
    "command",
    "command_text",
    "find_chrome",
    "is_listening",
    "launch",
]
