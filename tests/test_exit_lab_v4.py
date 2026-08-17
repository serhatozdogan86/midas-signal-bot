"""v4.36: V4_IZ - ATR iz-suren cikis varyanti (hipotez 8, ON-KAYIT 17 Agu).

research-log karar kurali: V4 = hedefsiz, stop = en iyi kapanis -/+
3.0xATR(14), yalniz lehte ilerler, sure V0 ile ayni (28 bar). Buradaki
testler mekanizmanin V3'ten GERCEKTEN farkli oldugunu sayiyla kanitlar:
ayni mum serisinde V3 -1R zarar yazarken V4 kari kilitler. Eski kodda
tum testler KeyError(V4_IZ) ile kirmizi yanar.
"""
from __future__ import annotations

from app.services.database import Database
from app.services.exit_lab import VARIANTS, ExitLab, replay
from app.services.signal_tracker import SignalTracker


def _sig(direction="LONG", entry_min=100.0, entry_max=101.0,
         stop=98.0, tp1=106.0, tp2=110.0):
    return {"id": 1, "symbol": "T", "direction": direction,
            "entry_min": entry_min, "entry_max": entry_max,
            "stop_loss": stop, "tp1": tp1, "tp2": tp2,
            "entry_candle_ts": 0}


def _bar(ts, o, h, l, c):
    return {"ts": ts, "open": o, "high": h, "low": l, "close": c}


def test_v4_tanimli_ve_ozet_kapsiyor(tmp_path):
    """V4_IZ varyant listesinde VE summary() bos defterde bile onu
    raporluyor - boylece denetimin 'varyant kapsama' kontrolu deploy
    aninda kirilmaz (EOD kosusu eski sinyalleri kendisi geri-doldurur)."""
    assert "V4_IZ" in VARIANTS
    db = Database(str(tmp_path / "v4.db"))
    tr = SignalTracker(db, "1h")
    lab = ExitLab(db, None, tr)
    assert "V4_IZ" in lab.summary()["variants"]


def test_iz_kari_kilitler_v3_ayni_seride_zarar_yazar():
    """MEKANIZMA KANITI: guclu ralli + sert dusus serisinde V4 izle
    kari kilitler; ayni seride V3 (sabit stop, hedefsiz) baslangic
    stopuna dusup -1R yazar. Iki varyant ayni sey olsaydi bu test
    anlamsiz olurdu - fark SAYIYLA olculuyor."""
    sig = _sig()
    candles = [_bar(0, 100.5, 101.5, 99.9, 100.8)]      # dolum @101
    px = 101.0
    for k in range(1, 17):                               # 16 bar siki ralli
        o, c = 100.0 + k, 101.0 + k
        candles.append(_bar(k * 1000, o, c + 0.2, o - 0.2, c))
        px = c
    assert px == 117.0
    candles.append(_bar(17000, 112.0, 112.5, 90.0, 91.0))  # sert dusus

    v4 = replay(sig, candles, "V4_IZ", fill_window=14)
    assert v4.status == "CLOSED" and v4.outcome == "WIN"
    assert v4.exit_price > 101.0                # dolumun USTUNDE cikti
    assert v4.r_gross > 2.0                     # kar kilitlendi

    v3 = replay(sig, candles, "V3_ORTA", fill_window=14)
    assert v3.outcome == "LOSS"
    assert v3.r_gross < 0                       # ayni seri, -1R
    assert v4.r_gross - v3.r_gross > 3.0        # fark buyuk ve olculu


def test_iz_isinmadan_canli_stop_korunur():
    """ATR(14) isinmadan (az bar) fiyat duserse cikis SINYALIN KENDI
    stopundan olur - iz baslangic stopunun gerisine hic dusmez."""
    sig = _sig()
    candles = [
        _bar(0, 100.5, 101.5, 99.9, 100.8),              # dolum @101
        _bar(1000, 100.8, 101.2, 100.2, 100.5),
        _bar(2000, 100.5, 100.9, 99.8, 100.0),
        _bar(3000, 100.0, 100.4, 97.9, 98.2),            # stop 98'e vurus
    ]
    r = replay(sig, candles, "V4_IZ", fill_window=14)
    assert r.status == "CLOSED" and r.outcome == "LOSS"
    assert r.exit_price == 98.0
    assert abs(r.r_gross - (-1.0)) < 0.01


def test_iz_short_tarafinda_simetrik():
    """SHORT: iz asagi yonde ilerler (min), yukari spike'ta kar kilitler."""
    sig = _sig(direction="SHORT", stop=103.0, tp1=94.0, tp2=90.0)
    candles = [_bar(0, 100.5, 101.2, 99.5, 99.8)]        # dolum @100
    for k in range(1, 17):                                # 16 bar dusus
        o, c = 100.0 - k, 99.0 - k
        candles.append(_bar(k * 1000, o, o + 0.2, c - 0.2, c))
    candles.append(_bar(17000, 86.0, 95.0, 85.5, 94.0))   # yukari spike
    r = replay(sig, candles, "V4_IZ", fill_window=14)
    assert r.status == "CLOSED" and r.outcome == "WIN"
    assert r.exit_price < 100.0                 # dolumun ALTINDA cikti (kar)
    assert r.r_gross > 2.0


def test_iz_zaman_stopu_v0_ile_ayni():
    """28. barda pozisyon hala acik ve iz vurulmadiysa EXPIRED -
    V0'la tek fark cikis mekanizmasi kalsin diye sure birebir."""
    sig = _sig()
    candles = [_bar(0, 100.5, 101.5, 99.9, 100.8)]
    for k in range(1, 30):                                # yatay seyir
        candles.append(_bar(k * 1000, 100.9, 101.4, 100.5, 101.0))
    r = replay(sig, candles, "V4_IZ", fill_window=14)
    assert r.status == "CLOSED" and r.outcome == "EXPIRED"
    assert [L["why"] for L in (r.legs or [])] == ["TIME"]
