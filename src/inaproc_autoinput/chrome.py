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
import os
import subprocess
import sys
import time
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

# Pemasangan Chrome per-pengguna di Windows tidak ada di Program Files.
if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
    KANDIDAT += (
        os.path.join(os.environ["LOCALAPPDATA"],
                     r"Google\Chrome\Application\chrome.exe"),
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


def tutup(port: int = PORT_DEFAULT, tunggu: float = 12.0) -> tuple[bool, str]:
    """Tutup Chrome berport debug lewat protokolnya sendiri.

    Ditutup baik-baik, bukan diputus paksa. Chrome menuliskan cookie dan sesi ke
    profil saat keluar normal, dan itulah yang membuat login bertahan setelah
    dijalankan lagi -- dimatikan paksa, yang tertulis belum tentu lengkap.

    Perintahnya memutus sambungannya sendiri, jadi galat setelah dikirim justru
    tanda berhasil. Yang menentukan cuma satu: port debugnya berhenti menjawab.
    """
    if not is_listening(port):
        return True, "Chrome memang sedang tidak berjalan."

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, ("Playwright belum terpasang, jadi Chrome tidak bisa "
                       "ditutup dari sini. Tutup jendelanya sendiri.")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{port}")
            try:
                browser.new_browser_cdp_session().send("Browser.close")
            except Exception:  # noqa: BLE001 -- sambungan putus saat Chrome keluar
                pass
    except Exception:  # noqa: BLE001 -- sama, dan bukan penentu berhasil
        pass

    batas = time.monotonic() + tunggu
    while time.monotonic() < batas:
        if not is_listening(port, timeout=0.5):
            return True, "Chrome ditutup."
        time.sleep(0.3)
    return False, ("Chrome belum juga menutup. Tutup jendelanya sendiri, lalu "
                   "klik 'Buka Chrome portal'.")


def mulai_ulang(port: int = PORT_DEFAULT, url: str = URL_AWAL) -> tuple[bool, str]:
    """Tutup lalu buka lagi Chrome portal.

    Chrome yang sudah lama hidup melambat cukup jauh: rangkaian uji yang sama
    berjalan 100 detik di Chrome yang dipakai berjam-jam, 29 detik setelah
    dijalankan ulang. Sesi login bertahan karena profilnya permanen.
    """
    berhasil, pesan = tutup(port)
    if not berhasil:
        return False, pesan
    berhasil, pesan_buka = launch(port, url)
    if not berhasil:
        return False, pesan_buka
    return True, "Chrome dijalankan ulang. Sesi loginmu tetap ada."


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
    # Chrome harus lepas dari aplikasi supaya tidak ikut mati saat jendela
    # ditutup. Caranya berbeda per sistem: start_new_session hanya berlaku di
    # POSIX -- Windows mengabaikannya diam-diam, jadi di sana dipakai
    # creationflags yang setara.
    lepas: dict = {}
    if sys.platform == "win32":
        lepas["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
    else:
        lepas["start_new_session"] = True

    try:
        subprocess.Popen(
            argumen,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **lepas,
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
    "mulai_ulang",
    "tutup",
]
