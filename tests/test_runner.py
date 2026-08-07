"""Uji pengisi form.

Bagian murni diuji tanpa browser. Bagian pengisian diuji terhadap
`mock_form.html` — halaman tiruan dengan id, name, dan perilaku dropdown yang
sama seperti form asli. Uji itu dilewati bila Chrome dengan port debug belum
berjalan; jalankan lebih dulu:

    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\
        --remote-debugging-port=9222 --user-data-dir="$HOME/.inaproc-chrome-uji"
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from inaproc_autoinput.assets import Assets
from inaproc_autoinput.runner import (
    CDP_DEFAULT,
    SEL_KATEGORI,
    BrowserRunner,
    Dibatalkan,
    Mode,
    ProductFormFiller,
    RunnerError,
    _angka,
    _normalisasi,
)

MOCK = Path(__file__).with_name("mock_form.html")


# --- bagian murni -----------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("85000", "85000"),
        ("1.250,50", "1250,50"),   # pemisah ribuan dibuang, desimal dijaga
        ("1250,50", "1250,50"),
        ("1.000.000", "1.000.000"),  # tanpa desimal: dibiarkan, validator yang menolak
        ("", ""),
        (None, ""),
    ],
)
def test_angka(raw, expected):
    assert _angka(raw) == expected


@pytest.mark.parametrize(
    "a,b",
    [
        ("Satuan Pengukuran", "satuan  pengukuran"),
        ("Lokasi Layanan (Kecamatan)", "Lokasi Layanan Kecamatan"),
        ("Sertifikat Badan Usaha (SBU) Konstruksi", "sertifikat badan usaha sbu konstruksi"),
    ],
)
def test_normalisasi_menyamakan_label(a, b):
    assert _normalisasi(a) == _normalisasi(b)


def test_mode_punya_label_manusia():
    assert Mode.ISI_SAJA.label == "Isi saja, jangan simpan"
    assert {m.value for m in Mode} == {"isi_saja", "simpan_draf", "simpan"}


def test_connect_gagal_memberi_petunjuk():
    runner = BrowserRunner("http://localhost:59999")
    with pytest.raises(RunnerError, match="remote-debugging-port"):
        runner.connect()


def test_jalankan_yang_dibatalkan_bukan_kegagalan():
    """Berhenti diperiksa sebelum halaman disentuh sama sekali.

    Yang dijaga di sini bukan pesannya, tapi `tersimpan`: apa pun yang terjadi,
    baris yang dihentikan tidak boleh dilaporkan sebagai sudah masuk portal.
    """

    class PageDiam:
        def is_closed(self) -> bool:
            return False

    runner = BrowserRunner()
    runner.page = PageDiam()
    hasil = runner.jalankan({"kategori": "A > B > C"}, Mode.SIMPAN,
                            batal=lambda: True)

    assert hasil.dibatalkan
    assert not hasil.berhasil
    assert not hasil.tersimpan
    assert hasil.langkah == []  # tidak satu langkah pun sempat jalan


# --- pengisian terhadap halaman tiruan --------------------------------------


def _cdp_hidup() -> bool:
    try:
        urllib.request.urlopen(f"{CDP_DEFAULT}/json/version", timeout=2)
        return True
    except (urllib.error.URLError, OSError):
        return False


pytestmark_browser = pytest.mark.skipif(
    not _cdp_hidup(), reason="Chrome dengan --remote-debugging-port=9222 belum jalan"
)


@pytest.fixture(scope="module")
def server():
    """Sajikan halaman tiruan lewat HTTP.

    `file://` melarang history.replaceState, padahal portal asli mengubah URL
    jadi /products/<id> setelah menyimpan — dan dari situlah id produk dibaca.
    """
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(MOCK.parent)
    )
    # Threading: Chrome memakai koneksi keep-alive, dan server satu-koneksi
    # akan membuat permintaan berikutnya menunggu sampai buntu.
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    httpd.RequestHandlerClass.log_message = lambda *args, **kwargs: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/{MOCK.name}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def runner():
    if not _cdp_hidup():
        pytest.skip("Chrome debug belum jalan")
    r = BrowserRunner().connect()
    yield r
    r.close()


@pytest.fixture
def halaman(runner, server):
    runner.page.goto(server)
    runner.page.wait_for_selector('input[placeholder="Pilih Kategori"]')
    return runner.page


@pytest.fixture(scope="module")
def berkas(tmp_path_factory):
    root = tmp_path_factory.mktemp("berkas")
    foto = root / "galian.png"
    foto.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 200)
    pdf = root / "sbu.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"0" * 200)
    return {"foto": str(foto), "pdf": str(pdf)}


def _baris(berkas) -> dict:
    return {
        "kategori": "Bidang Bina Marga > Divisi 3 Pekerjaan Tanah dan Geosintetik > 3.1 Galian",
        "nama_produk": "Galian Biasa untuk Badan Jalan",
        "deskripsi": "Pekerjaan galian biasa sesuai spesifikasi.",
        "kbki": "54310",
        "pdn_klasifikasi": "Lokal",
        "pdn_lokasi_produksi": "Diproduksi di seluruh Indonesia",
        "pdn_tenaga_kerja": "Dibuat oleh seluruh tenaga kerja Indonesia di dalam negeri",
        "pdn_bahan_baku": "Seluruh bahan baku dalam negeri",
        "ppn": "12%",
        "minimum_pembelian": "1",
        "harga_produk": "85000",
        "stok": "1000",
        "satuan_produk": "Meter",
        "atribut_1_nama": "Satuan Pengukuran",
        "atribut_1_nilai": "M3",
        "atribut_2_nama": "Kode Produk",
        "atribut_2_nilai": "BNS-GAL-01",
    }


def _assets(berkas, foto=None):
    """Berkas kini dipilih lewat panel aplikasi, bukan kolom Excel."""
    a = Assets(foto_umum=[foto or berkas["foto"]])
    a.set_dokumen("Sertifikat Standar", berkas["pdf"])
    return a


@pytestmark_browser
def test_isi_satu_baris_penuh(halaman, berkas):
    pengisi = ProductFormFiller(halaman)
    pengisi.isi(_baris(berkas), _assets(berkas))

    nilai = halaman.evaluate(
        """() => ({
          kategori: document.getElementById('kategori').value,
          nama: document.getElementById('form-product-name-input').value,
          deskripsi: document.querySelector('textarea[name=description]').value,
          harga: document.getElementById('form-product-price-input').value,
          stok: document.getElementById('stockUnit-value-input').value,
          minBeli: document.getElementById('form-product-min-purchase-input').value,
          ppn: document.getElementById('react-select-ppnPercentage-select-input').value,
          sni: document.getElementById('form-product-sni-switch').checked,
          merek: document.getElementById('form-product-brand-isActive-switch').checked,
          desimal: document.getElementById('form-product-decimal-qty-switch').checked,
          atribut: [...document.querySelectorAll('[name^="productInformations.mainInformations."]')].map(e => e.value),
          fotoAda: document.getElementById('product-image-input-0').files.length,
          dokumenAda: [...document.querySelectorAll('#document-field-input')].map(e => e.files.length),
        })"""
    )

    assert nilai["kategori"].endswith("3.1 Galian")
    assert nilai["nama"] == "Galian Biasa untuk Badan Jalan"
    assert nilai["deskripsi"].startswith("Pekerjaan galian")
    assert nilai["harga"] == "85000"
    assert nilai["stok"] == "1000"
    assert nilai["minBeli"] == "1"
    assert nilai["ppn"] == "12%"
    # Saklar Merek/SNI/TKDN tidak lagi punya kolom Excel: rincian yang muncul
    # setelah dinyalakan belum didukung, jadi keduanya dibiarkan mati.
    assert nilai["sni"] is False
    assert nilai["merek"] is False
    assert nilai["fotoAda"] == 1
    # Atribut dicocokkan lewat nama, bukan urutan di Excel.
    assert nilai["atribut"][:2] == ["M3", "BNS-GAL-01"]
    # Dokumen 'Sertifikat Standar' ada di urutan kedua pada kategori ini.
    assert nilai["dokumenAda"] == [0, 1]
    # Stok 1000 bulat -> kuantitas desimal tidak perlu dinyalakan.
    assert nilai["desimal"] is False


@pytestmark_browser
def test_kuantitas_desimal_disimpulkan_dari_stok(halaman, berkas):
    """Tidak ada kolomnya di Excel; nilainya disimpulkan dari angka stok."""
    pengisi = ProductFormFiller(halaman)
    pengisi.isi(dict(_baris(berkas), stok="332,35"), _assets(berkas))
    assert halaman.evaluate(
        "() => document.getElementById('form-product-decimal-qty-switch').checked"
    ) is True


@pytestmark_browser
def test_tipe_produk_dibaca_dari_portal(halaman, berkas):
    pengisi = ProductFormFiller(halaman)
    pengisi.pilih_kategori(_baris(berkas)["kategori"])
    assert pengisi.baca_tipe_produk() == "Jasa"


@pytestmark_browser
def test_label_atribut_mengikuti_kategori(halaman, berkas):
    pengisi = ProductFormFiller(halaman)
    pengisi.pilih_kategori(_baris(berkas)["kategori"])
    assert pengisi.label_atribut()[:2] == ["Satuan Pengukuran", "Kode Produk"]

    pengisi.pilih_kategori("Peralatan Kantor > Furnitur Kantor > Meja Kerja")
    assert pengisi.label_atribut() == ["Satuan Pengukuran", "Bahan Utama"]


@pytestmark_browser
def test_ketik_memasang_teks_utuh_dan_menekan_huruf_terakhir(halaman):
    """Pengetikan cepat tidak boleh mengorbankan penekanan tombol terakhir.

    Komponen pencarian yang menyimak keydown -- bukan perubahan nilai -- harus
    tetap terpicu, karena itu huruf penghabisan tetap diketik sungguhan.
    """
    pengisi = ProductFormFiller(halaman)
    kotak = halaman.locator(SEL_KATEGORI).first
    kotak.click()
    halaman.evaluate(
        """(sel) => {
             const el = document.querySelector(sel);
             window.__keydown = 0;
             el.addEventListener('keydown', () => window.__keydown++);
           }""",
        SEL_KATEGORI,
    )

    pengisi._ketik(kotak, "Meja Kerja")
    assert kotak.input_value() == "Meja Kerja"
    assert halaman.evaluate("() => window.__keydown") == 1


@pytestmark_browser
def test_ketik_teks_kosong_tidak_menyentuh_kotak(halaman):
    pengisi = ProductFormFiller(halaman)
    kotak = halaman.locator(SEL_KATEGORI).first
    kotak.fill("sisa")
    pengisi._ketik(kotak, "")
    assert kotak.input_value() == "sisa"


@pytestmark_browser
def test_atribut_asing_jadi_peringatan_bukan_gagal(halaman, berkas):
    data = dict(_baris(berkas), atribut_2_nama="Kepemilikan AMP", atribut_2_nilai="Milik Sendiri")
    pengisi = ProductFormFiller(halaman)
    pengisi.isi(data)
    assert any("Kepemilikan AMP" in p for p in pengisi.peringatan)


@pytestmark_browser
def test_kategori_tidak_ada_melempar_error(halaman):
    pengisi = ProductFormFiller(halaman)
    with pytest.raises(RunnerError, match="tidak ditemukan di pemilih"):
        pengisi.pilih_kategori("Bidang Bina Marga > Divisi 3 Pekerjaan Tanah dan Geosintetik > 9.9 Karangan")


@pytestmark_browser
def test_kategori_kurang_lengkap_ditolak(halaman):
    pengisi = ProductFormFiller(halaman)
    with pytest.raises(RunnerError, match="lengkap sampai Level 3"):
        pengisi.pilih_kategori("Bidang Bina Marga")


@pytestmark_browser
def test_berkas_hilang_melempar_error(halaman, berkas):
    hilang = _assets(berkas, foto="/tidak/ada/galian.png")
    pengisi = ProductFormFiller(halaman)
    with pytest.raises(RunnerError, match="berkas tidak ada"):
        pengisi.isi(_baris(berkas), hilang)


@pytestmark_browser
def test_mode_isi_saja_tidak_menekan_tombol(halaman, berkas):
    pengisi = ProductFormFiller(halaman)
    pengisi.isi(_baris(berkas), _assets(berkas))
    assert pengisi.simpan(Mode.ISI_SAJA) == ""
    assert halaman.locator("#hasil").inner_text() == ""


@pytestmark_browser
def test_mode_simpan_draf_menekan_tombol_draf(halaman, berkas):
    pengisi = ProductFormFiller(halaman)
    pengisi.isi(_baris(berkas), _assets(berkas))
    produk_id = pengisi.simpan(Mode.SIMPAN_DRAF)
    assert halaman.locator("#hasil").inner_text() == "DIKLIK: Simpan Draf Produk"
    assert produk_id == "abc12345def"


@pytestmark_browser
def test_jalankan_alur_penuh(runner, halaman, server, berkas, monkeypatch):
    """Alur yang dipakai jendela: buka form, isi, simpan draf, laporkan.

    Fixture `halaman` ikut diminta supaya halaman direset lebih dulu — uji ini
    berbagi satu tab dengan uji lain, dan urutannya diacak.
    """
    monkeypatch.setattr("inaproc_autoinput.runner.URL_TAMBAH", server)

    langkah_terpantau: list[str] = []
    hasil = runner.jalankan(
        _baris(berkas), Mode.SIMPAN_DRAF, catatan=langkah_terpantau.append
    )

    assert hasil.berhasil, hasil.pesan
    assert hasil.produk_id == "abc12345def"
    assert hasil.pesan == "tersimpan"
    assert any("Kategori:" in t for t in hasil.langkah)
    assert langkah_terpantau == hasil.langkah, "catatan langsung harus sama"


@pytestmark_browser
def test_jalankan_melaporkan_gagal_tanpa_melempar(runner, halaman, server, berkas, monkeypatch):
    monkeypatch.setattr("inaproc_autoinput.runner.URL_TAMBAH", server)
    rusak = dict(_baris(berkas), kategori="Bidang Karangan > Divisi > Pekerjaan")

    hasil = runner.jalankan(rusak, Mode.ISI_SAJA)
    assert not hasil.berhasil
    assert "tidak ditemukan di pemilih" in hasil.pesan


@pytestmark_browser
def test_ganti_kategori_menyetujui_konfirmasi(halaman, berkas):
    pengisi = ProductFormFiller(halaman)
    pengisi.pilih_kategori(_baris(berkas)["kategori"])
    pengisi.pilih_kategori("Bidang Bina Marga > Divisi 3 Pekerjaan Tanah dan Geosintetik > 3.2 Timbunan")
    assert halaman.locator("#kategori").input_value().endswith("3.2 Timbunan")


@pytestmark_browser
@pytest.mark.parametrize("mode,tersimpan", [
    (Mode.ISI_SAJA, False),
    (Mode.SIMPAN_DRAF, True),
])
def test_hasil_membedakan_terisi_dari_tersimpan(runner, halaman, berkas,
                                                monkeypatch, mode, tersimpan):
    """Mode "Isi saja" berhasil tanpa menyimpan apa pun.

    Bedanya penting: baris yang cuma terisi masih harus dikerjakan. Kalau
    ditandai sukses, "Lanjutkan sisanya" akan melewatinya diam-diam dan
    produknya tidak pernah masuk ke portal.
    """
    monkeypatch.setattr(runner, "buka_form", lambda: None)
    hasil = runner.jalankan(_baris(berkas), mode, assets=_assets(berkas))

    assert hasil.berhasil, hasil.pesan
    assert hasil.tersimpan is tersimpan
    assert ("tersimpan" if tersimpan else "menunggu kamu menyimpan") in hasil.pesan


# --- berhenti di tengah antrean ---------------------------------------------


@pytestmark_browser
def test_berhenti_memutus_di_tengah_pengisian(halaman, berkas):
    """Playwright sinkron tidak bisa diputus dari luar.

    Berhentinya karena itu diperiksa di sela-sela langkah: jedanya paling lama
    satu langkah, bukan satu baris penuh yang makan setengah menit.
    """
    langkah: list[str] = []
    pengisi = ProductFormFiller(halaman, langkah.append,
                                batal=lambda: len(langkah) >= 3)

    with pytest.raises(Dibatalkan):
        pengisi.isi(_baris(berkas), _assets(berkas))

    assert len(pengisi.langkah) == 3
    # Form tertinggal separuh terisi -- itu memang konsekuensinya, dan tidak
    # apa-apa: tidak ada yang tersimpan, dan baris berikutnya memuat ulang.
    assert halaman.locator("#form-product-price-input").input_value() == ""


@pytestmark_browser
def test_berhenti_tidak_jadi_mengklik_simpan(halaman):
    """Berhenti yang datang sedetik sebelum klik tidak boleh tetap menyimpan."""
    pengisi = ProductFormFiller(halaman, batal=lambda: True)

    with pytest.raises(Dibatalkan):
        pengisi.simpan(Mode.SIMPAN_DRAF)

    assert halaman.locator("#hasil").inner_text() == ""


@pytestmark_browser
def test_jalankan_melaporkan_dibatalkan_bukan_gagal(runner, halaman, berkas,
                                                    monkeypatch):
    monkeypatch.setattr(runner, "buka_form", lambda: None)
    hitung = {"n": 0}

    def batal() -> bool:
        hitung["n"] += 1
        return hitung["n"] > 4

    hasil = runner.jalankan(_baris(berkas), Mode.SIMPAN_DRAF,
                            assets=_assets(berkas), batal=batal)

    assert hasil.dibatalkan
    assert not hasil.berhasil and not hasil.tersimpan
    assert "dihentikan" in hasil.pesan
    assert hasil.langkah, "langkah yang sempat jalan tetap dilaporkan"
    assert halaman.locator("#hasil").inner_text() == ""
