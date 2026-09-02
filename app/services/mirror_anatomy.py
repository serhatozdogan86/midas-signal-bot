"""AYNA UYUSMAZLIK ANATOMISI - "biz mi fazla katiyiz, Alpaca mi fazla
gevsek?" sorusunu ayiran olcum. SALT OLCUM: hicbir karara, esige veya
karneye girmez (ayna izolasyon sozlesmesi md. 5 ile ayni statude).

NEDEN (30 Agu ayna kapisi, hukum (b) -> karar toplantisi):
Uyusmazliklarin govdesi "defter DOLMADI / ayna KAZANC" ekseninde. Iki
rakip aciklama var ve ikisi ZIT yone gotururu:
  (a) BIZ fazla katiyiz  - fiyat bolgeyi neredeyse katetmis, biz
      "dolmadi" demisiz; gercek dolum bizim modelin ustunde.
  (b) ALPACA fazla gevsek - fiyat bolgeye ancak degmis, Alpaca NBBO
      dokunusunda doldurmus; gercek dolum aynanin altinda.
Bu ikisi ancak FIYATIN BOLGEYE NE KADAR GIRDIGI olculerek ayrilir.

OLCU (nufuz orani):
  LONG icin  = (entry_max - donem_en_dusuk) / (entry_max - entry_min)
  SHORT icin = (donem_en_yuksek - entry_min) / (entry_max - entry_min)
  0.0  : bolgenin yakin ucuna bile gelmemis
  ~0+  : yalniz yakin uca degmis (2 Agu'da terk edilen "tek tik" dolum)
  1.0  : bolgeyi TAM katetmis = defterin dolum sarti (2 Agu kurali)
  >1.0 : bolgenin otesine gecmis
Donem = sinyalin dogum barindan sonraki FILL_WINDOW_BARS (14) mum -
defterin dolum penceresiyle BIREBIR ayni; baska bir pencere secmek
"hangi pencereyle hakli cikarim" oynamasi olurdu.

YORUM KURALI - sonuclara BAKILMADAN yazildi (1 Eyl 2026):
  medyan nufuz >= 0.85 ise (a) lehine kanit: model katiligi gercek
    islemleri eliyor -> KILIT-3'te dolum kurali gundeme alinir.
  medyan nufuz <= 0.50 ise (b) lehine kanit: ayna gevsekligi -
    uyusmazlik aynanin iyimserliginden dogar, defter DEGISMEZ.
  arada ise: hukum yok, ornek sayisi artirilir.
Bu esikler bir KARAR degil, kanit yonudur; parametre degisikligi
KILIT-3 ilanina kadar zaten yasak (Faz 4 zemin kurali 1).
"""
from __future__ import annotations

from app.services.alpaca_mirror import ledger_class, mirror_class


def penetration(direction: str, entry_min: float, entry_max: float,
                lowest: float | None, highest: float | None) -> float | None:
    """Fiyat giris bolgesine ne kadar girdi (0-1+). Veri yoksa None -
    0.0 DEGIL: "mum yok" ile "hic yaklasmadi" ayni sey degildir (2.1)."""
    if entry_min is None or entry_max is None:
        return None
    genislik = entry_max - entry_min
    if genislik <= 0:
        return None
    if direction == "LONG":
        if lowest is None:
            return None
        return round((entry_max - lowest) / genislik, 3)
    if highest is None:
        return None
    return round((highest - entry_min) / genislik, 3)


def anatomy_rows(pairs: list[dict]) -> list[dict]:
    """pairs: her biri sinyal + ayna alanlari + donem asiri degerleri
    (lowest/highest) tasiyan sozlukler. Yalnizca UYUSAN olmayanlari
    doner - uyusan ciftlerin anatomisi bu sorunun konusu degil."""
    out = []
    for r in pairs:
        d = ledger_class(r.get("status"), r.get("outcome"),
                         r.get("fill_price"))
        a = mirror_class(r.get("alpaca_status"), r.get("closed_reason"))
        if d is None or a is None or d == a:
            continue
        out.append({
            "symbol": r.get("symbol"),
            "direction": r.get("direction"),
            "defter": d, "ayna": a,
            "entry_min": r.get("entry_min"), "entry_max": r.get("entry_max"),
            "nufuz": penetration(r.get("direction"), r.get("entry_min"),
                                 r.get("entry_max"), r.get("lowest"),
                                 r.get("highest")),
            "defter_dolum": r.get("fill_price"),
            "ayna_dolum": r.get("alpaca_fill_price"),
            "bar_sayisi": r.get("bar_sayisi"),
        })
    return out


def anatomy_summary(rows: list[dict]) -> dict:
    """Yon hukmu: medyan nufuz hangi aciklamayi destekliyor?"""
    # Yalniz DEFTERIN girmedigi vakalar hukme girer - "biz mi kacirdik"
    # sorusunun oznesi bunlar. Diger uyusmazliklar (cikis ayrismasi)
    # ayri sayilir ve ayri raporlanir.
    kacirilan = [r for r in rows
                 if r["defter"] == "DOLMADI" and r["nufuz"] is not None]
    # v4.50 duzeltmesi (1 Eyl saha okumasi): eski kod "defter DOLMADI
    # DEGIL" olan her seyi tek torbaya atip 'cikis ayrismasi' diyordu -
    # oysa AYNANIN giremedigi vakalar (DE, JNJ) bir cikis ayrismasi
    # DEGIL, ters yonlu bir GIRIS ayrismasidir. Yanlis etiket toplanti
    # metnine "6 cikis ayrismasi" diye gececekti; dogrusu 4. Hukum
    # degismiyor (medyan yalniz kacirilan kumeyi kullanir) ama sayinin
    # kendisi bir argumandi: "cikista ayna 4/4 zarar yazdi".
    ayna_kacirdi = [r for r in rows if r["ayna"] == "DOLMADI"]
    cikis_ayrismasi = [r for r in rows
                       if r["defter"] != "DOLMADI" and r["ayna"] != "DOLMADI"]
    med = None
    if kacirilan:
        v = sorted(r["nufuz"] for r in kacirilan)
        n = len(v)
        med = v[n // 2] if n % 2 else round((v[n // 2 - 1] + v[n // 2]) / 2, 3)
    if med is None:
        hukum = "HUKUM YOK - olculebilir vaka yok"
    elif med >= 0.85:
        hukum = ("(a) MODEL KATILIGI lehine: fiyat bolgeyi neredeyse "
                 "katetmis, dolum kurali KILIT-3 gundemine")
    elif med <= 0.50:
        hukum = ("(b) AYNA GEVSEKLIGI lehine: fiyat bolgeye ancak degmis; "
                 "uyusmazlik aynanin iyimserliginden - defter DEGISMEZ")
    else:
        hukum = "ARADA - hukum yok, ornek sayisi artirilir"
    return {"label": "AYNA - karara girmez",
            "kacirilan_vaka": len(kacirilan),
            "medyan_nufuz": med,
            "ayna_kaciran_vaka": len(ayna_kacirdi),
            "cikis_ayrismasi": len(cikis_ayrismasi),
            "yorum_kurali": "1 Eyl 2026'da sonuclara bakilmadan yazildi",
            "hukum": hukum,
            "dayaniklilik": robustness(kacirilan, med)}


def robustness(kacirilan: list[dict], med: float | None) -> dict:
    """HUKMUN NE KADAR SAGLAM OLDUGU - hukmu DEGISTIRMEZ, yanina yazar.

    Neden (1 Eyl, yerel oturum uyarisi): ilk saha kosumunda medyan 0.852
    cikti, esik 0.85 - arada 0.002 var ve UC gozlemin medyani demek TEK
    gozlem demek. Kural on-kayitliydi ve durustce uygulandi, ama boyle
    bir hukmu "dayanak" diye sunmak yaniltici olurdu. Zayifligi hukmun
    KENDISI ilan etsin: ileride ornek artip yon degisirse bu "fikir
    degistirme" degil, zaten duyurulmus bir kirilganligin gerceklesmesi
    olur. Esikler DEGISMEDI - burada yalniz mesafe ve n raporlanir.
    """
    n = len(kacirilan)
    if med is None:
        return {"n": n, "saglam": False, "not": "olculebilir vaka yok"}
    mesafe = round(min(abs(med - 0.85), abs(med - 0.50)), 3)
    saglam = n >= 7 and mesafe >= 0.05
    if n < 7:
        gerekce = (f"n={n} (>=7 olmali): medyan tek-iki gozleme dayaniyor, "
                   "YON ISARETI - dayanak degil")
    elif mesafe < 0.05:
        gerekce = (f"medyan esige {mesafe} uzaklikta: kucuk bir oynamayla "
                   "hukum degisir")
    else:
        gerekce = "orneklem ve esik mesafesi yeterli"
    return {"n": n, "esige_mesafe": mesafe, "saglam": saglam,
            "not": gerekce}
