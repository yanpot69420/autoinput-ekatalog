"""Menjalankan pengisian di thread terpisah supaya jendela tidak membeku."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from ..runner import BrowserRunner, Hasil, Mode, RunnerError


class RunWorker(QThread):
    """Menyambung ke browser, mengisi satu baris, lalu melepas sambungan.

    Sambungan sengaja dibuat dan ditutup di dalam thread ini. Playwright versi
    sinkron terikat pada thread yang membuatnya, jadi objeknya tidak boleh
    dibuat di thread jendela lalu dipakai di sini.
    """

    langkah = Signal(str)
    selesai = Signal(object)  # Hasil

    def __init__(self, data: dict | None, mode: Mode, cdp_url: str, parent=None):
        super().__init__(parent)
        self._data = data
        self._mode = mode
        self._cdp_url = cdp_url

    def run(self) -> None:  # dipanggil Qt di thread baru
        runner = BrowserRunner(self._cdp_url)
        try:
            self.langkah.emit("Menyambung ke browser…")
            runner.connect()
        except RunnerError as error:
            self.selesai.emit(Hasil(False, str(error)))
            return
        except Exception as error:  # noqa: BLE001 -- apa pun dari lapisan browser
            self.selesai.emit(Hasil(False, f"{type(error).__name__}: {error}"))
            return

        try:
            if self._data is None:
                alamat = runner.page.url if runner.page else "(tanpa halaman)"
                self.selesai.emit(Hasil(True, f"Tersambung. Tab aktif: {alamat}"))
                return
            self.langkah.emit("Membuka halaman tambah produk…")
            self.selesai.emit(
                runner.jalankan(self._data, self._mode, catatan=self.langkah.emit)
            )
        finally:
            runner.close()


__all__ = ["RunWorker"]
