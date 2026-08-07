"""Uji perkabelan jendela: tombol, status baris, dan penyimpanan per baris.

Tanpa browser dan tanpa portal. Yang diuji di sini adalah apa yang terjadi pada
tabel dan berkas status ketika worker melaporkan hasil -- bagian yang paling
mudah salah sambung ketika antrean ditambahkan, dan paling mahal kalau salah:
status yang keliru membuat baris dikerjakan dua kali atau tidak sama sekali.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from inaproc_autoinput import state  # noqa: E402
from inaproc_autoinput.model import ProductRow, Status  # noqa: E402
from inaproc_autoinput.runner import Hasil, Ringkasan  # noqa: E402
from inaproc_autoinput.ui.main_window import MainWindow  # noqa: E402
from inaproc_autoinput.validation import Issue  # noqa: E402


@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def jendela(app, tmp_path):
    win = MainWindow()
    win._workbook_path = tmp_path / "produk.xlsx"
    yield win
    win.close()


def _rows(*status: Status) -> list[ProductRow]:
    return [
        ProductRow(excel_row=5 + i, data={"nama_produk": f"Produk {i}"}, status=s)
        for i, s in enumerate(status)
    ]


def _pasang(jendela, rows: list[ProductRow]) -> None:
    jendela._model.set_rows(rows)
    jendela._update_summary()


# --- tombol -----------------------------------------------------------------


def test_tombol_antrean_mati_saat_belum_ada_file(jendela):
    assert not jendela._btn_semua.isEnabled()
    assert not jendela._btn_sisa.isEnabled()
    assert not jendela._btn_stop.isEnabled()


def test_tombol_sisa_mati_bila_yang_tersisa_hanya_baris_gagal(jendela):
    """'Jalankan semua' masih ada gunanya, 'Lanjutkan sisanya' tidak."""
    _pasang(jendela, _rows(Status.GAGAL, Status.SUKSES))
    assert jendela._btn_semua.isEnabled()
    assert not jendela._btn_sisa.isEnabled()


def test_tombol_antrean_mati_saat_semua_sukses(jendela):
    _pasang(jendela, _rows(Status.SUKSES, Status.SUKSES))
    assert not jendela._btn_semua.isEnabled()
    assert not jendela._btn_sisa.isEnabled()


def test_semua_tombol_jalan_terkunci_saat_antrean_berjalan(jendela):
    _pasang(jendela, _rows(Status.MENUNGGU, Status.MENUNGGU))
    jendela._set_sedang_jalan(True)

    # Memuat ulang file di tengah antrean akan mengganti daftar barisnya di
    # bawah worker yang masih memegang posisi baris lama.
    for tombol in (jendela._btn_semua, jendela._btn_sisa, jendela._btn_satu,
                   jendela._btn_uji, jendela._btn_buka, jendela._btn_buat,
                   jendela._reload_button):
        assert not tombol.isEnabled()
    assert jendela._btn_stop.isEnabled()

    jendela._set_sedang_jalan(False)
    assert jendela._btn_semua.isEnabled()
    assert not jendela._btn_stop.isEnabled()


# --- status baris -----------------------------------------------------------


@pytest.mark.parametrize("hasil,harapan", [
    (Hasil(True, "tersimpan", tersimpan=True), Status.SUKSES),
    (Hasil(True, "terisi, menunggu kamu menyimpan"), Status.TERISI),
    (Hasil(False, "Tombol 'Simpan' tidak aktif"), Status.GAGAL),
    (Hasil(False, "dihentikan sebelum selesai", dibatalkan=True), Status.MENUNGGU),
])
def test_status_baris_mengikuti_hasil(jendela, hasil, harapan):
    """Empat hasil, empat status berbeda -- terutama dua yang gampang dicampur.

    "Terisi" bukan sukses (belum ada yang masuk portal) dan "dihentikan" bukan
    gagal (tidak ada yang salah dengan barisnya).
    """
    _pasang(jendela, _rows(Status.MENUNGGU))
    jendela._on_mulai(0)
    assert jendela._model.row_at(0).status is Status.BERJALAN

    jendela._on_hasil(0, hasil)
    assert jendela._model.row_at(0).status is harapan


def test_baris_dihentikan_masuk_lagi_ke_antrean_berikutnya(jendela):
    """Kalau ditandai gagal, 'Lanjutkan sisanya' akan melewatinya."""
    _pasang(jendela, _rows(Status.MENUNGGU, Status.MENUNGGU))
    jendela._on_hasil(0, Hasil(False, "dihentikan sebelum selesai",
                               dibatalkan=True))
    from inaproc_autoinput.model import antrean

    assert antrean(jendela._model.rows(), lewati_gagal=True) == [0, 1]


def test_status_disimpan_setiap_baris_bukan_di_akhir(jendela):
    """Aplikasi mati di baris ke-40 tidak boleh menghapus 39 baris sebelumnya."""
    _pasang(jendela, _rows(Status.MENUNGGU, Status.MENUNGGU))
    jendela._on_hasil(0, Hasil(True, "tersimpan", tersimpan=True, produk_id="abc"))

    berkas = state.state_path(jendela._workbook_path)
    tersimpan = json.loads(berkas.read_text(encoding="utf-8"))
    assert tersimpan["baris"]["5"]["status"] == "sukses"
    assert tersimpan["baris"]["5"]["produk_id"] == "abc"
    assert "6" not in tersimpan["baris"], "baris yang belum jalan belum ditulis"


def test_peringatan_ikut_terlihat_di_keterangan_baris(jendela):
    _pasang(jendela, _rows(Status.MENUNGGU))
    jendela._on_hasil(0, Hasil(True, "tersimpan", tersimpan=True,
                               peringatan=["Atribut 'X' tidak ada"]))
    assert "1 peringatan" in jendela._model.row_at(0).message


# --- laporan dan alasan -----------------------------------------------------


def test_laporan_menyebut_dihentikan_bukan_gagal(jendela):
    teks = jendela._laporan(
        Hasil(False, "dihentikan sebelum selesai", dibatalkan=True,
              langkah=["Kategori: A > B > C"]),
        ProductRow(excel_row=9, data={}),
    )
    assert teks.startswith("Baris 9 · DIHENTIKAN")
    assert "Kategori: A > B > C" in teks


def test_kenapa_kosong_membedakan_sebabnya(jendela):
    assert "Belum ada file" in jendela._kenapa_kosong()

    _pasang(jendela, _rows(Status.SUKSES))
    assert "sudah sukses" in jendela._kenapa_kosong()

    rusak = _rows(Status.MENUNGGU)
    rusak[0].issues = [Issue("harga_produk", "Harga Produk", "wajib diisi")]
    _pasang(jendela, rusak)
    assert "perbaiki" in jendela._kenapa_kosong().lower()

    _pasang(jendela, _rows(Status.GAGAL))
    assert "Jalankan semua" in jendela._kenapa_kosong()


def test_pesan_tuntas_menawarkan_lanjut_bila_masih_ada_sisa(jendela):
    teks = jendela._pesan_tuntas(Ringkasan(dikerjakan=4, sukses=4, sisa=6,
                                           dihentikan=True))
    assert "Lanjutkan sisanya" in teks
    assert "6 belum dikerjakan" in teks


def test_pesan_tuntas_tidak_menawarkan_lanjut_saat_browser_mati(jendela):
    """Menyuruh 'Lanjutkan sisanya' padahal browsernya mati cuma memutar-mutar."""
    teks = jendela._pesan_tuntas(
        Ringkasan(sisa=5, gagal_koneksi="Tidak bisa menyambung ke Chrome")
    )
    assert "Lanjutkan sisanya" not in teks
    assert "Tidak bisa menyambung" in teks
