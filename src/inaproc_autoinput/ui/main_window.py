"""Jendela utama aplikasi."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableView,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import state, workbook
from ..categories import Catalog
from ..model import Status, rows_from_records
from .. import chrome
from ..assets import Assets
from ..runner import CDP_DEFAULT, URL_TAMBAH, Mode
from ..validation import validate
from .assets_panel import AssetsPanel
from .table_model import COL_NAMA, COL_PESAN, ProductTableModel
from .worker import RunWorker

JUDUL = "INAPROC Autoinput — Katalog Elektronik v6"

# Menjalankan banyak baris berurutan dikerjakan di Tahap 3.
PESAN_TAHAP_3 = (
    "Menjalankan banyak baris sekaligus belum tersedia.\n\n"
    "Tahap 2 baru mencakup satu baris: pilih barisnya, lalu klik "
    "'Jalankan baris ini'."
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(JUDUL)
        self.resize(1180, 680)

        self._workbook_path: Path | None = None
        self._model = ProductTableModel()
        self._worker: RunWorker | None = None
        self._aktif: int | None = None  # posisi baris yang sedang dijalankan
        # Cache dipakai saat mulai supaya jendela tidak menunggu jaringan.
        self._catalog = Catalog([])

        self._build_ui()
        self._load_catalog(refresh=False)
        self._update_summary()

    # --- penyusunan tampilan ------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addLayout(self._build_file_bar())

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_detail())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 240])  # panel rincian cukup tinggi untuk dibaca
        layout.addWidget(splitter, stretch=1)

        layout.addLayout(self._build_action_bar())

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        # Label tetap: tidak tertimpa pesan sementara seperti "6 baris dibaca".
        self._catalog_label = QLabel()
        self.statusBar().addPermanentWidget(self._catalog_label)
        self._set_connection_status(False)

    def _build_file_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        self._file_label = QLabel("Belum ada file dibuka")
        self._file_label.setStyleSheet("font-weight: 600;")

        buka = QPushButton("Buka template terisi…")
        buka.clicked.connect(self.open_workbook)

        buat = QPushButton("Buat template kosong…")
        buat.clicked.connect(self.create_template)

        muat_ulang = QPushButton("Muat ulang")
        muat_ulang.clicked.connect(self.reload_workbook)
        self._reload_button = muat_ulang
        muat_ulang.setEnabled(False)

        kategori = QPushButton("Perbarui kategori")
        kategori.setToolTip("Unduh ulang daftar kategori dari portal INAPROC")
        kategori.clicked.connect(lambda: self._load_catalog(refresh=True))

        uji = QPushButton("Uji koneksi browser")
        uji.setToolTip(f"Coba menyambung ke Chrome di {CDP_DEFAULT}")
        uji.clicked.connect(self.test_connection)
        self._btn_uji = uji

        chrome_btn = QPushButton("Buka Chrome portal")
        chrome_btn.setToolTip(
            "Buka Chrome dengan port debug dan profil terpisah, lalu login "
            "sendiri di jendela itu"
        )
        chrome_btn.clicked.connect(self.open_chrome)

        bar.addWidget(self._file_label, stretch=1)
        bar.addWidget(chrome_btn)
        bar.addWidget(uji)
        bar.addWidget(kategori)
        bar.addWidget(muat_ulang)
        bar.addWidget(buka)
        bar.addWidget(buat)
        return bar

    def _build_table(self) -> QTableView:
        view = QTableView()
        view.setModel(self._model)
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
        view.setSelectionMode(QAbstractItemView.SingleSelection)
        view.setAlternatingRowColors(True)
        view.verticalHeader().setVisible(False)
        view.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_NAMA, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_PESAN, QHeaderView.Stretch)

        view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._table = view
        return view

    def _build_detail(self) -> QWidget:
        tab = QTabWidget()

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setPlaceholderText("Pilih satu baris untuk melihat rinciannya.")
        tab.addTab(self._detail, "Rincian baris")

        self._assets_panel = AssetsPanel()
        self._assets_panel.changed.connect(self._on_assets_changed)
        tab.addTab(self._assets_panel, "Berkas")
        self._tab = tab
        return tab

    def _build_action_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()

        self._mode = QComboBox()
        for mode in Mode:
            self._mode.addItem(mode.label, mode)
        self._mode.setToolTip(
            "Sejauh mana aplikasi boleh bertindak setelah form terisi"
        )
        bar.addWidget(QLabel("Setelah terisi:"))
        bar.addWidget(self._mode)

        self._btn_satu = QPushButton("Jalankan baris ini")
        self._btn_satu.setEnabled(False)
        self._btn_satu.clicked.connect(self.run_selected_row)
        bar.addWidget(self._btn_satu)

        self._btn_semua = QPushButton("Jalankan semua")
        self._btn_sisa = QPushButton("Lanjutkan sisanya")
        self._btn_stop = QPushButton("Berhenti")
        for button in (self._btn_semua, self._btn_sisa, self._btn_stop):
            button.setEnabled(False)
            button.clicked.connect(self._not_yet)
            bar.addWidget(button)

        bar.addStretch(1)
        self._summary = QLabel()
        bar.addWidget(self._summary)
        return bar

    # --- aksi ---------------------------------------------------------------

    def _load_catalog(self, refresh: bool) -> None:
        """Muat daftar kategori: dari cache saat mulai, dari portal bila diminta."""
        if refresh:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._catalog = Catalog.load(refresh=refresh)
        except OSError as error:
            if refresh:
                QMessageBox.warning(
                    self, "Gagal mengambil kategori",
                    f"{error}\n\nAplikasi tetap jalan, tapi nama kategori di file "
                    "tidak bisa diperiksa.",
                )
        finally:
            if refresh:
                QApplication.restoreOverrideCursor()

        self._update_catalog_status()
        if refresh and self._workbook_path:
            self.reload_workbook()

    def _update_catalog_status(self) -> None:
        if self._catalog.kosong:
            self._catalog_label.setText(
                "Kategori belum diunduh — klik 'Perbarui kategori'"
            )
            return
        semua = self._catalog.tally()
        dilayani = self._catalog.restrict().tally()
        waktu = self._catalog.diunduh[:10] or "?"
        self._catalog_label.setText(
            f"Kategori: {dilayani['level3']} dari {semua['level3']} dipakai "
            f"({dilayani['level1']} bidang, diunduh {waktu})"
        )

    def open_chrome(self) -> None:
        """Buka Chrome berport debug supaya aplikasi bisa menempel ke sesinya."""
        berhasil, pesan = chrome.launch(url=URL_TAMBAH)
        if berhasil:
            QMessageBox.information(self, "Chrome", pesan)
            self.statusBar().showMessage(pesan, 10000)
        else:
            QMessageBox.warning(self, "Chrome tidak bisa dibuka", pesan)

    def create_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan template kosong", "template-produk-inaproc.xlsx",
            "Excel (*.xlsx)",
        )
        if not path:
            return
        # Template hanya memuat bidang yang dilayani; katalog penuh tetap
        # dipakai saat memvalidasi.
        terbatas = self._catalog.restrict()
        try:
            written = workbook.create_template(path, catalog=terbatas)
        except OSError as error:
            QMessageBox.critical(self, "Gagal menyimpan", str(error))
            return

        tambahan = (
            f"\n\nSheet '{workbook.SHEET_KATEGORI}' berisi "
            f"{terbatas.tally()['level3']} kategori dari "
            f"{terbatas.tally()['level1']} bidang yang dilayani — salin jalur "
            "kategori dari sana supaya ejaannya persis."
            if not terbatas.kosong
            else "\n\nDaftar kategori belum diunduh, jadi tidak ikut disertakan."
        )
        QMessageBox.information(
            self, "Template dibuat",
            f"Template kosong tersimpan di:\n{written}\n\n"
            f"Isi mulai baris 5, satu baris satu produk. Lihat sheet 'Petunjuk'.{tambahan}",
        )

    def open_workbook(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Buka template terisi", "", "Excel (*.xlsx *.xlsm)"
        )
        if path:
            self._load(Path(path))

    def reload_workbook(self) -> None:
        if self._workbook_path:
            self._load(self._workbook_path)

    def _load(self, path: Path) -> None:
        try:
            missing = workbook.missing_columns(path)
            records = workbook.read_workbook(path)
        except (KeyError, OSError, ValueError) as error:
            QMessageBox.critical(
                self, "Tidak bisa membaca file",
                f"{error}\n\nPastikan file ini dibuat lewat 'Buat template kosong'.",
            )
            return

        if missing:
            QMessageBox.warning(
                self, "Kolom wajib tidak ditemukan",
                "Kolom berikut tidak ada di file:\n  • " + "\n  • ".join(missing)
                + "\n\nFile tetap dibuka, tapi baris kemungkinan besar tidak lengkap.",
            )

        rows = rows_from_records(records)
        for row in rows:
            row.issues = validate(row.data, catalog=self._catalog)

        self._assets_panel.set_assets(Assets.load(path))
        restored = state.apply(path, rows)

        self._workbook_path = path
        self._model.set_rows(rows)
        self._file_label.setText(str(path))
        self._reload_button.setEnabled(True)
        self._detail.clear()
        self._update_summary()

        note = f" · {restored} baris memulihkan status sebelumnya" if restored else ""
        self.statusBar().showMessage(f"{len(rows)} baris dibaca{note}", 8000)

    def _not_yet(self) -> None:
        QMessageBox.information(self, "Belum tersedia", PESAN_TAHAP_3)

    # --- menjalankan ke portal ---------------------------------------------

    def test_connection(self) -> None:
        self._mulai_worker(None, "Menguji koneksi ke browser…")

    def run_selected_row(self) -> None:
        posisi = self._selected_position()
        row = self._model.row_at(posisi) if posisi is not None else None
        if row is None:
            return

        mode: Mode = self._mode.currentData()
        if mode is not Mode.ISI_SAJA:
            jawab = QMessageBox.question(
                self, "Konfirmasi",
                f"Baris {row.excel_row} — {row.nama}\n\n"
                f"Setelah form terisi, aplikasi akan: {mode.label}.\n"
                "Tindakan ini mengubah data di akun penyedia. Lanjutkan?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if jawab != QMessageBox.Yes:
                return

        row.status = Status.BERJALAN
        row.message = "menyiapkan…"
        self._model.set_active(posisi)
        self._model.refresh(posisi)
        self._aktif = posisi
        self._mulai_worker(dict(row.data), f"Menjalankan baris {row.excel_row}…")

    def _mulai_worker(self, data: dict | None, pesan: str) -> None:
        self._set_sedang_jalan(True)
        self.statusBar().showMessage(pesan)

        self._worker = RunWorker(data, self._mode.currentData(), CDP_DEFAULT,
                                 self._assets_panel.assets(), self)
        self._worker.langkah.connect(self._on_langkah)
        self._worker.selesai.connect(self._on_selesai)
        self._worker.finished.connect(lambda: self._set_sedang_jalan(False))
        self._worker.start()

    def _on_langkah(self, pesan: str) -> None:
        self.statusBar().showMessage(pesan)
        if self._aktif is None:
            return
        row = self._model.row_at(self._aktif)
        if row is not None:
            row.message = pesan
            self._model.refresh(self._aktif)

    def _on_selesai(self, hasil) -> None:
        if self._aktif is None:  # hasil uji koneksi
            judul = "Koneksi berhasil" if hasil.berhasil else "Koneksi gagal"
            kotak = QMessageBox.information if hasil.berhasil else QMessageBox.warning
            kotak(self, judul, hasil.pesan)
            self.statusBar().showMessage(hasil.pesan, 10_000)
            return

        posisi, self._aktif = self._aktif, None
        row = self._model.row_at(posisi)
        if row is not None:
            row.status = Status.SUKSES if hasil.berhasil else Status.GAGAL
            row.message = hasil.pesan
            row.produk_id = hasil.produk_id or row.produk_id
            if hasil.peringatan:
                row.message += f" · {len(hasil.peringatan)} peringatan"
            self._model.refresh(posisi)
            if self._workbook_path:
                state.save(self._workbook_path, self._model.rows())

        self._model.set_active(None)
        self._update_summary()
        self._detail.setPlainText(self._laporan(hasil))
        self.statusBar().showMessage(hasil.pesan, 10_000)

    @staticmethod
    def _laporan(hasil) -> str:
        baris = [("BERHASIL" if hasil.berhasil else "GAGAL") + f" — {hasil.pesan}", ""]
        if hasil.produk_id:
            baris += [f"ID produk: {hasil.produk_id}", ""]
        if hasil.langkah:
            baris.append("Langkah yang dijalankan:")
            baris += [f"  {i}. {t}" for i, t in enumerate(hasil.langkah, 1)]
        if hasil.peringatan:
            baris += ["", "Perlu diperhatikan:"]
            baris += [f"  ! {p}" for p in hasil.peringatan]
        return "\n".join(baris)

    def _set_sedang_jalan(self, jalan: bool) -> None:
        self._btn_uji.setEnabled(not jalan)
        self._btn_satu.setEnabled(not jalan and self._baris_siap())
        self._mode.setEnabled(not jalan)
        self._reload_button.setEnabled(not jalan and self._workbook_path is not None)

    def _selected_position(self) -> int | None:
        indexes = self._table.selectionModel().selectedRows()
        return indexes[0].row() if indexes else None

    def _baris_siap(self) -> bool:
        posisi = self._selected_position()
        row = self._model.row_at(posisi) if posisi is not None else None
        return row is not None and not row.blocking_issues

    # --- pembaruan tampilan -------------------------------------------------

    def _on_selection_changed(self, *_args) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            self._detail.clear()
            self._assets_panel.set_baris(None)
            return
        row = self._model.row_at(indexes[0].row())
        if row:
            self._detail.setPlainText(self._describe(row))
            self._assets_panel.set_baris(row.excel_row, row.nama)

    def _on_assets_changed(self) -> None:
        """Simpan pilihan berkas di sebelah workbook, lalu perbarui ringkasan."""
        if self._workbook_path:
            self._assets_panel.assets().save(self._workbook_path)
        self._update_summary()
        self._btn_satu.setEnabled(self._baris_siap())

    def _describe(self, row) -> str:
        lines = [
            f"Baris Excel {row.excel_row} · {row.status.label}",
            f"Nama    : {row.nama or '(kosong)'}",
            f"Kategori: {row.kategori or '(kosong)'}",
            f"Tipe    : {row.tipe_produk or '(ditentukan portal dari kategori)'}",
        ]
        if row.produk_id:
            lines.append(f"ID produk di INAPROC: {row.produk_id}")
        if row.message:
            lines.append(f"Pesan   : {row.message}")

        atribut = row.atribut
        if atribut:
            lines.append("")
            lines.append("Atribut khusus kategori:")
            lines += [f"  • {nama}: {nilai or '(kosong)'}" for nama, nilai in atribut.items()]

        assets = self._assets_panel.assets()
        foto = assets.foto_untuk(row.excel_row)
        lines.append("")
        lines.append(f"Foto ({len(foto)}): " + (
            ", ".join(Path(f).name for f in foto) or "belum dipilih — lihat tab Berkas"))
        if assets.dokumen:
            lines.append("Dokumen:")
            lines += [f"  • {n}: {Path(b).name}"
                      for n, b in sorted(assets.dokumen.items())]
        else:
            lines.append("Dokumen: belum dipilih — lihat tab Berkas")

        errors = row.blocking_issues
        warnings = [i for i in row.issues if not i.blocking]
        if errors:
            lines.append("")
            lines.append(f"Harus diperbaiki ({len(errors)}):")
            lines += [f"  ✗ {issue}" for issue in errors]
        if warnings:
            lines.append("")
            lines.append(f"Perlu diperhatikan ({len(warnings)}):")
            lines += [f"  ! {issue}" for issue in warnings]
        if not errors and not warnings:
            lines.append("")
            lines.append("Baris ini siap dijalankan.")
        return "\n".join(lines)

    def _update_summary(self) -> None:
        counts = self._model.tally()
        siap = len(self._model.pending_positions())
        bermasalah = sum(1 for row in self._model.rows() if row.blocking_issues)
        # Berkas berlaku untuk semua baris, jadi masalahnya disebut sekali di
        # ringkasan -- bukan diulang di tiap baris tabel.
        berkas = self._assets_panel.assets().masalah()
        catatan = f" · berkas: {len(berkas)} perlu dibereskan" if berkas else ""
        self._summary.setText(
            f"{counts[Status.SUKSES]} sukses · {counts[Status.GAGAL]} gagal · "
            f"{siap} siap dijalankan · {bermasalah} perlu diperbaiki{catatan}"
        )

    def _set_connection_status(self, connected: bool) -> None:
        self.statusBar().showMessage(
            "Siap. Buka file template, pilih satu baris, lalu 'Jalankan baris ini'."
        )


__all__ = ["MainWindow"]
