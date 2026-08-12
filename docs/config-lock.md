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
- 2026-08-12 (v4.30): GO-LIVE KAPISINA ISTATISTIK SARTI (Serhat onayi,
  "evet" 12 Agu). Kaynak: iki-bot karsilastirma raporu Bulgu 7 (bagimsiz
  dogrulandi: net-R sapmasi ~1.1 -> +0.15R esigi 60 islemde ~1 SE;
  sanssiz sistemin gecis olasiligi %15-25). Yeni sart: kume-blok
  bootstrap %95 CI ALT siniri > 0 (yontem ON-KAYITLI:
  go-live-kriteri.md kosul 4; kod signal_tracker.cluster_bootstrap_ci;
  rapor golive_status.criteria.ci_low_r; tohum sabit, memo'lu).
  SINIFLAMA: karar KURALI degisikligi, motor DEGIL - strategies/
  dokunulmadi, engine_sha sabit, sinyal uretimi/cikisi ayni. Kapiyi
  yalnizca SIKILASTIRDIGI ve kohortta henuz cok az sonuclanan islem
  oldugu icin KILIT-2 SAYACI SIFIRLANMADI (v3.8/v3.10 emsali). Ayni
  raporun diger midas bulgulari: dolum kurali bilincli/belgeli
  muhafazakar tercih (2 Agu notu) - DOKUNULMADI, hukmu Alpaca aynasi
  verecek (adim 3 anahtar bekliyor); rejim maliyeti olcumu + bagimsiz
  sonuc denetcisi ideas.md kuyruguna.
- 2026-08-08 (v4.24): AYNA ADIM 2 + KOTA KORUMASI + CI-GATED DEPLOY
  ISKELETI - motor/kohort etkisiz (strategies/ degismedi, engine_sha
  sabit, KILIT-2 kohortu kesintisiz).
  AYNA ADIM 2 (Serhat onayi; secimler onerildigi gibi): emir yasam
  dongusu istemci ARAYUZU uzerinden - limit+bracket gonderim (LONG
  entry_max / SHORT entry_min = tracker'in worst-fill tarafi; qty
  100$ risk referansi), dolum/cikis TRANSKRIPSIYONU (ayna simulasyon
  yapmaz - broker ne dediyse onu yazar), 14 kapanmis-bar pencere iptali
  (canli FILL_WINDOW_BARS birebir), 28 bar time-stop kapamasi.
  SHORT'lar da aynalanir (kapatma karari gelirse bagimsiz veri).
  Istemci adim 2'de SAHTE (testlerde, 8 test); uretimde client=None +
  ALPACA_MIRROR_ENABLED=false -> dongu tamamen ATIL. Izolasyon
  sozlesmesi aynen (13. degismez + import kilidi yesil). Adim 3:
  canli paper istemcisi (emir yetkili anahtar Render env'e eklendiginde)
  + 2 hafta alarmsiz izleme + sapma esikleri OLCUMDEN ONCE.
  KOTA KORUMASI (/quotes, /fundamentals): kimliksiz uclara sembol beyaz
  listesi (evren + acik sinyaller + cuzdan + endeks) + onbellek tavani.
  Gerekce: keyfi sembol dongusuyle disaridan Finnhub kotasi tuketilirse
  index_pulse bos kalir ve kill-switch (belgeli fail-open istisnasi
  geregi) SESSIZCE korlesirdi - botun tek freni dis istekle
  koreltilebilirdi. Liste bos donerse (restart ani) filtre uygulanmaz.
  CI-GATED DEPLOY (.github/workflows/deploy.yml): tests.yml main'de
  yesil bitince Render hook'unu tetikler. RENDER_DEPLOY_HOOK secret'i
  tanimlanana kadar ATIL; devreye almak icin Serhat'in iki adimi var
  (GitHub secret + Render auto-deploy OFF, ayrinti workflow basliginda).
- 2026-08-08 (v4.23): KILIT-2 ILANI - MOTOR DUZELTME PAKETI. Kilit
  kuralinin uc sarti tamamlandi: (1) gerekce olculdu (7 Agu bes-denetci
  raporu + el dogrulamasi, asagida), (2) Serhat ONAYI alindi, (3) yeni
  kilit + yeni kohort bu notla baslar (CONFIG_LOCK_UTC=2026-08-08T00:00Z,
  engine_sha bu commit'le degisir; kilit-1 kohortu 2026-08-01..08, ~18
  sonuclanan islem, AYRI degerlendirilir ve go-live sayacina SAYILMAZ).
  DUZELTILEN KANITLI MEKANIZMA HATALARI:
  (1) RETEST/ACCEPTANCE (structure_analyzer): dilimler kirilim mumunun
  kendisini tariyordu -> kirilim mumu seviyeyi asagidan gectigi icin
  low'u neredeyse her zaman tolerans altinda = retest kosulu BOSTU;
  acceptance de kirilim kapanisini sayip 2 yerine fiilen 1'di.
  "Breakout+retest" retestsiz kovalama girisiydi - kilit-1 defterinin
  16/17 islemi bu setap ve -12R. Dilimler artik break_i+1'den baslar.
  Kirilabilirlik stash ile kanitli (eski kod testte kirmizi).
  (2) GUNLUK CLOSED_ONLY (scheduler._get_daily_cached): seans ici
  (re)start'ta bugunun olusmakta olan gunluk bari trend/pivot/ATR/rejim/
  RS hesabina girip gun boyu cache'te kaliyordu (v3.19 repaint
  duzeltmesinin eksik ayagi). Gunluk cache artik closed_only.
  (3) REJIM MIN_BARS (regime_detector): SMA200 egimi 221 bar ister;
  esik 210'du -> 210-220 barlik seride NaN egim "unknown" yerine
  "neutral" donuyordu (NaN uzerinden fail-open). Esik 221 + isfinite
  guvencesi; veri yetersizse UNKNOWN (sinyal yok).
  (4) HACIM CAPASI (volume_analyzer): ortalama hacim hep bugunun
  SMA20'sindan (iloc[-2]) aliniyordu; tarihi breakout tetigi olay
  SONRASI hacme bolunuyordu. Ortalama artik olay oncesi pencereden.
  YAN DUZELTME (self_audit, motor disi): "motor surumu" degismezi
  bilincli yeni kilitte eski kohortun ACIK sinyallerini suclamaz;
  yalniz kilit sonrasi dogan farkli sha ihlaldir.
  BEKLENEN ETKI: breakout sinyal sayisi DUSER (gercek retest sarti),
  pullback kolu hipotez kohortuyla olculmeye devam eder. Kilit-2
  esikleri kilit-1 ile AYNI (go-live besli VE; degisiklik yok).
  ERTELENENLER (bir sonraki pencereye): pivot esitligi birlestirme,
  RSI(3) loss==0 ucu, 1h bayatlik kapisi (S3; docs/ideas.md).
- 2026-08-07 (v4.22): DERIN DENETIM DUZELTMELERI - bes bagimsiz denetci
  (motor/defter/orkestra/servis/finans) + el dogrulamasi. strategies/
  DEGISMEDI (engine_sha sabit); motor bulgularinin listesi ASAGIDA ayri
  karar bekliyor. Buradakiler olcum/altyapi katmani kritik duzeltmeleri.
  GOLGE MUHASEBE (kilitteki YAZILI kurallarin uygulanmasi; eski satirlar
  yeniden islenmez, duzeltme ileriye donuk):
  (1) GAP SIRASI: acilis stop/hedef OTESINDEYSE sira bilinir; eski kod
  stop+TP ayni barda diye AMBIGUOUS(0R) yazip EN KOTU gap zararlarini
  (ve simetrik gap kazanclarini) defterden dusuruyordu. Artik yazili
  kural uygulanir: cikis ACILISTAN (tracker + exit_lab birebir).
  (2) DOLUM BARI: bolgeyi katedip AYNI barda stop kesen mum zarar
  yazmiyordu ('continue' atliyordu). Artik dolum barinda stop -> LOSS,
  stop+TP -> AMBIGUOUS, yalniz TP -> pozisyon ACIK kalir (iyimser WIN
  yazilmaz; kotumser muhasebe ilkesi).
  (3) TIME-STOP CAPASI: coklu-tur degerlendirmede sayac dolum yerine
  DOGUMDAN basliyordu (fill_ts okunmuyordu) -> 14 bara kadar erken ve
  non-determinist EXPIRED. Artik fill_ts'ten kurulur; exit_lab ile ayni.
  (4) NET-DD: maks dusus egrisi brut R'dan hesaplaniyordu; go-live
  beklentisi NET iken DD brut kalinca 8R esigi iyimser kaciyordu ->
  DD artik net egriden.
  (5) EXIT LAB PENCERESI: uretimde fill_window=12 kurulmus, canli 14 -
  13-14. barda dolan sinyaller varyantlarda NOT_FILLED sayilip kiyas
  farkli orneklemde yapiliyordu. main.py artik FILL_WINDOW_BARS gecirir.
  (6) V1 KISMI-AMBIGUOUS: gerceklesmis TP1 bacagi maliyetsiz ve
  toplam disi kaliyordu; artik _finish ile maliyetli muhasebelestirilir.
  KALICILIK/OLCUM:
  (7) GERCEK SATIR YEDEGI HAM DOKUME GECTI (export_signals): cluster_id/
  engine_sha/mom_pct/atr/contract_json restore'da kayboluyordu -> her
  restart go-live 25-kume sayacini COKERTIYORDU (tum tarih tek NULL kume),
  kume tavanini gevsetiyordu, dilim analizleri birikemiyordu. import da
  ayni alanlari geri yukler (eski yedeklerle geriye uyumlu).
  (8) HIPOTEZ SIMETRISI: blocked=5 adayi artik _entry_block'tan gecer
  (kill-switch/acilis/tavan) - 'yalniz hacim farki' iddiasi korunur.
  (9) BILANCO TAZELIGI (fail-closed genislemesi, 2.2): takvim son
  basarili yuklemeden 24 saat sonra BAYAT sayilir -> ready=False, motor
  sinyal uretmez; basarisiz yenileme artik TTL yerine 10 dk'da bir
  yeniden denenir. TAKAS: >24s Finnhub kesintisinde sinyal uretilmez -
  bilinçli guvenli taraf.
  (10) DENETIM DAMGASI: 'bilanco korumasi' artik sinyal DOGARKEN takvim
  hazir miydi damgasina bakar (contract_json.earnings_ready); 'su an
  ready mi' semantigi gun-ici restart'ta sahte KRITIK alarm (7 Agu),
  gun sonu toparlanmada gercek ihlali gizleme uretiyordu.
  ALTYAPI: gist restore artik yedegin zaman damgasini da tasir; sync
  basarisizliginda 5 dk geri cekilme (tick basina MB'lik PATCH firtinasi
  bitti); buyuk JSON'lar indent'siz (~%60 kucuk); Finnhub timeout'lari
  da devre kesiciyi acar + WARNING (acik kuyruk #4 kapandi); haber
  added==0 artik ariza sayilmaz (alarm gurultusu); fundamentals None
  sonucu 24 saat degil 15 dk negatif-cache; /scan ile tick taramasi
  ayni anda kosamaz (_scan_gate) + acik-gercek-kayit tekligi DB'de
  kismi UNIQUE indeksle garanti.
  KOHORT NOTU: sayac SIFIRLANMADI - strateji degismedi, olcum aleti
  duzeltildi. 7 Agu oncesi sonuclanan ~18 islem ESKI muhasebe
  kurallariyla olculmustur (gap-AMBIGUOUS ve erken time-stop sapmalari
  iceriyor olabilir); go-live degerlendirmesinde bu heterojenlik
  hatirlanmali. Testler: 5 yeni dosya-testi + 14 regresyon (once
  kirmizi yazildi), toplam 356.
- 2026-08-07 (v4.21): BLOCKED KOHORT KALICILIK DUZELTMESI - kilit IHLALI
  YOK (yedekleme katmani; motor/karne/V0 defteri AYNEN, engine_sha sabit).
  VAKA: gist yedegi 0_signals.json'i recent_signals()'tan uretiyordu ve o
  sorgu blocked=0 filtreli (karne icin dogru) - restore da AYNI dosyadan
  yukluyordu. Sonuc: v3.9'dan beri HER restart tum blocked kohortlarini
  (2=tavan, 3=kill-switch, 4=acilis penceresi, 5=hipotez) sessizce
  siliyordu; korumalarin "kacirdigimiz R" (hypo_r) olcumu hic birikemedi.
  blocked_summary'nin dusuk sayilari bu yuzden - veri az degil, SILINIYORDU.
  Ayrica import_signals blocked/block_reason/cluster_id kolonlarini zaten
  yazmiyordu (ikinci katman ayni hastalik).
  DUZELTME: blocked satirlar AYRI dosyada (0_signals_blocked.json)
  yedeklenir (recent_signals_blocked); restore import_signals_blocked ile
  geri yukler - dedup anahtari blocked SINIFINI da icerir (ayni sembol/
  yon/an hem gercek hem varsayimsal satir tasiyabilir). Eski yedeklerle
  geriye uyumlu: dosya yoksa sessizce atlanir. Donus turu regresyon
  testli (tests/test_blocked_persistence.py; test ONCE yazildi, eski
  kodda kirildigi goruldu).
  OLCUM NOTU: 7 Agu oncesi blocked verisi kurtarilamaz (yedege hic
  girmedi). Hipotez kohortu (v4.18 karar kurali: 20 sonuclanmis hipotez)
  ve sinif bazli hypo_r sayaclari bugunden itibaren GERCEKTEN birikir;
  onceki blocked_summary okumalari eksik veriyle yorumlanmis sayilmali.
- 2026-08-07 (v4.19): ALPACA AYNA KATMANI ADIM 1 (iskelet) - kilit IHLALI
  YOK: strategies/ degismedi, motor davranisi ayni; salt olcum katmani
  (v3.19 exit_lab emsali).
  AMAC: defterin tum R muhasebesi simule dolum varsayimlarina dayanir
  (bolgenin tam katedilmesi, 5bp kayma, gap'te acilis fiyati). 60 islemlik
  kohorttan verilecek kararlar (go-live, V0/V1/V2/V3, short) oncesinde bu
  varsayimlar Alpaca KAGIT hesabiyla bagimsiz dogrulanacak. Sinir da
  kayitli: Alpaca paper da bir simulasyondur (NBBO dolumu) - mutlak gercek
  degil, bagimsiz IKINCI GORUS olarak okunur.
  IZOLASYON SOZLESMESI (tests/test_alpaca_mirror.py ile kilitli; ihlal
  denemesinin testi KIRDIGI gosterildi): karar modulleri (strategies/*,
  signal_tracker) aynayi import edemez (AST); ayna verisi YALNIZ kendi
  tablosunda (mirror_fills) yasar, signals semasina alan eklenmez; veri
  akisi tek yonlu (signals salt-okunur -> mirror -> rapor); self_audit
  13. degismezi ("ayna izolasyonu", critical) sema ayrikligini canlida
  izler; ciktilar yalniz "AYNA - karara girmez" etiketiyle raporlanir;
  sapma bulgusu otomatik ayar DEGIL, config-lock surecine girdidir.
  ADIM 1 kapsami: depo + niyet kaydi, EMIR YOK (ALPACA_MIRROR_ENABLED
  varsayilan False). Adim 2: sahte istemciyle emir dongusu + scheduler
  kancasi. Adim 3: canli paper hesap, 2 hafta alarmsiz izleme (yanlis
  alarm dersi). Adim 4: sapma esikleri OLCUMDEN ONCE yazilir (research-log
  yontemi), EOD raporuna AYNA bolumu. Acik sorular: paper hesap API
  anahtari (Render env, 2.7), short'larin da aynalanmasi (oneri: evet),
  emir bekleme penceresi (14 bar birebir mi, 2 islem gunu mu).
  AYNI GUN (v4.19a): pre-push hook - 2.5/2.6 kurallari mekaniklesti
  (motor disi altyapi, kohorta etkisi yok).
- 2026-08-06 (v4.18): HACIM/PULLBACK HIPOTEZ KOHORTU (blocked=5) - kilit
  IHLALI YOK: strategies/ degismedi (engine_sha 4f29f1f5adf1 oncesi=sonrasi,
  git stash kaniti), canli motor/filtreler/V0 defteri AYNEN.
  BULGU (6 Agu decision-arsiv otopsisi, son 2000 karar): pullback setup'i
  8 kez bulundu, 8'inde de VOLUME kesti (cogu kil payi: 1.16-1.26x < 1.30x);
  breakout_retest 165 bulgu / 25 SIGNAL. Defter fiilen TEK-SETUP kaldi
  (sonuclanan 17 islemin 16'si breakout). Mekanizma yapisal: geri cekilme
  tanim geregi dusuk hacimli bir evredir; tetik mumunda 1.3x sarti
  pullback'i fiilen imkansizlastirirken breakout'a dogal gecit verir.
  KURULUM (app/services/hypo_lab.py): VOLUME'da elenen pullback adayi
  icin motorun SAF fonksiyonlariyla (detect_setup + build_trade_plan +
  ayni RR bandi + ayni maliyet filtresi) varsayimsal plan kurulur ve
  blocked=5 sinifiyla izlenir. Hacim DISINDAKI tum kapilar aynen
  uygulanir ki kohort canli defterden YALNIZ hacim kosuluyla ayrissin.
  Gercek hacim orani block_reason'a yazilir (esik alt-kumeleri analizde
  kesilebilir). Ayarlanabilir: HYPO_VOLUME_PULLBACK (varsayilan acik).
  KARANTINA: tum karne/tavan sorgulari blocked=0 (testle kilitli:
  test_hypo_lab). Yan duzeltme: setup_mix() blocked satirlari sayiyordu
  (mevcut kucuk bug) - panel canli defteri yansitsin diye blocked=0
  filtresi eklendi; hipotez blocked_summary.by_class["5"]'te okunur.
  KARAR KURALI (simdiden yazildi, sonradan oynanmaz): blocked=5 kohortu
  20 SONUCLANMIS hipoteze ulastiginda net-R beklentisi (ayni maliyet
  modeli) hesaplanir. Hipotez ancak su UC sart birlikte saglanirsa bir
  SONRAKI kilit penceresinde motor degisikligi onerisine donusur:
  (1) net beklenti > 0, (2) isaret iki yari-donemde ayni, (3) canli
  breakout kohortunun net beklentisinden dusuk degil. Aksi halde hipotez
  YANLISLANMIS sayilir ve hacim filtresi aklanir - bu da kayda gecer.
- 2026-08-03 (v3.19): CIKIS LABORATUVARI + MOMENTUM ETIKETI - kilit
  IHLALI YOK: canli motor, filtreler ve V0 defteri AYNEN; varyantlar
  ayni sinyallerin sanal yeniden oynatimi, momentum yalniz etiket.
  GEREKCE (backtest, research/): mevcut cikis mekanigi (TP1 tam cikis,
  4 gun) alti giris ailesinin ALTISINI da negatife cekiyor; ayni
  girisler genis stop + hedefsiz + uzun tutmayla pozitif. Tek kararli
  pozitif giris ailesi: 12-1 kesitsel momentum (NW t=3.3).
  KURULUM:
  - exit_lab: V1_KISMI (TP1'de %50, kalan TP2, 70 bar) ve V2_GENIS
    (hedefsiz, stop 5/3x, 140 bar). Dolum/gap/ayni-bar kurallari canli
    tracker ile BIREBIR (test_v0_mirrors_live guvencesi). Maliyet bacak
    basina Midas modeli. R paydasi HER varyantta canli risk -> ayni olcek.
  - mom_pct: sinyal dogarken 12-1 momentum evren yuzdeligi damgalanir
    (253+ gunluk bar sarti; karara karismaz).
  KARAR KURALI (simdiden yazildi, sonradan oynanmaz): kilit kohortu
  60 islem / 25 kumeye ulastiginda V1 ve V2, V0'a karsi net-R ile
  kiyaslanir; bir varyant hem toplam net-R hem beklenti olarak V0'i
  geciyorsa VE isaret iki yari-donemde tutarliysa motor cikisi o
  varyanta gecirilir (yeni kilit + yeni kohort). SMC sweep gunluk
  testte sifir cikti (t=0.6) - kol olmaz, etiket kalir. Order book
  stratejileri L2 verisi gerektirir - bizim veri dunyamizda OLCULEMEZ,
  taahhut edilmedi.
- 2026-08-03 (v3.18): BILANCO TAKVIMINE YEDEK KAYNAK. Fail-closed
  dogru davranis ama tek kaynaga bagli kalmak o filtreyi Finnhub'in
  calisma suresine mahkum ediyordu (bugun tum seans ready=false).
  Finnhub takvimi yoksa yfinance'in SCRAPE tabanli get_earnings_dates
  ucu devreye girer (Render'da engelli olan .info/quoteSummary ucundan
  FARKLI - yine de garanti degil; hata verirse "bilmiyoruz" kalir ve
  motor guvenli tarafta durur).
  MALIYET KONTROLU: yedek YALNIZ pass-2 adaylari icin (~50 sembol,
  gunluk onbellekli, 4 is parcacigi) calisir; pass-1'in 300 sembolu
  asla yedege gitmez.
  KILITLENME KORUMASI: pass-1 artik strict=False ile sorgular (o gecis
  1h verisi olmadigi icin SIGNAL uretemez, sadece aday eler). Aksi
  halde takvim yokken tum adaylar pass-1'de elenir, pass-2'ye kimse
  ulasmaz ve yedek kaynak HIC calismazdi.
  AYRIM KORUNDU: [] = "bilanco kaydi yok", None = "bilmiyoruz".
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
