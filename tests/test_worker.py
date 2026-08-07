"""Uji loop antrean: apa yang dikerjakan, kapan berhenti, dan apa laporannya.

Dijalankan tanpa browser dan tanpa thread: `_kerjakan` diberi runner tiruan yang
mengembalikan hasil sesuai skenario. Yang diuji di sini keputusan-keputusannya,
bukan pengisian formnya -- itu sudah diuji terhadap halaman tiruan.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from inaproc_autoinput.runner import BATAS_GAGAL_BERUNTUN, Hasil, Mode  # noqa: E402
from inaproc_autoinput.ui.worker import RunWorker  # noqa: E402

SUKSES = Hasil(True, "tersimpan", tersimpan=True)
TERISI = Hasil(True, "terisi, menunggu kamu menyimpan")
GAGAL = Hasil(False, "Tombol 'Simpan' tidak aktif")
DIHENTIKAN = Hasil(False, "dihentikan sebelum selesai", dibatalkan=True)


class RunnerTiruan:
    """Mengembalikan hasil yang sudah disiapkan, satu per pemanggilan."""

    def __init__(self, urutan: list[Hasil], saat_baris=None):
        self.urutan = list(urutan)
        self.dipanggil = 0
        self._saat_baris = saat_baris or (lambda indeks: None)

    def jalankan(self, data, mode, catatan=None, assets=None, batal=None):
        self._saat_baris(self.dipanggil)
        self.dipanggil += 1
        if batal and batal():
            return DIHENTIKAN
        return self.urutan.pop(0)


def _worker(jumlah: int) -> RunWorker:
    jobs = [(i, {"nama_produk": f"Produk {i}"}) for i in range(jumlah)]
    return RunWorker(jobs, Mode.ISI_SAJA, "http://localhost:9222")


def test_antrean_penuh_tanpa_masalah():
    worker = _worker(3)
    ringkasan = worker._kerjakan(RunnerTiruan([SUKSES, TERISI, SUKSES]))

    assert (ringkasan.dikerjakan, ringkasan.sisa) == (3, 0)
    assert (ringkasan.sukses, ringkasan.terisi, ringkasan.gagal) == (2, 1, 0)
    assert not ringkasan.dihentikan and not ringkasan.beruntun


def test_gagal_beruntun_menghentikan_antrean():
    """Tiga gagal berturut-turut berarti sesinya rusak, bukan barisnya."""
    worker = _worker(10)
    ringkasan = worker._kerjakan(RunnerTiruan([GAGAL] * 10))

    assert ringkasan.beruntun
    assert ringkasan.dikerjakan == BATAS_GAGAL_BERUNTUN
    assert ringkasan.sisa == 10 - BATAS_GAGAL_BERUNTUN
    assert "sesinya" in ringkasan.alasan


def test_kegagalan_yang_diselingi_sukses_tidak_menghentikan():
    """Beberapa baris memang buruk sendiri-sendiri; itu bukan sesi yang rusak."""
    worker = _worker(6)
    ringkasan = worker._kerjakan(
        RunnerTiruan([GAGAL, GAGAL, SUKSES, GAGAL, GAGAL, SUKSES])
    )

    assert not ringkasan.beruntun
    assert (ringkasan.dikerjakan, ringkasan.gagal, ringkasan.sukses) == (6, 4, 2)


def test_berhenti_sebelum_baris_berikutnya_diambil():
    worker = _worker(5)
    tiruan = RunnerTiruan(
        [SUKSES] * 5,
        saat_baris=lambda indeks: worker.stop() if indeks == 1 else None,
    )
    ringkasan = worker._kerjakan(tiruan)

    # Baris ke-2 keburu diminta berhenti di tengah, jadi tidak dihitung selesai.
    assert ringkasan.dikerjakan == 1
    assert ringkasan.sisa == 4
    assert ringkasan.dihentikan
    assert tiruan.dipanggil == 2, "baris ke-3 tidak boleh ikut dimulai"


def test_baris_yang_dihentikan_tetap_terhitung_sisa():
    """Baris yang diputus di tengah belum dikerjakan, jadi masih harus diulang."""
    worker = _worker(4)
    ringkasan = worker._kerjakan(RunnerTiruan([SUKSES, DIHENTIKAN, SUKSES, SUKSES]))

    assert ringkasan.dikerjakan == 1
    assert ringkasan.sisa == 3
    assert ringkasan.dihentikan
    assert ringkasan.gagal == 0, "dihentikan bukan gagal"


def test_berhenti_diteruskan_ke_pengisi_form():
    """Tanpa ini, Berhenti baru terasa setelah baris berjalan selesai penuh."""
    worker = _worker(2)
    diterima = {}

    def jalankan(data, mode, catatan=None, assets=None, batal=None):
        diterima["batal"] = batal
        return SUKSES

    worker._kerjakan(type("R", (), {"jalankan": staticmethod(jalankan)})())

    assert diterima["batal"] is not None
    assert diterima["batal"]() is False
    worker.stop()
    assert diterima["batal"]() is True


def test_gagal_menyambung_melapor_lewat_tuntas_bukan_koneksi():
    """Antrean yang tidak pernah mulai tetap harus menutup dirinya sendiri.

    Kalau laporannya lewat sinyal uji-koneksi, jendela tidak pernah tahu
    antreannya berakhir dan tombolnya tinggal terkunci selamanya.
    """
    worker = _worker(7)
    terkumpul = []
    worker.tuntas.connect(terkumpul.append)
    worker.koneksi.connect(terkumpul.append)

    worker._gagal_menyambung("Tidak bisa menyambung ke Chrome di localhost:9222")

    assert len(terkumpul) == 1
    ringkasan = terkumpul[0]
    assert ringkasan.sisa == 7 and ringkasan.dikerjakan == 0
    assert "Tidak bisa menyambung" in ringkasan.alasan
