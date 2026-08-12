# Fikir Rafi (kilit doneminde dokunulmaz)
Format: tarih | fikir | tetikleyen gozlem
- 2026-07-30 | Pullback kolu neden sessiz - esik dengesi incelemesi | ilk 14 sinyalin tamami BO
  DURUM (2026-08-06, v4.18): KOK NEDEN BULUNDU - decision arsivinde pullback
  8/8 VOLUME'da elendi (1.3x tetik-mumu sarti geri cekilmenin dogasiyla
  celisiyor). Olcum basladi: blocked=5 hipotez kohortu (hypo_lab) hacim
  sarti olmadan pullback'in gercek ileri-performansini izliyor. Muhtemel
  motor degisikligi (setup-tipine gore ayrisan hacim kosulu: breakout
  tetik mumunda genisleme, pullback'te cekilme sirasinda DARALMA + donus
  mumunda genisleme) bir SONRAKI kilit penceresinde, kohort verisi ve
  config-lock.md'deki onceden yazilmis karar kuraliyla degerlendirilecek.
- 2026-07-30 | NOT_FILLED kohort analizi (kacanlar daha mi iyi?) | konsey/veri bilimci
- 2026-07-30 | Sektor ETF eslemesi -> cluster_id'ye sektor boyutu | konsey/risk
- 2026-08-02 | SEANS DISI TARAMA (pre/after-market sinyal uretimi) | kullanici sorusu
  DURUM: ertelendi - kilit doneminde motor davranisi degismez. Bunun yerine
  seans FAZI etiketlemesi eklendi (bkz. market_calendar.session_phase),
  boylece karar veriyle verilecek.
  ONEMLI GIRDI (2 Agu): Midas seans disi emir KABUL EDIYOR - yani bu fikrin
  pratik engeli yok, sadece sirasi bekliyor.
  ACILMADAN ONCE COZULMESI GEREKENLER:
    1) Hacim filtresi seans disinda anlamsizlasir (hacim normal seansin kucuk
       bir kesri) -> ayri, faza duyarli bir esik gerekir
    2) yfinance saatlik verisi varsayilan olarak seans disini ICERMEZ
       (prepost parametresi) -> veri katmani degisikligi
    3) Makas (spread) genisligi: gap/kayma varsayimlari yeniden olculmeli
    4) Kilit kohortu sifirlanir -> 40 islemlik sayac bastan baslar
  KARAR ANI: >=40 sonuclanan islem sonrasi, phase_breakdown ciktisiyla
  birlikte degerlendirilecek (hangi fazlarin gercekten iyi oldugu gorulunce)
- 2026-08-02 | ALPACA KAGIT HESABI "AYNA" KATMANI | konsey: "%100 dolum kovalama suphesi"
  DURUM: 8-9 Agustos hafta sonuna ERTELENDI (kullanici karari). Gerekce: bu hafta
  zaten dort yeni parca ilk kez sahada (faz etiketleme, giris kaniti paneli,
  histerezisli rejim, veri kiyasi) - once onlarin temiz calistigi gorulsun,
  sonra yeni kirilma yuzeyi eklensin.
  KAPSAM (dar ve tek yonlu): sinyal dogunca Alpaca kagit hesabina ayni
  giris/stop/hedefle emir gonder -> doldu mu / ne zaman / hangi fiyattan izle ->
  bizim golge defterle KIYASLA. Alpaca'nin P&L'i KULLANILMAZ (komisyon modeli
  tamamen farkli: Alpaca komisyonsuz, Midas 1.50$/islem). Hicbir karari
  etkilemez -> KILIT KOHORTU SIFIRLANMAZ.
  DURUST CEKINCELER: (1) Alpaca kagit dolumlari da bir SIMULASYON - kendi
  dokumani "kayma ve kismi dolumlar gercek arz-talebi tam yansitmaz" diyor;
  (2) ucretsiz planda veri IEX (~%2.5 hacim) - ince akis dolum gercekciligini
  azaltabilir. Yani "kesin dogru" degil, BAGIMSIZ IKINCI GORUS olarak okunacak.
  BEKLEMENIN MALIYETI: eslestirilmis veri gerekiyor - bu arada kapanan her
  sinyal bir kiyas firsati olarak kayboluyor.
- 2026-08-12 | REJIM FILTRESININ BEDELI OLCULMUYOR | iki-bot raporu Bulgu 2
  Rejim filtresi boru hattinda 2. sirada SERT keser - plan hic kurulmadigi
  icin "bu kapi koruyor mu, firsat mi kaciriyor" olculemiyor. bybit'te ayni
  kapi hattin SONUNDA: engellenen sinyal tam plan uretip ayri deftere
  yaziliyor. Ayni prensip midas'ta baska korumalar icin zaten var
  (blocked=3 kill-switch, blocked=5 hipotez). FIKIR: rejim reddi icin de
  golge plan uret (yeni blocked sinifi, SALT OLCUM, karara girmez ->
  kohort sifirlanmaz). MALIYET: reddedilen gunlerde tam boru hatti
  kosturulur - islem yuku olculmeli (agir-is-tick dersi).
- 2026-08-12 | BAGIMSIZ SONUC DENETCISI (bybit'ten tasima) | iki-bot raporu Bulgu 10
  bybit'te sonuclar mumlardan SIFIRDAN, ayri bir uygulamayla yeniden
  turetilip kayitla kiyaslaniyor (291 kayit, 0 uyusmazlik). Gerekcesi:
  "kendi dongusunu tekrar kullanan denetim, o dongudeki hatayi goremez."
  midas'ta karsiligi yok; oysa muhasebemizde tek surumde 4 hata duzeltildi
  (v4.22) - boyle bir denetci onlari deploy'dan ONCE yakalardi. SALT
  OLCUM, motora dokunmaz. SIRA: Faz 2 kesimi oturduktan sonra.
- 2026-08-12 | Giris bolgesi genisligi RISKE oranlanmali (ATR'ye degil) | dis inceleme, defter olcumu
  GOZLEM: dolum kurali tetigi bolgenin DIBINE (entry_min) bagliyor ama
  fiyati TEPESINDEN (entry_max) yaziyor -> islem defterde dogdugu anda
  bolge genisligi kadar zararda basliyor. 26 dolmus islemde ortalama
  0.33R pesin zarar (WIN 0.15R / LOSS 0.28R / EXPIRED 1.06R). Net
  beklenti -0.50R iken acigin ucte ikisi buradan.
  Mevcut korumalar yakalamiyor: MAX_ENTRY_ZONE_ATR ve
  WORST_FILL_TP1_R_MIN bolgeyi ATR'ye oranliyor, RISKE oranlamiyor.
  Stop yapisal oldugunda risk 1.2 ATR'den kucuk olabiliyor ve bolge/risk
  1.0'i asabiliyor (defterde GM 1.10, V 1.02).
  CEKINCE: bu gercek strateji kusuru DA olabilir, olcum aracinin fazla
  kotumser olmasi DA - kodla ayirt edilemez. Ayirt eden tek sey
  alpaca_mirror (adim 2'de, kapali).
  KARAR KURALI (simdiden yazildi): kilit-2 kohortu 40 sonuclanan isleme
  ulastiginda, bolge/risk orani medyanin ustu ve alti karsilastirilir.
  Ust dilim alt dilimden >= 0.20R kotuyse VE isaret iki yari-donemde
  ayniysa bolge/risk tavani (oneri 0.25R) motora eklenir. Aksi halde
  hipotez YANLISLANMIS sayilir ve kayda gecer.
  Ayrinti: docs/ikiz-depo-notu.md maddesi M3.
