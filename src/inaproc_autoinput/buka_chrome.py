"""Pembuka Chrome portal yang berdiri sendiri, di luar jendela aplikasi.

Dipakai lewat pintasan "Chrome Portal INAPROC" supaya Chrome tidak lagi terikat
pada aplikasi: kamu membukanya sendiri, login sekali, dan membiarkannya terbuka
berhari-hari. Aplikasi tinggal menempel lewat "Uji koneksi browser" dan tidak
pernah menjalankan maupun menutup Chrome.

Pilihan profilnya sama dengan yang tersimpan di aplikasi, jadi keduanya selalu
menunjuk browser yang sama.

    python -m inaproc_autoinput.buka_chrome

Keluar dengan kode 0 bila Chrome siap dipakai, 1 bila tidak -- pesannya dicetak
supaya pembungkus pintasan bisa menampilkannya sebagai kotak peringatan.
"""

from __future__ import annotations

import sys

from . import chrome


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    port = chrome.PORT_DEFAULT
    for arg in argv:
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=", 1)[1])
            except ValueError:
                print(f"Port tidak sah: {arg}")
                return 1

    versi = chrome.is_listening(port)
    if versi:
        print(f"Chrome portal sudah terbuka dan siap dipakai ({versi}). "
              "Di aplikasi, klik 'Uji koneksi browser'.")
        return 0

    berhasil, pesan = chrome.launch(port=port)
    print(pesan)
    return 0 if berhasil else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
