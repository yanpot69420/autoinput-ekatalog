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

# Profil terpisah milik aplikasi. Chrome sehari-harimu tidak perlu ditutup, tapi
# portal jadi melihat dua sesi untuk satu akun -- dan karena hanya satu yang
# diizinkan, yang satunya ditendang dengan kotak "Akun Telah Keluar".
PROFIL = Path.home() / ".inaproc-chrome"
PROFIL_APLIKASI = PROFIL

# Profil Chrome harian. Satu profil berarti satu sesi, jadi tidak ada yang
# saling menendang -- tapi Chrome harus ditutup dulu sepenuhnya, karena port
# debug hanya bisa dibuka saat Chrome mulai berjalan.
if sys.platform == "win32":
    PROFIL_HARIAN = Path(os.environ.get("LOCALAPPDATA", Path.home())) / \
        "Google" / "Chrome" / "User Data"
elif sys.platform == "darwin":
    PROFIL_HARIAN = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
else:
    PROFIL_HARIAN = Path.home() / ".config" / "google-chrome"

PILIHAN_PATH = Path.home() / ".inaproc-autoinput" / "chrome.json"

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


def pakai_harian(path: Path | None = None) -> bool:
    """Apakah aplikasi memakai profil Chrome harian, bukan profil sendiri."""
    berkas = path or PILIHAN_PATH
    try:
        return bool(json.loads(berkas.read_text(encoding="utf-8")).get("harian"))
    except (OSError, ValueError):
        return False


def set_pakai_harian(harian: bool, path: Path | None = None) -> Path:
    berkas = path or PILIHAN_PATH
    berkas.parent.mkdir(parents=True, exist_ok=True)
    berkas.write_text(json.dumps({"harian": bool(harian)}, indent=2), "utf-8")
    return berkas


def profil(harian: bool | None = None) -> Path:
    if harian is None:
        harian = pakai_harian()
    return PROFIL_HARIAN if harian else PROFIL_APLIKASI


def sedang_berjalan(dir_profil: Path | None = None) -> bool:
    """Apakah ada Chrome yang sedang memakai profil ini.

    Dibaca dari berkas kunci yang dibuat Chrome sendiri, bukan dari daftar
    proses -- tidak perlu perkakas yang berbeda tiap sistem. Kuncinya bisa
    tertinggal setelah Chrome mati mendadak, jadi ini petunjuk, bukan bukti.

    Diperiksa dengan lexists, bukan exists: di macOS dan Linux SingletonLock
    adalah symlink ke "namahost-pid" yang memang tidak pernah ada sebagai
    berkas. exists() mengikuti symlink itu, tidak menemukan apa-apa, lalu
    menjawab "tidak berjalan" untuk Chrome yang jelas sedang berjalan.
    """
    dasar = Path(dir_profil or profil())
    return any(os.path.lexists(dasar / nama)
               for nama in ("SingletonLock", "lockfile"))


def command(port: int = PORT_DEFAULT, chrome: Path | None = None,
            dir_profil: Path | None = None) -> list[str]:
    """Perintah lengkap untuk membuka Chrome berport debug."""
    binary = chrome or find_chrome()
    return [
        str(binary or "google-chrome"),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={dir_profil or profil()}",
        "--no-first-run",
        "--no-default-browser-check",
    ]


def command_text(port: int = PORT_DEFAULT, dir_profil: Path | None = None) -> str:
    """Perintah yang bisa disalin ke Terminal, dengan tanda kutip seperlunya."""
    bagian = []
    for arg in command(port, dir_profil=dir_profil):
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


def mulai_ulang(port: int = PORT_DEFAULT, url: str = URL_AWAL,
                dir_profil: Path | None = None) -> tuple[bool, str]:
    """Tutup lalu buka lagi Chrome portal.

    Chrome yang sudah lama hidup melambat cukup jauh: rangkaian uji yang sama
    berjalan 100 detik di Chrome yang dipakai berjam-jam, 29 detik setelah
    dijalankan ulang. Sesi login bertahan karena profilnya permanen.
    """
    berhasil, pesan = tutup(port)
    if not berhasil:
        return False, pesan
    berhasil, pesan_buka = launch(port, url, dir_profil)
    if not berhasil:
        return False, pesan_buka
    return True, "Chrome dijalankan ulang. Sesi loginmu tetap ada."


def launch(port: int = PORT_DEFAULT, url: str = URL_AWAL,
           dir_profil: Path | None = None) -> tuple[bool, str]:
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
            + command_text(port, dir_profil)
        )

    dasar = Path(dir_profil or profil())
    # Port debug hanya bisa dibuka saat Chrome mulai berjalan. Kalau profilnya
    # sudah dipakai, Chrome baru cuma menyerahkan alamatnya ke jendela yang
    # sudah ada lalu keluar -- portnya tidak pernah hidup, dan dari luar itu
    # terlihat seperti aplikasi yang gagal tanpa sebab.
    if sedang_berjalan(dasar):
        return False, (
            f"Chrome sedang berjalan dengan profil ini:\n  {dasar}\n\n"
            "Port debug hanya bisa dibuka saat Chrome mulai dijalankan, jadi "
            "Chrome harus ditutup dulu sepenuhnya — semua jendelanya, lalu "
            "Keluar dari menu Chrome. Setelah itu coba lagi.\n\n"
            "Kalau kamu yakin Chrome tidak terbuka, berkas kuncinya mungkin "
            "tertinggal dari Chrome yang mati mendadak; buka sendiri dengan:\n\n"
            + command_text(port, dasar)
        )

    argumen = command(port, binary, dasar) + [url or URL_AWAL]
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
    "PILIHAN_PATH",
    "PROFIL_APLIKASI",
    "PROFIL_HARIAN",
    "launch",
    "mulai_ulang",
    "pakai_harian",
    "profil",
    "sedang_berjalan",
    "set_pakai_harian",
    "tutup",
]
