# midas-signal-bot (Faz 1 — MVP)

Midas'ta listelenen ABD hisseleri icin kisa vadeli swing (1-3 gun, time-stop 3-5
islem gunu) LONG/SHORT sinyalleri ureten, Telegram'a bildirim gonderen karar
destek botu. **Emir gondermez** — islemler Midas uygulamasindan manuel girilir.

Iskelet [bybit-signal-bot](https://github.com/serhatozdogan86/bybit-signal-bot)
mimarisinden tasinmistir; strateji icerigi ABD hisse piyasasina gore yeniden
tasarlanmistir. Tum tasarim kararlari `midas-signal-bot-plan.md` dokumanindadir.

## Faz 1 kapsami
- Evren: getmidas.com scrape -> gunluk cache -> statik yedek liste zinciri
  + likidite filtresi (min fiyat, min 20G ortalama dolar hacmi)
- Veri: yfinance toplu 1D + 1h (tarihsel omurga); Finnhub yalnizca bilanco
  takvimi (ucretsiz planda OHLCV endpoint'i KAPALIDIR - asla mum cekilmez)
- Karar hatti (ilk fail'de kisa devre): DATA -> MARKET_REGIME (SPY/QQQ 200G) ->
  TREND (MA hiyerarsisi + HH/HL, short'ta + zayif RS) -> EARNINGS (+-2 gun) ->
  SETUP (1h pullback / breakout+retest) -> VOLUME -> (confluence) ->
  RISK_REWARD + maliyet filtresi -> SIGNAL
- 15 dk'da bir kaba tarama (tum filtrelenmis evren); sinyal dogrudan Telegram'a
  (ince tarama Faz 2'de Finnhub quote ile eklenecek)
- 15:45 TR hazirlik + 23:15 TR gun sonu ozeti; hafta sonu/tatilde uyur
  (statik NYSE takvimi 2025-2027 — yillik bakim gerekir)
- State: SQLite (cooldown + son sonuclar); shadow tracking / Gist / dashboard Faz 3

## Tasarim notu: RR tanimi
Plan TP1 = 1x, TP2 = 2x gunluk ATR ve ATR bazli stop (carpan 1.2) kilitler;
RR esigi 2.0 ile TP1 uzerinden RR matematiksel olarak tutmaz (1/1.2 < 2).
Bu yuzden uygulama:
- **Stop = yapisal stop** (son 1h swing ucu + 0.1 ATR tampon), ust siniri
  `entry -/+ 1.2 x gunluk ATR` (ATR_STOP_MULT),
- **RR = (TP2 - entry) / risk** olarak hesaplar.
Farkli bir tanim istenirse yalnizca `risk_manager.py` degisir.

## Kurulum ve calistirma
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                      # 53 test, canli API gerekmez (sentetik veri)

cp .env.example .env        # token/key degerlerini doldur
python -m app.main          # http://localhost:10000
```

## Dogrulama (deploy sonrasi da ayni sira)
```bash
curl localhost:10000/healthz
curl localhost:10000/universe    # evren kaynagi + filtrelenmis liste
curl localhost:10000/scan/dry    # Telegram'a mesaj ATMADAN tam tarama (contract JSON)
curl localhost:10000/status      # son sonuclar + rejim
curl localhost:10000/watchlist   # gec asamada takilan adaylar (Faz 2 girdisi)
```

## Render deploy
1. Repo'yu GitHub'a itin, Render'da "New +" -> "Blueprint" -> repo secin
   (`render.yaml` okunur).
2. Secret env'leri girin: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `FINNHUB_API_KEY`.
3. `TELEGRAM_ENABLED=false` ile 1-2 hafta **golge mod** calistirin
   (plan bolum 7); `/scan/dry` ve loglarla dogrulayin, sonra `true` yapin.
4. Free planda disk ephemeral'dir: cooldown restart'ta sifirlanir.
   Kalicilik icin paid disk veya Faz 3 Gist yedeklemesi.

## Bilinen sinirlar / bakim
- yfinance resmi olmayan kutuphanedir; kirilirsa `YFinanceClient` +
  `MarketDataService` degistirilerek Polygon/Twelve Data'ya gecilir.
- Midas sayfa yapisi degisirse `parse_midas_html` guncellenir; bu arada bot
  cache -> statik liste zinciriyle calismaya devam eder
  (`data/static_universe.txt` haftalik gozden gecirilmeli).
- `NYSE_HOLIDAYS` tablosu 2027 sonuna kadar tanimlidir.
- Finnhub ucretsiz plani bazi sembollerde bilanco tarihi vermeyebilir; tarih
  bilinmiyorsa EARNINGS filtresi gecer, sinyal mesajinda "bilinmiyor" yazar.

## Faz haritasi
- **Faz 2:** Finnhub quote + izleme listesi oncelik kuyrugu + ~1 dk ince tarama
  (giris seviyesi kirilim tetigi)
- **Faz 3:** shadow tracking, gun sonu performans raporu, Gist arsivi, dashboard
- **Faz 4:** parametre kalibrasyonu (golge mod verisi), RS/sektor ETF confluence
