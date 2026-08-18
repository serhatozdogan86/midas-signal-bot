"""Coklu-strateji KORELASYON/ORTUSME olcum aleti (v4.37, salt rapor).

IKIZ AKTARIMI (ikiz-depo-notu.md "midas oturumuna acik is", 13 Agu;
tasima 17 Agu): bybit app/services/correlation.py'den uyarlandi. Kural
2.3/3b geregi: bybit'te yeni olcum aleti cikti -> midas'ta karsiligi
kontrol edildi (StrategyLab coklu paralel strateji isletiyor, bagimsizlik
olcumu YOKTU) -> alet tasindi + anahtar test yazildi.

NE YAPAR: strateji laboratuvari adaylarinin (S1-S5) gunluk net-R
serilerini cift cift karsilastirir: Pearson korelasyonu, etkin bagimsiz
bahis sayisi (N_eff), ayni-gun sinyal ortusmesi. "5 aday" gercekte kac
BAGIMSIZ fikir? sorusuna sayi verir.

KALIBRASYON DUZELTMESI (18 Agu, ilk canli rapor): oz-dogrulama noktasi
same_day_signal'dir - S1|S5 ayni girisi paylasir, ortusme orani 1.000
CIKMALI (canlida cikti). Net-R korelasyonlari ise ~1 CIKMAK ZORUNDA
DEGIL: cikislar farkli (S1->V0, S5->V2 genis) ve canli olcum 0.198
verdi. Bu alet hatasi degil ARASTIRMA BULGUSUdur: ayni giristen dogan
iki strateji net-R'de yalniz 0.198 korele ise P&L'i giris degil CIKIS
kurali belirliyor - "cikis > giris" bulgusunun ucuncu bagimsiz kaniti
(research-log).

NE YAPMAZ: esik/karar/agirlik URETMEZ. Karar modulleri bu modulu
IMPORT EDEMEZ (anahtar test: tests/test_correlation.py).

bybit'ten bilincli FARKLAR (uyarlama notlari):
- Veri kaynagi DB degil, laboratuvarin bellek-ici Trade listeleri
  (midas lab ham islemi saklamaz - bellek dersi v4.4); seriler ozet
  aninda cikarilir, rapor lab ozetiyle birlikte meta'ya kalicilasir.
- Gunluk R = kapanis gununun NET R toplami (midas lab r_net uretir;
  bybit brut kullanir ve bunu raporda soyler - biz de soyluyoruz).
- Yon ortusmesi: midas lab su an LONG-only oldugundan "ayni gun ikisi
  de sinyal acti" oranina indirgenir; SHORT gelirse ayni kod calisir.
"""
from __future__ import annotations

MIN_DAYS = 10          # bir cift icin korelasyon raporlamanin alt esigi


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Klasik Pearson; n<2 veya sifir varyans -> None."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / (sxx * syy) ** 0.5


def pair_days(a: dict[str, float], b: dict[str, float]) -> tuple[list, list]:
    """Iki gunluk seriyi hizala: EN AZ BIRININ islem yaptigi gunler
    (ikisinin de bos oldugu gunler korelasyonu yapay sisirirdi)."""
    days = sorted(set(a) | set(b))
    return ([a.get(d, 0.0) for d in days], [b.get(d, 0.0) for d in days])


def correlation_matrix(series: dict[str, dict[str, float]],
                       min_days: int = MIN_DAYS) -> dict:
    """{'A|B': {'corr': r|None, 'days': n}} - alfabetik cift anahtari.
    Esik: HER IKI serinin de kendi basina yeterli aktif gunu olmali
    (tek islemlik seri, birlesik gun sayisini gecse de anlamsizdir)."""
    out: dict[str, dict] = {}
    names = sorted(series)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            xs, ys = pair_days(series[a], series[b])
            enough = (len(series[a]) >= min_days
                      and len(series[b]) >= min_days)
            r = pearson(xs, ys) if enough else None
            out[f"{a}|{b}"] = {
                "corr": (round(r, 3) if r is not None else None),
                "days": len(xs),
            }
    return out


def effective_bets(matrix: dict, n: int) -> dict:
    """N_eff = N / (1 + (N-1) * ort_korelasyon). Kac BAGIMSIZ bahis var?
    EVREN TUTARLILIGI (bybit incelemesi 13 Agu, MAJOR - aynen tasindi):
    ortalama korelasyon yalniz OLCULEN ciftlerden gelir; N de ayni
    evrenden sayilmali (n_measured), yoksa olculmemis stratejiler
    N_eff'i temelsizce sisirir."""
    measured = {k: v for k, v in matrix.items() if v["corr"] is not None}
    names: set[str] = set()
    for k in measured:
        a, b = k.split("|", 1)
        names.update((a, b))
    n_measured = len(names)
    vals = [v["corr"] for v in measured.values()]
    if n_measured < 2 or not vals:
        return {"n_strategies": n, "n_measured": n_measured,
                "avg_pairwise_corr": None, "effective_bets": None,
                "pairs_measured": len(vals)}
    avg = sum(vals) / len(vals)
    denom = 1 + (n_measured - 1) * avg
    n_eff = n_measured / denom if denom > 0 else float(n_measured)
    return {"n_strategies": n, "n_measured": n_measured,
            "avg_pairwise_corr": round(avg, 3),
            "effective_bets": round(
                min(max(n_eff, 1.0), float(n_measured)), 2),
            "pairs_measured": len(vals)}


def signal_overlap(opens: dict[str, set]) -> dict:
    """Ayni gun sinyal acan ciftlerin ortusme orani.
    opens: {strateji: {gun, ...}} (midas LONG-only sadelestirmesi)."""
    out: dict[str, dict] = {}
    names = sorted(opens)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            union = opens[a] | opens[b]
            both = opens[a] & opens[b]
            out[f"{a}|{b}"] = {
                "union_days": len(union), "both_days": len(both),
                "rate": (round(len(both) / len(union), 3) if union else None),
            }
    return out


def series_from_trades(all_trades: dict[str, list]) -> tuple[dict, dict]:
    """Lab Trade listelerinden (ozete gitmeden ONCE) kompakt seriler.
    Donus: (series {strateji: {gun: net_r_toplami}},
            opens  {strateji: {sinyal gunleri}})."""
    series: dict[str, dict[str, float]] = {}
    opens: dict[str, set] = {}
    for name, trades in all_trades.items():
        s = series.setdefault(name, {})
        o = opens.setdefault(name, set())
        for t in trades:
            o.add(t.entry_date)
            if t.r_net is not None and t.exit_date:
                s[t.exit_date] = s.get(t.exit_date, 0.0) + float(t.r_net)
    return series, opens


def build_report(all_trades: dict[str, list]) -> dict:
    """Lab kosumundan tam rapor (saf; I/O yok)."""
    series, opens = series_from_trades(all_trades)
    matrix = correlation_matrix(series)
    return {
        "note": ("OLCUM ALETI - salt rapor, karar/esik uretmez. Gunluk "
                 f"NET R uzerinden; cift icin iki tarafta da >= {MIN_DAYS} "
                 "aktif gun ister. N_eff yalniz olculen ciftlerin "
                 "evreninden (n_measured). Ikiz kaynak: bybit "
                 "correlation.py (Faz A)."),
        "min_days": MIN_DAYS,
        "basis": "net_daily_r",
        "strategies": {k: {"active_days": len(v)}
                       for k, v in sorted(series.items())},
        "daily_corr": matrix,
        "independence": effective_bets(matrix, len(series)),
        "same_day_signal": signal_overlap(opens),
    }
