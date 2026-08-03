# KONFIG KILIDI - midas-signal-bot P0
Ilan: 2026-07-30 (v3.4-P0 commit'i itibariyla). Motor/risk parametreleri
DONMUSTUR; go-live sayaci (docs/go-live-kriteri.md) bu andan baslar.
Her sinyal engine_sha (strategies/ kaynak hash'i) ile damgalanir;
kilit-oncesi sinyaller (30 Tem oncesi ~14 adet) ayri kohorttur ve
40'lik sayaca SAYILMAZ.

## Kilit kapsami (degistirilemez; kritik bug fix istisna + tarihli not)
- Boru hatti: rejim SPY+QQQ 200G MA; hacim >=1.3x (NEUTRAL 1.5x);
  RR bandi 2.0-6.0 (TP2); maliyet filtresi TP1 >= %2; bilanco +-2 gun
- Golge kurallari: giris penceresi 14 bar / izleme 28 bar (1h);
  ayni-bar stop+TP -> AMBIGUOUS; gap'te ACILIS fiyatindan cikis
- Maliyet modeli v0: 2 x 1.50$ sabit + 5bp cikis kaymasi;
  referans boy 10.000$ / %1 risk; beklenti NET-R uzerinden
- Portfoy tavanlari: eszamanli <=10, gunluk <=6 (tavan kohortu blocked=2)
- Evren: Midas scrape + min 3$ / 5M$ gunluk dolar hacmi

## Tarihli notlar
- 2026-08-03 (v3.17): FAIL-OPEN DENETIMI - tum karar filtreleri "verisi
  gelmezse sessizce gecer mi?" gozuyle tarandi (bilanco vakasinin
  ardindan). Bulgular:
  GUVENLI TARAFTA OLANLAR (degisiklik yok): MARKET_REGIME (UNKNOWN ->
  sinyal yok), VOLUME (ortalama hesaplanamazsa teyit yok sayilir),
  SHORT zayif-RS (benchmark yoksa saglanmaz), DATA (min bar), likidite
  evreni (veri yoksa sembol duser; hepsi duserse v3.11 alarmi).
  DUZELTILENLER:
  (1) BAYAT GUNLUK VERI: "veri var" ile "veri guncel" ayni degildi.
      yfinance bozuk yanitta eski mumlar dondurebilir, motor bunu
      guncel sanip sinyal uretirdi. Son gunluk mum
      MAX_DAILY_BAR_AGE_DAYS (5) gunden eskiyse DATA_MISSING.
  (2) GAP NOBETI SESSIZLIGI: acik pozisyonun quote'u alinamazsa kontrol
      sessizce atlaniyordu (bilanco vakasiyla AYNI hastalik). Artik
      ERROR + Telegram uyarisi + /diag'da positions_unchecked.
  (3) NYSE TATIL TABLOSU 2027'de bitiyor; bitince tatiller normal islem
      gunu sayilirdi. Tablo bitmeden 120 gun once KIRILAN onleyici test
      eklendi (test_holiday_table_not_near_expiry).
  YAN BULGU: test fixture'lari 1970'ten baslayan zaman damgalari
  uretiyordu (ts=i*3600000) - yani tum testler 56 yil bayat veriyle
  kosuyordu. Damgalar simdiye sabitlendi ve son bar KAPANMIS bar
  sinirina oturtuldu (closed_only ile tutarli).
- 2026-08-03 (v3.16): BILANCO FILTRESI FAIL-CLOSED - kanitli mekanizma
  hatasi uzerine kilit acildi (kilit kuralinin 3. sarti).
  VAKA: 14:45 deploy'u sonrasi prep sirasinda Finnhub /calendar/earnings
  15 sn timeout'a dustu. EarningsService._dates BOS kaldi, info() bos
  EarningsInfo dondu, motorun blackout kontrolu 'days_to is not None'
  sartina bagli oldugu icin SESSIZCE ATLANDI. TTL 6 saat oldugundan
  yeniden deneme de olmadi -> bilanco filtresi TUM SEANS devre disiydi.
  ZARAR GERCEKLESTI: AMGN'e bilancosuna 1 islem gunu kala LONG sinyali
  uretildi (bagimsiz dogrulama: AMGN earnings 2026-08-04).
  DUZELTMELER:
  (1) EarningsInfo.available -> takvim yuklenmediyse motor NO_TRADE
      dondurur (EARNINGS_FAIL_CLOSED=true). "Bilanco yok" ile
      "bilmiyoruz" artik ayni sey degil.
  (2) Veri yokken TTL beklenmez: 10 dk'da bir yeniden denenir.
  (3) /diag'da earnings blogu (ready, symbols, fail_streak, last_ok) +
      takvim yuklenemezse TELEGRAM uyarisi.
  TAKAS: Finnhub uzun kesintide o gun sinyal uretilmez. Bilmeden
  bilancoya girmektense sinyal uretmemek dogru taraftir; esik
  kapatilabilir (EARNINGS_FAIL_CLOSED=false).
  KOHORT NOTU: bugun uretilen 5 sinyal (AMGN, VZ, V, SBUX, ITW) bilanco
  filtresi DEVRE DISIYKEN dogdu. AMGN kohort disi birakilmali (analizde
  isaretlendi); digerlerinin bilanco tarihleri kontrol edildi ve
  blackout penceresinde degil (VZ 20 Eki, V 27 Eki, SBUX 28 Eki,
  ITW 23 Eki) - onlar kohortta kalir.
- 2026-08-02 (v3.10): GIRIS BOLGESI GERCEKCILIGI - onaylı motor degisikligi.
  BULGU (29 Tem defter otopsisi, sayilarla): bolge = sorted(level, close)
  oldugu icin fiyat kirilim seviyesinden uzaklastikca giris araligi
  genisliyor. GM vakasi: bolge 84.33-91.04 (%7.4), dolum 91.04, TP1 90.63
  -> islem HEDEFIN USTUNDE doldu (en kotu dolumda -0.07R), yani dogar
  dogmaz zararda. PCG/TRV'de de dolum bolgenin en kotu ucundan oldu.
  IKI KORUMA (ikisi de risk_manager, saf):
  (1) bolge genisligi <= MAX_ENTRY_ZONE_ATR (0.5) x gunluk ATR
  (2) EN KOTU dolumda (tracker LONG'da entry_max, SHORT'ta entry_min
      kaydeder) TP1 kazanci >= WORST_FILL_TP1_R_MIN (0.5) x risk
  GERIYE DONUK ETKI: 29 Tem'in 14 sinyalinden 3'u (GE, GM, PCG) elenirdi.
  NOT - KONSEY/DIS INCELEME DUZELTMESI: "TP1'de cikis +0.83R verir,
  basabas %55 isabet ister" iddiasi VERIYLE YANLISLANDI. Defterdeki 14
  sinyalin R@TP1 ortancasi 1.03 (BMY gercek: +1.05R). Sebep: 1.2 ATR bir
  TAVAN; RR>=2 filtresi zaten riski ~1 ATR altina zorluyor. Basabas
  isabet ~%49. TP1 asimetrisi ACIK MADDE OLMAKTAN CIKARILDI; yerine
  gercek sorun (bolge genisligi) kodlandi.
  Kilit kohortunda halen 0 sonuclanan islem var -> sayac sifirlama
  maliyeti YOK. Go-live esikleri degismedi.
- 2026-08-02 (v3.9.4): DIS KOD INCELEMESI uzerine iki duzeltme.
  (1) NaN SAVUNMASI: NaN karsilastirmalari her zaman False dondugu icin
  risk<=0, RR tavani/tabani ve maliyet filtresi NaN'i SESSIZCE gecirirdi
  -> NaN hedefli SIGNAL mumkundu. Bugun sizmiyordu (KlineSeries NaN
  barlari dusuruyor) ama koruma tek katmanda kalmamali; build_trade_plan
  artik tum ciktilarda math.isfinite dogrulamasi yapar. Motor DAVRANISI
  degismez (gecerli planlar aynen uretilir) - yalnizca gecersiz plan
  reddedilir; kilit kohortu SIFIRLANMADI.
  (2) YONETIM UCU KILIDI: GET /scan kimlik dogrulamasiz TAM TARAMA
  tetikliyor, Telegram'a sinyal gonderiyor ve golge deftere kayit
  aciyordu - bir link on-yuklemesi bile KILIT KOHORTUNU KIRLETEBILIRDI
  (veri butunlugu riski). /scan, /scan/dry, /backup/now artik ADMIN_TOKEN
  ister (tanimsizsa 503 = guvenli varsayilan). Salt-okunur uclar acik.
  /wallet POST: 200 satir + alan uzunlugu tavani.
  ACIK KALAN (dis inceleme de bagimsiz olarak dogruladi): TP1/stop
  asimetrisi - RR etiketi TP2 uzerinden, cikis TP1'de TAM yapiliyor.
- 2026-08-02 (v3.9): 29 Tem OTOPSISI uzerine iki koruma + bir bug fix.
  Otopsi bulgusu: 14 sinyalin tamami 29 Tem'de, tamami LONG, 13/14
  breakout_retest; SPY o gun -1.42% / QQQ -2.04% duserken gunluk rejim
  filtresi gun icinde KOR kaldi; 8 kaybin 7'si 30 Tem 14:34'te ayni
  dakikada stop oldu. n=1 kume - sistem hukmu verilemez, ama zafiyet
  MEKANIZMA duzeyinde kanitli. Eklenenler:
  (1) ENDEKS KILL-SWITCH: SPY <= -0.75% veya QQQ <= -1.0% (onceki
  kapanisa gore) iken yeni LONG acilmaz; SHORT ayna (+esikler). Yalniz
  YENI girisler; acik sinyal yonetimi/cikislar etkilenmez. Veri yoksa
  fail-open + WARNING. Kaynak: index_pulse (60 sn onbellek, ek API yok).
  (2) ACILIS PENCERESI: acilistan sonraki ilk 30 dk breakout tetigi
  calismaz (kaba taramada breakout SIGNAL dahil); bolge/pullback
  tetikleri etkilenmez.
  OLCUM: iki korumanin engelledigi adaylar blocked=3 (kill-switch) ve
  blocked=4 (acilis penceresi) siniflariyla hypo_r uzerinden izlenir -
  korumalarin R-etkisi sinif bazinda YANLISLANABILIR (blocked_summary
  by_class).
  (3) BUG FIX (cift kayit): yon/kume tavani maybe_track'ten SONRA
  kontrol edildigi icin tavana takilan sinyal hem blocked=0 (karneye
  sizar) hem blocked=2 olarak cift kaydedilebiliyor, tavan sayimi
  sinyalin kendi satirini da sayiyordu. Giris karari artik TEK noktada
  (_entry_block) ve maybe_track'ten ONCE. Tavan semantigi netlesti:
  "kume tavani 3" = 3 sinyale IZIN, 4.su engellenir.
  Kilit kohortunda halen 0 sonuclanan islem oldugu icin bu degisiklikler
  SAYAC SIFIRLAMA MALIYETI OLMADAN yapildi (v3.8 A+B+C ile ayni bilincli
  zamanlama). Go-live esikleri DEGISMEDI (60 islem + 25 kume + tek kume
  <=%25 + net beklenti >=+0.15R + maksDD <=8R).
- 2026-08-02: LLM konseyi (5 bagimsiz model) bulgulari uzerine UC duzeltme.
  (A) REPAINT: motor SETUP tetigini serinin son bari uzerinde ariyordu;
  kaba tarama 15 dk'da bir kostugu icin o bar cogu zaman HENUZ
  KAPANMAMISTI. Artik KlineSeries.closed_only() ile kapanmamis bar
  motora verilmiyor. (B) DOLUM: "bolgeye dokundu = doldu" varsayimi
  birakildi; bolgenin TAMAMEN katedilmesi sart. Kayma cift yonlu oldu.
  (C) Go-live esikleri 40 -> 60 islem + 25 kume + tek kume payi <=%25.
  Kilit kohortunda 0 sonuclanan islem oldugu icin bu degisiklikler
  SAYAC SIFIRLAMA MALIYETI OLMADAN yapildi (bilincli zamanlama).
  ACIK KALAN: TP1(1.0 ATR) < Stop(1.2 ATR) asimetrisi - TP1'de TAM cikis
  yapildigi icin kazanc +0.83R, kayip -1.0R; basabas icin ~%55 isabet
  gerekiyor. Kaba tarihsel dogrulama sonrasi VERIYLE ele alinacak.
- 2026-08-02: Seans FAZI etiketlemesi eklendi (PRE_MARKET / OPENING_RANGE /
  MORNING / LUNCH / AFTERNOON / POWER_HOUR / AFTER_HOURS). Bu bir MOTOR
  DEGISIKLIGI DEGILDIR - hicbir filtre, esik veya karar etkilenmez; yalnizca
  her sinyale 'hangi saat diliminde dogdu' sutunu eklenir (salt gozlem).
  Bu nedenle KILIT KOHORTU SIFIRLANMADI ve go-live sayaci kesintisiz devam
  eder. Seans DISI tarama (davranis degisikligi olurdu) bilincli olarak
  ertelendi -> docs/ideas.md.
- 2026-08-01: P1 (onayli uyarlama plani) eklendi: rejim histerezisi
  (200G MA +-%0.5 bant, 2 gun kapanis teyidi), isi motoru (ayni-yon <=8,
  kume <=3), dead-man switch (seans ici 25 dk tarama sessizligi alarmi).
  Motor davranisi degistigi icin kilit ani ve go-live sayaci
  2026-08-01T06:30Z'ye tasindi; onceki acik sinyaller (GM/PCAR/PCG/DAL/UAL)
  kohort-0'a katildi. Uyku donemi (30 Tem 17:50 - 1 Agu 08:30 TR, Render
  askisi) veri boslugudur; sonuclar geri doldurma ile hesaplanir.
- 2026-07-30: Go-live 'beklenti' olcusu bruttan NET-R'ye cevrildi
  (muhafazakar muhasebe ilkesi; kilit ilanindan ONCE, sayac bastan).

Esik "iyilestirme" fikirleri docs/ideas.md rafina yazilir; bir SONRAKI
kilit penceresinde (>=40 sonuclanan islem sonrasi) topluca degerlendirilir.
