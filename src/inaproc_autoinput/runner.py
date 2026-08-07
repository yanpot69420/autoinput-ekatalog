"""Pengisi form tambah produk di portal, lewat browser yang sudah kamu login.

Aplikasi tidak pernah menyimpan kata sandi. Kamu menjalankan Chrome dengan port
debug terbuka, login sendiri seperti biasa, lalu aplikasi menempel ke sesi itu:

    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\
        --remote-debugging-port=9222 --user-data-dir="$HOME/.inaproc-chrome"

Profil terpisah dipakai supaya Chrome sehari-harimu tidak perlu ditutup. Login
sekali di jendela itu, dan sesinya bertahan.

Cara mengisi sengaja mengutamakan `name` dan `id` elemen yang stabil; hanya
bagian yang tidak punya keduanya yang dicari lewat teks labelnya.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .assets import Assets
from .schema import (
    TIPE_BARANG,
    attribute_pairs,
    perlu_kuantitas_desimal,
    split_category,
)

URL_TAMBAH = "https://penyedia.inaproc.id/products/add"
CDP_DEFAULT = "http://localhost:9222"

# Nama field pada form. Diambil dari docs/form-tambah-produk.md.
SEL_KATEGORI = 'input[placeholder="Pilih Kategori"]'
SEL_NAMA = "#form-product-name-input"
SEL_DESKRIPSI = 'textarea[name="description"]'
SEL_VIDEO_URL = "#form-product-video-url-input"
SEL_FOTO = "#product-image-input-{}"
SEL_VIDEO = "#videoInput"
SEL_HARGA = "#form-product-price-input"
SEL_MIN_BELI = "#form-product-min-purchase-input"
SEL_STOK = "#stockUnit-value-input"
SEL_PPN = "#react-select-ppnPercentage-select-input"
SEL_DOKUMEN = "#document-field-input"
SEL_ATRIBUT_UTAMA = 'input[name^="productInformations.mainInformations."]'
SEL_ATRIBUT_LAIN = 'input[name^="productInformations.additionalInformations."]'
SEL_OPSI_TERLIHAT = '[role="option"]:visible, [class*="option"]:visible'

SAKLAR = {
    "pre_order": "#form-product-preorder-isActive-switch",
}
# Saklar ini tidak punya kolom Excel: nilainya disimpulkan, bukan ditanyakan.
SEL_KUANTITAS_DESIMAL = "#form-product-decimal-qty-switch"
SAKLAR_NYALA = {"Ya", "Aktif"}

TOMBOL_SIMPAN_DRAF = "Simpan Draf Produk"
TOMBOL_SIMPAN = "Simpan"

TIMEOUT_PENDEK = 8_000
TIMEOUT_PANJANG = 25_000


class Mode(str, Enum):
    """Sejauh mana aplikasi boleh bertindak."""

    ISI_SAJA = "isi_saja"          # berhenti sebelum menyimpan; kamu yang klik
    SIMPAN_DRAF = "simpan_draf"    # simpan sebagai draf, belum tayang
    SIMPAN = "simpan"              # simpan dan ajukan seperti biasa

    @property
    def label(self) -> str:
        return {
            Mode.ISI_SAJA: "Isi saja, jangan simpan",
            Mode.SIMPAN_DRAF: "Simpan sebagai draf",
            Mode.SIMPAN: "Simpan (produk diajukan)",
        }[self]


@dataclass
class Hasil:
    berhasil: bool
    pesan: str = ""
    # Benar hanya bila produk sungguh disimpan ke portal. Mode "Isi saja"
    # berhasil tanpa menyimpan apa pun, dan bedanya penting: baris yang cuma
    # terisi masih harus dikerjakan.
    tersimpan: bool = False
    produk_id: str = ""
    langkah: list[str] = field(default_factory=list)
    peringatan: list[str] = field(default_factory=list)


class RunnerError(RuntimeError):
    """Kegagalan yang sudah dijelaskan dengan bahasa manusia."""


def _teks(nilai) -> str:
    return "" if nilai is None else str(nilai).strip()


def _angka(nilai) -> str:
    """'1.250,50' -> '1250,50'. Form menolak pemisah ribuan."""
    teks = _teks(nilai)
    return teks.replace(".", "") if re.fullmatch(r"[\d.]+,\d+", teks) else teks


class ProductFormFiller:
    """Mengisi satu halaman tambah produk. Dipisah dari koneksi agar bisa diuji."""

    def __init__(self, page, catatan=None):
        self.page = page
        self.langkah: list[str] = []
        self.peringatan: list[str] = []
        self._catatan = catatan or (lambda pesan: None)

    def _catat(self, pesan: str) -> None:
        self.langkah.append(pesan)
        self._catatan(pesan)

    # --- primitif -----------------------------------------------------------

    def _isi(self, selector: str, nilai: str, label: str) -> None:
        if not nilai:
            return
        elemen = self.page.locator(selector).first
        elemen.wait_for(state="visible", timeout=TIMEOUT_PENDEK)
        elemen.fill(nilai)
        self._catat(f"{label}: {nilai[:60]}")

    def _pilih_dropdown(self, pembuka, nilai: str, label: str) -> None:
        """react-select: klik, ketik, lalu pilih opsi yang cocok."""
        if not nilai:
            return
        pembuka.click()
        self.page.keyboard.type(nilai, delay=15)
        # Hanya opsi yang terlihat. Menu lain yang sudah ditutup tetap ada di DOM,
        # dan kalau ikut terjaring, penantian akan macet pada elemen tersembunyi.
        opsi = self.page.locator(SEL_OPSI_TERLIHAT)
        try:
            opsi.first.wait_for(state="visible", timeout=TIMEOUT_PENDEK)
        except Exception as error:  # noqa: BLE001 -- diterjemahkan jadi pesan
            raise RunnerError(
                f"{label}: daftar pilihan tidak muncul untuk '{nilai}'"
            ) from error

        cocok = opsi.filter(has_text=re.compile(rf"^\s*{re.escape(nilai)}", re.I))
        (cocok.first if cocok.count() else opsi.first).click()
        self._catat(f"{label}: {nilai}")

    def _saklar(self, selector: str, nyala: bool, label: str) -> None:
        elemen = self.page.locator(selector).first
        if not elemen.count():
            return
        if elemen.is_checked() != nyala:
            elemen.click()
            self._catat(f"{label}: {'aktif' if nyala else 'tidak aktif'}")

    def _unggah(self, selector: str, path: str, label: str) -> None:
        if not path:
            return
        berkas = Path(path).expanduser()
        if not berkas.is_file():
            raise RunnerError(f"{label}: berkas tidak ada — {berkas}")
        self.page.locator(selector).first.set_input_files(str(berkas))
        self._catat(f"{label}: {berkas.name}")

    # --- bagian form --------------------------------------------------------

    def pilih_kategori(self, jalur: str) -> None:
        satu, dua, tiga = split_category(jalur)
        if not tiga:
            raise RunnerError("Kategori harus lengkap sampai Level 3")

        kotak = self.page.locator(SEL_KATEGORI).first
        kotak.click()
        kotak.fill("")
        self.page.keyboard.type(tiga, delay=20)

        for tingkat, nama in ((1, satu), (2, dua), (3, tiga)):
            pilihan = self.page.get_by_text(nama, exact=True).locator("visible=true")
            try:
                pilihan.first.wait_for(state="visible", timeout=TIMEOUT_PENDEK)
            except Exception as error:  # noqa: BLE001
                raise RunnerError(
                    f"Kategori tidak ditemukan di pemilih portal: Level {tingkat} "
                    f"'{nama}' tidak muncul saat mencari '{tiga}'"
                ) from error
            pilihan.first.click()

        # Mengganti kategori pada form yang sudah terisi memunculkan konfirmasi.
        konfirmasi = self.page.get_by_role("button", name="Ya, Ubah")
        if konfirmasi.count():
            konfirmasi.first.click()

        self.page.wait_for_timeout(1_500)  # bagian baru dirender setelah kategori
        self._catat(f"Kategori: {jalur}")

    def baca_tipe_produk(self) -> str:
        """Portal menuliskan 'Kategori ini termasuk jenis Produk Jasa'."""
        petunjuk = self.page.get_by_text(re.compile(r"termasuk jenis Produk"))
        if not petunjuk.count():
            return ""
        cocok = re.search(r"Produk\s+(\w+)", petunjuk.first.inner_text())
        return cocok.group(1) if cocok else ""

    def label_atribut(self) -> list[str]:
        """Label bagian Informasi Utama, berurut sesuai indeks di form."""
        hasil: list[str] = []
        for elemen in self.page.locator(SEL_ATRIBUT_UTAMA).all():
            nama = elemen.get_attribute("name") or ""
            cocok = re.search(r"\.(\d+)\.value$", nama)
            if not cocok:
                continue
            petunjuk = elemen.get_attribute("placeholder") or ""
            hasil.append(re.sub(r"^Masukkan\s+", "", petunjuk).strip())
        return hasil

    def isi_atribut(self, atribut: dict[str, str]) -> None:
        """Cocokkan Atribut/Nilai dari Excel dengan field di halaman, lewat namanya."""
        if not atribut:
            return
        tersedia = {
            _normalisasi(lbl): idx
            for idx, lbl in enumerate(self.label_atribut())
            if lbl
        }
        for nama, nilai in atribut.items():
            indeks = tersedia.get(_normalisasi(nama))
            if indeks is None:
                self.peringatan.append(
                    f"Atribut '{nama}' tidak ada di form kategori ini, dilewati"
                )
                continue
            self._isi(
                f'input[name="productInformations.mainInformations.{indeks}.value"]',
                nilai, f"Atribut {nama}",
            )

    def isi_lampiran(self, lampiran: dict[str, str]) -> None:
        """Bagian Lampiran hanya dibedakan urutannya, jadi dicocokkan lewat judul."""
        if not lampiran:
            return
        jumlah = self.page.locator(SEL_DOKUMEN).count()
        urutan = self._urutan_lampiran(jumlah)

        for nama, berkas in lampiran.items():
            indeks = urutan.get(_normalisasi(nama))
            if indeks is None:
                self.peringatan.append(
                    f"Dokumen '{nama}' tidak ada di form kategori ini, dilewati"
                )
                continue
            self._unggah(f"{SEL_DOKUMEN} >> nth={indeks}", berkas, f"Dokumen {nama}")

    def _urutan_lampiran(self, jumlah: int) -> dict[str, int]:
        """Petakan judul dokumen -> urutan input berkas di bagian Lampiran."""
        judul = self.page.evaluate(
            """() => [...document.querySelectorAll('#document-field-input')]
                 .map(el => {
                   let n = el.closest('div');
                   for (let i = 0; i < 8 && n; i++, n = n.parentElement) {
                     const t = (n.innerText || '').trim().split('\\n')[0];
                     if (t && t.length < 90 && !t.startsWith('Pilih atau tarik')) return t;
                   }
                   return '';
                 })"""
        )
        return {_normalisasi(t): i for i, t in enumerate(judul[:jumlah]) if t}

    # --- alur utama ---------------------------------------------------------

    def isi(self, data: dict, assets: Assets | None = None) -> None:
        assets = assets or Assets()
        foto = assets.foto_untuk(int(data.get("_row") or 0))

        self.pilih_kategori(_teks(data.get("kategori")))
        tipe = self.baca_tipe_produk()
        if tipe:
            self._catat(f"Portal menyebut kategori ini bertipe {tipe}")

        self._isi(SEL_NAMA, _teks(data.get("nama_produk")), "Nama Produk")
        self._isi(SEL_DESKRIPSI, _teks(data.get("deskripsi")), "Deskripsi")

        for nomor in range(1, 6):
            berkas = foto[nomor - 1] if nomor <= len(foto) else ""
            self._unggah(SEL_FOTO.format(nomor - 1), _teks(berkas), f"Foto {nomor}")
        self._unggah(SEL_VIDEO, _teks(assets.video), "Video")
        self._isi(SEL_VIDEO_URL, _teks(assets.video_url), "URL Video")

        self._pilih_dropdown(self._dropdown_dekat("Kode KBKI"),
                             _teks(data.get("kbki")), "Kode KBKI")
        for kunci, label in (
            ("pdn_klasifikasi", "Klasifikasi Produk"),
            ("pdn_lokasi_produksi", "Lokasi Produksi"),
            ("pdn_tenaga_kerja", "Tenaga Kerja dalam Proses Produksi"),
            ("pdn_bahan_baku", "Bahan Baku dalam Proses Produksi"),
        ):
            self._pilih_dropdown(self._dropdown_dekat(label),
                                 _teks(data.get(kunci)), label)

        self._pilih_dropdown(self.page.locator(SEL_PPN).first,
                             _teks(data.get("ppn")), "PPN")

        for kunci, selector in SAKLAR.items():
            nilai = _teks(data.get(kunci))
            if nilai:
                self._saklar(selector, nilai in SAKLAR_NYALA, kunci)

        if perlu_kuantitas_desimal(data):
            self._saklar(SEL_KUANTITAS_DESIMAL, True, "Kuantitas Desimal")

        self._isi(SEL_MIN_BELI, _angka(data.get("minimum_pembelian")),
                  "Minimum Pembelian")
        self._isi(SEL_HARGA, _angka(data.get("harga_produk")), "Harga Produk")
        self._isi(SEL_STOK, _angka(data.get("stok")), "Jumlah Stok")
        self._pilih_dropdown(self._dropdown_dekat("Satuan Produk"),
                             _teks(data.get("satuan_produk")), "Satuan Produk")

        if tipe == TIPE_BARANG:
            self._isi_pengiriman(data)

        self.isi_atribut(attribute_pairs(data))
        self.isi_lampiran(dict(assets.dokumen))

    def _isi_pengiriman(self, data: dict) -> None:
        for kunci, label in (
            ("berat_gram", "Berat Produk"),
            ("panjang_cm", "Panjang"),
            ("lebar_cm", "Lebar"),
            ("tinggi_cm", "Tinggi"),
        ):
            nilai = _angka(data.get(kunci))
            if not nilai:
                continue
            kotak = self._input_dekat(label)
            if kotak is None:
                self.peringatan.append(f"{label}: kolomnya tidak ketemu di form")
                continue
            kotak.fill(nilai)
            self._catat(f"{label}: {nilai}")

    def _dropdown_dekat(self, label: str):
        """Pembuka dropdown pada baris berlabel tertentu."""
        baris = self.page.locator(f'div:has-text("{label}")').last
        return baris.locator('input[role="combobox"], [class*="control"] input').first

    def _input_dekat(self, label: str):
        baris = self.page.locator(f'div:has-text("{label}")').last
        kotak = baris.locator('input[type="text"], input:not([type])').first
        return kotak if kotak.count() else None

    # --- penyimpanan --------------------------------------------------------

    def simpan(self, mode: Mode) -> str:
        if mode is Mode.ISI_SAJA:
            self._catat("Berhenti sebelum menyimpan — silakan periksa lalu klik sendiri")
            return ""

        nama = TOMBOL_SIMPAN_DRAF if mode is Mode.SIMPAN_DRAF else TOMBOL_SIMPAN
        tombol = self.page.get_by_role("button", name=nama, exact=True)
        if not tombol.count():
            raise RunnerError(f"Tombol '{nama}' tidak ditemukan")
        if not tombol.first.is_enabled():
            raise RunnerError(f"Tombol '{nama}' tidak aktif — form belum lengkap")

        tombol.first.click()
        self.page.wait_for_timeout(3_000)
        self._catat(f"Diklik: {nama}")

        cocok = re.search(r"/products/([0-9a-f-]{8,})", self.page.url)
        return cocok.group(1) if cocok else ""


def _normalisasi(teks: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(teks or "").lower()).strip()


class BrowserRunner:
    """Menempel ke Chrome yang sudah login, lalu mengisi baris satu per satu."""

    def __init__(self, cdp_url: str = CDP_DEFAULT):
        self.cdp_url = cdp_url
        self._playwright = None
        self._browser = None
        self.page = None

    def connect(self):
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(self.cdp_url)
        except Exception as error:  # noqa: BLE001
            self.close()
            from .chrome import command_text

            raise RunnerError(
                f"Tidak bisa menyambung ke Chrome di {self.cdp_url}.\n\n"
                "Klik 'Buka Chrome portal' di jendela aplikasi, atau jalankan "
                "sendiri lalu login:\n\n" + command_text()
            ) from error

        konteks = self._browser.contexts[0] if self._browser.contexts else None
        if konteks is None:
            self.close()
            raise RunnerError("Chrome tersambung tapi tidak punya jendela terbuka")

        self.page = next(
            (h for h in konteks.pages if "penyedia.inaproc.id" in h.url),
            konteks.pages[0] if konteks.pages else konteks.new_page(),
        )
        return self

    def siap(self) -> bool:
        return self.page is not None and not self.page.is_closed()

    def buka_form(self) -> None:
        if not self.page.url.startswith(URL_TAMBAH):
            self.page.goto(URL_TAMBAH, wait_until="domcontentloaded",
                           timeout=TIMEOUT_PANJANG)
        else:
            self.page.reload(wait_until="domcontentloaded", timeout=TIMEOUT_PANJANG)
        self.page.locator(SEL_KATEGORI).first.wait_for(
            state="visible", timeout=TIMEOUT_PANJANG
        )

    def jalankan(self, data: dict, mode: Mode = Mode.ISI_SAJA, catatan=None,
                 assets: Assets | None = None) -> Hasil:
        if not self.siap():
            return Hasil(False, "Browser belum tersambung")

        pengisi = ProductFormFiller(self.page, catatan)
        try:
            self.buka_form()
            pengisi.isi(data, assets)
            produk_id = pengisi.simpan(mode)
        except RunnerError as error:
            return Hasil(False, str(error), langkah=pengisi.langkah,
                         peringatan=pengisi.peringatan)
        except Exception as error:  # noqa: BLE001 -- apa pun dari browser
            return Hasil(False, f"{type(error).__name__}: {error}".split("\n")[0],
                         langkah=pengisi.langkah, peringatan=pengisi.peringatan)

        tersimpan = mode is not Mode.ISI_SAJA
        pesan = "tersimpan" if tersimpan else "terisi, menunggu kamu menyimpan"
        return Hasil(True, pesan, tersimpan, produk_id,
                     pengisi.langkah, pengisi.peringatan)

    def close(self) -> None:
        for obj, tutup in ((self._browser, "close"), (self._playwright, "stop")):
            try:
                if obj is not None:
                    getattr(obj, tutup)()
            except Exception:  # noqa: BLE001 -- penutupan tidak boleh menggagalkan
                pass
        self._browser = self._playwright = self.page = None


__all__ = [
    "BrowserRunner",
    "CDP_DEFAULT",
    "Hasil",
    "Mode",
    "ProductFormFiller",
    "RunnerError",
    "URL_TAMBAH",
]
