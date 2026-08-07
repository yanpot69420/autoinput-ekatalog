"""Menjalankan pengisian di thread terpisah supaya jendela tidak membeku."""

from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from ..assets import Assets
from ..runner import (
    BATAS_GAGAL_BERUNTUN,
    BrowserRunner,
    Hasil,
    Mode,
    Ringkasan,
    RunnerError,
    pesan_penghalang,
)


class RunWorker(QThread):
    """Menyambung ke browser, mengerjakan antrean baris, lalu melepasnya.

    Sambungan sengaja dibuat dan ditutup di dalam thread ini. Playwright versi
    sinkron terikat pada thread yang membuatnya, jadi objeknya tidak boleh
    dibuat di thread jendela lalu dipakai di sini.

    Satu sambungan dipakai untuk seluruh antrean. Menyambung ulang tiap baris
    berarti membayar ongkos start Playwright puluhan kali tanpa ada gunanya --
    tab yang dipakai tetap sama.
    """

    langkah = Signal(str)
    mulai = Signal(int)          # posisi baris yang mulai dikerjakan
    hasil = Signal(int, object)  # posisi baris, Hasil
    tuntas = Signal(object)      # Ringkasan, saat antrean selesai atau berhenti
    koneksi = Signal(object)     # Hasil, khusus uji koneksi

    def __init__(self, jobs: list[tuple[int, dict]] | None, mode: Mode,
                 cdp_url: str, assets: Assets | None = None, parent=None):
        super().__init__(parent)
        # jobs None berarti cuma menguji koneksi, tanpa menyentuh form.
        self._jobs = jobs
        # Combobox Qt mengembalikan nilai enum sebagai str biasa.
        self._mode = Mode(mode)
        self._cdp_url = cdp_url
        self._assets = assets
        self._berhenti = threading.Event()

    def stop(self) -> None:
        """Minta antrean berhenti. Aman dipanggil dari thread jendela."""
        self._berhenti.set()

    @property
    def diminta_berhenti(self) -> bool:
        return self._berhenti.is_set()

    def run(self) -> None:  # dipanggil Qt di thread baru
        runner = BrowserRunner(self._cdp_url)
        try:
            self.langkah.emit("Menyambung ke browser…")
            runner.connect()
        except RunnerError as error:
            self._gagal_menyambung(str(error))
            return
        except Exception as error:  # noqa: BLE001 -- apa pun dari lapisan browser
            self._gagal_menyambung(f"{type(error).__name__}: {error}")
            return

        try:
            if self._jobs is None:
                # Tersambung belum berarti bisa dipakai: sesi yang sudah
                # berakhir menampilkan modal beroverlay, dan uji koneksi adalah
                # tempat paling awal untuk mengetahuinya.
                halangan = runner.penghalang()
                if halangan:
                    self.koneksi.emit(Hasil(False, pesan_penghalang(halangan)))
                    return
                # Menguji koneksi tidak membuka tab. Belum adanya tab portal
                # bukan masalah -- tabnya dibuat nanti, saat ada baris yang
                # benar-benar dikerjakan.
                if runner.page is None:
                    self.koneksi.emit(Hasil(
                        True, "Tersambung. Belum ada tab portal terbuka — "
                              "tabnya dibuat saat baris pertama dijalankan."))
                    return
                self.koneksi.emit(Hasil(
                    True, f"Tersambung. Tab portal: {runner.page.url}"))
                return
            self.tuntas.emit(self._kerjakan(runner))
        finally:
            runner.close()

    def _gagal_menyambung(self, pesan: str) -> None:
        """Tanpa browser tidak ada baris yang bisa dikerjakan sama sekali."""
        if self._jobs is None:
            self.koneksi.emit(Hasil(False, pesan))
            return
        self.langkah.emit(pesan)
        self.tuntas.emit(Ringkasan(sisa=len(self._jobs), gagal_koneksi=pesan))

    def _kerjakan(self, runner: BrowserRunner) -> Ringkasan:
        ringkasan = Ringkasan(sisa=len(self._jobs))
        beruntun = 0

        for posisi, data in self._jobs:
            if self._berhenti.is_set():
                ringkasan.dihentikan = True
                break

            self.mulai.emit(posisi)
            hasil = runner.jalankan(
                data, self._mode, catatan=self.langkah.emit,
                assets=self._assets, batal=self._berhenti.is_set,
            )
            self.hasil.emit(posisi, hasil)

            if hasil.dibatalkan:
                # Baris ini tidak jadi dikerjakan, jadi tetap dihitung sisa.
                ringkasan.dihentikan = True
                break

            ringkasan.dikerjakan += 1
            ringkasan.sisa -= 1
            if not hasil.berhasil:
                beruntun += 1
                ringkasan.gagal += 1
                if beruntun >= BATAS_GAGAL_BERUNTUN:
                    ringkasan.beruntun = True
                    break
                continue

            beruntun = 0
            if hasil.tersimpan:
                ringkasan.sukses += 1
            else:
                ringkasan.terisi += 1

        return ringkasan


__all__ = ["RunWorker"]
