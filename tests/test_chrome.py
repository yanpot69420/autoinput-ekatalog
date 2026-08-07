"""Uji pembuka Chrome berport debug."""

from __future__ import annotations

from pathlib import Path

from inaproc_autoinput import chrome


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


def test_launch_selalu_membuka_alamat(monkeypatch):
    """Chrome tanpa alamat tidak punya target yang bisa dikendalikan.

    Halaman tab baru tidak muncul di /json/list, jadi port debug hidup tapi
    kosong -- dan galatnya menyesatkan. Karena itu URL tidak boleh dilewatkan.
    """
    dijalankan = {}

    def palsu(argumen, **_):
        dijalankan["argumen"] = argumen
        return None

    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "")
    monkeypatch.setattr(chrome, "find_chrome", lambda: Path("/bin/echo"))
    monkeypatch.setattr(chrome.subprocess, "Popen", palsu)

    berhasil, _ = chrome.launch()
    assert berhasil
    assert dijalankan["argumen"][-1] == chrome.URL_AWAL

    chrome.launch(url="")  # url kosong pun tetap diberi alamat bawaan
    assert dijalankan["argumen"][-1] == chrome.URL_AWAL


def test_launch_tidak_membuka_jendela_kedua(monkeypatch):
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "Chrome/150")

    def jangan_dipanggil(*a, **k):  # pragma: no cover
        raise AssertionError("seharusnya tidak menjalankan Chrome lagi")

    monkeypatch.setattr(chrome.subprocess, "Popen", jangan_dipanggil)
    berhasil, pesan = chrome.launch()
    assert berhasil and "sudah terbuka" in pesan


def test_launch_melapor_bila_chrome_tidak_ada(monkeypatch):
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "")
    monkeypatch.setattr(chrome, "find_chrome", lambda: None)
    berhasil, pesan = chrome.launch()
    assert not berhasil
    assert "--remote-debugging-port" in pesan  # tetap beri perintah manualnya


def test_is_listening_saat_port_mati():
    assert chrome.is_listening(port=59999, timeout=0.4) == ""


def test_proses_chrome_dilepas_sesuai_sistem(monkeypatch):
    """Chrome tidak boleh ikut mati saat jendela aplikasi ditutup.

    Caranya berbeda per sistem, dan bedanya diam-diam: `start_new_session`
    hanya berlaku di POSIX, Windows mengabaikannya tanpa galat. Kalau tidak
    diperiksa, Chrome di Windows akan tertutup bersama aplikasinya.
    """
    for platform, kunci in (("darwin", "start_new_session"),
                            ("linux", "start_new_session"),
                            ("win32", "creationflags")):
        dipakai = {}

        def palsu(argumen, **kw):
            dipakai.update(kw)
            return None

        monkeypatch.setattr(chrome.sys, "platform", platform)
        monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "")
        monkeypatch.setattr(chrome, "find_chrome", lambda: Path("/bin/echo"))
        monkeypatch.setattr(chrome.subprocess, "Popen", palsu)

        berhasil, _ = chrome.launch()
        assert berhasil, platform
        assert kunci in dipakai, f"{platform} tidak memakai {kunci}"

    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    assert dipakai["creationflags"] == 0x8 | 0x200


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
