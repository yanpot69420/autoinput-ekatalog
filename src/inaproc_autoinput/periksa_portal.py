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

# Kecepatan perender Chrome saat sehat, diukur pada halaman kosong -- tanpa
# jaringan dan tanpa portal, jadi yang tersisa cuma Chrome-nya sendiri.
SEHAT_JS = 8_100_000     # ribuan operasi dalam 400 ms
SEHAT_FRAME = 8.3        # milidetik per frame
# Chrome kadang meninggalkan proses perender yatim yang terus berputar tanpa
# halaman apa pun -- terukur membakar 72% CPU dengan satu tab about:blank.
# Akibatnya seluruh Chrome melambat dua sampai tiga kali lipat, di situs mana
# pun. Di bawah/di atas ambang ini, yang bermasalah Chrome-nya, bukan portal.
AMBANG_JS = SEHAT_JS * 0.6
AMBANG_FRAME = SEHAT_FRAME * 1.7

_UKUR_PERENDER = """() => {
  let n = 0, t = performance.now();
  while (performance.now() - t < 400) { for (let i = 0; i < 1000; i++) n += Math.sqrt(i); }
  const js = Math.round(n / 1000);
  return new Promise(res => {
    const d = []; let a = performance.now(); const habis = a + 1500;
    (function tick(now) { d.push(now - a); a = now;
      now < habis ? requestAnimationFrame(tick) : res({js, frame: d}); })(a);
  });
}"""


def chrome_melambat(js: int, frame: float) -> bool:
    """Apakah Chrome sendiri yang melambat, terlepas dari portalnya.

    Salah satu saja sudah cukup: pada kejadian nyata keduanya turun bersamaan,
    tapi menuntut keduanya berarti melewatkan gejala yang baru mulai.
    """
    return js < AMBANG_JS or frame > AMBANG_FRAME


def _ukur_perender(page) -> tuple[int, float]:
    """Kecepatan Chrome sendiri, diukur di halaman kosong.

    Sengaja bukan di halaman portal: kalau diukur di sana, Chrome yang lambat
    dan portal yang berat tidak bisa dibedakan -- dan keduanya butuh tindakan
    yang sama sekali berbeda.
    """
    page.goto("about:blank")
    hasil = page.evaluate(_UKUR_PERENDER)
    frame = sorted(x for x in hasil["frame"][2:] if x < 3000)
    return hasil["js"], (st.median(frame) if frame else float("nan"))


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
            js, frame = _ukur_perender(page)
            hasil = [_ukur(page) for _ in range(JUMLAH)]
            halangan = penghalang(page)
        finally:
            page.close()
            browser.close()

    print("Kecepatan Chrome sendiri, diukur di halaman kosong:\n")
    print(f"  JS {js:,} kops (sehat ±{SEHAT_JS:,}) · "
          f"frame {frame:.1f} ms (sehat ±{SEHAT_FRAME} ms)\n")

    chrome_lambat = chrome_melambat(js, frame)
    if chrome_lambat:
        print("  ^ Chrome-nya sendiri yang melambat, bukan portal. Ini terjadi\n"
              "    bila ada proses perender yang tersangkut dan terus berputar\n"
              "    tanpa halaman — terukur membakar 72% CPU dengan satu tab\n"
              "    kosong, dan memperlambat semua situs, bukan cuma portal.\n"
              "    Jalankan ulang Chrome; sesi login tetap ada:\n"
              "      python -m inaproc_autoinput.buka_chrome --mulai-ulang\n")

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
    elif chrome_lambat:
        print(f"Portal sehat: form siap dalam {st.median(siap):.1f} detik.\n"
              "Yang berat Chrome-nya — lihat catatan di atas.")
    else:
        print(f"Portal sehat ({st.median(siap):.1f} detik) dan Chrome sehat.\n"
              "Kalau tetap terasa berat, yang melambat di luar keduanya —\n"
              "catat jam kejadiannya dan jalankan ini lagi tepat saat itu.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
