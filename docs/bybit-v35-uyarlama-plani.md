# bybit v3.4-v3.5 Paketinin Midas'a Uyarlama Plani (taslak - onay bekliyor)

Kaynak: bybit-signal-bot ec09d40..36c64c7 (kullanicinin v3.4/v3.5 calismasi).
Ilke: mekanizma tasinir, parametre ABD/Midas gercekligine gore yeniden yazilir.

## P0 - Dogrudan tasinacaklar (dusuk risk, yuksek deger)
1. **Net-R muhasebesi (cost_r/r_net).** bybit: % taker ucret -> R'ye oran.
   Midas FARKI: ucret SABIT 1.50$ x2 -> maliyet POZISYON BUYUKLUGUNE bagli.
   Uyarlama: referans hesap varsayimi (10.000$, %1 risk) ile r_net kolonu
   + dashboard simulasyonunda KULLANICININ girdigi $ ile gercek net hesap.
   Ek: 5bp stop kaymasi varsayimi (muhafazakar). Funding YOK (spot hisse).
2. **Engellenen sinyal kohortu (blocked + block_reason + hypo_r).**
   Portfoy tavanina takilan SIGNAL artik sadece log degil: DB'ye blocked=2
   olarak yazilir, golge fiyat akisiyla hypo_r'i hesaplanir -> tavanin
   MALIYETI olculur ("tavan bizi kardan mi zarardan mi koruyor?").
3. **cluster_id.** yon + islem gunu (+ ileride sektor) -> ayni gun/yon
   kumeleri etiketlenir; go-live orneklem sayimi kume-farkindali yapilir,
   kume basina acik sinyal tavani (<=3) eklenir.
4. **engine_sha damgasi + KONFIG KILIDI.** Motor parametrelerinin hash'i
   her sinyale yazilir; docs/config-lock.md ile esikler DONDURULur,
   go-live sayaci kilit anindan baslar, fikirler docs/ideas.md rafina.
   (Not: kilit ilani = mevcut 14 acik sinyal kilit-oncesi kohort olur.)
5. **Yanlislama kriterleri.** go-live-kriteri.md'ye basarisizlik esikleri:
   orn. 40 islemde beklenti <= -0.10R VEYA maksDD > 8R -> golge durdur,
   Faz 4 analizi one cek. (bybit'teki simetrik on-kayit ilkesi.)

## P1 - Uyarlanarak tasinacaklar
6. **Isi motoru (heat).** bybit: ayni-yon<=4 / kume<=2 / toplam<=8.
   Midas mevcut: toplam<=10 + gunluk<=6. Uyarlama: ayni-yon tavani ekle
   (BULL'da fiilen toplam=ayni-yon; asil degeri NEUTRAL doneminde) +
   kume tavani (madde 3 ile). Esik onerisi: yon<=8, kume<=3, toplam<=10.
7. **Rejim histerezisi + fail-closed.** SPY/QQQ 200G MA gecislerinde
   +-%0.5 bant + 2 gun kapanis teyidi (rejim ziplamasi onlenir);
   endeks verisi cekilemezse UNKNOWN=uretim yok zaten (mevcut, dogrula).
8. **Dead-man switch.** Seans acikken son basarili tarama > 25 dk ise
   Telegram'a TEK uyari ("bot sessiz - kontrol et") + nabza bayrak.
9. **recent_signals r_net raporlama fix'i** (bybit 36c64c7 esdegeri) -
   madde 1 ile birlikte.

## P2 - Simdilik TASINMAYACAKLAR (gerekce kaydi)
- **Market gate karsi-olgu (blocked=1).** Midas'ta rejim yon filtresi
  setup'tan ONCE kisa devre yapar; karsi-yon karsi-olgusu icin ek pipeline
  kosusu gerekir (compute + kod karmasi). Faz 4'te veriyle tartisilacak.
- **24s ciro top-150 rotasyonu.** Midas evreni zaten likidite filtreli
  ve genis; daraltma kalibrasyon verisi olmadan erken optimizasyon.

## Sira ve dokunulan dosyalar
P0(1-2-3) tek surum: tracker (kolonlar+migration+hypo eval), scheduler
(cap -> track_blocked cagrisi), sim/dashboard (net hucreler), testler.
P0(4-5) dokuman + kucuk kod (sha uret + kolona yaz). P1(6-7-8) ikinci surum.
Tahmin: P0 ~1 oturum, P1 ~1 oturum. ONAY SONRASI baslanacak.
