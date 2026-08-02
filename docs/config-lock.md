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
