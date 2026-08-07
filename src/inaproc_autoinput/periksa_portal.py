"""Ukur seberapa cepat portal menjawab, saat itu juga.

Dipakai ketika portal terasa berat. "Lag" adalah kesan, dan kesan tidak bisa
ditindaklanjuti -- yang bisa cuma angka: berapa lama servernya menjawab, berapa
lama form siap dipakai, dan permintaan mana yang menahan.

Bedanya penting. Portal yang lambat tidak bisa dipercepat dari sini, dan
mengejarnya di aplikasi cuma membuang waktu. Sebaliknya, halaman yang tidak
pernah siap padahal servernya menjawab cepat menunjuk ke hal lain sama sekali --
sesi yang mati, atau modal yang menutupi halaman.

    python -m inaproc_autoinput.periksa_portal

Chrome berport debug harus sudah terbuka. Halaman yang sedang kamu buka tidak
diganggu: pengukuran memakai tab tersendiri yang ditutup lagi setelah selesai.
"""

from __future__ import annotations

import statistics as st
import time

from . import chrome
from .runner import CDP_DEFAULT, SEL_KATEGORI, URL_TAMBAH, penghalang

JUMLAH = 3
# Di atas ini portalnya memang sedang berat, bukan perasaan. Diambil dari
# pengukuran saat portal sehat: form siap dalam 0,8 detik.
BATAS_LAMBAT = 5.0


def _ukur(page) -> dict:
    catat: list = []

    # Fungsi biasa, bukan `catat.append`: Playwright menandai objek listener-nya
    # dan metode bawaan list menolak diberi atribut.
    def rekam(response) -> None:
        catat.append(response)

    page.on("response", rekam)

    mulai = time.perf_counter()
    page.goto(URL_TAMBAH, wait_until="load", timeout=120_000)
    load = time.perf_counter() - mulai
    try:
        page.locator(SEL_KATEGORI).first.wait_for(state="visible", timeout=60_000)
        siap = time.perf_counter() - mulai
    except Exception:  # noqa: BLE001 -- form tidak pernah muncul; itu datanya
        siap = float("nan")

    server = page.evaluate(
        """() => { const x = performance.getEntriesByType('navigation')[0];
             return x ? Math.round(x.responseStart - x.requestStart) : -1; }"""
    )
    lambat = []
    for r in catat:
        waktu = r.request.timing
        ms = (waktu.get("responseEnd") or 0) - (waktu.get("requestStart") or 0)
        if ms > 300:
            lambat.append((ms, r.url.split("?")[0]))
    page.remove_listener("response", rekam)
    return {"load": load, "siap": siap, "server": server,
            "permintaan": len(catat), "lambat": sorted(lambat, reverse=True)}


def main(argv: list[str] | None = None) -> int:
    if not chrome.is_listening():
        print("Chrome berport debug belum terbuka.\n\nBuka dulu lewat pintasan "
              "'Chrome Portal INAPROC', atau tombol 'Buka Chrome portal' di "
              "aplikasi. Lalu jalankan ini lagi.")
        return 1

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_DEFAULT)
        konteks = browser.contexts[0]
        # Tab sendiri: halaman yang sedang kamu kerjakan tidak boleh ikut
        # dimuat ulang cuma untuk diukur.
        page = konteks.new_page()
        try:
            hasil = [_ukur(page) for _ in range(JUMLAH)]
            halangan = penghalang(page)
        finally:
            page.close()
            browser.close()

    print(f"Portal diukur {JUMLAH} kali:\n")
    for nomor, h in enumerate(hasil, 1):
        siap = "tidak pernah siap" if h["siap"] != h["siap"] else f"{h['siap']:5.2f}s"
        print(f"  #{nomor}  memuat {h['load']:5.2f}s · form siap {siap} · "
              f"tunggu server {h['server']:4} ms · {h['permintaan']} permintaan")

    siap = [h["siap"] for h in hasil if h["siap"] == h["siap"]]
    lambat = [x for h in hasil for x in h["lambat"]]
    if lambat:
        print("\n  Permintaan yang menahan:")
        for ms, url in sorted(lambat, reverse=True)[:5]:
            print(f"    {ms:6.0f} ms  {url[-68:]}")

    print("\n" + "-" * 66)
    if halangan:
        print("Portal menutupi halaman dengan kotak, jadi angka di atas tidak\n"
              "mengukur apa pun yang bisa kamu pakai:\n\n  " + halangan[:150])
    elif not siap:
        print("Form tidak pernah siap sampai batas waktu. Servernya menjawab,\n"
              "tapi halamannya tidak selesai terbentuk — periksa apakah kamu\n"
              "masih login di jendela Chrome itu.")
    elif st.median(siap) > BATAS_LAMBAT:
        print(f"Portal sedang berat: form siap dalam {st.median(siap):.1f} detik,\n"
              f"padahal saat sehat sekitar 0,8 detik. Ini di sisi portal — tidak\n"
              "ada setelan di aplikasi yang bisa mempercepatnya. Tunda dulu, atau\n"
              "jalankan di jam yang lebih sepi.")
    else:
        print(f"Portal sehat: form siap dalam {st.median(siap):.1f} detik.\n"
              "Kalau tetap terasa berat, yang melambat bukan portalnya —\n"
              "catat jam kejadiannya dan jalankan ini lagi tepat saat itu.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
