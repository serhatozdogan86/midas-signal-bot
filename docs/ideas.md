# Fikir Rafi (kilit doneminde dokunulmaz)
Format: tarih | fikir | tetikleyen gozlem
- 2026-07-30 | Pullback kolu neden sessiz - esik dengesi incelemesi | ilk 14 sinyalin tamami BO
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
