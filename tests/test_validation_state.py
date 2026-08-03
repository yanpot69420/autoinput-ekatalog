"""Uji pemeriksaan baris dan penyimpanan status."""

from __future__ import annotations

import pytest

from inaproc_autoinput import state
from inaproc_autoinput.model import ProductRow, Status, rows_from_records
from inaproc_autoinput.validation import validate


@pytest.fixture(scope="module")
def berkas(tmp_path_factory):
    """Berkas contoh yang benar-benar ada, karena validator memeriksa keberadaannya."""
    root = tmp_path_factory.mktemp("berkas")
    foto = root / "galian.png"
    foto.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    dokumen = root / "sbu.pdf"
    dokumen.write_bytes(b"%PDF-1.4\n" + b"0" * 100)
    besar = root / "besar.pdf"
    besar.write_bytes(b"%PDF-1.4\n" + b"0" * (11 * 1024 * 1024))
    return {"foto": str(foto), "pdf": str(dokumen), "pdf_besar": str(besar)}


@pytest.fixture
def lengkap(berkas):
    return {
        "kategori": "Bidang Bina Marga > Divisi 3 Pekerjaan Tanah dan Geosintetik > 3.1 Galian",
        "produk_sektoral": "Galian Biasa",
        "nama_produk": "Galian Biasa untuk Badan Jalan",
        "foto_1": berkas["foto"],
        "kbki": "54310",
        "pdn_klasifikasi": "Lokal",
        "pdn_lokasi_produksi": "Diproduksi di seluruh Indonesia",
        "pdn_tenaga_kerja": "Dibuat oleh seluruh tenaga kerja Indonesia di dalam negeri",
        "pdn_bahan_baku": "Seluruh bahan baku dalam negeri",
        "ppn": "12%",
        "harga_produk": "85000",
        "stok": "1000",
        "satuan_produk": "Meter",
        "atribut_1_nama": "Satuan Pengukuran",
        "atribut_1_nilai": "M3",
        "dokumen_1_nama": "Sertifikat Standar",
        "dokumen_1_berkas": berkas["pdf"],
    }


def _errors(row):
    return [i for i in validate(row) if i.blocking]


def test_baris_lengkap_lolos(lengkap):
    assert _errors(lengkap) == []


def test_kolom_wajib_kosong_terdeteksi(lengkap):
    row = dict(lengkap)
    del row["harga_produk"]
    assert any(i.key == "harga_produk" for i in _errors(row))


def test_produk_sektoral_tidak_wajib(lengkap):
    """Bagian ini hanya muncul di sebagian kategori, jadi tidak bisa diwajibkan.

    Kategori Jasa 3.1 Galian punya Daftar Produk Sektoral; kategori Barang
    Meja Kerja tidak punya bagian itu sama sekali.
    """
    row = dict(lengkap)
    del row["produk_sektoral"]
    assert not [i for i in _errors(row) if i.key == "produk_sektoral"]


# --- batas panjang mengikuti form, bukan template unggah massal -------------


def test_nama_lima_karakter_lolos(lengkap):
    assert not [i for i in _errors(dict(lengkap, nama_produk="Pagar")) if i.key == "nama_produk"]


def test_nama_empat_karakter_ditolak(lengkap):
    assert any(i.key == "nama_produk" for i in _errors(dict(lengkap, nama_produk="Cor")))


def test_nama_lebih_dari_250_ditolak(lengkap):
    assert any(i.key == "nama_produk" for i in _errors(dict(lengkap, nama_produk="A" * 251)))


def test_deskripsi_seratus_karakter_lolos(lengkap):
    """Template unggah massal membatasi 100; form membolehkan sampai 2000."""
    row = dict(lengkap, deskripsi="Pekerjaan galian biasa. " * 20)
    assert not [i for i in _errors(row) if i.key == "deskripsi"]


def test_deskripsi_lebih_dari_2000_ditolak(lengkap):
    assert any(i.key == "deskripsi" for i in _errors(dict(lengkap, deskripsi="A" * 2001)))


# --- harga ------------------------------------------------------------------


def test_harga_harus_angka_polos(lengkap):
    pesan = [i.message for i in _errors(dict(lengkap, harga_produk="Rp 85.000,-"))]
    assert any("angka polos" in m for m in pesan)


def test_harga_nol_ditolak(lengkap):
    assert any(i.key == "harga_produk" for i in _errors(dict(lengkap, harga_produk="0")))


def test_pilihan_di_luar_daftar_ditolak(lengkap):
    assert any(i.key == "ppn" for i in _errors(dict(lengkap, ppn="11%")))


def test_pre_order_hari_wajib_saat_aktif(lengkap):
    assert any(i.key == "pre_order_hari" for i in _errors(dict(lengkap, pre_order="Aktif")))


# --- berkas -----------------------------------------------------------------


def test_produk_tanpa_foto_ditolak(lengkap):
    row = {k: v for k, v in lengkap.items() if k != "foto_1"}
    assert any(i.key == "foto_1" for i in _errors(row))


def test_foto_berupa_tautan_ditolak(lengkap):
    """Form meminta unggah berkas, bukan tautan seperti pada unggah massal."""
    row = dict(lengkap, foto_1="https://i.imgur.com/ErNwW2p.png")
    assert any(i.key == "foto_1" for i in _errors(row))


def test_foto_tidak_ada_di_disk_ditolak(lengkap):
    row = dict(lengkap, foto_1="/tidak/ada/galian.png")
    pesan = [i.message for i in _errors(row) if i.key == "foto_1"]
    assert pesan and "tidak ditemukan" in pesan[0]


def test_foto_format_salah_ditolak(lengkap, berkas):
    row = dict(lengkap, foto_1=berkas["pdf"])
    pesan = [i.message for i in _errors(row) if i.key == "foto_1"]
    assert pesan and "format harus" in pesan[0]


def test_dokumen_melebihi_batas_ukuran_ditolak(lengkap, berkas):
    row = dict(lengkap, video_berkas=berkas["pdf_besar"])
    assert any(i.key == "video_berkas" for i in _errors(row))


def test_dokumen_bukan_pdf_ditolak(lengkap, berkas):
    row = dict(lengkap, dokumen_1_berkas=berkas["foto"])
    assert any("Sertifikat Standar" in i.label for i in _errors(row))


def test_dokumen_hilang_di_disk_ditolak(lengkap):
    row = dict(lengkap, dokumen_1_berkas="/tidak/ada/sbu.pdf")
    assert any("tidak ditemukan" in i.message for i in _errors(row))


# --- blok berpasangan -------------------------------------------------------


def test_atribut_bernama_tanpa_nilai_ditolak(lengkap):
    row = dict(lengkap, atribut_2_nama="Kode Produk", atribut_2_nilai="")
    assert any("Kode Produk" in i.label for i in _errors(row))


def test_nilai_tanpa_nama_atribut_ditolak(lengkap):
    row = dict(lengkap, atribut_2_nama="", atribut_2_nilai="M3")
    assert any("nama atributnya kosong" in i.message for i in _errors(row))


def test_dokumen_bernama_tanpa_berkas_ditolak(lengkap):
    row = dict(lengkap, dokumen_2_nama="Sertifikat Standar", dokumen_2_berkas="")
    assert any("path berkasnya" in i.message for i in _errors(row))


def test_tanpa_atribut_hanya_peringatan(lengkap):
    row = {k: v for k, v in lengkap.items() if not k.startswith("atribut_")}
    atribut = [i for i in validate(row) if i.key == "atribut_1_nama"]
    assert atribut and not atribut[0].blocking


# --- status -----------------------------------------------------------------


def _rows(lengkap):
    rows = rows_from_records([dict(lengkap, _row=5), dict(lengkap, _row=6)])
    rows[0].status = Status.SUKSES
    rows[0].produk_id = "12345"
    rows[1].status = Status.GAGAL
    rows[1].message = "KBKI ditolak portal"
    return rows


def test_status_tersimpan_dan_dipulihkan(tmp_path, lengkap):
    book = tmp_path / "produk.xlsx"
    state.save(book, _rows(lengkap))

    segar = rows_from_records([dict(lengkap, _row=5), dict(lengkap, _row=6)])
    assert state.apply(book, segar) == 2
    assert segar[0].status is Status.SUKSES and segar[0].produk_id == "12345"
    assert segar[1].status is Status.GAGAL


def test_data_berubah_membatalkan_status_sukses(tmp_path, lengkap):
    book = tmp_path / "produk.xlsx"
    state.save(book, _rows(lengkap))

    diubah = rows_from_records([dict(lengkap, _row=5, harga_produk="99000")])
    state.apply(book, diubah)
    assert diubah[0].status is Status.MENUNGGU
    assert "berubah" in diubah[0].message


def test_status_berjalan_dianggap_belum_selesai(tmp_path, lengkap):
    book = tmp_path / "produk.xlsx"
    state.save(book, [ProductRow(excel_row=5, data=dict(lengkap), status=Status.BERJALAN)])

    segar = rows_from_records([dict(lengkap, _row=5)])
    state.apply(book, segar)
    assert segar[0].status is Status.MENUNGGU
    assert "terhenti" in segar[0].message


def test_tanpa_berkas_status_tidak_error(tmp_path, lengkap):
    assert state.apply(tmp_path / "belum-ada.xlsx", _rows(lengkap)) == 0


def test_lampiran_terbaca_dari_baris(lengkap, berkas):
    row = rows_from_records([dict(lengkap, _row=5)])[0]
    assert row.lampiran == {"Sertifikat Standar": berkas["pdf"]}
    assert row.atribut == {"Satuan Pengukuran": "M3"}
