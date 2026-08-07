"""Uji berkas: dokumen PDF, foto, dan video yang dipilih lewat aplikasi."""

from __future__ import annotations

import pytest

from inaproc_autoinput.assets import (
    DOKUMEN_LAZIM,
    IKUT_BERKAS,
    MAKS_FOTO,
    Assets,
    periksa,
    state_path,
)
from inaproc_autoinput.schema import DOKUMEN_EXT, FOTO_EXT, VIDEO_EXT

SBU = "Sertifikat Badan Usaha (SBU) Konstruksi"
MASA_SBU = "Masa Berlaku Sertifikat Badan Usaha (SBU) Konstruksi"


@pytest.fixture(scope="module")
def berkas(tmp_path_factory):
    root = tmp_path_factory.mktemp("berkas")
    foto = root / "galian.png"
    foto.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    foto2 = root / "galian-2.jpg"
    foto2.write_bytes(b"\xff\xd8\xff" + b"0" * 100)
    pdf = root / "sbu.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"0" * 100)
    besar = root / "besar.pdf"
    besar.write_bytes(b"%PDF-1.4\n" + b"0" * (11 * 1024 * 1024))
    return {k: str(v) for k, v in
            {"foto": foto, "foto2": foto2, "pdf": pdf, "pdf_besar": besar}.items()}


# --- pemeriksaan berkas -----------------------------------------------------


def test_periksa_berkas_sehat(berkas):
    assert periksa(berkas["foto"], FOTO_EXT) == ""
    assert periksa(berkas["pdf"], DOKUMEN_EXT, 10) == ""


def test_periksa_kosong():
    assert periksa("", FOTO_EXT) == "belum dipilih"


def test_periksa_format_salah(berkas):
    assert "format harus" in periksa(berkas["pdf"], FOTO_EXT)


def test_periksa_tidak_ada():
    assert "tidak ditemukan" in periksa("/tidak/ada/galian.png", FOTO_EXT)


def test_periksa_terlalu_besar(berkas):
    assert "batasnya 10 MB" in periksa(berkas["pdf_besar"], DOKUMEN_EXT, 10)


def test_periksa_video_menerima_mov():
    assert "format harus" in periksa("/x/klip.avi", VIDEO_EXT)


# --- dokumen ----------------------------------------------------------------


def test_masa_berlaku_sbu_ikut_berkas_sbu(berkas):
    """Portal minta dua unggahan, isinya dokumen yang sama."""
    a = Assets()
    a.set_dokumen(SBU, berkas["pdf"])
    assert a.dokumen[SBU] == berkas["pdf"]
    assert a.dokumen[MASA_SBU] == berkas["pdf"]


def test_menghapus_sbu_ikut_menghapus_masa_berlakunya(berkas):
    a = Assets()
    a.set_dokumen(SBU, berkas["pdf"])
    a.set_dokumen(SBU, "")
    assert SBU not in a.dokumen and MASA_SBU not in a.dokumen


def test_daftar_dokumen_lazim_memuat_empat_yang_diminta_portal():
    assert len(DOKUMEN_LAZIM) == 4
    assert SBU in DOKUMEN_LAZIM and MASA_SBU in DOKUMEN_LAZIM
    assert IKUT_BERKAS[MASA_SBU] == SBU


# --- foto -------------------------------------------------------------------


def test_foto_umum_dipakai_semua_baris(berkas):
    a = Assets(foto_umum=[berkas["foto"]])
    assert a.foto_untuk(5) == [berkas["foto"]]
    assert a.foto_untuk(99) == [berkas["foto"]]


def test_foto_baris_menimpa_foto_umum(berkas):
    a = Assets(foto_umum=[berkas["foto"]])
    a.set_foto_baris(7, [berkas["foto2"]])
    assert a.foto_untuk(7) == [berkas["foto2"]]
    assert a.foto_untuk(8) == [berkas["foto"]]


def test_foto_baris_dikosongkan_kembali_ke_umum(berkas):
    a = Assets(foto_umum=[berkas["foto"]])
    a.set_foto_baris(7, [berkas["foto2"]])
    a.set_foto_baris(7, [])
    assert a.foto_untuk(7) == [berkas["foto"]]


def test_foto_dibatasi_lima(berkas):
    a = Assets()
    a.set_foto_baris(5, [berkas["foto"]] * 8)
    assert len(a.foto_untuk(5)) == MAKS_FOTO


# --- kesiapan ---------------------------------------------------------------


def test_tanpa_apa_apa_tetap_bisa_jalan_lewat_placeholder():
    """Form mewajibkan minimal satu foto; placeholder membuka jalannya."""
    a = Assets()
    assert a.masalah() == []
    assert a.baris_pakai_placeholder(5)
    # Pemakaiannya tidak boleh diam-diam.
    assert any("placeholder" in c.lower() for c in a.catatan())
    assert any("dokumen" in c.lower() for c in a.catatan())


def test_tanpa_foto_dan_tanpa_placeholder_belum_siap():
    a = Assets(pakai_placeholder=False)
    assert any("Foto" in m for m in a.masalah())


def test_foto_khusus_per_baris_tidak_bikin_alarm_palsu(berkas):
    """Ringkasan tidak boleh mengeluh 'belum ada foto' bila tiap baris punya sendiri."""
    a = Assets(pakai_placeholder=False)
    a.set_foto_baris(5, [berkas["foto"]])
    assert not [m for m in a.masalah() if "belum ada foto" in m]

    kosong = Assets(pakai_placeholder=False)
    assert [m for m in kosong.masalah() if "belum ada foto" in m]


def test_foto_asli_menang_atas_placeholder(berkas):
    a = Assets(foto_umum=[berkas["foto"]])
    assert not a.baris_pakai_placeholder(5)
    a.set_foto_baris(9, [berkas["foto2"]])
    assert a.foto_untuk(9) == [berkas["foto2"]]
    assert not any("placeholder" in c.lower() for c in a.catatan())


def test_catatan_menyebut_baris_yang_berfoto_sendiri(berkas):
    a = Assets()
    a.set_foto_baris(7, [berkas["foto"]])
    catatan = " ".join(a.catatan())
    assert "1 baris berfoto sendiri" in catatan
    assert not a.baris_pakai_placeholder(7)
    assert a.baris_pakai_placeholder(8)


def test_dokumen_rusak_tetap_jadi_masalah(berkas):
    a = Assets(foto_umum=[berkas["foto"]])
    a.set_dokumen("Sertifikat Standar", "/tidak/ada/s.pdf")
    assert a.catatan() == []
    assert any("tidak ditemukan" in m for m in a.masalah())


def test_lengkap_dianggap_siap(berkas):
    a = Assets(foto_umum=[berkas["foto"]])
    for nama in DOKUMEN_LAZIM:
        a.set_dokumen(nama, berkas["pdf"])
    assert a.siap(), a.masalah()


def test_berkas_hilang_terdeteksi(berkas):
    a = Assets(foto_umum=["/tidak/ada/foto.png"])

    a.set_dokumen(SBU, berkas["pdf"])
    assert any("tidak ditemukan" in m for m in a.masalah())


def test_dokumen_terlalu_besar_terdeteksi(berkas):
    a = Assets(foto_umum=[berkas["foto"]])
    a.set_dokumen("Sertifikat Standar", berkas["pdf_besar"])
    assert any("batasnya 10 MB" in m for m in a.masalah())


def test_kesiapan_diperiksa_per_baris(berkas):
    """Baris tanpa foto khusus tetap memakai foto umum, jadi tetap siap."""
    a = Assets(foto_umum=[berkas["foto"]])
    for nama in DOKUMEN_LAZIM:
        a.set_dokumen(nama, berkas["pdf"])
    assert a.siap(excel_row=5)

    a.foto_umum = []
    a.pakai_placeholder = False
    a.set_foto_baris(5, [berkas["foto"]])
    assert a.siap(excel_row=5)
    assert not a.siap(excel_row=6)


# --- penyimpanan ------------------------------------------------------------


def test_simpan_dan_muat_ulang(tmp_path, berkas):
    book = tmp_path / "produk.xlsx"
    a = Assets(foto_umum=[berkas["foto"]], video=berkas["foto"])
    a.set_dokumen(SBU, berkas["pdf"])
    a.set_foto_baris(9, [berkas["foto2"]])
    a.save(book)

    b = Assets.load(book)
    assert b.dokumen == a.dokumen
    assert b.foto_umum == a.foto_umum
    assert b.foto_baris == {9: [berkas["foto2"]]}   # kunci baris tetap angka
    assert b.video == a.video


def test_berkas_pendamping_di_sebelah_workbook(tmp_path):
    assert state_path(tmp_path / "produk.xlsx").name == "produk.berkas.json"


def test_muat_tanpa_berkas_pendamping(tmp_path):
    assert Assets.load(tmp_path / "belum-ada.xlsx").kosong


def test_muat_berkas_rusak_tidak_error(tmp_path):
    book = tmp_path / "produk.xlsx"
    state_path(book).write_text("{bukan json", encoding="utf-8")
    assert Assets.load(book).kosong


# --- placeholder ------------------------------------------------------------


def test_placeholder_dihasilkan_sebagai_png_sah(tmp_path):
    """Ditulis sendiri dengan zlib, jadi kelayakannya perlu dibuktikan."""
    import struct

    from inaproc_autoinput import placeholder

    path = placeholder.buat(tmp_path / "ph.png")
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

    lebar, tinggi, kedalaman, tipe = struct.unpack(">IIBB", data[16:26])
    assert (lebar, tinggi) == (placeholder.SISI, placeholder.SISI)
    assert kedalaman == 8 and tipe == 2  # RGB
    # Portal menerima 300x300 sampai 2048x2048.
    assert 300 <= lebar <= 2048


def test_pastikan_membuat_sekali_lalu_memakai_ulang(tmp_path):
    from inaproc_autoinput import placeholder

    path = tmp_path / "ph.png"
    assert not path.exists()
    placeholder.pastikan(path)
    assert path.exists()

    sebelum = path.stat().st_mtime_ns
    placeholder.pastikan(path)
    assert path.stat().st_mtime_ns == sebelum


def test_placeholder_ikut_tersimpan(tmp_path, berkas):
    book = tmp_path / "produk.xlsx"
    Assets(pakai_placeholder=False).save(book)
    assert Assets.load(book).pakai_placeholder is False

    Assets().save(book)
    assert Assets.load(book).pakai_placeholder is True
