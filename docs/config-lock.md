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
- 2026-07-30: Go-live 'beklenti' olcusu bruttan NET-R'ye cevrildi
  (muhafazakar muhasebe ilkesi; kilit ilanindan ONCE, sayac bastan).

Esik "iyilestirme" fikirleri docs/ideas.md rafina yazilir; bir SONRAKI
kilit penceresinde (>=40 sonuclanan islem sonrasi) topluca degerlendirilir.
