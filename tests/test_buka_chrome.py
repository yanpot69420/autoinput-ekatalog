"""Uji pembuka Chrome yang berdiri sendiri, di luar jendela aplikasi."""

from __future__ import annotations

from inaproc_autoinput import buka_chrome, chrome


def test_lapor_siap_bila_port_sudah_hidup(monkeypatch, capsys):
    """Chrome yang sudah terbuka tidak perlu disentuh sama sekali."""
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "Chrome/151")

    def jangan_dipanggil(*a, **k):  # pragma: no cover
        raise AssertionError("Chrome sudah terbuka, tidak boleh dijalankan lagi")

    monkeypatch.setattr(chrome, "launch", jangan_dipanggil)

    assert buka_chrome.main([]) == 0
    keluaran = capsys.readouterr().out
    assert "sudah terbuka" in keluaran
    assert "Uji koneksi browser" in keluaran


def test_membuka_bila_port_mati(monkeypatch, capsys):
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "")
    monkeypatch.setattr(chrome, "launch", lambda **k: (True, "Chrome dibuka."))
    assert buka_chrome.main([]) == 0
    assert "Chrome dibuka." in capsys.readouterr().out


def test_kode_keluar_satu_saat_gagal(monkeypatch, capsys):
    """Pembungkus pintasan memakai kode keluar untuk memunculkan peringatan."""
    monkeypatch.setattr(chrome, "is_listening", lambda *a, **k: "")
    monkeypatch.setattr(chrome, "launch",
                        lambda **k: (False, "Chrome harus ditutup dulu"))
    assert buka_chrome.main([]) == 1
    assert "ditutup dulu" in capsys.readouterr().out


def test_port_bisa_diganti(monkeypatch):
    dipakai = {}
    monkeypatch.setattr(chrome, "is_listening",
                        lambda port=0, **k: dipakai.setdefault("periksa", port) and "")
    monkeypatch.setattr(chrome, "launch",
                        lambda port=0, **k: (dipakai.update(buka=port), (True, ""))[1])
    buka_chrome.main(["--port=9444"])
    assert dipakai["periksa"] == 9444
    assert dipakai["buka"] == 9444


def test_port_tidak_sah_ditolak(monkeypatch, capsys):
    monkeypatch.setattr(chrome, "launch",
                        lambda **k: (_ for _ in ()).throw(AssertionError("jangan")))
    assert buka_chrome.main(["--port=abc"]) == 1
    assert "tidak sah" in capsys.readouterr().out
