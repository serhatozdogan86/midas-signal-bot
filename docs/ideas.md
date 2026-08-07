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
