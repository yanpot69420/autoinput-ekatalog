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
# Portal memakai modal beroverlay untuk hal yang menghentikan segalanya --
# terutama "Akun Telah Keluar", yang muncul bila akun yang sama dipakai masuk
# dari browser lain. Halaman di bawahnya tetap terlihat normal, tapi overlaynya
# menelan semua klik dan ketikan.
SEL_MODAL = '[role="dialog"]:visible'

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
# Batas menunggu halaman berpindah setelah tombol simpan diklik. Lebih pendek
# dari TIMEOUT_PENDEK karena form yang ditolak portal memang tidak berpindah,
# dan menunggu delapan detik untuk memastikannya cuma menghukum kegagalan.
TIMEOUT_SIMPAN = 6_000

POLA_PRODUK = re.compile(r"/products/[0-9a-f-]{8,}")

# Kecepatan perender Chrome saat sehat, diukur pada halaman kosong -- tanpa
# jaringan dan tanpa portal, jadi yang tersisa cuma Chrome-nya sendiri.
SEHAT_JS = 8_100_000     # ribuan operasi dalam 300 ms
SEHAT_FRAME = 8.3        # milidetik per frame
# Chrome kadang meninggalkan proses perender yatim yang terus berputar tanpa
# halaman apa pun -- terukur membakar 72% CPU dengan satu tab kosong, dan
# pernah menjatuhkan kecepatan JS sampai sepersembilan. Yang melambat semua
# situs, bukan cuma portal, jadi gampang dikira portalnya yang berat.
AMBANG_JS = SEHAT_JS * 0.6
AMBANG_FRAME = SEHAT_FRAME * 1.7

_UKUR_PERENDER = """() => {
  let n = 0, t = performance.now();
  while (performance.now() - t < 300) { for (let i = 0; i < 1000; i++) n += Math.sqrt(i); }
  const js = Math.round(n / 1000 * (400 / 300));
  return new Promise(res => {
    const d = []; let a = performance.now(); const habis = a + 1000;
    (function tick(now) { d.push(now - a); a = now;
      now < habis ? requestAnimationFrame(tick) : res({js, frame: d}); })(a);
  });
}"""


def chrome_melambat(js: int, frame: float) -> bool:
    """Apakah Chrome sendiri yang melambat, terlepas dari portalnya.

    Salah satu saja sudah cukup: pada kejadian nyata keduanya turun bersamaan,
    tapi menuntut keduanya berarti melewatkan gejala yang baru mulai.
    """
    return js < AMBANG_JS or frame > AMBANG_FRAME


def pesan_chrome_lambat(js: int, frame: float) -> str:
    return (
        f"Chrome sedang melambat sendiri: kecepatan JS {js:,} (sehat "
        f"±{SEHAT_JS:,}), {frame:.1f} ms per frame (sehat ±{SEHAT_FRAME}).\n\n"
        "Penyebabnya proses perender yang tersangkut dan terus berputar tanpa "
        "halaman. Yang melambat semua situs, bukan cuma portal, dan pengisian "
        "akan terasa berat sampai Chrome dijalankan ulang:\n\n"
        "  python -m inaproc_autoinput.buka_chrome --mulai-ulang\n\n"
        "Sesi loginmu tetap ada."
    )

# Menandai elemen dengan id acak lalu mengembalikan selektornya. Dipakai karena
# id asli react-select berubah tiap render, jadi tidak bisa ditulis tetap.
_TANDAI = """const tandai = el => {
  if (!el.id) el.id = 'ia-' + Math.random().toString(36).slice(2, 10);
  return '#' + CSS.escape(el.id);
};"""

_CARI_KOTAK = _TANDAI + r"""
(arg => {
  const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
  const label = [...document.querySelectorAll('*')].find(
    e => e.children.length === 0 && rapi(e.textContent).startsWith(arg.teks));
  if (!label) return null;

  const wadahDari = inp => inp.closest('[class*="control"], [class*="select"]');
  const layak = inp => inp.placeholder !== 'Pilih Kategori' &&
      (!arg.dropdown || !!wadahDari(inp) || inp.getAttribute('role') === 'combobox');

  // Berhenti di tingkat pertama yang sudah punya isian layak. Terus naik walau
  // sudah ketemu berarti menyeberang ke kelompok sebelah, dan kotak milik
  // kolom lain yang dikembalikan -- pernah terjadi, dan galatnya cuma
  // "daftar pilihan tidak muncul".
  let n = label;
  for (let i = 0; i < 6 && n; i++, n = n.parentElement) {
    const calon = [...n.querySelectorAll('input:not([type=hidden])')].filter(layak);
    if (!calon.length) continue;
    const inp = calon.find(wadahDari) || calon[0];
    return { klik: tandai(wadahDari(inp) || inp), ketik: tandai(inp) };
  }
  return null;
})"""

_WADAH_DROPDOWN = _TANDAI + r"""
(sel => {
  const inp = document.querySelector(sel);
  const wadah = inp && inp.closest('[class*="control"], [class*="select"]');
  return wadah ? tandai(wadah) : '';
})"""


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
    # Dihentikan operator di tengah jalan. Bukan kegagalan: tidak ada yang
    # salah dengan barisnya, jadi statusnya dikembalikan ke menunggu -- bukan
    # gagal, yang akan membuatnya dilewati "Lanjutkan sisanya".
    dibatalkan: bool = False


@dataclass
class Ringkasan:
    """Hasil satu antrean, untuk dilaporkan setelah semuanya selesai."""

    dikerjakan: int = 0
    sukses: int = 0
    terisi: int = 0
    gagal: int = 0
    sisa: int = 0            # sudah masuk antrean tapi belum sempat dikerjakan
    dihentikan: bool = False  # operator menekan Berhenti
    beruntun: bool = False    # dihentikan sendiri karena gagal berturut-turut
    gagal_koneksi: str = ""   # browser tidak bisa disambung sejak awal

    @property
    def pesan(self) -> str:
        if self.gagal_koneksi:
            return f"Tidak ada baris yang dikerjakan — {self.gagal_koneksi.splitlines()[0]}"
        bagian = [f"{self.dikerjakan} baris dikerjakan"]
        if self.sukses:
            bagian.append(f"{self.sukses} tersimpan")
        if self.terisi:
            bagian.append(f"{self.terisi} terisi, menunggu kamu menyimpan")
        if self.gagal:
            bagian.append(f"{self.gagal} gagal")
        if self.sisa:
            bagian.append(f"{self.sisa} belum dikerjakan")
        return " · ".join(bagian)

    @property
    def alasan(self) -> str:
        """Kenapa antrean berhenti, bila berhentinya bukan karena habis."""
        if self.gagal_koneksi:
            return self.gagal_koneksi
        if self.beruntun:
            return (
                f"Berhenti sendiri setelah {BATAS_GAGAL_BERUNTUN} baris gagal "
                "berturut-turut. Kegagalan sebanyak itu hampir selalu berarti "
                "sesinya yang rusak — logout, portal bermasalah, atau halaman "
                "berubah — bukan barisnya. Periksa Chrome dulu, baru lanjutkan."
            )
        if self.dihentikan:
            return "Dihentikan atas permintaanmu."
        return ""


# Kegagalan beruntun sebanyak ini menghentikan antrean. Tiga baris gagal
# berturut-turut hampir selalu berarti sesinya yang rusak, bukan tiga baris
# yang kebetulan buruk -- meneruskannya cuma menambah 48 kegagalan yang sama
# sambil menghabiskan waktu setengah menit per baris.
BATAS_GAGAL_BERUNTUN = 3


class RunnerError(RuntimeError):
    """Kegagalan yang sudah dijelaskan dengan bahasa manusia."""


class Dibatalkan(Exception):
    """Operator menekan Berhenti di tengah pengisian.

    Bukan turunan RunnerError: ini bukan kegagalan, dan tidak boleh ikut
    tertangkap oleh penanganan galat biasa yang akan menandai barisnya gagal.
    """


def _teks(nilai) -> str:
    return "" if nilai is None else str(nilai).strip()


def _angka(nilai) -> str:
    """'1.250,50' -> '1250,50'. Form menolak pemisah ribuan."""
    teks = _teks(nilai)
    return teks.replace(".", "") if re.fullmatch(r"[\d.]+,\d+", teks) else teks


class ProductFormFiller:
    """Mengisi satu halaman tambah produk. Dipisah dari koneksi agar bisa diuji."""

    def __init__(self, page, catatan=None, batal=None):
        self.page = page
        self.langkah: list[str] = []
        self.peringatan: list[str] = []
        self._catatan = catatan or (lambda pesan: None)
        # Dipanggil di sela-sela langkah. Playwright versi sinkron tidak bisa
        # diputus dari luar, jadi berhentinya diperiksa di antara langkah --
        # jeda paling lama satu langkah, bukan satu baris penuh.
        self._batal = batal or (lambda: False)

    def periksa_batal(self) -> None:
        if self._batal():
            raise Dibatalkan()

    def _catat(self, pesan: str) -> None:
        self.langkah.append(pesan)
        self._catatan(pesan)
        self.periksa_batal()

    # --- primitif -----------------------------------------------------------

    def _isi(self, selector: str, nilai: str, label: str) -> None:
        if not nilai:
            return
        elemen = self.page.locator(selector).first
        elemen.wait_for(state="visible", timeout=TIMEOUT_PENDEK)

        # Sebagian kolom dikunci portal setelah pilihan lain dibuat -- Nama
        # Produk, misalnya, terisi sendiri begitu Daftar Produk Sektoral
        # dipilih. fill() pada kolom terkunci menunggu sampai batas waktunya
        # habis, tiga puluh detik, lalu menggagalkan seluruh barisnya.
        if not elemen.is_editable():
            ada = ""
            try:
                ada = (elemen.input_value() or "").strip()
            except Exception:  # noqa: BLE001 -- bukan kotak isian biasa
                pass
            if ada and _normalisasi(ada) != _normalisasi(nilai):
                self.peringatan.append(
                    f"{label}: dikunci portal dan sudah berisi '{ada[:50]}', "
                    f"berbeda dari isi Excel ('{nilai[:50]}') — dilewati")
            else:
                self.peringatan.append(f"{label}: dikunci portal, dilewati")
            return

        elemen.fill(nilai)
        self._catat(f"{label}: {nilai[:60]}")

    def _ketik(self, teks: str) -> None:
        """Ketik ke elemen yang sedang fokus, tanpa satu perjalanan per karakter.

        Lewat papan ketik, bukan `fill()` pada elemen tertentu. Kotak react-select
        punya dua input: satu untuk pencarian, satu lagi penampung nilai yang
        dikendalikan React. `fill()` pada penampung menulis nilainya langsung
        tanpa React tahu -- dari luar kolomnya tampak terisi, padahal tidak ada
        yang pernah terpilih, dan yang sampai ke pencarian cuma huruf terakhir.

        `insert_text` mengirim seluruh teks sebagai satu peristiwa input yang
        sungguhan, jadi React memprosesnya seperti ketikan. Karakter terakhir
        tetap ditekan betulan supaya komponen yang menyimak tombol, bukan
        perubahan nilai, ikut terpicu.
        """
        if not teks:
            return
        if len(teks) > 1:
            self.page.keyboard.insert_text(teks[:-1])
        self.page.keyboard.type(teks[-1])

    def _pilih_dropdown(self, pembuka, nilai: str, label: str) -> None:
        """react-select: klik, ketik, lalu pilih opsi yang cocok.

        Yang diklik `pembuka` -- wadah dropdownnya, bukan input di dalamnya.
        Input milik react-select lebarnya nyaris nol dan sering tertutup elemen
        lain, jadi Playwright menolak mengkliknya dan menunggu sampai batas
        waktu habis tanpa menyebut sebabnya.
        """
        if not nilai:
            return
        pembuka.click()
        self._ketik(nilai)

        # Hanya elemen ber-role="option". Portal membungkus tiap opsi dalam
        # empat elemen berkelas *option* -- wrapper, label, dan description ikut
        # terjaring kalau disaring lewat kelas, dan yang terklik bisa jadi span
        # yang tidak memilih apa pun.
        opsi = self.page.locator('[role="option"]:visible')
        try:
            opsi.first.wait_for(state="visible", timeout=TIMEOUT_PENDEK)
        except Exception:
            opsi = self.page.locator(SEL_OPSI_TERLIHAT)
            try:
                opsi.first.wait_for(state="visible", timeout=TIMEOUT_PENDEK)
            except Exception as error:  # noqa: BLE001 -- diterjemahkan jadi pesan
                raise RunnerError(
                    f"{label}: daftar pilihan tidak muncul untuk '{nilai}'"
                ) from error

        # Baris pertama saja: sebagian opsi punya keterangan di baris kedua.
        teks = [t.strip().split("\n")[0] for t in opsi.all_inner_texts()]
        cari = _normalisasi(nilai)
        indeks = next((i for i, x in enumerate(teks) if _normalisasi(x) == cari), None)
        if indeks is None:
            indeks = next(
                (i for i, x in enumerate(teks) if _normalisasi(x).startswith(cari)), None)
        if indeks is None:
            # Dulu opsi pertama yang diklik saat tidak ada yang cocok. Itu diam-
            # diam memilih nilai yang salah -- jauh lebih buruk daripada berhenti,
            # karena hasilnya kelihatan benar sampai produknya tayang.
            contoh = "; ".join(teks[:4]) or "(daftar kosong)"
            raise RunnerError(
                f"{label}: '{nilai}' tidak ada di daftar pilihan portal.\n\n"
                f"Yang ditawarkan portal antara lain: {contoh}\n\n"
                "Samakan tulisannya di Excel dengan salah satu pilihan itu."
            )
        opsi.nth(indeks).click()
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
        self._ketik(tiga)

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

        self._tunggu_form_kategori()
        self._catat(f"Kategori: {jalur}")

    def _tunggu_form_kategori(self) -> None:
        """Tunggu bagian yang baru dirender setelah kategori dipilih.

        Dulu dijeda 1,5 detik pukul rata. Jeda tetap selalu salah di kedua arah:
        dibayar penuh walau formnya sudah siap dalam dua ratus milidetik, dan
        tetap kurang saat portal sedang lambat. Yang ditunggu sekarang tandanya
        -- kolom atribut atau keterangan tipe produk, dua hal yang cuma muncul
        setelah kategorinya terpasang.
        """
        try:
            self.page.locator(
                f'{SEL_ATRIBUT_UTAMA}, :text-matches("termasuk jenis Produk")'
            ).first.wait_for(state="visible", timeout=TIMEOUT_PENDEK)
        except Exception:  # noqa: BLE001 -- kategori tanpa atribut maupun keterangan
            self.page.wait_for_timeout(1_000)

    def baca_tipe_produk(self) -> str:
        """Portal menuliskan 'Kategori ini termasuk jenis Produk Jasa'."""
        petunjuk = self.page.get_by_text(re.compile(r"termasuk jenis Produk"))
        if not petunjuk.count():
            return ""
        cocok = re.search(r"Produk\s+(\w+)", petunjuk.first.inner_text())
        return cocok.group(1) if cocok else ""

    def medan_atribut(self) -> list[dict]:
        """Kolom Informasi Utama: indeks, label, dan bentuknya.

        Dibaca sekali jalan lewat evaluate. Menanyakan tiap elemen satu per satu
        berarti puluhan perjalanan ke browser untuk delapan kolom.

        Tidak semua kolom berupa kotak teks. Sebagian -- Satuan Pengukuran, SBU
        Konstruksi, Sertifikat Standar -- adalah dropdown, dan dropdown tidak
        punya placeholder sama sekali. Labelnya diambil dari teks di sekitarnya
        ("Pilih Satuan Pengukuran"), karena kalau hanya placeholder yang dibaca,
        ketiganya terbaca tanpa nama lalu dilewati diam-diam sebagai "tidak ada
        di form kategori ini".
        """
        mentah = self.page.evaluate(
            """(sel) => [...document.querySelectorAll(sel)].map(el => {
                 let n = el, sekitar = '';
                 for (let i = 0; i < 8 && n; i++, n = n.parentElement) {
                   const t = (n.innerText || '').trim().split('\\n')[0];
                   if (t && t.length < 70) { sekitar = t; break; }
                 }
                 return {
                   name: el.getAttribute('name') || '',
                   ph: el.getAttribute('placeholder') || '',
                   sekitar,
                   dropdown: !!el.closest('[class*="control"], [class*="select"]'),
                 };
               })""",
            SEL_ATRIBUT_UTAMA,
        )
        hasil: list[dict] = []
        for m in mentah:
            cocok = re.search(r"\.(\d+)\.value$", m["name"])
            if not cocok:
                continue
            label = re.sub(r"^(Masukkan|Pilih)\s+", "",
                           (m["ph"] or m["sekitar"]).strip()).strip()
            hasil.append({"indeks": int(cocok.group(1)), "label": label,
                          "dropdown": bool(m["dropdown"])})
        return hasil

    def label_atribut(self) -> list[str]:
        """Label bagian Informasi Utama, berurut sesuai indeks di form."""
        return [m["label"] for m in self.medan_atribut()]

    def isi_atribut(self, atribut: dict[str, str]) -> None:
        """Cocokkan Atribut/Nilai dari Excel dengan field di halaman, lewat namanya."""
        if not atribut:
            return
        tersedia = {_normalisasi(m["label"]): m
                    for m in self.medan_atribut() if m["label"]}
        for nama, nilai in atribut.items():
            medan = tersedia.get(_normalisasi(nama))
            if medan is None:
                self.peringatan.append(
                    f"Atribut '{nama}' tidak ada di form kategori ini, dilewati"
                )
                continue
            selektor = (f'input[name="productInformations.mainInformations.'
                        f'{medan["indeks"]}.value"]')
            if medan["dropdown"]:
                # Dropdown menolak diisi langsung: nilainya dikendalikan React,
                # dan fill() cuma mengubah teks pencariannya tanpa memilih apa
                # pun. Harus diketik lalu dipilih dari daftar yang muncul.
                self._pilih_dropdown_selektor(selektor, nilai, f"Atribut {nama}")
            else:
                self._isi(selektor, nilai, f"Atribut {nama}")

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
        self.periksa_batal()
        assets = assets or Assets()
        foto = assets.foto_untuk(int(data.get("_row") or 0))

        self.pilih_kategori(_teks(data.get("kategori")))
        tipe = self.baca_tipe_produk()
        if tipe:
            self._catat(f"Portal menyebut kategori ini bertipe {tipe}")

        # Wajib di form dan baru muncul setelah kategori dipilih. Sebelumnya
        # tidak pernah diisi sama sekali, jadi setiap produk tertahan di sini.
        self._pilih_dropdown_dekat("Daftar Produk Sektoral",
                                   _teks(data.get("produk_sektoral")))

        self._isi(SEL_NAMA, _teks(data.get("nama_produk")), "Nama Produk")
        self._isi(SEL_DESKRIPSI, _teks(data.get("deskripsi")), "Deskripsi")

        for nomor in range(1, 6):
            berkas = foto[nomor - 1] if nomor <= len(foto) else ""
            self._unggah(SEL_FOTO.format(nomor - 1), _teks(berkas), f"Foto {nomor}")
        self._unggah(SEL_VIDEO, _teks(assets.video), "Video")
        self._isi(SEL_VIDEO_URL, _teks(assets.video_url), "URL Video")

        self._pilih_dropdown_dekat("Kode KBKI", _teks(data.get("kbki")))
        for kunci, label in (
            ("pdn_klasifikasi", "Klasifikasi Produk"),
            ("pdn_lokasi_produksi", "Lokasi Produksi"),
            ("pdn_tenaga_kerja", "Tenaga Kerja dalam Proses Produksi"),
            ("pdn_bahan_baku", "Bahan Baku dalam Proses Produksi"),
        ):
            self._pilih_dropdown_dekat(label, _teks(data.get(kunci)))

        self._pilih_dropdown_selektor(SEL_PPN, _teks(data.get("ppn")), "PPN")

        for kunci, selector in SAKLAR.items():
            nilai = _teks(data.get(kunci))
            if nilai:
                self._saklar(selector, nilai in SAKLAR_NYALA, kunci)

        # Selalu dinyalakan bila kolomnya muncul. Portal hanya memunculkannya
        # pada kategori yang memang membolehkan kuantitas pecahan, jadi
        # kemunculannya sendiri sudah menjadi jawabannya. Dulu disimpulkan dari
        # ada tidaknya desimal pada stok -- tapi stok bulat hari ini bukan
        # jaminan stok bulat selamanya, dan saklar yang mati membuat penyedia
        # tidak bisa memasukkan pecahan sama sekali.
        self._saklar(SEL_KUANTITAS_DESIMAL, True, "Kuantitas Desimal")

        self._isi(SEL_MIN_BELI, _angka(data.get("minimum_pembelian")),
                  "Minimum Pembelian")
        self._isi(SEL_HARGA, _angka(data.get("harga_produk")), "Harga Produk")
        self._isi(SEL_STOK, _angka(data.get("stok")), "Jumlah Stok")
        self._pilih_dropdown_dekat("Satuan Produk", _teks(data.get("satuan_produk")))

        if tipe == TIPE_BARANG:
            self._isi_pengiriman(data)

        atribut = attribute_pairs(data)
        for nama, nilai in list(atribut.items()):
            if not nilai:
                atribut[nama] = assets.nilai_atribut(nama)
        self.isi_atribut({n: v for n, v in atribut.items() if v})
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

    def _selektor_dekat(self, label: str, dropdown: bool) -> str:
        """Selektor kotak isian milik label tertentu, atau string kosong.

        Menggantikan `div:has-text("label")` yang dipakai sebelumnya. Selektor
        itu cocok dengan setiap div yang memuat teksnya -- termasuk pembungkus
        seluruh halaman -- lalu `.last` memilih yang paling dalam, yang belum
        tentu kotak yang dimaksud. Di portal sungguhan itu berujung klik yang
        kehabisan waktu tiga puluh detik tanpa menyebut sebabnya.

        Sekarang labelnya yang dicari lebih dulu, lalu naik paling banyak
        delapan tingkat sampai ketemu kotak isian di dalam kelompok yang sama.
        Kotak kategori utama sengaja ditolak: sebagian label tidak punya kotak
        sendiri, dan tanpa penolakan ini pencariannya menyeberang ke sana.
        """
        return self.page.evaluate(_CARI_KOTAK, {"teks": label, "dropdown": dropdown})

    def _pilih_dropdown_selektor(self, selektor: str, nilai: str, label: str) -> None:
        """Pilih dropdown yang selektor inputnya sudah diketahui.

        Wadahnya dicari dulu: yang bisa diklik adalah wadah react-select, bukan
        input di dalamnya. Berlaku untuk PPN dan atribut kategori, yang sama-sama
        punya selektor tetap.
        """
        if not nilai:
            return
        wadah = self.page.evaluate(_WADAH_DROPDOWN, selektor) or selektor
        self._pilih_dropdown(self.page.locator(wadah).first, nilai, label)

    def _pilih_dropdown_dekat(self, label: str, nilai: str) -> None:
        """Cari dropdown lewat labelnya, lalu pilih nilainya."""
        if not nilai:
            return
        kotak = self._selektor_dekat(label, dropdown=True)
        if not kotak:
            self.peringatan.append(f"{label}: kolomnya tidak ketemu di form, dilewati")
            return
        self._pilih_dropdown(self.page.locator(kotak["klik"]).first, nilai, label)

    def _input_dekat(self, label: str):
        kotak = self._selektor_dekat(label, dropdown=False)
        return self.page.locator(kotak["ketik"]).first if kotak else None

    # --- penyimpanan --------------------------------------------------------

    def simpan(self, mode: Mode) -> str:
        # Dibakukan dulu. Mode datang dari combobox Qt, yang mengembalikan
        # 'isi_saja' sebagai str biasa -- bukan anggota Mode. Dengan `is`,
        # perbandingannya diam-diam salah dan mode "Isi saja" justru menekan
        # tombol Simpan.
        mode = Mode(mode)
        # Diperiksa sebelum tombolnya disentuh: berhenti yang datang sedetik
        # sebelum klik tidak boleh berujung produk yang tetap tersimpan.
        self.periksa_batal()
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
        # Tandanya alamat halaman berpindah ke /products/<id>. Ditunggu sampai
        # itu terjadi, bukan dihitung tiga detik pukul rata -- form yang ditolak
        # portal memang tidak pernah berpindah, jadi jeda tetap itu selalu
        # terlalu lama saat berhasil dan belum tentu cukup saat portal lambat.
        try:
            self.page.wait_for_url(POLA_PRODUK, timeout=TIMEOUT_SIMPAN)
        except Exception:  # noqa: BLE001 -- draf tidak selalu berpindah halaman
            self.page.wait_for_timeout(1_000)
        self._catat(f"Diklik: {nama}")

        cocok = POLA_PRODUK.search(self.page.url)
        return cocok.group(0).rsplit("/", 1)[1] if cocok else ""


def _normalisasi(teks: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(teks or "").lower()).strip()


def penghalang(page) -> str:
    """Isi modal yang sedang menutupi halaman, atau string kosong.

    Dibaca sebelum menyentuh apa pun. Tanpa ini, satu modal membuat tiap klik
    menunggu sampai batas waktunya habis -- setengah menit per baris, tiga baris
    berturut-turut, lalu antrean berhenti dengan pesan yang cuma menyebut
    "Timeout" dan tidak menjelaskan apa-apa.
    """
    try:
        dialog = page.locator(SEL_MODAL)
        if not dialog.count():
            return ""
        return " ".join(dialog.first.inner_text().split())
    except Exception:  # noqa: BLE001 -- pemeriksaan bantu, tidak boleh menggagalkan
        return ""


def pesan_penghalang(teks: str) -> str:
    """Terjemahkan isi modal jadi petunjuk yang bisa ditindaklanjuti."""
    if re.search(r"telah keluar|masuk kembali", teks, re.I):
        return (
            "Sesi portalmu sudah berakhir, dan portal menutupi halaman dengan "
            "kotak 'Akun Telah Keluar'. Selama kotak itu ada, tidak ada tombol "
            "yang bisa diklik dan tidak ada kolom yang bisa diketik — halaman "
            "terlihat normal tapi diam saja.\n\n"
            "Login ulang di jendela Chrome yang dibuka aplikasi, lalu jalankan "
            "lagi. Ini muncul bila akun yang sama dipakai masuk dari browser "
            "lain; portal hanya mengizinkan satu sesi."
        )
    return (
        "Portal menampilkan kotak yang menutupi seluruh halaman, jadi tidak ada "
        f"yang bisa diklik:\n\n  {teks[:200]}\n\n"
        "Selesaikan dulu di jendela Chrome, lalu jalankan lagi."
    )


class BrowserRunner:
    """Menempel ke Chrome yang sudah login, lalu mengisi baris satu per satu."""

    def __init__(self, cdp_url: str = CDP_DEFAULT):
        self.cdp_url = cdp_url
        self._playwright = None
        self._browser = None
        self._konteks = None
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

        self._konteks = konteks
        # Menyambung tidak membuka tab apa pun. Tab baru cuma dibuat kalau
        # memang ada yang mau diisi -- lihat siapkan_halaman().
        self.page = self._halaman_terpakai()
        return self

    def _halaman_terpakai(self):
        """Tab yang boleh dipakai aplikasi, atau None kalau belum ada.

        Tab portal lebih dulu. Kalau belum ada, tab kosong pun boleh dipakai
        ulang -- itu yang mencegah tab menumpuk: tab yang baru dibuka berisi
        about:blank, jadi tanpa aturan ini pemanggilan berikutnya tidak
        mengenalinya dan membuat satu lagi, terus-menerus.

        Tab lain tidak pernah disentuh. Dengan profil Chrome harian, tab
        pertama bisa saja email atau pekerjaan lain, dan langkah berikutnya
        memuat halaman tambah produk di atasnya.
        """
        if self._konteks is None:
            return None
        kosong = None
        for halaman in self._konteks.pages:
            try:
                alamat = halaman.url
            except Exception:  # noqa: BLE001 -- tab sedang ditutup
                continue
            if "penyedia.inaproc.id" in alamat:
                return halaman
            if kosong is None and alamat in ("", "about:blank", "chrome://newtab/"):
                kosong = halaman
        return kosong

    def siapkan_halaman(self):
        """Pastikan ada tab siap pakai, membuatnya hanya bila benar-benar perlu."""
        if self.page is None or self.page.is_closed():
            self.page = self._halaman_terpakai() or self._konteks.new_page()
        return self.page

    def siap(self) -> bool:
        if self.page is not None:
            return not self.page.is_closed()
        return self._konteks is not None

    def buka_form(self) -> None:
        self.siapkan_halaman()
        if not self.page.url.startswith(URL_TAMBAH):
            self.page.goto(URL_TAMBAH, wait_until="domcontentloaded",
                           timeout=TIMEOUT_PANJANG)
        else:
            self.page.reload(wait_until="domcontentloaded", timeout=TIMEOUT_PANJANG)
        self.page.locator(SEL_KATEGORI).first.wait_for(
            state="visible", timeout=TIMEOUT_PANJANG
        )
        # Kotak kategori bisa terlihat sekaligus tak tersentuh: modal portal
        # menutupinya dari atas. Diperiksa di sini, sebelum satu klik pun
        # dicoba, karena setelah itu galatnya cuma "Timeout".
        halangan = self.penghalang()
        if halangan:
            raise RunnerError(pesan_penghalang(halangan))

    def penghalang(self) -> str:
        return penghalang(self.page) if self.page else ""

    def kecepatan(self) -> tuple[int, float]:
        """Kecepatan perender Chrome, diukur di tab yang sedang dipakai.

        Dipanggil sekali per antrean. Ongkosnya sekitar satu setengah detik,
        jauh lebih murah daripada mengisi berpuluh baris di Chrome yang sedang
        melambat sembilan kali lipat tanpa ada yang tahu sebabnya.
        """
        halaman = self.siapkan_halaman()
        hasil = halaman.evaluate(_UKUR_PERENDER)
        frame = sorted(x for x in hasil["frame"][2:] if x < 3000)
        tengah = frame[len(frame) // 2] if frame else float("nan")
        return hasil["js"], tengah

    def jalankan(self, data: dict, mode: Mode = Mode.ISI_SAJA, catatan=None,
                 assets: Assets | None = None, batal=None) -> Hasil:
        mode = Mode(mode)
        if not self.siap():
            return Hasil(False, "Browser belum tersambung")

        pengisi = ProductFormFiller(self.page, catatan, batal)
        try:
            pengisi.periksa_batal()
            self.buka_form()
            pengisi.isi(data, assets)
            produk_id = pengisi.simpan(mode)
        except Dibatalkan:
            # Bukan gagal: form tertinggal separuh terisi, tapi tidak ada apa
            # pun yang masuk ke portal, dan baris berikutnya memuat ulang
            # halaman ini dari awal.
            return Hasil(False, "dihentikan sebelum selesai", dibatalkan=True,
                         langkah=pengisi.langkah, peringatan=pengisi.peringatan)
        except RunnerError as error:
            return Hasil(False, str(error), langkah=pengisi.langkah,
                         peringatan=pengisi.peringatan)
        except Exception as error:  # noqa: BLE001 -- apa pun dari browser
            # Sesi bisa berakhir di tengah pengisian. Yang terlihat cuma klik
            # yang kehabisan waktu, padahal sebabnya modal yang baru muncul --
            # jadi diperiksa dulu sebelum galatnya dilaporkan apa adanya.
            halangan = self.penghalang()
            pesan = (pesan_penghalang(halangan) if halangan
                     else f"{type(error).__name__}: {error}".split("\n")[0])
            return Hasil(False, pesan, langkah=pengisi.langkah,
                         peringatan=pengisi.peringatan)

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
        self._browser = self._playwright = self._konteks = None
        self.page = None


__all__ = [
    "BATAS_GAGAL_BERUNTUN",
    "SEL_MODAL",
    "BrowserRunner",
    "CDP_DEFAULT",
    "Dibatalkan",
    "Hasil",
    "Mode",
    "ProductFormFiller",
    "Ringkasan",
    "RunnerError",
    "URL_TAMBAH",
    "penghalang",
    "pesan_penghalang",
]
