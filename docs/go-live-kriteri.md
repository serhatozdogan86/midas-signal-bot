# Go-Live Kriteri (yazili karar cercevesi)

> Konsey karari (30 Tem 2026): Golge moddan gercek para emirlerine gecis
> KARARI asagidaki UC kosulun TAMAMI karsilanmadan verilmez. Amac, gecis
> aninda karar vericinin o gunku ruh hali degil, onceden yazilmis kurallarin
> konusmasidir. Esikler `app/config/settings.py`'de tanimlidir; degistirmek
> serbesttir ama **ancak bu dosyada gerekcesiyle not dusulerek** - sessiz
> esik oynatmak kriterin varlik nedenini bozar.

## Kosullar (uclu VE)
1. **Orneklem:** >= 40 sonuclanmis golge islem (WIN/LOSS/EXPIRED;
   NOT_FILLED ve AMBIGUOUS sayilmaz). Not: sinyaller kumeler halinde
   geldigi icin (ayni gun/rejim) etkin orneklem gorunenden kucuktur;
   40 bir taban, tavan degil.
2. **Beklenti:** ortalama >= +0.15R / islem (toplam R / sonuclanan).
3. **Dayaniklilik:** kumulatif R egrisinde maksimum dusus <= 8R.

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

## Portfoy tavanlari (bu kriterle birlikte yururlukte)
- Eszamanli acik sinyal <= 10 (`MAX_OPEN_SIGNALS`)
- Gun basina yeni sinyal <= 6 (`MAX_DAILY_SIGNALS`)
- Tavan doluyken motorun urettigi sinyal veri setine KAYDedilir ama takip
  ve bildirim yapilmaz (`portfolio_cap_skip` logu).
