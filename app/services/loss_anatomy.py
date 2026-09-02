"""ZARAR ANATOMISI (Faz 4 / F1) - "bu kurulum neden kaybediyor?"

SALT OLCUM: karara, esiklere, karneye girmez. Kapali kohortu OKUR.

NEDEN (1 Eyl 2026): kohort 20 Agu'da yanlislandi ve sonrasinda da
bozulmaya devam etti (maksDD 8.90R -> 12.47R; 48 kararda kazanma orani
%14.6). Ayni yone ikinci bagimsiz kanit: F6 backtest'inde yedi
stratejiden altisi negatif, motorun gunluk vekili -0.050R. Yani soru
artik "o 8 islem neden" degil, "bu kurulum neden kaybediyor".

DORT SORU ve KARAR KURALLARI - hepsi SONUCA BAKILMADAN yazildi
(1 Eyl 2026; sayilar bulut oturumunda gorulemiyor, VM'de kosulacak):

Q1 - GIRIS MI, CIKIS MI?  (bu belgenin ana sorusu)
  Her ZARAR islemi icin MFE = pozisyon lehte gittigi EN IYI nokta
  (tasarim riski = |dolum - stop| birimiyle). Islem stop'a carpmadan
  once ne kadar kazandirmisti?
    medyan MFE >= 0.8R -> CIKIS/STOP sorunu baskin: islemler once
        calisti, sonra geri verdi. Cikis tasarimi KILIT-3'un merkezine.
    medyan MFE <= 0.3R -> GIRIS/SECIM sorunu baskin: islemler bastan
        yanlisti; cikisi degistirmek kurtarmaz.
    arasi -> KARISIK: iki koldan da ayri olcum gerekir.
  Gerekce: depo bulgusu 2 "cikis tasarimi giristen belirleyici" bu
  soruyu tam olarak boler ve iki cevap ZIT is listesi uretir.

Q2 - ZARAR TEK BIR SETUP'TA MI TOPLANIYOR?
  n >= 5 VE net-R <= -3.0 olan setup, KILIT-3 roster incelemesine
  yazilir (otomatik cikarma YOK - F2'nin S2 icin yazdigi usul).

Q3 - SHORT TARAFI (research-log hipotez 5, ON-KAYITLI 30 Tem):
  short kohortu net-R < 0 VE n >= 20 -> short kapatilmasi KILIT-3
  gundemine. Bu kural YENI DEGIL, aynen uygulanir.

Q4 - REJIM / SEANS FAZI: yalniz RAPOR. Ornek sayisi hukum icin kucuk;
  karar kurali YAZILMADI, dolayisiyla yorum da yapilmaz (2.2 refleksi:
  "veri var" ile "hukum var" ayni sey degil).
"""
from __future__ import annotations

from statistics import median


def excursions(direction: str, fill_price: float | None,
               stop_loss: float | None, highs: list[float],
               lows: list[float]) -> tuple[float | None, float | None]:
    """(MFE, MAE) - tasarim riski birimiyle (R). Veri yoksa (None, None):
    "mum yok" ile "hic lehte gitmedi" ayni sey degildir (2.1).

    MFE = en iyi lehte hareket, MAE = en kotu aleyhte hareket. Ikisi de
    DOLUM fiyatindan olculur ve |dolum - stop| ile bolunur - yani
    "1.0 MFE" demek "stop mesafesi kadar kazandirmisti" demek.
    """
    if fill_price is None or stop_loss is None or not highs or not lows:
        return None, None
    risk = abs(fill_price - stop_loss)
    if risk <= 0:
        return None, None
    if direction == "LONG":
        mfe = (max(highs) - fill_price) / risk
        mae = (min(lows) - fill_price) / risk
    else:
        mfe = (fill_price - min(lows)) / risk
        mae = (fill_price - max(highs)) / risk
    return round(mfe, 2), round(mae, 2)


def q1_entry_or_exit(losers: list[dict]) -> dict:
    """Q1 hukmu: zararlarin medyan MFE'si giris mi cikis mi diyor?
    losers: her biri 'mfe' tasiyan ZARAR kayitlari."""
    v = [r["mfe"] for r in losers if r.get("mfe") is not None]
    if not v:
        return {"n": 0, "medyan_mfe": None,
                "hukum": "HUKUM YOK - olculebilir zarar kaydi yok"}
    med = round(median(v), 2)
    if med >= 0.8:
        hukum = ("CIKIS/STOP sorunu baskin: islemler calisti sonra geri "
                 "verildi - cikis tasarimi KILIT-3'un merkezine")
    elif med <= 0.3:
        hukum = ("GIRIS/SECIM sorunu baskin: islemler bastan yanlisti - "
                 "cikisi degistirmek kurtarmaz")
    else:
        hukum = "KARISIK - iki kol ayri olculur, tek hukum verilmez"
    # dayaniklilik: anatomi aletinin 1 Eyl dersi - zayifligi hukum
    # kendisi ilan etsin (n<10 ise yon isareti, dayanak degil).
    saglam = len(v) >= 10 and min(abs(med - 0.8), abs(med - 0.3)) >= 0.1
    return {"n": len(v), "medyan_mfe": med, "hukum": hukum,
            "dayaniklilik": {
                "saglam": saglam,
                "not": ("yeterli" if saglam else
                        f"n={len(v)} ve/veya esige cok yakin - YON ISARETI, "
                        "dayanak degil")}}


def breakdown(rows: list[dict], key: str) -> list[dict]:
    """Bir alana gore kirilim: n, net-R, kazanma orani. Sirali (en
    zararlidan). Alan bos olan kayitlar '(bilinmiyor)' altinda toplanir -
    sessizce ATILMAZ."""
    gruplar: dict[str, list[dict]] = {}
    for r in rows:
        gruplar.setdefault(r.get(key) or "(bilinmiyor)", []).append(r)
    out = []
    for ad, g in gruplar.items():
        rs = [x["r"] for x in g if x.get("r") is not None]
        kazanan = sum(1 for x in rs if x > 0)
        out.append({"grup": ad, "n": len(g),
                    "net_r": round(sum(rs), 2),
                    "kazanma_%": round(100 * kazanan / len(rs), 1) if rs else None})
    return sorted(out, key=lambda d: d["net_r"])


def q2_setup_flags(rows: list[dict]) -> list[dict]:
    """Q2: n>=5 VE net-R<=-3.0 olan setup'lar KILIT-3 incelemesine."""
    return [g for g in breakdown(rows, "setup_type")
            if g["n"] >= 5 and g["net_r"] <= -3.0]


def q3_short_verdict(rows: list[dict]) -> dict:
    """Q3: research-log hipotez 5'in ON-KAYITLI kurali, aynen."""
    shorts = [r for r in rows if r.get("direction") == "SHORT"]
    rs = [r["r"] for r in shorts if r.get("r") is not None]
    net = round(sum(rs), 2) if rs else 0.0
    n = len(rs)
    if n < 20:
        hukum = f"HENUZ HUKUM YOK (n={n} < 20) - on-kayitli sart dolmadi"
    elif net < 0:
        hukum = ("KURAL TETIKLENDI: short kohortu negatif ve n>=20 -> "
                 "short tarafinin kapatilmasi KILIT-3 gundemine")
    else:
        hukum = "short kohortu negatif DEGIL - kural tetiklenmedi"
    return {"n": n, "net_r": net, "hukum": hukum}
