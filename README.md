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
- State: SQLite (cooldown + son sonuclar)
- **Faz 3 (aktif):** golge takip (shadow tracking), Gist yedekleme, /dashboard

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

## v2.2: bybit v3.x paritesi (kullanicinin bybit guncellemelerinin portu)
- **RR tavani 6.0** (RISK_REWARD_MAX): asiri dar stop'tan dogan "fantezi RR"
  planlari reddedilir (bybit golge verisi dersi)
- **Orphan sinyal degerlendirme** ("IONQ vakasi"): evren/likidite filtresinden
  dusen sembollerin acik golge sinyalleri her tarama sonunda ayrica yasatilir
- **Kalite etiketleri kalici**: confidence + setup_type sinyal kaydina yazilir
  (DB migration guvenli, tek cagri), tabloda ve modalda rozet olarak gorunur
- **Dashboard**: JetBrains Mono ile terminal tipografisi, KPI/kart/boru-hatti
  hover tooltip'leri, A-/A+ yazi boyutu, sinyal tablosunda CANLI fiyat kolonu
  (/live beslemesi), Portfoy Simulasyonu'na KAPASITE MODU (sermaye K slota
  bolunur, defter doluyken sinyal atlanir; sinirsiz varsayim referansiyla yan
  yana). NOT: bybit'teki "market gate" portlanmadi - Midas'ta MARKET_REGIME
  zaten 2. sirada SERT filtredir (daha guclu esdeger).

## Yahoo rate limit stratejisi (v1.1)
Render gibi paylasimli IP'lerde Yahoo cok agresif limit uygular. Onlemler:
- **yfinance 1.5.2** (curl_cffi tarayici taklidi - eski 0.2.x surumlerine gore
  engellenmeye cok daha direncli)
- Istekler **sirali** atilir (thread patlamasi yok), chunk'lar arasi bekleme +
  bos/limitli chunk'ta ustel backoff ile tekrar (loglarda `yf_rate_backoff`
  gorulmesi NORMALDIR - bot kendini toparlar)
- **Gunluk mumlar gunde 1 kez** indirilir ve cache'lenir (seans icinde degismez)
- Kaba tarama **iki gecislidir**: 1. gecis yalniz gunluk veriyle rejim/trend/
  bilanco filtrelerini kosar; 1h verisi SADECE sag kalan adaylar icin indirilir
  (HOURLY_FETCH_MAX, default 120). 15 dk'lik tarama boylece ~300 yerine
  ~on-yuz arasi istekle tamamlanir.
- Likidite filtresi (hazirlik, gunde 1 kez) kisa period ("1mo") kullanir.
  Ham Midas evreni buyuk oldugundan ilk hazirlik taramasi 10-20 dk surebilir.

## Bilinen sinirlar / bakim
- yfinance resmi olmayan kutuphanedir; kirilirsa `YFinanceClient` +
  `MarketDataService` degistirilerek Polygon/Twelve Data'ya gecilir.
- Midas sayfa yapisi degisirse `parse_midas_html` guncellenir; bu arada bot
  cache -> statik liste zinciriyle calismaya devam eder
  (`data/static_universe.txt` haftalik gozden gecirilmeli).
- `NYSE_HOLIDAYS` tablosu 2027 sonuna kadar tanimlidir.
- Finnhub ucretsiz plani bazi sembollerde bilanco tarihi vermeyebilir; tarih
  bilinmiyorsa EARNINGS filtresi gecer, sinyal mesajinda "bilinmiyor" yazar.

## Faz 3: golge takip + Gist + dashboard (kripto projesindeki duzenin uyarlamasi)

**Shadow tracking (SHADOW_TRACKING=true):** Her karar `decisions` tablosuna, her
1h/1d mum `candles` arsivine, her SIGNAL `signals` tablosuna yazilir ve sonraki
mumlarla sessizce sonuclandirilir: girise gelmezse NOT_FILLED (~2 seans), gelirse
stop=LOSS / TP1=WIN / sure asimi=EXPIRED (~4 seans). ABD uyarlamasi: **gap
muhasebesi** — bar stop/TP'nin otesinde acilirsa cikis ACILIS fiyatindan sayilir;
gap-through-stop -1R'den derin kayit dusebilir (gercekci olcum).

**Gist yedekleme (GITHUB_TOKEN + GIST_SYNC=true):** Bot verisini saatte bir
secret gist'e yazar (0_performance / 0_signals / 0_decisions / 0_meta + sinyal
ureten sembollerin mum CSV'leri). Render free'nin ephemeral disk sorununu cozer:
restart sonrasi DB bossa gist'ten otomatik geri yuklenir (self-healing) ve gist
revizyonlari istatistik GECMISINI arsivler.
Token: github.com -> Settings -> Developer settings -> Personal access tokens
-> **yalnizca `gist` scope** isaretle (repo erisimi verme).

**Uzaktan tani (/diag):** Son WARNING/ERROR loglari bellekte tutulur (ring
buffer) ve `/diag` ucundan JSON olarak sunulur; ayni JSON dashboard sayfasinin
kaynagina `<script id="server-diag">` blogu olarak gomulur. Boylece Render log
konsoluna girmeden TEK URL'den (kok sayfa) botun sagligi okunabilir: son tarama
suresi/sayilari, rejim, evren, golge istatistik, gist durumu, son uyarilar.

**Gunluk piyasa notu (market_report):** Hazirlikta (15:45 TR) gunluk verilerden
uretilir - SPY/QQQ degisimi, genislik (50G MA ustu oran), RS liderleri/zayiflari,
bilanco blackout sayisi, rejime gore gun plani. Telegram hazirlik mesajina,
dashboard'a ve /diag'a gider. Dis kaynak yok; saf fonksiyon, offline test edilir.

**Otomatik degerlendirme (commentary):** bybit botundaki CommentaryService'in
ABD uyarlamasi. Seans icinde saatte bir + gun sonunda kural tabanli oz-degerlendirme
uretir: basabas konumu, yon bilancosu (rejim baglamli), giris isabeti, gap
kaynakli derin kayip uyarisi, time-stop orani, orneklem uyarisi. LLM cagrisi
yoktur; dashboard'da "kural tabanli" olarak etiketlenir. Gun sonu Telegram
mesajina eklenir, gist'e 0_commentary.json olarak yazilir, /commentary ucundan okunur.

**Acilis oncesi gap nobeti (onayli plan eki, 2026-07-29):** Seans disi SINYAL
uretilmez (likidite/spread/hacim filtresi gerekceleriyle) ama acilis-30dk
penceresinde bot, acik golge pozisyonlarini ve guclu adaylari Finnhub pre-market
fiyatlariyla yoklar: stop'un otesinde acilacak pozisyon icin "Midas'ta
pre-market LIMIT emirle cikisi degerlendir" uyarisi, TP otesi lehte gap bilgisi,
>=%3 gap'leyen aday icin setup suphesi notu gonderir. Bildirilecek sey yoksa
sessiz kalir. (Midas uzatilmis islem saatleri: 11:00-16:30 / 23:00-03:00 TR,
limit emir.) Finnhub free planin pre-market tazeligi ilk gunlerde loglardan
dogrulanacak; yetersizse yfinance yedegine gecilir.

**Dashboard (v2, koyu tema):** `https://<servis>/dashboard` (veya kok `/`).
bybit-signal-bot dashboard duzeninin ABD uyarlamasi: strateji sozlesmesi karti,
tiklanabilir filtre boru hatti (asama -> elenen semboller), portfoy simulasyonu
(golge-bilesik: baslangic $ + risk %), WIN/LOSS noktali equity egrisi, yon
bilancosu (tikla -> tablo filtresi), satir-tikla sinyal detay modali, piyasa
nabzi, kural tabanli degerlendirme, "Nasil okunur?" egitimi ve HABER AKISI.

**Haber akisi (NewsService):** Finnhub genel piyasa haberleri + izlenen
hisselerin (acik pozisyon + gunun sinyalleri + izleme listesi, rotasyonla)
sirket haberleri; 10 dk'da bir sunucu tarafinda tazelenir, dashboard 30sn-5dk
secilebilir aralikla ceker. Basliklar dis kaynaktan aynen aktarilir; bot haber
YORUMLAMAZ ve haberi sinyal kararlarina KATMAZ (olasi Faz 4+ konusu). KPI kartlari
(win rate, toplam R, acik sinyal, giris isabeti), equity egrisi, karar hatti
hunisi (son taramada filtre bazinda elenen sayilar), sinyal tablosu, rejim,
izleme listesi ve gist durumu. 60 sn'de bir kendini yeniler.
Ek uclar: `/performance`, `/signals?limit=N`, `/backup/info`, `POST /backup/now`.

## Faz 2: ince tarama (v2.4 - AKTIF)
Seans icinde ~1 dk'da bir (FINE_SCAN_INTERVAL_SEC) canli fiyat yoklamasi:
1. **Bolge tetigi:** PENDING sinyalin fiyati giris bolgesine girdigi AN
   Telegram'a "GIRIS TETIKLENDI" bildirimi (sinyal basina bir kez).
2. **Kirilim tetigi:** Kaba tarama SETUP'ta takilan adaya son yapinin
   tepesinden (long; short ayna) tetik seviyesi takar. Canli fiyat seviyeyi
   (+%0.05 tampon) kirdiginda tek sembolluk TAM pipeline aninda kosulur ->
   SIGNAL ise dispatch. Sinyal gecikmesi <=15 dk'dan ~1 dk'ya iner.
Butce: tur basina en cok FINE_MAX_SYMBOLS (30) quote; sembol basi 60 sn
onbellek; aday basina 5 dk tekrar-degerlendirme cooldown'u. Ince tarama
hatasi kaba taramayi ASLA etkilemez (izole try/except).

## Faz haritasi
- ~~Faz 2~~ tamamlandi (v2.4)
- ~~Faz 3~~ tamamlandi (one cekildi)
- **Faz 4:** parametre kalibrasyonu - 30-50 sonuclanmis golge sinyalden SONRA
  (veri kilidi); RS/sektor ETF confluence; "HIGH guven gercekten daha mi iyi"
  analizi (kalite etiketleri hazir)
