"""Panel pemilih berkas: dokumen PDF, foto, dan video.

Menggantikan kolom path yang dulu ada di Excel. Dokumen dan foto umum berlaku
untuk semua baris; foto khusus hanya untuk baris yang sedang dipilih.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..assets import DOKUMEN_LAZIM, IKUT_BERKAS, MAKS_FOTO, Assets, periksa
from ..placeholder import PLACEHOLDER_PATH
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


class PemilihFoto(QWidget):
    """Daftar foto terpilih, dengan penghapusan satu per satu.

    Dulu foto cuma ditampilkan sebagai satu baris teks dan satu-satunya cara
    membuangnya adalah mengosongkan seluruh daftar. Salah pilih satu dari lima
    berarti memilih ulang kelimanya.
    """

    berubah = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._berkas: list[str] = []

        tata = QVBoxLayout(self)
        tata.setContentsMargins(0, 0, 0, 0)
        tata.setSpacing(4)

        self._daftar = QListWidget()
        self._daftar.setSelectionMode(QListWidget.ExtendedSelection)
        self._daftar.setMaximumHeight(96)
        self._daftar.setAlternatingRowColors(True)
        self._daftar.itemSelectionChanged.connect(self._perbarui_tombol)
        tata.addWidget(self._daftar)

        bar = QHBoxLayout()
        self._btn_tambah = QPushButton("Tambah…")
        self._btn_tambah.clicked.connect(self._tambah)
        self._btn_hapus = QPushButton("Hapus terpilih")
        self._btn_hapus.clicked.connect(self._hapus_terpilih)
        self._btn_kosong = QPushButton("Kosongkan")
        self._btn_kosong.clicked.connect(self._kosongkan)
        for tombol in (self._btn_tambah, self._btn_hapus, self._btn_kosong):
            bar.addWidget(tombol)
        bar.addStretch(1)
        tata.addLayout(bar)

        self.set_berkas([])

    # --- data ---------------------------------------------------------------

    def berkas(self) -> list[str]:
        return list(self._berkas)

    def set_berkas(self, berkas: list[str]) -> None:
        self._berkas = list(berkas or [])
        self._daftar.clear()
        for path_teks in self._berkas:
            galat = periksa(path_teks, FOTO_EXT)
            item = QListWidgetItem(
                Path(path_teks).name + (f"  — {galat}" if galat else ""))
            item.setToolTip(path_teks)
            item.setForeground(QColor("#c62828") if galat else QColor("#2e7d32"))
            self._daftar.addItem(item)
        self._perbarui_tombol()

    def set_dapat_diubah(self, boleh: bool) -> None:
        self._dapat_diubah = boleh
        self._perbarui_tombol()

    # --- aksi ---------------------------------------------------------------

    def _perbarui_tombol(self) -> None:
        boleh = getattr(self, "_dapat_diubah", True)
        self._btn_tambah.setEnabled(boleh and len(self._berkas) < MAKS_FOTO)
        self._btn_hapus.setEnabled(boleh and bool(self._daftar.selectedItems()))
        self._btn_kosong.setEnabled(boleh and bool(self._berkas))
        self._daftar.setEnabled(boleh)

    def _tambah(self) -> None:
        pilihan, _ = QFileDialog.getOpenFileNames(self, "Pilih foto", "", SARINGAN_FOTO)
        if not pilihan:
            return
        # Yang sudah ada dipertahankan: "Tambah" menambah, bukan mengganti.
        gabung = self._berkas + [p for p in pilihan if p not in self._berkas]
        self.set_berkas(gabung[:MAKS_FOTO])
        self.berubah.emit()

    def _hapus_terpilih(self) -> None:
        buang = {self._daftar.row(i) for i in self._daftar.selectedItems()}
        if not buang:
            return
        self.set_berkas([f for n, f in enumerate(self._berkas) if n not in buang])
        self.berubah.emit()

    def _kosongkan(self) -> None:
        if self._berkas:
            self.set_berkas([])
            self.berubah.emit()


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
        self._layout.addWidget(QLabel("Foto untuk semua baris"))
        self._foto_umum = PemilihFoto()
        self._foto_umum.berubah.connect(self._foto_umum_berubah)
        self._layout.addWidget(self._foto_umum)

        self._pakai_ph = QCheckBox(
            "Pakai foto placeholder bila belum ada foto"
        )
        self._pakai_ph.setToolTip(
            "Form mewajibkan minimal satu foto. Placeholder membuka jalan supaya "
            "pengisian tidak tertahan, tapi produknya akan terlihat belum berfoto.\n"
            f"Berkas: {PLACEHOLDER_PATH}"
        )
        self._pakai_ph.toggled.connect(self._ubah_placeholder)
        self._layout.addWidget(self._pakai_ph)

        self._label_khusus = QLabel("Foto khusus baris terpilih")
        self._layout.addWidget(self._label_khusus)
        self._foto_khusus = PemilihFoto()
        self._foto_khusus.berubah.connect(self._foto_baris_berubah)
        self._layout.addWidget(self._foto_khusus)
        self._catatan_khusus = QLabel()
        self._catatan_khusus.setStyleSheet(_ABU)
        self._layout.addWidget(self._catatan_khusus)

        self._layout.addWidget(self._judul(
            "Video produk", "Opsional. Berkas .mp4/.mov, atau tautan YouTube."
        ))
        self._video_label = QLabel()
        self._video_label.setStyleSheet(_ABU)
        self._layout.addLayout(self._baris_tombol(
            "Video", self._video_label,
            [("Pilih…", self._pilih_video), ("Hapus", self._hapus_video)],
        ))

        self._url = QLineEdit()
        self._url.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self._url.editingFinished.connect(self._simpan_url)
        hapus_url = QPushButton("Hapus")
        hapus_url.setToolTip("Kosongkan URL video")
        hapus_url.clicked.connect(self._hapus_url)
        bar_url = QHBoxLayout()
        bar_url.addWidget(QLabel("URL Video"))
        bar_url.addWidget(self._url, stretch=1)
        bar_url.addWidget(hapus_url)
        self._layout.addLayout(bar_url)

        kosong_semua = QPushButton("Kosongkan semua berkas…")
        kosong_semua.setToolTip(
            "Lepas semua dokumen, foto, dan video sekaligus. Dipakai saat "
            "berpindah penyedia atau kompetisi, supaya berkas klien sebelumnya "
            "tidak ikut terunggah."
        )
        kosong_semua.clicked.connect(self._kosongkan_semua)
        self._layout.addWidget(kosong_semua)

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

    def _foto_umum_berubah(self) -> None:
        self._assets.foto_umum = self._foto_umum.berkas()
        self._selesai()

    def _foto_baris_berubah(self) -> None:
        if self._baris is not None:
            self._assets.set_foto_baris(self._baris, self._foto_khusus.berkas())
        self._selesai()

    def _hapus_url(self) -> None:
        if self._assets.video_url or self._url.text().strip():
            self._url.clear()
            self._assets.video_url = ""
            self._selesai()

    def _kosongkan_semua(self) -> None:
        if self._assets.kosong:
            return
        jawab = QMessageBox.question(
            self, "Kosongkan semua berkas",
            "Semua dokumen, foto, dan video akan dilepas dari template ini.\n\n"
            "Berkasnya sendiri tidak dihapus dari komputer — yang dilepas cuma "
            "kaitannya.\n\nLanjutkan?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if jawab == QMessageBox.Yes:
            self._assets.kosongkan()
            self._selesai()

    def _ubah_placeholder(self, nyala: bool) -> None:
        if nyala != self._assets.pakai_placeholder:
            self._assets.pakai_placeholder = nyala
            self._selesai()

    def _pilih_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pilih video", "", SARINGAN_VIDEO)
        if path:
            self._assets.video = path
            self._selesai()

    def _hapus_video(self) -> None:
        self._assets.video = ""
        self._selesai()

    def _simpan_url(self) -> None:
        teks = self._url.text().strip()
        if teks != self._assets.video_url:
            self._assets.video_url = teks
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

        if self._foto_umum.berkas() != self._assets.foto_umum:
            self._foto_umum.set_berkas(self._assets.foto_umum)

        if self._pakai_ph.isChecked() != self._assets.pakai_placeholder:
            self._pakai_ph.blockSignals(True)
            self._pakai_ph.setChecked(self._assets.pakai_placeholder)
            self._pakai_ph.blockSignals(False)

        punya_baris = self._baris is not None
        self._foto_khusus.set_dapat_diubah(punya_baris)
        if punya_baris:
            self._label_khusus.setText(
                f"Foto khusus baris {self._baris}"
                + (f" ({self._nama_baris[:28]})" if self._nama_baris else "")
            )
            khusus = self._assets.foto_baris.get(self._baris, [])
            if self._foto_khusus.berkas() != khusus:
                self._foto_khusus.set_berkas(khusus)
            if khusus:
                catatan = ""
            elif self._assets.baris_pakai_placeholder(self._baris):
                catatan = "belum ada foto khusus — baris ini memakai placeholder"
            else:
                catatan = "belum ada foto khusus — baris ini memakai foto umum"
            self._catatan_khusus.setText(catatan)
        else:
            self._label_khusus.setText("Foto khusus baris terpilih")
            self._foto_khusus.set_berkas([])
            self._catatan_khusus.setText("pilih satu baris di tabel dulu")

        galat_video = periksa(self._assets.video, VIDEO_EXT) if self._assets.video else ""
        self._video_label.setText(
            f"{_ringkas(self._assets.video)}{'  — ' + galat_video if galat_video else ''}"
        )
        self._video_label.setStyleSheet(
            _MERAH if galat_video else (_HIJAU if self._assets.video else _ABU)
        )

        if self._url.text().strip() != self._assets.video_url:
            self._url.setText(self._assets.video_url)

        masalah = self._assets.masalah(self._baris)
        catatan = self._assets.catatan()
        if masalah:
            self._status.setText("Perlu dibereskan:\n  • " + "\n  • ".join(masalah))
            self._status.setStyleSheet(_MERAH)
        elif catatan:
            self._status.setText("Perlu diperhatikan:\n  • " + "\n  • ".join(catatan))
            self._status.setStyleSheet(_ABU)
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
