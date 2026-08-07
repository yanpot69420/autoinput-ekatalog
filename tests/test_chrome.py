"""Uji pembuka Chrome berport debug."""

from __future__ import annotations

from pathlib import Path

import pytest

from inaproc_autoinput import chrome


@pytest.fixture(autouse=True)
def pilihan_terisolasi(tmp_path, monkeypatch):
    """Jangan pernah membaca pilihan profil nyata milik pengguna.

    command() dan profil() mengikut berkas pilihan di home. Dibiarkan begitu,
    hasil uji berubah mengikuti apa yang kebetulan dipilih di aplikasi -- dan
    uji yang lolos di satu mesin gagal di mesin lain tanpa ada kode yang
    berubah. Sempat terjadi persis begitu.
    """
    monkeypatch.setattr(chrome, "PILIHAN_PATH", tmp_path / "pilihan.json")


def _chrome_palsu(monkeypatch) -> dict:
    """Chrome tiruan: port mati sebelum dijalankan, hidup begitu prosesnya jalan.

    launch() menunggu port debugnya benar-benar menjawab sebelum melapor
    berhasil. Tiruan yang portnya mati selamanya bukan tiruan Chrome yang
    berhasil -- itu tiruan Chrome yang gagal, dan ujinya jadi menguji hal lain.
    """
    catat: dict = {}

    def popen(argumen, **kw):
        catat["argumen"] = argumen
        catat["kw"] = kw
        catat["hidup"] = True
        return None

    monkeypatch.setattr(
        chrome, "is_listening",
        lambda *a, **k: "Chrome/151" if catat.get("hidup") else "")
    monkeypatch.setattr(chrome, "find_chrome", lambda: Path("/bin/echo"))
    monkeypatch.setattr(chrome.subprocess, "Popen", popen)
    return catat


def test_perintah_memuat_port_dan_profil_terpisah():
    argumen = chrome.command()
    assert f"--remote-debugging-port={chrome.PORT_DEFAULT}" in argumen
    assert f"--user-data-dir={chrome.PROFIL}" in argumen
    # Profil terpisah supaya Chrome sehari-hari tidak perlu ditutup.
    assert chrome.PROFIL != Path.home() / "Library/Application Support/Google/Chrome"


def test_perintah_teks_memberi_tanda_kutip_pada_spasi():
    teks = chrome.command_text()
    assert "--remote-debugging-port=9222" in teks
    for bagian in teks.split(" --"):
        if bagian.startswith('"') or " " not in bagian:
            continue
        assert bagian.startswith('"') or "=" in bagian


def test_port_bisa_diganti():
    assert "--remote-debugging-port=9333" in chrome.command(port=9333)


def test_launch_selalu_membuka_alamat(monkeypatch, tmp_path):
    """Chrome tanpa alamat tidak punya target yang bisa dikendalikan.

    Halaman tab baru tidak muncul di /json/list, jadi port debug hidup tapi
    kosong -- dan galatnya menyesatkan. Karena itu URL tidak boleh dilewatkan.
    """
    dijalankan = _chrome_palsu(monkeypatch)

    # Profil sendiri: profil nyata di home bisa sedang terkunci Chrome yang
    # betulan berjalan, dan uji ini tidak sedang menguji itu.
    berhasil, _ = chrome.launch(dir_profil=tmp_path)
    assert berhasil
    assert dijalankan["argumen"][-1] == chrome.URL_AWAL

    chrome.launch(url="", dir_profil=tmp_path)  # url kosong tetap diberi bawaan
    assert dijalankan["argumen"][-1] == chrome.URL_AWAL


def test_launch_tidak_membuka_jendela_kedua(monkeypatch):
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "Chrome/150")

    def jangan_dipanggil(*a, **k):  # pragma: no cover
        raise AssertionError("seharusnya tidak menjalankan Chrome lagi")

    monkeypatch.setattr(chrome.subprocess, "Popen", jangan_dipanggil)
    berhasil, pesan = chrome.launch()
    assert berhasil and "sudah terbuka" in pesan


def test_launch_gagal_bila_port_tak_pernah_hidup(monkeypatch, tmp_path):
    """Prosesnya jalan bukan berarti port debugnya hidup.

    Chrome yang menemukan profilnya sudah dipakai jendela lain cuma menyerahkan
    alamatnya lalu keluar -- tanpa galat, tanpa port. Dulu itu dilaporkan
    "Chrome dibuka", padahal yang terbuka justru tab di Chrome harian yang sama
    sekali tidak bisa dikendalikan aplikasi.
    """
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "")
    monkeypatch.setattr(chrome, "find_chrome", lambda: Path("/bin/echo"))
    monkeypatch.setattr(chrome.subprocess, "Popen", lambda *a, **k: None)

    berhasil, pesan = chrome.launch(dir_profil=tmp_path, tunggu_siap=0.5)
    assert not berhasil
    assert "tidak pernah hidup" in pesan
    assert "Profil terpisah" in pesan


def test_launch_melapor_bila_chrome_tidak_ada(monkeypatch):
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "")
    monkeypatch.setattr(chrome, "find_chrome", lambda: None)
    berhasil, pesan = chrome.launch()
    assert not berhasil
    assert "--remote-debugging-port" in pesan  # tetap beri perintah manualnya


def test_is_listening_saat_port_mati():
    assert chrome.is_listening(port=59999, timeout=0.4) == ""


def test_proses_chrome_dilepas_sesuai_sistem(monkeypatch, tmp_path):
    """Chrome tidak boleh ikut mati saat jendela aplikasi ditutup.

    Caranya berbeda per sistem, dan bedanya diam-diam: `start_new_session`
    hanya berlaku di POSIX, Windows mengabaikannya tanpa galat. Kalau tidak
    diperiksa, Chrome di Windows akan tertutup bersama aplikasinya.
    """
    for platform, kunci in (("darwin", "start_new_session"),
                            ("linux", "start_new_session"),
                            ("win32", "creationflags")):
        monkeypatch.setattr(chrome.sys, "platform", platform)
        dijalankan = _chrome_palsu(monkeypatch)

        berhasil, _ = chrome.launch(dir_profil=tmp_path)
        assert berhasil, platform
        assert kunci in dijalankan["kw"], f"{platform} tidak memakai {kunci}"

    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    assert dijalankan["kw"]["creationflags"] == 0x8 | 0x200


# --- menutup dan menjalankan ulang ------------------------------------------


def test_tutup_saat_chrome_memang_mati(monkeypatch):
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "")
    berhasil, pesan = chrome.tutup()
    assert berhasil and "tidak berjalan" in pesan


def test_tutup_menyerah_bila_port_tak_kunjung_mati(monkeypatch):
    """Lebih baik menyuruh menutup sendiri daripada mengaku berhasil.

    Portnya sengaja yang kosong: is_listening dipalsukan supaya port terlihat
    hidup terus, tapi perintah tutupnya tetap benar-benar dikirim -- diarahkan
    ke 9222 uji ini akan menutup Chrome yang sedang dipakai uji lain.
    """
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "Chrome/1")
    berhasil, pesan = chrome.tutup(port=59998, tunggu=0.5)
    assert not berhasil and "Tutup jendelanya sendiri" in pesan


def test_mulai_ulang_tidak_membuka_bila_gagal_menutup(monkeypatch):
    """Chrome lama masih hidup; membuka lagi cuma menambah jendela sia-sia."""
    dibuka = []
    monkeypatch.setattr(chrome, "tutup", lambda *a, **k: (False, "belum menutup"))
    monkeypatch.setattr(chrome, "launch", lambda *a, **k: dibuka.append(1) or (True, ""))
    berhasil, pesan = chrome.mulai_ulang()
    assert not berhasil and pesan == "belum menutup"
    assert dibuka == []


def test_mulai_ulang_menutup_lalu_membuka(monkeypatch):
    urutan = []
    monkeypatch.setattr(chrome, "tutup",
                        lambda *a, **k: urutan.append("tutup") or (True, ""))
    monkeypatch.setattr(chrome, "launch",
                        lambda *a, **k: urutan.append("buka") or (True, ""))
    berhasil, pesan = chrome.mulai_ulang()
    assert berhasil and urutan == ["tutup", "buka"]
    assert "Sesi loginmu tetap ada" in pesan


# --- pilihan profil ---------------------------------------------------------


def test_profil_terpisah_jadi_bawaan(tmp_path):
    assert not chrome.pakai_harian(tmp_path / "belum-ada.json")
    assert chrome.profil(harian=False) == chrome.PROFIL_APLIKASI
    assert chrome.profil(harian=True) == chrome.PROFIL_HARIAN


def test_pilihan_profil_tersimpan(tmp_path):
    berkas = tmp_path / "chrome.json"
    chrome.set_pakai_harian(True, berkas)
    assert chrome.pakai_harian(berkas)
    chrome.set_pakai_harian(False, berkas)
    assert not chrome.pakai_harian(berkas)


def test_pilihan_rusak_kembali_ke_profil_terpisah(tmp_path):
    """Berkas cacat tidak boleh diam-diam memakai profil pribadi penyedia."""
    berkas = tmp_path / "chrome.json"
    berkas.write_text("{ bukan json", encoding="utf-8")
    assert not chrome.pakai_harian(berkas)


def test_symlink_kunci_yang_menggantung_tetap_terbaca_berjalan(tmp_path):
    """SingletonLock menunjuk 'namahost-pid' yang memang tidak pernah ada.

    Path.exists() mengikuti symlink itu, tidak menemukan apa-apa, lalu menjawab
    'tidak berjalan' untuk Chrome yang jelas sedang berjalan -- dan Chrome baru
    pun diluncurkan tanpa port debug yang pernah hidup.
    """
    (tmp_path / "SingletonLock").symlink_to("komputer-12345")
    assert not (tmp_path / "SingletonLock").exists()   # menggantung, memang
    assert chrome.sedang_berjalan(tmp_path)


def test_profil_kosong_terbaca_tidak_berjalan(tmp_path):
    assert not chrome.sedang_berjalan(tmp_path)


def test_launch_menolak_bila_profilnya_sedang_dipakai(tmp_path):
    """Chrome baru cuma menyerahkan alamat ke jendela lama lalu keluar."""
    (tmp_path / "SingletonLock").symlink_to("komputer-12345")
    berhasil, pesan = chrome.launch(port=59996, dir_profil=tmp_path)
    assert not berhasil
    assert "ditutup dulu sepenuhnya" in pesan
    assert str(tmp_path) in pesan


def test_perintah_memakai_profil_yang_diminta(tmp_path):
    argumen = chrome.command(dir_profil=tmp_path)
    assert f"--user-data-dir={tmp_path}" in argumen


def test_perintah_mengikuti_pilihan_yang_tersimpan(tmp_path):
    """Tanpa dir_profil, yang dipakai adalah pilihan di aplikasi."""
    chrome.set_pakai_harian(True, chrome.PILIHAN_PATH)
    assert f"--user-data-dir={chrome.PROFIL_HARIAN}" in chrome.command()

    chrome.set_pakai_harian(False, chrome.PILIHAN_PATH)
    assert f"--user-data-dir={chrome.PROFIL_APLIKASI}" in chrome.command()
