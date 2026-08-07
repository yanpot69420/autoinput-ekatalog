"""Model tabel produk untuk QTableView."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont

from ..model import ProductRow, Status

COL_PENANDA = 0
COL_BARIS = 1
COL_STATUS = 2
COL_NAMA = 3
COL_KATEGORI = 4
COL_TIPE = 5
COL_PESAN = 6

HEADERS = ["", "Baris", "Status", "Nama Produk", "Kategori Level 3", "Tipe", "Keterangan"]

# Warna dipilih yang terbaca di tema terang maupun gelap.
WARNA = {
    Status.MENUNGGU: QColor("#9e9e9e"),
    Status.BERJALAN: QColor("#42a5f5"),
    Status.TERISI: QColor("#ffa726"),
    Status.SUKSES: QColor("#4caf50"),
    Status.GAGAL: QColor("#ef5350"),
    Status.DILEWATI: QColor("#bdbdbd"),
}


class ProductTableModel(QAbstractTableModel):
    def __init__(self, rows: list[ProductRow] | None = None, parent=None):
        super().__init__(parent)
        self._rows: list[ProductRow] = rows or []
        self._active: int | None = None  # indeks baris yang sedang dijalankan

    # --- data dasar ---------------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            return self._text(row, column, index.row())
        if role == Qt.ForegroundRole and column in (COL_PENANDA, COL_STATUS):
            return WARNA.get(row.status)
        if role == Qt.FontRole and index.row() == self._active:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.TextAlignmentRole and column in (COL_PENANDA, COL_BARIS, COL_TIPE):
            return int(Qt.AlignCenter)
        if role == Qt.ToolTipRole:
            return self._tooltip(row)
        return None

    def _text(self, row: ProductRow, column: int, position: int):
        if column == COL_PENANDA:
            return "▶" if position == self._active else row.status.symbol
        if column == COL_BARIS:
            return row.excel_row
        if column == COL_STATUS:
            return row.status.label
        if column == COL_NAMA:
            return row.nama or "(tanpa nama)"
        if column == COL_KATEGORI:
            return row.kategori_3
        if column == COL_TIPE:
            return row.tipe_produk
        if column == COL_PESAN:
            if row.message:
                return row.message
            blocking = row.blocking_issues
            if blocking:
                extra = f" (+{len(blocking) - 1} lagi)" if len(blocking) > 1 else ""
                return f"{blocking[0]}{extra}"
            warnings = [i for i in row.issues if not i.blocking]
            return f"{len(warnings)} peringatan" if warnings else ""
        return None

    def _tooltip(self, row: ProductRow) -> str:
        if not row.issues:
            return "Tidak ada temuan"
        return "\n".join(
            f"{'✗' if issue.blocking else '!'} {issue}" for issue in row.issues
        )

    # --- pengubah -----------------------------------------------------------

    def set_rows(self, rows: list[ProductRow]) -> None:
        self.beginResetModel()
        self._rows = rows
        self._active = None
        self.endResetModel()

    def rows(self) -> list[ProductRow]:
        return self._rows

    def row_at(self, position: int) -> ProductRow | None:
        if 0 <= position < len(self._rows):
            return self._rows[position]
        return None

    def set_active(self, position: int | None) -> None:
        previous, self._active = self._active, position
        for pos in {previous, position}:
            if pos is not None and 0 <= pos < len(self._rows):
                self.refresh(pos)

    def refresh(self, position: int) -> None:
        left = self.index(position, 0)
        right = self.index(position, self.columnCount() - 1)
        self.dataChanged.emit(left, right)

    # --- ringkasan ----------------------------------------------------------

    def tally(self) -> dict[Status, int]:
        counts = {status: 0 for status in Status}
        for row in self._rows:
            counts[row.status] += 1
        return counts

    def pending_positions(self) -> list[int]:
        """Posisi baris yang siap dijalankan: belum sukses dan tanpa error."""
        return [i for i, row in enumerate(self._rows) if row.siap]


__all__ = [
    "COL_NAMA",
    "COL_PESAN",
    "COL_STATUS",
    "HEADERS",
    "ProductTableModel",
]
