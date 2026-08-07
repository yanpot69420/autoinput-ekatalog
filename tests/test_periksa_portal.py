"""Uji ambang pembeda: Chrome yang melambat vs portal yang berat."""

from __future__ import annotations

from inaproc_autoinput import periksa_portal as pp


_chrome_lambat = pp.chrome_melambat


def test_chrome_sehat_tidak_dikeluhkan():
    """Angka nyata saat sehat: 8,16 juta kops, 8,3 ms per frame."""
    assert not _chrome_lambat(8_157_491, 8.3)


def test_perender_tersangkut_terdeteksi():
    """Angka nyata saat ada perender yatim berputar: 3,77 juta kops, 16,7 ms.

    Keduanya sendirian sudah cukup untuk menandai, karena keduanya muncul
    bersama pada kejadian yang sama.
    """
    assert _chrome_lambat(3_767_245, 16.7)
    assert _chrome_lambat(3_767_245, 8.3)
    assert _chrome_lambat(8_157_491, 16.7)


def test_ambang_tidak_terlalu_ketat():
    """Mesin sibuk wajar tidak boleh dikira Chrome rusak.

    Turun seperempat masih normal; yang ditandai penurunan dua kali lipat ke
    atas, seperti yang benar-benar terukur.
    """
    assert not _chrome_lambat(int(pp.SEHAT_JS * 0.75), 11.0)


def test_ambang_diturunkan_dari_angka_sehat():
    assert pp.AMBANG_JS < pp.SEHAT_JS
    assert pp.AMBANG_FRAME > pp.SEHAT_FRAME
