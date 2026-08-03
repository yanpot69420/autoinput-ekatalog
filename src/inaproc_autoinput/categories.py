"""Pohon kategori Katalog Elektronik v6, diambil langsung dari portal.

Portal menyediakan seluruh kategori lewat satu panggilan GraphQL publik --
tanpa login. Sekali ambil menghasilkan 57 kategori level 1, 456 level 2, dan
2.934 level 3, lengkap dengan UUID masing-masing.

Ini penting karena dua hal:

* Nama kategori yang ditulis penyedia di Excel bisa diperiksa sebelum aplikasi
  membuka portal. Salah ketik satu huruf berarti pemilih kategori di halaman
  tambah produk tidak akan ketemu, dan baris itu gagal setelah menghabiskan
  waktu pengisian.
* UUID-nya kelak dipakai untuk memilih kategori secara langsung, bukan dengan
  mengetik dan menebak hasil pencarian.

Hasil unduhan disimpan sebagai cache supaya aplikasi tetap jalan tanpa internet.
"""

from __future__ import annotations

import difflib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .schema import TIPE_BARANG, TIPE_DIGITAL, TIPE_JASA

ENDPOINT = "https://katalog.inaproc.id/graphql"

_FIELDS = (
    "id level name productType "
    "children { id level name productType "
    "children { id level name productType } }"
)
QUERY = (
    "query { allMinifiedProductCategory(input: {}) { __typename "
    "... on AllMinifiedProductCategories { items { %s } } } }" % _FIELDS
)

# productType di portal <-> Tipe Produk di template.
TIPE_KE_PORTAL = {
    TIPE_BARANG: "PHYSICAL",
    TIPE_JASA: "SERVICE",
    TIPE_DIGITAL: "DIGITAL",
}
PORTAL_KE_TIPE = {v: k for k, v in TIPE_KE_PORTAL.items()}

CACHE_PATH = Path.home() / ".inaproc-autoinput" / "categories.json"
SCOPE_PATH = Path.home() / ".inaproc-autoinput" / "bidang.json"

# Bidang yang dilayani: konstruksi dan pertanian. Dari 57 kategori level 1 yang
# ada di portal, 21 ini menyisakan 1.277 dari 2.934 kategori level 3.
#
# Daftar ini bisa diubah tanpa menyentuh kode dengan menulis SCOPE_PATH:
#   {"bidang": ["Bidang Bina Marga", "..."]}
BIDANG_DEFAULT: tuple[str, ...] = (
    # Konstruksi -- pekerjaan dan material
    "Bidang Bina Marga",
    "Bidang Bina Marga 2025",
    "Bidang Cipta Karya",
    "Bidang Sumber Daya Air",
    "Bidang Perumahan dan Kawasan Permukiman",
    "Bidang Umum",  # isinya U.1 Persiapan s.d. U.6 Air Tanah
    "Sistem Manajemen Keselamatan Konstruksi (SMKK)",
    "Komponen Struktur",
    "Material Dasar Utama",
    "Material Olahan Utama",
    "Pesawat/Peralatan Konstruksi Lainnya",
    "Jasa Sewa Pesawat/Peralatan Konstruksi Lainnya",
    # Konstruksi -- alat berat
    "Pesawat Angkat",
    "Pesawat Angkut",
    "Pesawat Tenaga dan Produksi",
    "Jasa Sewa Pesawat Angkat",
    "Jasa Sewa Pesawat Angkut",
    "Jasa Sewa Pesawat Tenaga dan Produksi",
    # Pertanian
    "Pekerjaan Cetak Sawah",
    "Tanaman dan Sarana Pendukung",
    "Hewan dan Ternak",
)

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://katalog.inaproc.id",
    "Referer": "https://katalog.inaproc.id/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class Category:
    id: str
    level: int
    name: str
    product_type: str
    children: tuple["Category", ...] = field(default_factory=tuple)

    @property
    def tipe_produk(self) -> str:
        """Tipe dalam istilah template: Barang / Jasa / Digital."""
        return PORTAL_KE_TIPE.get(self.product_type, self.product_type)


def _to_category(raw: dict) -> Category:
    return Category(
        id=raw.get("id", ""),
        level=int(raw.get("level", 0)),
        name=(raw.get("name") or "").strip(),
        product_type=raw.get("productType", ""),
        children=tuple(_to_category(c) for c in raw.get("children") or ()),
    )


def fetch(timeout: int = 60) -> list[Category]:
    """Ambil pohon kategori dari portal. Melempar OSError bila gagal."""
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps({"query": QUERY}).encode("utf-8"), headers=_HEADERS
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)

    if payload.get("errors"):
        pesan = payload["errors"][0].get("message", "tidak diketahui")
        raise OSError(f"portal menolak permintaan kategori: {pesan}")

    items = (payload.get("data") or {}).get("allMinifiedProductCategory") or {}
    return [_to_category(raw) for raw in items.get("items") or ()]


def _serialize(category: Category) -> dict:
    data = {
        "id": category.id,
        "level": category.level,
        "name": category.name,
        "productType": category.product_type,
    }
    if category.children:
        data["children"] = [_serialize(c) for c in category.children]
    return data


def save_cache(roots: list[Category], path: Path | None = None) -> Path:
    path = path or CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "diunduh": datetime.now().isoformat(timespec="seconds"),
        "items": [_serialize(c) for c in roots],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    return path


def load_cache(path: Path | None = None) -> tuple[list[Category], str]:
    path = path or CACHE_PATH
    if not path.exists():
        return [], ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [], ""
    return [_to_category(raw) for raw in payload.get("items", [])], payload.get(
        "diunduh", ""
    )


def load_scope(path: Path | None = None) -> tuple[str, ...]:
    """Daftar bidang yang dilayani. Berkas SCOPE_PATH menimpa daftar bawaan."""
    path = path or SCOPE_PATH
    if not path.exists():
        return BIDANG_DEFAULT
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return BIDANG_DEFAULT
    bidang = payload.get("bidang")
    return tuple(bidang) if bidang else BIDANG_DEFAULT


def save_scope(bidang: tuple[str, ...], path: Path | None = None) -> Path:
    path = path or SCOPE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"bidang": list(bidang)}, ensure_ascii=False, indent=1), "utf-8"
    )
    return path


def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).casefold()


class Catalog:
    """Pohon kategori siap pakai: pencarian, pencocokan, dan saran ejaan."""

    def __init__(self, roots: list[Category], diunduh: str = ""):
        self.roots = roots
        self.diunduh = diunduh
        self._level1 = {_norm(c.name): c for c in roots}

    # --- pemuatan -----------------------------------------------------------

    @classmethod
    def load(cls, refresh: bool = False, path: Path | None = None) -> "Catalog":
        """Pakai cache bila ada; ambil dari portal bila belum ada atau diminta."""
        if not refresh:
            roots, diunduh = load_cache(path)
            if roots:
                return cls(roots, diunduh)
        roots = fetch()
        save_cache(roots, path)
        return cls(roots, datetime.now().isoformat(timespec="seconds"))

    # --- penyaringan bidang -------------------------------------------------

    def restrict(self, bidang: tuple[str, ...] | None = None) -> "Catalog":
        """Katalog berisi bidang terpilih saja, untuk template dan dropdown.

        Katalog penuh tetap dipakai saat memvalidasi, supaya kategori yang sah
        tapi di luar bidang dilaporkan sebagai peringatan yang jelas -- bukan
        sebagai 'kategori tidak ada', yang akan menyesatkan.
        """
        bidang = bidang if bidang is not None else load_scope()
        pilihan = {_norm(b) for b in bidang}
        return Catalog(
            [c for c in self.roots if _norm(c.name) in pilihan], self.diunduh
        )

    def in_scope(self, level1: str, bidang: tuple[str, ...] | None = None) -> bool:
        bidang = bidang if bidang is not None else load_scope()
        return _norm(level1) in {_norm(b) for b in bidang}

    # --- penelusuran --------------------------------------------------------

    @property
    def kosong(self) -> bool:
        return not self.roots

    def level1_names(self, tipe: str = "") -> list[str]:
        portal = TIPE_KE_PORTAL.get(tipe, "")
        return [
            c.name for c in self.roots if not portal or c.product_type == portal
        ]

    def find_level1(self, name: str) -> Category | None:
        return self._level1.get(_norm(name))

    def children_of(self, *path: str) -> list[Category]:
        """Anak dari jalur kategori, mis. children_of('Bidang Bina Marga')."""
        node = self.find_level1(path[0]) if path else None
        for name in path[1:]:
            if node is None:
                return []
            node = next((c for c in node.children if _norm(c.name) == _norm(name)), None)
        return list(node.children) if node else [c for c in self.roots]

    def resolve(self, l1: str, l2: str, l3: str) -> tuple[Category | None, str]:
        """Cari kategori level 3 dari jalur namanya.

        Mengembalikan (kategori, pesan). Pesan berisi alasan bila gagal, plus
        saran ejaan terdekat -- karena penyebab tersering adalah salah ketik.
        """
        satu = self.find_level1(l1)
        if satu is None:
            return None, self._gagal("Kategori Level 1", l1, self.level1_names())

        dua = next((c for c in satu.children if _norm(c.name) == _norm(l2)), None)
        if dua is None:
            return None, self._gagal(
                "Kategori Level 2", l2, [c.name for c in satu.children]
            )

        tiga = next((c for c in dua.children if _norm(c.name) == _norm(l3)), None)
        if tiga is None:
            return None, self._gagal(
                "Kategori Level 3", l3, [c.name for c in dua.children]
            )
        return tiga, ""

    def resolve_path(self, jalur: str) -> tuple[Category | None, str]:
        """Cari kategori dari satu string 'Level 1 > Level 2 > Level 3'."""
        from .schema import split_category

        teks = str(jalur or "").strip()
        if not teks:
            return None, "Kategori belum diisi"

        satu, dua, tiga = split_category(teks)
        if not tiga:
            return None, (
                "Kategori harus lengkap sampai Level 3, dipisah ' > '. "
                "Salin dari sheet 'Daftar Kategori'."
            )
        return self.resolve(satu, dua, tiga)

    @staticmethod
    def _gagal(label: str, nilai: str, pilihan: list[str]) -> str:
        if not str(nilai or "").strip():
            return f"{label} belum diisi"
        dekat = difflib.get_close_matches(nilai, pilihan, n=2, cutoff=0.6)
        if dekat:
            return f"{label} '{nilai}' tidak ada. Maksudnya '{dekat[0]}'?"
        return f"{label} '{nilai}' tidak ada dalam daftar portal ({len(pilihan)} pilihan)"

    # --- ringkasan ----------------------------------------------------------

    def tally(self) -> dict[str, int]:
        level2 = [c for r in self.roots for c in r.children]
        level3 = [c for p in level2 for c in p.children]
        return {"level1": len(self.roots), "level2": len(level2), "level3": len(level3)}

    def flatten(self) -> list[dict]:
        """Ratakan jadi baris (tipe, l1, l2, l3, id) -- untuk diekspor."""
        rows: list[dict] = []
        for satu in self.roots:
            for dua in satu.children:
                for tiga in dua.children:
                    rows.append({
                        "tipe_produk": satu.tipe_produk,
                        "kategori_1": satu.name,
                        "kategori_2": dua.name,
                        "kategori_3": tiga.name,
                        "id_kategori_3": tiga.id,
                    })
        return rows


__all__ = ["CACHE_PATH", "Catalog", "Category", "ENDPOINT", "QUERY", "fetch"]
