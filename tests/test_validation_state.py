"""Uji pemeriksaan baris dan penyimpanan status."""

from __future__ import annotations

import pytest

from inaproc_autoinput import state
from inaproc_autoinput.model import ProductRow, Status, rows_from_records
from inaproc_autoinput.validation import validate


@pytest.fixture
def lengkap():
    return {
        "kategori": "Bidang Bina Marga > Divisi 3 Pekerjaan Tanah dan Geosintetik > 3.1 Galian",
        "produk_sektoral": "Galian Biasa",
        "nama_produk": "Galian Biasa untuk Badan Jalan",
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
    }


def _errors(row):
    return [i for i in validate(row) if i.blocking]


def test_baris_lengkap_lolos(lengkap):
    assert _errors(lengkap) == []


def test_kolom_wajib_kosong_terdeteksi(lengkap):
    row = dict(lengkap)
    del row["harga_produk"]
    assert any(i.key == "harga_produk" for i in _errors(row))


def test_produk_sektoral_wajib(lengkap):
    """Form menandainya Wajib begitu kategori dipilih."""
    row = dict(lengkap)
    del row["produk_sektoral"]
    assert any(i.key == "produk_sektoral" for i in _errors(row))


def test_pdn_tidak_wajib(lengkap):
    """Tiga pertanyaan self-declare PDN tidak bertanda Wajib di form.

    Portal sudah mengisinya dengan jawaban bawaan, jadi memblokir baris karena
    ketiganya kosong akan menolak sesuatu yang portal sendiri terima.
    """
    row = {k: v for k, v in lengkap.items() if not k.startswith("pdn_lokasi")
           and not k.startswith("pdn_tenaga") and not k.startswith("pdn_bahan")}
    assert not [i for i in _errors(row) if i.key.startswith("pdn_")
                and i.key != "pdn_klasifikasi"]


def test_klasifikasi_pdn_tetap_wajib(lengkap):
    row = {k: v for k, v in lengkap.items() if k != "pdn_klasifikasi"}
    assert any(i.key == "pdn_klasifikasi" for i in _errors(row))


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


def test_pemisah_ribuan_ditolak_dengan_angka_benarnya(lengkap):
    """'1.000' dibaca portal sebagai 1 -- meleset seribu kali tanpa disadari."""
    pesan = [i.message for i in _errors(dict(lengkap, stok="1.000")) if i.key == "stok"]
    assert pesan and "terbaca portal sebagai 1, bukan 1000" in pesan[0]
    assert "1000" in pesan[0]


def test_desimal_dua_digit_lolos(lengkap):
    for nilai in ("332,35", "332.35", "1,5", "1000"):
        assert not [i for i in _errors(dict(lengkap, stok=nilai)) if i.key == "stok"], nilai


def test_desimal_lebih_dari_dua_digit_ditolak(lengkap):
    """Form membatasi maksimal dua digit di belakang koma."""
    pesan = [i.message for i in _errors(dict(lengkap, stok="0,055")) if i.key == "stok"]
    assert pesan and "dua digit" in pesan[0]


def test_harga_nol_ditolak(lengkap):
    assert any(i.key == "harga_produk" for i in _errors(dict(lengkap, harga_produk="0")))


def test_pilihan_di_luar_daftar_ditolak(lengkap):
    assert any(i.key == "ppn" for i in _errors(dict(lengkap, ppn="11%")))


def test_pre_order_hari_wajib_saat_aktif(lengkap):
    assert any(i.key == "pre_order_hari" for i in _errors(dict(lengkap, pre_order="Aktif")))


# --- blok berpasangan -------------------------------------------------------


def test_atribut_bernama_tanpa_nilai_ditolak(lengkap):
    row = dict(lengkap, atribut_2_nama="Kode Produk", atribut_2_nilai="")
    assert any("Kode Produk" in i.label for i in _errors(row))


def test_nilai_tanpa_nama_atribut_ditolak(lengkap):
    row = dict(lengkap, atribut_2_nama="", atribut_2_nilai="M3")
    assert any("nama atributnya kosong" in i.message for i in _errors(row))


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


def test_atribut_terbaca_dari_baris(lengkap):
    row = rows_from_records([dict(lengkap, _row=5)])[0]
    assert row.atribut == {"Satuan Pengukuran": "M3"}


def test_status_terisi_belum_dianggap_selesai(lengkap):
    """Baris yang cuma terisi masih harus dikerjakan, jadi tetap 'siap'."""
    row = rows_from_records([dict(lengkap, _row=5)])[0]
    row.status = Status.TERISI
    assert row.siap

    row.status = Status.SUKSES
    assert not row.siap
