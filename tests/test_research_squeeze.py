"""S6 Squeeze sinyal kuralinin davranis testleri (hipotez 9, F6).

Neden test var: research/ uretim kodu degil, ama SINYAL TANIMI bir
karar girdisi - "kirilimi yanlis yerde gorursek" backtest hukmu
yanlis cikar ve o hukum KILIT-3 roster'ina girer. Burada olculen
sey backtest SONUCU degil, tanimin sozlesmesi:
  1) >=6 barlik sikisma + araligin uzerinde kapanis -> tetik
  2) sikisma kisa ise (5 bar) tetik YOK
  3) ayni sikismadan yalnizca ILK kirilim (spam yok)
  4) look-ahead yok: i barinin sinyali i+1..sonu degistiginde degismez

Veri cekilmez (bulut oturumunun agi Yahoo'ya kapali); seriler sentetik.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.strategies import squeeze_breakout


def _bars(closes, spread=0.2):
    """close dizisinden gunluk mum tablosu (high/low = close +- spread)."""
    idx = pd.bdate_range("2024-01-01", periods=len(closes))
    c = pd.Series(np.asarray(closes, dtype=float), index=idx)
    return pd.DataFrame({"open": c.shift(1).fillna(c.iloc[0]),
                         "high": c + spread, "low": c - spread,
                         "close": c, "volume": 1_000_000.0}, index=idx)


def _quiet_then_break(n_quiet=40, quiet_amp=0.05, jump=6.0, tail=5):
    """Once genis oynaklik (bantlar acik), sonra n_quiet bar sessizlik
    (BB, KC'nin icine girer = sikisma), sonra yukari kirilim."""
    rng = np.random.default_rng(7)
    loud = 100 + np.cumsum(rng.normal(0, 2.0, 60))       # bantlari acar
    quiet = loud[-1] + rng.normal(0, quiet_amp, n_quiet)  # sikisma
    after = [quiet[-1] + jump] + [quiet[-1] + jump] * (tail - 1)
    return np.concatenate([loud, quiet, after])


def test_sikisma_sonrasi_kirilim_tetikler():
    bars = _bars(_quiet_then_break())
    sig = squeeze_breakout(bars, "LONG")
    assert sig.any(), "sikisma + kirilim sinyal uretmeliydi"
    # tetik, sicramanin ILK barinda olmali (sessizligin bittigi yer)
    first = int(np.argmax(sig.values))
    assert first == 100, f"tetik yanlis barda: {first}"


def test_sure_esigi_gercekten_baglayici():
    """min_bars bir SUS DEGIL: ayni seride esigi sikismanin uzunlugunun
    ustune cikarinca tetik KAYBOLUR. (Sentetik seride 5 barlik gercek
    bir sikisma uretmek mumkun degil - BB penceresi 20 bar - o yuzden
    esik yukaridan zorlanir; olculen sey ayni sozlesme.)"""
    bars = _bars(_quiet_then_break(n_quiet=40))
    assert squeeze_breakout(bars, "LONG", min_bars=6).any()
    assert not squeeze_breakout(bars, "LONG", min_bars=41).any()


def test_ayni_sikismadan_tek_sinyal():
    """SPAM KORUMASI - ve bu testin kirilabildigi OLCULDU.

    Kritik ayrinti: buyuk bir sicrayis sikismayi da bitirir, o yuzden
    "tekrar" riski ancak fiyat KUCUK adimlarla yukselirken (sikisma
    devam ederken) dogar. Seri bilerek oyle kuruldu: 0.5'lik merdiven
    basamaklari, mum genisligi 0.2 - yani her basamak bir onceki
    araligin ustunde kapaniyor ama bantlar hala KC icinde.
    Olcum: 'fired' korumasi kaldirilinca bu seri 1 yerine 3 sinyal
    uretiyor (dogrulandi 24 Agu). Duz sicrayisli seride fark cikmaz -
    o yuzden bu seri secildi."""
    rng = np.random.default_rng(7)
    loud = 100 + np.cumsum(rng.normal(0, 2.0, 60))
    quiet = loud[-1] + rng.normal(0, 0.05, 40)
    steps = [quiet[-1] + 0.5 * k for k in range(1, 6)]
    bars = _bars(np.concatenate([loud, quiet, steps]))
    sig = squeeze_breakout(bars, "LONG")
    assert sig.sum() == 1, f"tekrar sinyal uretildi: {sig.sum()}"


def test_look_ahead_yok():
    """i barinin sinyali GELECEGE bakmamali: seriyi tetikten sonra
    kesince o tetik AYNI yerde durmali."""
    full = _bars(_quiet_then_break(tail=10))
    sig_full = squeeze_breakout(full, "LONG")
    i = int(np.argmax(sig_full.values))
    kesik = squeeze_breakout(full.iloc[:i + 1], "LONG")
    assert bool(kesik.iloc[i]) is True
    assert list(sig_full.values[:i + 1]) == list(kesik.values)


def test_short_ayna():
    """Ayna taraf: sessizlikten ASAGI kirilim SHORT tetikler, LONG'u
    tetiklemez."""
    bars = _bars(_quiet_then_break(jump=-6.0))
    assert squeeze_breakout(bars, "SHORT").sum() == 1
    assert not squeeze_breakout(bars, "LONG").any()
