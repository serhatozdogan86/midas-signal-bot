"""Evren kaymasi denetcisi + arastirma evreninin canliyla hizasi (24 Agu).

Kaynak vaka: F6 backtest'inin ILK kosumunda iki uyari cikti -
"BRK.B verisi yok" (bicim; uretim bunu 30 Tem'de cozmustu, arastirma
katmani kendi yolunu yazdigi icin geri getirdi) ve "SQ verisi yok"
(gercekten bayat: Block Inc. sembolu XYZ oldu). Ikisi de arastirma
evreninin canli evrenden sessizce ayrismasi sinifindan.
"""
from __future__ import annotations

import json

import pytest

from research import data as rdata
from tools.universe_drift import drift, read_live, read_static


def test_drift_iki_yonu_de_ayirir():
    d = drift(["AAPL", "SQ", "MSFT"], ["AAPL", "XYZ", "MSFT"])
    assert d["ortak"] == 2
    assert d["yalniz_statik"] == ["SQ"]        # yedekte bayat kalan
    assert d["yalniz_canli"] == ["XYZ"]        # yedegin kacirdigi


def test_onbellek_yoksa_bos_liste_degil_none(tmp_path):
    """'Onbellek yok' ile 'evren bos' ayni sey degildir (2.2 refleksi):
    yok ise None doner, bos liste DEGIL - yoksa denetci 'tum evren
    kaybolmus' diye yanlis alarm verirdi."""
    assert read_live(tmp_path / "olmayan.json") is None
    (tmp_path / "bos.json").write_text("{}")
    assert read_live(tmp_path / "bos.json") == []


def test_statik_liste_yorumlari_atlar(tmp_path):
    p = tmp_path / "u.txt"
    p.write_text("# yorum\nAAPL\n\n  msft  \n", encoding="utf-8")
    assert read_static(p) == ["AAPL", "MSFT"]


def test_depodaki_statik_listede_bayat_sembol_yok():
    """Somut regresyon: SQ duzeltildi, XYZ var. Bu test, listeyi bir
    daha guncellerken eski sembolun geri gelmesini yakalar."""
    syms = read_static()
    assert "XYZ" in syms
    assert "SQ" not in syms


def test_arastirma_sembolu_yahoo_bicimine_cevrilir():
    """BRK.B tuzagi: uretim kuralini yeniden kullaniyor muyuz?
    (Kendi kopyamizi yazsaydik 30 Tem'de cozulen hata geri gelirdi -
    zaten 24 Agu'da tam olarak bu oldu.)"""
    harita = rdata.to_yahoo(["AAPL", "BRK.B", "HEI.A"])
    assert harita["BRK-B"] == "BRK.B"          # yahoo bicimi -> depo bicimi
    assert harita["HEI-A"] == "HEI.A"
    assert harita["AAPL"] == "AAPL"


def test_arastirma_evreni_once_canli_onbellegi_okur(tmp_path, monkeypatch):
    """Arastirma, statik yedek yerine botun kendi kazidigi listeyi
    kullanmali - yoksa hukum baska bir evrene ait olur."""
    cache = tmp_path / "universe_cache.json"
    cache.write_text(json.dumps({"symbols": ["AAPL", "XYZ"]}))
    monkeypatch.setattr(rdata, "CACHE_JSON", cache)
    syms, kaynak = rdata.universe()
    assert set(syms) == {"AAPL", "XYZ", "SPY"}  # SPY kiyas tabani, eklenir
    assert "canli evren" in kaynak


def test_onbellek_yoksa_statige_duser(tmp_path, monkeypatch):
    monkeypatch.setattr(rdata, "CACHE_JSON", tmp_path / "yok.json")
    syms, kaynak = rdata.universe()
    assert kaynak == "statik yedek liste"
    assert "AAPL" in syms and "SPY" in syms


@pytest.mark.parametrize("bozuk", ["{ bu json degil", '{"symbols": []}'])
def test_bozuk_veya_bos_onbellek_statige_duser(tmp_path, monkeypatch, bozuk):
    """Bozuk JSON ya da bos liste sessizce 'evren bos'a donusmez."""
    c = tmp_path / "c.json"
    c.write_text(bozuk)
    monkeypatch.setattr(rdata, "CACHE_JSON", c)
    syms, kaynak = rdata.universe()
    assert kaynak == "statik yedek liste"
    assert len(syms) > 50
