"""Panel pemilih berkas: dokumen PDF, foto, dan video.

Menggantikan kolom path yang dulu ada di Excel. Dokumen dan foto umum berlaku
untuk semua baris; foto khusus hanya untuk baris yang sedang dipilih.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..assets import DOKUMEN_LAZIM, IKUT_BERKAS, MAKS_FOTO, Assets, periksa
from ..schema import BATAS_DOKUMEN_MB, DOKUMEN_EXT, FOTO_EXT, VIDEO_EXT

SARINGAN_PDF = "Dokumen PDF (*.pdf)"
SARINGAN_FOTO = "Gambar (*.jpg *.jpeg *.png)"
SARINGAN_VIDEO = "Video (*.mp4 *.mov)"

_HIJAU = "color: #2e7d32;"
_MERAH = "color: #c62828;"
_ABU = "color: #808080;"


def _ringkas(path_teks: str, lebar: int = 52) -> str:
    if not path_teks:
        return "belum dipilih"
    nama = Path(path_teks).name
    return nama if len(nama) <= lebar else nama[: lebar - 1] + "…"


class AssetsPanel(QWidget):
    """Panel Berkas. Memancarkan `changed` setiap kali pilihan berubah."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._assets = Assets()
        self._baris: int | None = None
        self._nama_baris = ""
        self._build()
        self.refresh()

    # --- penyusunan ---------------------------------------------------------

    def _build(self) -> None:
        luar = QVBoxLayout(self)
        luar.setContentsMargins(0, 0, 0, 0)

        gulir = QScrollArea()
        gulir.setWidgetResizable(True)
        gulir.setFrameShape(QFrame.NoFrame)
        isi = QWidget()
        self._layout = QVBoxLayout(isi)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(12)

        self._layout.addWidget(self._judul(
            "Dokumen PDF", "Berlaku untuk semua baris. Maksimal "
            f"{BATAS_DOKUMEN_MB} MB per berkas."
        ))
        self._dok_label: dict[str, QLabel] = {}
        kisi = QGridLayout()
        kisi.setColumnStretch(1, 1)
        kisi.setHorizontalSpacing(10)
        for baris, nama in enumerate(DOKUMEN_LAZIM):
            kisi.addWidget(QLabel(nama), baris, 0)
            nilai = QLabel()
            nilai.setStyleSheet(_ABU)
            kisi.addWidget(nilai, baris, 1)
            self._dok_label[nama] = nilai
            if nama in IKUT_BERKAS:
                catatan = QLabel("mengikuti SBU")
                catatan.setStyleSheet(_ABU)
                kisi.addWidget(catatan, baris, 2)
            else:
                pilih = QPushButton("Pilih…")
                pilih.clicked.connect(lambda _=False, n=nama: self._pilih_dokumen(n))
                kisi.addWidget(pilih, baris, 2)
                hapus = QPushButton("Hapus")
                hapus.clicked.connect(lambda _=False, n=nama: self._hapus_dokumen(n))
                kisi.addWidget(hapus, baris, 3)
        self._layout.addLayout(kisi)

        self._layout.addWidget(self._judul(
            "Foto produk", f"Maksimal {MAKS_FOTO} foto, format .jpg .jpeg .png."
        ))
        self._foto_umum = QLabel()
        self._foto_umum.setStyleSheet(_ABU)
        self._layout.addLayout(self._baris_tombol(
            "Foto untuk semua baris", self._foto_umum,
            [("Pilih…", self._pilih_foto_umum), ("Kosongkan", self._hapus_foto_umum)],
        ))

        self._foto_khusus = QLabel()
        self._foto_khusus.setStyleSheet(_ABU)
        self._label_khusus = QLabel("Foto khusus baris terpilih")
        self._btn_foto_baris = QPushButton("Pilih…")
        self._btn_foto_baris.clicked.connect(self._pilih_foto_baris)
        self._btn_hapus_baris = QPushButton("Hapus")
        self._btn_hapus_baris.clicked.connect(self._hapus_foto_baris)
        bar = QHBoxLayout()
        bar.addWidget(self._label_khusus)
        bar.addWidget(self._foto_khusus, stretch=1)
        bar.addWidget(self._btn_foto_baris)
        bar.addWidget(self._btn_hapus_baris)
        self._layout.addLayout(bar)

        self._layout.addWidget(self._judul("Video produk", "Opsional. .mp4 atau .mov."))
        self._video_label = QLabel()
        self._video_label.setStyleSheet(_ABU)
        self._layout.addLayout(self._baris_tombol(
            "Video", self._video_label,
            [("Pilih…", self._pilih_video), ("Hapus", self._hapus_video)],
        ))

        self._status = QLabel()
        self._status.setWordWrap(True)
        self._layout.addWidget(self._status)
        self._layout.addStretch(1)

        gulir.setWidget(isi)
        luar.addWidget(gulir)

    @staticmethod
    def _judul(teks: str, keterangan: str) -> QWidget:
        kotak = QWidget()
        tata = QVBoxLayout(kotak)
        tata.setContentsMargins(0, 0, 0, 0)
        tata.setSpacing(1)
        judul = QLabel(teks)
        judul.setStyleSheet("font-weight: 600;")
        tata.addWidget(judul)
        sub = QLabel(keterangan)
        sub.setStyleSheet(_ABU)
        tata.addWidget(sub)
        return kotak

    @staticmethod
    def _baris_tombol(label: str, nilai: QLabel, tombol) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.addWidget(QLabel(label))
        bar.addWidget(nilai, stretch=1)
        for teks, aksi in tombol:
            btn = QPushButton(teks)
            btn.clicked.connect(aksi)
            bar.addWidget(btn)
        return bar

    # --- data ---------------------------------------------------------------

    def set_assets(self, assets: Assets) -> None:
        self._assets = assets
        self.refresh()

    def assets(self) -> Assets:
        return self._assets

    def set_baris(self, excel_row: int | None, nama: str = "") -> None:
        self._baris, self._nama_baris = excel_row, nama
        self.refresh()

    # --- aksi ---------------------------------------------------------------

    def _pilih_dokumen(self, nama: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, f"Pilih {nama}", "", SARINGAN_PDF)
        if path:
            self._assets.set_dokumen(nama, path)
            self._selesai()

    def _hapus_dokumen(self, nama: str) -> None:
        self._assets.set_dokumen(nama, "")
        self._selesai()

    def _pilih_foto_umum(self) -> None:
        berkas, _ = QFileDialog.getOpenFileNames(
            self, "Pilih foto untuk semua baris", "", SARINGAN_FOTO
        )
        if berkas:
            self._assets.foto_umum = berkas[:MAKS_FOTO]
            self._selesai()

    def _hapus_foto_umum(self) -> None:
        self._assets.foto_umum = []
        self._selesai()

    def _pilih_foto_baris(self) -> None:
        if self._baris is None:
            return
        berkas, _ = QFileDialog.getOpenFileNames(
            self, f"Pilih foto untuk baris {self._baris}", "", SARINGAN_FOTO
        )
        if berkas:
            self._assets.set_foto_baris(self._baris, berkas)
            self._selesai()

    def _hapus_foto_baris(self) -> None:
        if self._baris is not None:
            self._assets.set_foto_baris(self._baris, [])
            self._selesai()

    def _pilih_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pilih video", "", SARINGAN_VIDEO)
        if path:
            self._assets.video = path
            self._selesai()

    def _hapus_video(self) -> None:
        self._assets.video = ""
        self._selesai()

    def _selesai(self) -> None:
        self.refresh()
        self.changed.emit()

    # --- tampilan -----------------------------------------------------------

    def refresh(self) -> None:
        for nama, label in self._dok_label.items():
            berkas = self._assets.dokumen.get(nama, "")
            galat = periksa(berkas, DOKUMEN_EXT, BATAS_DOKUMEN_MB) if berkas else ""
            label.setText(f"{_ringkas(berkas)}{'  — ' + galat if galat else ''}")
            label.setStyleSheet(_MERAH if (galat or not berkas) else _HIJAU)
            label.setToolTip(berkas)

        self._foto_umum.setText(self._daftar(self._assets.foto_umum, FOTO_EXT))
        self._foto_umum.setStyleSheet(
            _HIJAU if self._assets.foto_umum else _ABU
        )

        punya_baris = self._baris is not None
        self._btn_foto_baris.setEnabled(punya_baris)
        self._btn_hapus_baris.setEnabled(punya_baris)
        if punya_baris:
            self._label_khusus.setText(
                f"Foto khusus baris {self._baris}"
                + (f" ({self._nama_baris[:28]})" if self._nama_baris else "")
            )
            khusus = self._assets.foto_baris.get(self._baris, [])
            self._foto_khusus.setText(
                self._daftar(khusus, FOTO_EXT) if khusus else "memakai foto umum"
            )
            self._foto_khusus.setStyleSheet(_HIJAU if khusus else _ABU)
        else:
            self._label_khusus.setText("Foto khusus baris terpilih")
            self._foto_khusus.setText("pilih satu baris di tabel dulu")
            self._foto_khusus.setStyleSheet(_ABU)

        galat_video = periksa(self._assets.video, VIDEO_EXT) if self._assets.video else ""
        self._video_label.setText(
            f"{_ringkas(self._assets.video)}{'  — ' + galat_video if galat_video else ''}"
        )
        self._video_label.setStyleSheet(
            _MERAH if galat_video else (_HIJAU if self._assets.video else _ABU)
        )

        masalah = self._assets.masalah(self._baris)
        if masalah:
            self._status.setText("Perlu dibereskan:\n  • " + "\n  • ".join(masalah))
            self._status.setStyleSheet(_MERAH)
        else:
            self._status.setText("Semua berkas siap.")
            self._status.setStyleSheet(_HIJAU)

    @staticmethod
    def _daftar(berkas: list[str], ekstensi: tuple[str, ...]) -> str:
        if not berkas:
            return "belum dipilih"
        nama = ", ".join(Path(b).name for b in berkas[:3])
        sisa = f" (+{len(berkas) - 3})" if len(berkas) > 3 else ""
        rusak = [b for b in berkas if periksa(b, ekstensi)]
        return f"{len(berkas)} berkas: {nama}{sisa}" + (
            f"  — {len(rusak)} bermasalah" if rusak else ""
        )


__all__ = ["AssetsPanel"]
