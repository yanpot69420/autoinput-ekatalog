"""Uji pemilihan baris untuk antrean, dan ringkasan hasilnya.

Dua tombol memakai daftar yang sama dengan satu perbedaan, dan perbedaan itu
gampang tergeser tanpa sengaja -- karena itu diuji satu per satu.
"""

from __future__ import annotations

from inaproc_autoinput.model import ProductRow, Status, antrean
from inaproc_autoinput.runner import BATAS_GAGAL_BERUNTUN, Ringkasan
from inaproc_autoinput.validation import Issue


def _baris(status: Status = Status.MENUNGGU, error: bool = False) -> ProductRow:
    row = ProductRow(excel_row=5, data={"nama_produk": "X"}, status=status)
    if error:
        row.issues = [Issue("harga_produk", "Harga Produk", "wajib diisi")]
    return row


def test_semua_baris_menunggu_masuk_antrean():
    rows = [_baris(), _baris(), _baris()]
    assert antrean(rows) == [0, 1, 2]
    assert antrean(rows, lewati_gagal=True) == [0, 1, 2]


def test_baris_sukses_tidak_pernah_diulang():
    """Mengulangnya membuat produk kedua di portal, bukan memperbarui yang ada."""
    rows = [_baris(Status.SUKSES), _baris()]
    assert antrean(rows) == [1]
    assert antrean(rows, lewati_gagal=True) == [1]


def test_baris_ber_error_dilewati():
    rows = [_baris(error=True), _baris()]
    assert antrean(rows) == [1]


def test_baris_gagal_diulang_jalankan_semua_tapi_tidak_lanjutkan_sisanya():
    rows = [_baris(Status.GAGAL), _baris()]
    assert antrean(rows) == [0, 1]
    assert antrean(rows, lewati_gagal=True) == [1]


def test_baris_terisi_selalu_ikut():
    """Terisi bukan selesai: belum ada apa pun yang masuk ke portal.

    Kalau baris ini ikut dilewati 'Lanjutkan sisanya', produknya hilang diam-diam
    dari daftar pekerjaan padahal tidak pernah tersimpan.
    """
    rows = [_baris(Status.TERISI)]
    assert antrean(rows) == [0]
    assert antrean(rows, lewati_gagal=True) == [0]


def test_baris_gagal_yang_juga_ber_error_tetap_dilewati():
    rows = [_baris(Status.GAGAL, error=True)]
    assert antrean(rows) == []


# --- ringkasan --------------------------------------------------------------


def test_ringkasan_menyebut_yang_terisi_terpisah_dari_sukses():
    r = Ringkasan(dikerjakan=5, sukses=2, terisi=3)
    assert "2 tersimpan" in r.pesan
    assert "3 terisi" in r.pesan
    assert r.alasan == ""


def test_ringkasan_menghitung_sisa_saat_dihentikan():
    r = Ringkasan(dikerjakan=4, sukses=4, sisa=6, dihentikan=True)
    assert "6 belum dikerjakan" in r.pesan
    assert "Dihentikan" in r.alasan


def test_ringkasan_menjelaskan_berhenti_karena_gagal_beruntun():
    r = Ringkasan(dikerjakan=3, gagal=3, sisa=48, beruntun=True)
    assert str(BATAS_GAGAL_BERUNTUN) in r.alasan
    assert "sesinya" in r.alasan  # menunjuk ke sesi, bukan menyalahkan barisnya


def test_ringkasan_gagal_koneksi_tidak_menyalahkan_baris():
    r = Ringkasan(sisa=12, gagal_koneksi="Tidak bisa menyambung ke Chrome\nrinci")
    assert r.pesan.startswith("Tidak ada baris yang dikerjakan")
    assert "\n" not in r.pesan  # pesan satu baris untuk status bar
    assert r.alasan.startswith("Tidak bisa menyambung")
