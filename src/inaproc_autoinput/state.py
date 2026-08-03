"""Penyimpanan status eksekusi per baris.

Status sengaja TIDAK ditulis balik ke file Excel penyedia. Kalau file itu sedang
dibuka di Excel, penulisan akan gagal (terkunci), dan pekerjaan berjam-jam bisa
hilang. Status disimpan di berkas pendamping `<nama>.status.json` di folder yang
sama -- terlihat oleh operator, gampang dihapus bila ingin mengulang dari nol.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .model import ProductRow, Status

SUFFIX = ".status.json"


def state_path(workbook: str | Path) -> Path:
    workbook = Path(workbook)
    return workbook.with_name(workbook.stem + SUFFIX)


def save(workbook: str | Path, rows: list[ProductRow]) -> Path:
    path = state_path(workbook)
    payload = {
        "workbook": Path(workbook).name,
        "diperbarui": datetime.now().isoformat(timespec="seconds"),
        "baris": {
            str(row.excel_row): {
                "status": row.status.value,
                "pesan": row.message,
                "produk_id": row.produk_id,
                "sidik_jari": row.fingerprint(),
            }
            for row in rows
            if row.status is not Status.MENUNGGU
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
    return path


def apply(workbook: str | Path, rows: list[ProductRow]) -> int:
    """Pasang status tersimpan ke baris yang baru dibaca. Mengembalikan jumlah cocok.

    Baris yang isinya berubah sejak terakhir dijalankan dikembalikan ke status
    menunggu -- status suksesnya tidak lagi mewakili apa yang ada di file.
    """
    path = state_path(workbook)
    if not path.exists():
        return 0

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    stored = payload.get("baris", {})
    matched = 0
    for row in rows:
        entry = stored.get(str(row.excel_row))
        if not entry:
            continue
        if entry.get("sidik_jari") and entry["sidik_jari"] != row.fingerprint():
            row.status = Status.MENUNGGU
            row.message = "data berubah sejak terakhir dijalankan"
            continue
        try:
            row.status = Status(entry.get("status", Status.MENUNGGU.value))
        except ValueError:
            row.status = Status.MENUNGGU
        if row.status is Status.BERJALAN:
            # Aplikasi berhenti di tengah jalan; baris itu tidak pernah selesai.
            row.status = Status.MENUNGGU
            row.message = "terhenti di tengah proses, perlu diulang"
        else:
            row.message = entry.get("pesan", "")
        row.produk_id = entry.get("produk_id", "")
        matched += 1
    return matched


def clear(workbook: str | Path) -> bool:
    path = state_path(workbook)
    if path.exists():
        path.unlink()
        return True
    return False


__all__ = ["apply", "clear", "save", "state_path"]
