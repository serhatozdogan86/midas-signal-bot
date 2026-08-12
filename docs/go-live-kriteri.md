# Go-Live Kriteri (yazili karar cercevesi)

> Konsey karari (30 Tem 2026): Golge moddan gercek para emirlerine gecis
> KARARI asagidaki UC kosulun TAMAMI karsilanmadan verilmez. Amac, gecis
> aninda karar vericinin o gunku ruh hali degil, onceden yazilmis kurallarin
> konusmasidir. Esikler `app/config/settings.py`'de tanimlidir; degistirmek
> serbesttir ama **ancak bu dosyada gerekcesiyle not dusulerek** - sessiz
> esik oynatmak kriterin varlik nedenini bozar.

## Kosullar (altili VE) - 2 Agu 2026 konsey + 12 Agu 2026 istatistik revizyonu
1. **Orneklem:** >= 60 sonuclanmis golge islem (WIN/LOSS/EXPIRED;
   NOT_FILLED ve AMBIGUOUS sayilmaz).
1b. **Bagimsizlik:** >= 25 farkli kume (cluster_id = yon+gun) VE hicbir
   tek kumenin toplam icindeki payi > %25 olmamali.
   GEREKCE (5 bagimsiz LLM konseyinin OYBIRLIGI): sinyaller kumeler
   halinde dogdugu icin 40 ham islem etkin olarak ~15-20 bagimsiz
   gozleme denk geliyordu. Ham sayi tek basina yaniltici.
2. **Beklenti:** ortalama >= +0.15R / islem (toplam R / sonuclanan).
3. **Dayaniklilik:** kumulatif R egrisinde maksimum dusus <= 8R.
4. **Istatistik (12 Agu 2026, ON-KAYIT; Serhat onayi):** islem basina NET
   beklentinin kume-blok bootstrap guven araliginin ALT siniri > 0 olmali.
   YONTEM (onceden sabit, sonuca bakip degistirilemez): kumeler
   (cluster_id) BLOK olarak iadeli orneklenir, her turda k kumeden k kume
   cekilir, istatistik = cekilen islemlerin net-R ortalamasi; 10.000 tur,
   %95 guven (percentil), tohum SABIT (tekrarlanabilirlik). Kod:
   `signal_tracker.cluster_bootstrap_ci`, esikler settings
   (`GOLIVE_CI_*`), rapor `golive_status.criteria.ci_low_r`.
   GEREKCE (iki-bot karsilastirma raporu Bulgu 7, bagimsiz dogrulandi):
   defterde islem basina net-R sapmasi ~1.1 iken +0.15R esigi 60 islemde
   ~1 standart hataya esit; hic ustunlugu olmayan bir sistemin kapiyi
   gecme olasiligi ~%15 (islem bazinda) - %25 (kume bazinda) idi. Bu sart
   o tesadufu keser. Kapiyi YALNIZCA SIKILASTIRIR ve motora dokunmaz;
   bu nedenle KILIT-2 sayaci SIFIRLANMADI (v3.8/v3.10 ile ayni bilincli
   zamanlama: kohortta henuz cok az sonuclanan islem varken eklendi).

## Ek ilkeler
- Ilerleme her gun sonu raporunda ve nabizda otomatik yayimlanir
  (`scheduler.golive_status`). Karsilanmadan "gecelim mi" tartismasi acilmaz.
- Kriter karsilandiginda gecis OTOMATIK DEGILDIR: kullanici karari +
  pozisyon boyutu plani (baslangicta minimum boy) + ilk 2 hafta yari-boy
  onerilir.
- Kriter surecinde parametre degisikligi yapilirsa sayac SIFIRLANIR
  (degisen sistem, eski karnesiyle savunulamaz).
- Ilk 5 ardisik kayipta sistem KAPATILMAZ; kriter sureci isler. Kapatma
  esigi ayri: maksDD 8R'yi asarsa golge mod da durdurulup Faz 4 analizi
  one cekilir.

## 2 Agu 2026 - muhasebe sikilastirmasi
- DOLUM: bolgenin yakin ucuna dokunmak artik dolum SAYILMAZ; fiyatin
  bolgeyi TAMAMEN katetmis olmasi gerekir (emirler manuel giriliyor,
  30-60 sn gecikme gercegi). Muhafazakar ALT SINIR.
- KAYMA: artik cift yonlu (giris + cikis), once yalniz cikis sayiliyordu.
- REPAINT: motor artik yalnizca KAPANMIS bar uzerinde setup tetigi arar.

## Yanlislama Kriterleri (eklendi 2026-07-30 - on-kayit simetriktir)
Basari gibi basarisizlik da onceden tanimlidir:
- 40 sonuclanan islemde NET beklenti <= -0.10R -> golge uretim durdurulur,
  Faz 4 analizi one cekilir (parametre "kurtarma" denemesi YAPILMAZ).
- Herhangi bir anda maksimum dusus > 8R -> ayni durdurma.
- 60 sinyalde NOT_FILLED orani > %60 -> giris bolgesi tasarimi gozden
  gecirilir (tavsiye niteliginde; durdurmaz).
Not (2026-07-30): 'beklenti' NET-R'dir (maliyet modeli: config-lock.md);
sayac KONFIG KILIDI aninda sifirdan baslar - kilit oncesi ~14 sinyal
kohort-0 olarak ayri raporlanir.

## Portfoy tavanlari (bu kriterle birlikte yururlukte)
- Eszamanli acik sinyal <= 10 (`MAX_OPEN_SIGNALS`)
- Gun basina yeni sinyal <= 6 (`MAX_DAILY_SIGNALS`)
- Tavan doluyken motorun urettigi sinyal veri setine KAYDedilir ama takip
  ve bildirim yapilmaz (`portfolio_cap_skip` logu).
