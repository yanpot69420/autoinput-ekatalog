"""Jendela utama aplikasi."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
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
from ..model import Status, antrean, rows_from_records
from .. import chrome
from ..assets import Assets
from ..runner import CDP_DEFAULT, URL_TAMBAH, Mode
from ..validation import validate
from .assets_panel import AssetsPanel
from .table_model import COL_NAMA, COL_PESAN, ProductTableModel
from .worker import RunWorker

JUDUL = "INAPROC Autoinput — Katalog Elektronik v6"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(JUDUL)
        self.resize(1180, 680)

        self._workbook_path: Path | None = None
        self._model = ProductTableModel()
        self._worker: RunWorker | None = None
        self._aktif: int | None = None  # posisi baris yang sedang dijalankan
        self._sedang_jalan = False
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
        self._btn_buka = buka

        buat = QPushButton("Buat template kosong…")
        buat.clicked.connect(self.create_template)
        self._btn_buat = buat

        muat_ulang = QPushButton("Muat ulang")
        muat_ulang.clicked.connect(self.reload_workbook)
        self._reload_button = muat_ulang
        muat_ulang.setEnabled(False)

        kategori = QPushButton("Perbarui kategori")
        kategori.setToolTip("Unduh ulang daftar kategori dari portal INAPROC")
        kategori.clicked.connect(lambda: self._load_catalog(refresh=True))
        self._btn_kategori = kategori

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
        self._btn_chrome = chrome_btn

        ulang = QPushButton("Mulai ulang Chrome")
        ulang.setToolTip(
            "Tutup lalu buka lagi Chrome portal. Chrome yang sudah lama hidup "
            "melambat cukup jauh — terukur 100 detik jadi 29 detik untuk "
            "pekerjaan yang sama. Sesi loginmu tetap ada."
        )
        ulang.clicked.connect(self.restart_chrome)
        self._btn_ulang = ulang

        self._profil = QComboBox()
        self._profil.addItem("Profil terpisah", False)
        self._profil.addItem("Profil Chrome harian", True)
        self._profil.setCurrentIndex(1 if chrome.pakai_harian() else 0)
        self._profil.setToolTip(
            "Profil terpisah: Chrome harianmu tidak perlu ditutup, tapi portal "
            "melihat dua sesi untuk satu akun dan menendang salah satunya "
            "dengan kotak 'Akun Telah Keluar'.\n\n"
            "Profil harian: satu sesi saja, jadi tidak ada yang saling "
            "menendang — tapi Chrome harus ditutup sepenuhnya dulu setiap kali."
        )
        self._profil.currentIndexChanged.connect(self._ganti_profil)

        bar.addWidget(self._file_label, stretch=1)
        bar.addWidget(QLabel("Profil Chrome:"))
        bar.addWidget(self._profil)
        bar.addWidget(chrome_btn)
        bar.addWidget(ulang)
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
        self._btn_satu.setToolTip(
            "Kerjakan baris yang sedang dipilih. Tetap bisa ditekan walau "
            "barisnya masih bermasalah — kolom yang kosong dilewati, dan mode "
            "'Isi saja' tidak menyimpan apa pun ke portal"
        )
        self._btn_satu.clicked.connect(self.run_selected_row)

        self._btn_semua = QPushButton("Jalankan semua")
        self._btn_semua.setToolTip(
            "Kerjakan semua baris siap dari atas, termasuk mengulang yang gagal"
        )
        self._btn_semua.clicked.connect(self.run_all)

        self._btn_sisa = QPushButton("Lanjutkan sisanya")
        self._btn_sisa.setToolTip(
            "Sama, tapi baris yang sudah gagal dilewati — biasanya perlu "
            "diperbaiki dulu, bukan diulang apa adanya"
        )
        self._btn_sisa.clicked.connect(self.run_rest)

        self._btn_stop = QPushButton("Berhenti")
        self._btn_stop.setToolTip(
            "Hentikan antrean. Baris yang sedang diisi diputus di langkah "
            "berikutnya dan dikembalikan ke Menunggu"
        )
        self._btn_stop.clicked.connect(self.stop_queue)

        for button in (self._btn_satu, self._btn_semua, self._btn_sisa,
                       self._btn_stop):
            button.setEnabled(False)
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
            self._periksa_setelah_chrome()
        else:
            QMessageBox.warning(self, "Chrome tidak bisa dibuka", pesan)

    def _periksa_setelah_chrome(self, sisa: int = 40) -> None:
        """Setelah Chrome terbuka, periksa sendiri keadaan halamannya.

        Sesi yang sudah ditendang membuat portal menampilkan halaman rusak
        berikut modal yang menelan semua klik dan ketikan. Dari kursi pengguna
        itu terasa persis seperti Chrome yang lambat -- padahal perendernya
        baik-baik saja dan yang mati cuma sesinya. Diberitahu di sini supaya
        tidak ada yang mengejar masalah yang salah.

        Ditunggu dengan pencacah, bukan jeda: Chrome butuh beberapa detik untuk
        siap, dan menahan jendela selama itu justru menambah kesan membeku.
        """
        if chrome.is_listening():
            self.test_connection()
        elif sisa:
            QTimer.singleShot(500, lambda: self._periksa_setelah_chrome(sisa - 1))

    def _ganti_profil(self, *_args) -> None:
        """Simpan pilihan profil, lalu jelaskan konsekuensinya sekali."""
        harian = bool(self._profil.currentData())
        chrome.set_pakai_harian(harian)
        if harian:
            self.statusBar().showMessage(
                "Profil Chrome harian dipakai. Tutup Chrome sepenuhnya dulu "
                "sebelum klik 'Buka Chrome portal'.", 15000)
        else:
            self.statusBar().showMessage(
                f"Profil terpisah dipakai: {chrome.PROFIL_APLIKASI}", 10000)

    def restart_chrome(self) -> None:
        """Tutup lalu buka lagi Chrome portal, mengembalikan kecepatannya."""
        if not chrome.is_listening():
            self.open_chrome()
            return

        jawab = QMessageBox.question(
            self, "Mulai ulang Chrome",
            "Jendela Chrome portal akan ditutup lalu dibuka lagi.\n\n"
            "Sesi loginmu tetap ada — profilnya permanen. Tapi apa pun yang "
            "belum tersimpan di halaman itu akan hilang, termasuk form yang "
            "sedang setengah terisi.\n\nLanjutkan?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if jawab != QMessageBox.Yes:
            return

        # Menutup Chrome memakan beberapa detik dan menahan jendela ini selama
        # itu. Kursor tunggu dipasang supaya diamnya terbaca sebagai sedang
        # bekerja, bukan sebagai aplikasi yang ikut membeku.
        self.statusBar().showMessage("Menutup Chrome…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            berhasil, pesan = chrome.mulai_ulang(url=URL_TAMBAH)
        finally:
            QApplication.restoreOverrideCursor()

        if berhasil:
            QMessageBox.information(self, "Chrome", pesan)
            self.statusBar().showMessage(pesan, 10000)
            self._periksa_setelah_chrome()
        else:
            QMessageBox.warning(self, "Chrome tidak bisa dimulai ulang", pesan)

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
        # Berkas dimuat lebih dulu: sebagian atribut diisi dari dokumen yang
        # dipilih, jadi memeriksa baris sebelum tahu berkasnya akan mengeluh
        # soal nilai yang sebenarnya sudah ada sumbernya.
        self._assets_panel.set_assets(Assets.load(path))
        for row in rows:
            # Tipe produk ditentukan portal dari kategorinya, bukan diketik
            # penyedia -- jadi diambil dari katalog, bukan dari kolom Excel.
            node, _ = self._catalog.resolve_path(row.data.get("kategori", ""))
            row.tipe_portal = node.tipe_produk if node else ""
        self._periksa_ulang(rows)

        restored = state.apply(path, rows)

        self._workbook_path = path
        self._model.set_rows(rows)
        self._file_label.setText(str(path))
        self._reload_button.setEnabled(True)
        self._detail.clear()
        self._update_summary()

        note = f" · {restored} baris memulihkan status sebelumnya" if restored else ""
        self.statusBar().showMessage(f"{len(rows)} baris dibaca{note}", 8000)

    # --- menjalankan ke portal ---------------------------------------------

    def test_connection(self) -> None:
        self._mulai_worker(None, "Menguji koneksi ke browser…")

    def run_selected_row(self) -> None:
        posisi = self._selected_position()
        if posisi is not None and self._model.row_at(posisi) is not None:
            self._mulai_antrean([posisi], "baris ini")

    def run_all(self) -> None:
        self._mulai_antrean(antrean(self._model.rows()), "semua baris")

    def run_rest(self) -> None:
        self._mulai_antrean(antrean(self._model.rows(), lewati_gagal=True),
                            "sisanya")

    def stop_queue(self) -> None:
        if self._worker is None or not self._worker.isRunning():
            return
        self._worker.stop()
        self._btn_stop.setEnabled(False)
        self.statusBar().showMessage(
            "Menghentikan… baris yang sedang diisi diputus di langkah berikutnya"
        )

    def _mulai_antrean(self, posisi: list[int], sebutan: str) -> None:
        if not posisi:
            QMessageBox.information(self, "Tidak ada yang dikerjakan",
                                    self._kenapa_kosong())
            return
        if not self._konfirmasi_antrean(posisi, sebutan):
            return

        jobs = [(p, dict(self._model.row_at(p).data)) for p in posisi]
        awalan = "Menjalankan" if len(jobs) == 1 else f"Menjalankan {len(jobs)} baris"
        kurang = sum(1 for p in posisi if self._model.row_at(p) is not None
                     and self._model.row_at(p).blocking_issues)
        # Tidak menghalangi, tapi juga tidak diam: dijalankan apa adanya perlu
        # terlihat, supaya form yang terisi separuh tidak dikira sudah lengkap.
        catatan = f" · {kurang} baris masih kurang, dijalankan apa adanya" if kurang else ""
        self._mulai_worker(jobs, f"{awalan} — menyambung ke browser…{catatan}")

    def _kenapa_kosong(self) -> str:
        """Kosongnya antrean punya beberapa sebab, dan bedanya penting."""
        rows = self._model.rows()
        if not rows:
            return "Belum ada file template dibuka."
        counts = self._model.tally()
        bermasalah = sum(1 for row in rows if row.blocking_issues)
        if counts[Status.SUKSES] == len(rows):
            return "Semua baris sudah sukses. Tidak ada yang tersisa."
        if bermasalah:
            return (
                f"{bermasalah} baris masih punya error dan tidak bisa dijalankan. "
                "Klik barisnya untuk melihat apa yang harus diperbaiki, betulkan "
                "di Excel, lalu 'Muat ulang'."
            )
        return (
            f"Tidak ada baris yang perlu dikerjakan. {counts[Status.GAGAL]} baris "
            "gagal dilewati oleh 'Lanjutkan sisanya' — pakai 'Jalankan semua' "
            "bila memang ingin mengulangnya."
        )

    def _mode_terpilih(self) -> Mode:
        """Mode dari combobox, dibakukan jadi anggota Mode.

        Qt menyimpan nilai enum lalu mengembalikannya sebagai str biasa, jadi
        `currentData()` memberi 'isi_saja', bukan Mode.ISI_SAJA. Setiap
        perbandingan `is` sesudahnya diam-diam salah -- termasuk yang menentukan
        apakah tombol Simpan di portal boleh ditekan.
        """
        return Mode(self._mode.currentData())

    def _konfirmasi_antrean(self, posisi: list[int], sebutan: str) -> bool:
        """Konfirmasi sebelum antrean jalan. Selalu untuk mode yang menyimpan."""
        mode = self._mode_terpilih()
        catatan = list(self._assets_panel.assets().catatan())
        berkas = self._assets_panel.assets().masalah()
        # Baris bermasalah tidak lagi dihalangi tombolnya, jadi di sinilah
        # keberatannya disampaikan -- sekali, dan hanya saat ada yang benar-benar
        # tersimpan ke portal.
        bermasalah = [
            self._model.row_at(p) for p in posisi
            if self._model.row_at(p) is not None
            and self._model.row_at(p).blocking_issues
        ]

        if mode is Mode.ISI_SAJA and not berkas:
            return True

        garis = [f"{len(posisi)} baris akan dikerjakan ({sebutan}).",
                 f"Setelah tiap form terisi, aplikasi akan: {mode.label}."]
        if mode is not Mode.ISI_SAJA:
            garis.append("Tindakan ini mengubah data di akun penyedia.")
        if bermasalah and mode is not Mode.ISI_SAJA:
            garis += ["", f"{len(bermasalah)} baris masih bermasalah dan "
                          "kemungkinan besar ditolak portal:"]
            for row in bermasalah[:5]:
                galat = "; ".join(str(i) for i in row.blocking_issues[:2])
                garis.append(f"  • baris {row.excel_row}: {galat}")
        if berkas:
            garis += ["", f"Berkas yang perlu dibereskan ({len(berkas)}):"]
            garis += [f"  • {p}" for p in berkas[:5]]
        if catatan and mode is not Mode.ISI_SAJA:
            garis += [""] + [f"! {c}" for c in catatan]
        garis += ["", "Lanjutkan?"]

        jawab = QMessageBox.question(
            self, "Konfirmasi", "\n".join(garis),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        return jawab == QMessageBox.Yes

    def _mulai_worker(self, jobs: list[tuple[int, dict]] | None, pesan: str) -> None:
        self._set_sedang_jalan(True)
        self.statusBar().showMessage(pesan)

        self._worker = RunWorker(jobs, self._mode_terpilih(), CDP_DEFAULT,
                                 self._assets_panel.assets(), self)
        self._worker.langkah.connect(self._on_langkah)
        self._worker.mulai.connect(self._on_mulai)
        self._worker.hasil.connect(self._on_hasil)
        self._worker.tuntas.connect(self._on_tuntas)
        self._worker.koneksi.connect(self._on_koneksi)
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

    def _on_mulai(self, posisi: int) -> None:
        row = self._model.row_at(posisi)
        if row is None:
            return
        row.status = Status.BERJALAN
        row.message = "menyiapkan…"
        self._aktif = posisi
        self._model.set_active(posisi)
        # Antrean panjang akan melewati batas layar; barisnya diikuti supaya
        # yang sedang dikerjakan selalu terlihat.
        self._table.scrollTo(self._model.index(posisi, 0))

    def _on_hasil(self, posisi: int, hasil) -> None:
        self._aktif = None
        row = self._model.row_at(posisi)
        if row is None:
            return

        # "Isi saja" berhasil tanpa menyimpan apa pun. Menandainya Sukses akan
        # membuat baris ini dilewati nanti, padahal produknya belum pernah
        # masuk ke portal. Baris yang dihentikan juga bukan gagal: tidak ada
        # yang salah dengannya, jadi dikembalikan ke menunggu.
        if hasil.dibatalkan:
            row.status = Status.MENUNGGU
        elif not hasil.berhasil:
            row.status = Status.GAGAL
        elif hasil.tersimpan:
            row.status = Status.SUKSES
        else:
            row.status = Status.TERISI

        row.message = hasil.pesan
        row.produk_id = hasil.produk_id or row.produk_id
        if hasil.peringatan:
            row.message += f" · {len(hasil.peringatan)} peringatan"
        self._model.refresh(posisi)

        # Disimpan tiap baris, bukan di akhir antrean: kalau aplikasi mati di
        # baris ke-40, 39 baris sebelumnya tidak boleh ikut hilang.
        if self._workbook_path:
            state.save(self._workbook_path, self._model.rows())

        self._detail.setPlainText(self._laporan(hasil, row))
        self._update_summary()

    def _on_tuntas(self, ringkasan) -> None:
        self._aktif = None
        self._model.set_active(None)
        self._update_summary()

        macet = bool(ringkasan.beruntun or ringkasan.gagal_koneksi)
        kotak = QMessageBox.warning if macet else QMessageBox.information
        kotak(self, "Antrean berhenti" if macet else "Antrean selesai",
              self._pesan_tuntas(ringkasan))
        self.statusBar().showMessage(ringkasan.pesan, 15_000)

    @staticmethod
    def _pesan_tuntas(ringkasan) -> str:
        garis = [ringkasan.pesan]
        if ringkasan.alasan:
            garis += ["", ringkasan.alasan]
        # Menawarkan "Lanjutkan sisanya" saat browsernya yang mati cuma
        # memutar-mutar operator ke kegagalan yang sama.
        if ringkasan.sisa and not ringkasan.gagal_koneksi:
            garis += ["", "Klik 'Lanjutkan sisanya' untuk meneruskan."]
        return "\n".join(garis)

    def _on_koneksi(self, hasil) -> None:
        judul = "Koneksi berhasil" if hasil.berhasil else "Koneksi gagal"
        kotak = QMessageBox.information if hasil.berhasil else QMessageBox.warning
        kotak(self, judul, hasil.pesan)
        self.statusBar().showMessage(hasil.pesan, 10_000)

    @staticmethod
    def _laporan(hasil, row=None) -> str:
        if hasil.dibatalkan:
            kepala = "DIHENTIKAN"
        else:
            kepala = "BERHASIL" if hasil.berhasil else "GAGAL"
        judul = f"{kepala} — {hasil.pesan}"
        if row is not None:
            judul = f"Baris {row.excel_row} · {judul}"
        baris = [judul, ""]
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
        """Kunci semua yang bisa menggeser tanah di bawah antrean yang berjalan.

        Memuat ulang file di tengah antrean akan mengganti daftar barisnya,
        sementara worker masih memegang posisi baris dari daftar yang lama.
        """
        self._sedang_jalan = jalan
        # Menutup Chrome di tengah antrean akan memutus browser yang sedang
        # dipakai worker, jadi kedua tombol Chrome ikut dikunci.
        for tombol in (self._btn_uji, self._btn_buka, self._btn_buat,
                       self._btn_kategori, self._btn_chrome, self._btn_ulang):
            tombol.setEnabled(not jalan)
        self._mode.setEnabled(not jalan)
        self._profil.setEnabled(not jalan)
        self._reload_button.setEnabled(not jalan and self._workbook_path is not None)
        self._btn_stop.setEnabled(jalan)
        self._perbarui_tombol()

    def _perbarui_tombol(self) -> None:
        jalan = getattr(self, "_sedang_jalan", False)
        rows = self._model.rows()
        self._btn_satu.setEnabled(not jalan and self._baris_terpilih())
        self._btn_semua.setEnabled(not jalan and bool(antrean(rows)))
        self._btn_sisa.setEnabled(
            not jalan and bool(antrean(rows, lewati_gagal=True))
        )

    def _selected_position(self) -> int | None:
        indexes = self._table.selectionModel().selectedRows()
        return indexes[0].row() if indexes else None

    def _baris_terpilih(self) -> bool:
        """Cukup ada baris yang dipilih -- masalahnya tidak ikut menentukan.

        Tombol yang mati tidak memberi tahu apa pun tentang sebabnya, dan saat
        menguji satu baris itu menghalangi tanpa melindungi: mode 'Isi saja'
        tidak menyimpan apa-apa, dan kolom yang kosong memang dilewati. Apa yang
        kurang tetap terbaca di kolom Keterangan, dan mode yang menyimpan tetap
        menanyakannya lebih dulu.
        """
        posisi = self._selected_position()
        return posisi is not None and self._model.row_at(posisi) is not None

    # --- pembaruan tampilan -------------------------------------------------

    def _on_selection_changed(self, *_args) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            self._detail.clear()
            self._assets_panel.set_baris(None)
            self._perbarui_tombol()
            return
        row = self._model.row_at(indexes[0].row())
        if row:
            self._detail.setPlainText(self._describe(row))
            self._assets_panel.set_baris(row.excel_row, row.nama)
        self._perbarui_tombol()

    def _periksa_ulang(self, rows=None) -> None:
        """Periksa ulang seluruh baris dengan berkas yang berlaku sekarang."""
        assets = self._assets_panel.assets()
        for row in rows if rows is not None else self._model.rows():
            row.issues = validate(row.data, catalog=self._catalog, assets=assets)

    def _on_assets_changed(self) -> None:
        """Simpan pilihan berkas di sebelah workbook, lalu perbarui ringkasan.

        Memilih dokumen bisa membuat baris yang tadinya terhalang jadi siap --
        atribut seperti Komponen Struktur Biaya Tayang mengambil nilainya dari
        nama berkas. Karena itu barisnya diperiksa ulang, bukan cuma ringkasan
        yang disegarkan.
        """
        if self._workbook_path:
            self._assets_panel.assets().save(self._workbook_path)
        self._periksa_ulang()
        for posisi in range(len(self._model.rows())):
            self._model.refresh(posisi)
        self._perbarui_tombol()
        self._update_summary()

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
        terisi = counts[Status.TERISI]
        belum_disimpan = f" · {terisi} terisi belum disimpan" if terisi else ""
        self._summary.setText(
            f"{counts[Status.SUKSES]} sukses · {counts[Status.GAGAL]} gagal"
            f"{belum_disimpan} · {siap} siap dijalankan · "
            f"{bermasalah} perlu diperbaiki{catatan}"
        )
        self._perbarui_tombol()

    def _set_connection_status(self, connected: bool) -> None:
        self.statusBar().showMessage(
            "Siap. Buka file template, pilih satu baris, lalu 'Jalankan baris ini'."
        )

    # --- penutupan ----------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Jangan biarkan antrean mati bersama jendelanya tanpa ditanya.

        Menutup jendela di tengah antrean meninggalkan satu baris berstatus
        'berjalan' di berkas status. Baris itu memang dipulihkan ke menunggu
        saat file dibuka lagi, tapi keputusannya tetap milik operator.
        """
        if self._worker is not None and self._worker.isRunning():
            jawab = QMessageBox.question(
                self, "Antrean masih berjalan",
                "Baris masih dikerjakan. Hentikan antreannya dan tutup aplikasi?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if jawab != QMessageBox.Yes:
                event.ignore()
                return
            self._worker.stop()
            self._worker.wait(20_000)
        super().closeEvent(event)


__all__ = ["MainWindow"]
