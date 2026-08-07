"""Uji panel Berkas: yang sudah dipilih harus bisa dilepas lagi."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from inaproc_autoinput.assets import Assets  # noqa: E402
from inaproc_autoinput.ui.assets_panel import AssetsPanel, PemilihFoto  # noqa: E402


@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    p = AssetsPanel()
    yield p
    p.deleteLater()


def test_hapus_foto_terpilih_menyisakan_yang_lain(app):
    pemilih = PemilihFoto()
    pemilih.set_berkas(["a.jpg", "b.jpg", "c.jpg"])
    pemilih._daftar.item(1).setSelected(True)
    pemilih._hapus_terpilih()
    assert pemilih.berkas() == ["a.jpg", "c.jpg"]


def test_tambah_menambah_bukan_mengganti(app, monkeypatch, tmp_path):
    from inaproc_autoinput.ui import assets_panel as ap

    baru = str(tmp_path / "b.jpg")
    monkeypatch.setattr(ap.QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *a, **k: ([baru], "")))
    pemilih = PemilihFoto()
    pemilih.set_berkas(["a.jpg"])
    pemilih._tambah()
    assert pemilih.berkas() == ["a.jpg", baru]


def test_tombol_hapus_mati_tanpa_pilihan(app):
    pemilih = PemilihFoto()
    pemilih.set_berkas(["a.jpg"])
    assert not pemilih._btn_hapus.isEnabled()
    pemilih._daftar.item(0).setSelected(True)
    assert pemilih._btn_hapus.isEnabled()


def test_url_video_bisa_dikosongkan(panel):
    panel.set_assets(Assets(video_url="https://youtu.be/abc"))
    panel._hapus_url()
    assert panel.assets().video_url == ""
    assert panel._url.text() == ""


def test_kosongkan_semua_minta_konfirmasi_dulu(panel, monkeypatch):
    from inaproc_autoinput.ui import assets_panel as ap

    panel.set_assets(Assets(dokumen={"SBU": "s.pdf"}, video="v.mp4"))
    monkeypatch.setattr(ap.QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.No))
    panel._kosongkan_semua()
    assert panel.assets().dokumen, "dibatalkan, jadi tidak boleh terhapus"

    monkeypatch.setattr(ap.QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    panel._kosongkan_semua()
    assert panel.assets().kosong


def test_kosongkan_semua_tidak_bertanya_saat_sudah_kosong(panel, monkeypatch):
    from inaproc_autoinput.ui import assets_panel as ap

    monkeypatch.setattr(ap.QMessageBox, "question",
                        staticmethod(lambda *a, **k: pytest.fail("tidak perlu bertanya")))
    panel.set_assets(Assets())
    panel._kosongkan_semua()


def test_foto_khusus_terkunci_sebelum_ada_baris_dipilih(panel):
    panel.set_assets(Assets(foto_umum=["a.jpg"]))
    panel.set_baris(None)
    assert not panel._foto_khusus._btn_tambah.isEnabled()

    panel.set_baris(5, "Sewa lahan")
    assert panel._foto_khusus._btn_tambah.isEnabled()


def test_menghapus_foto_baris_lewat_panel_tersimpan_ke_assets(panel):
    panel.set_assets(Assets(foto_baris={5: ["a.jpg", "b.jpg"]}))
    panel.set_baris(5)
    panel._foto_khusus._daftar.item(0).setSelected(True)
    panel._foto_khusus._hapus_terpilih()
    assert panel.assets().foto_baris[5] == ["b.jpg"]


def test_saringan_tidak_pernah_menyembunyikan_berkas():
    """Saringan huruf kecil membuat .PDF dan .JPG tampak abu-abu.

    Tidak bisa dipilih, tanpa keterangan apa pun — dari kursi pengguna itu
    terlihat seperti aplikasi yang tidak menyediakan opsinya sama sekali.
    """
    from inaproc_autoinput.ui import assets_panel as ap

    for saringan in (ap.SARINGAN_PDF, ap.SARINGAN_FOTO, ap.SARINGAN_VIDEO):
        assert saringan.endswith("Semua berkas (*)"), saringan

    assert "*.PDF" in ap.SARINGAN_PDF
    assert "*.JPG" in ap.SARINGAN_FOTO and "*.PNG" in ap.SARINGAN_FOTO
    assert "*.MP4" in ap.SARINGAN_VIDEO


def test_berkas_huruf_besar_tetap_diterima_pemeriksa():
    """Boleh dipilih, dan memang sah — bukan cuma dibiarkan lalu ditolak."""
    from inaproc_autoinput.assets import periksa
    from inaproc_autoinput.schema import DOKUMEN_EXT

    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        berkas = pathlib.Path(d) / "SBU.PDF"
        berkas.write_bytes(b"%PDF-")
        assert periksa(str(berkas), DOKUMEN_EXT) == ""
