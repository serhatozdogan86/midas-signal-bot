# Faz 4 — Yanlislama Sonrasi Analiz (baslangic: 2026-08-20)

> KILIT-2 kohortu 20 Agu 2026'da YANLISLANDI (NET maksDD 8.90R > 8R;
> 30 Tem on-kayitli kural; bagimsiz dogrulama config-lock v4.42).
> Serhat karari "B": karne kapandi, sistem SALT-OLCUM modunda akiyor,
> analiz basladi. Bu belge analizin gundemi ve karar disiplinidir.

## Zemin kurallari
1. **Parametre "kurtarma" YASAK** (go-live-kriteri.md): KILIT-3 ilanina
   kadar motora/esiklere dokunulmaz. Analiz OLCER, degistirmez.
2. Her madde icin karar kurali SONUCA BAKILMADAN once yazilir
   (research-log usulu); Faz 4 ciktilari KILIT-3 tasarimina girer,
   KILIT-3 ancak Serhat onayi + yeni kilit ilaniyla baslar.
3. Veri kaynaklari: kapanan KILIT-2 defteri (14 islem + engelli
   kohortlar), akmaya devam eden salt-olcum sinyalleri, ayna, exit_lab,
   strategy_lab, hypo_lab, research/ backtest duzenegi.

## Gundem (oncelik sirasiyla)

### F1 — Zarar anatomisi: 8 islemlik seri neden olustu?
14 islemin ortak profili: hangi setup (hepsi breakout mu?), hangi rejim
gunleri, bolge/risk orani, MFE/MAE, karartma-temiz mi. Cikti: zarar tek
bir mekanizmaya mi (orn. kirilim kovalama dusen piyasada) yayilma mi.

### F2 — S2 Donchian'in kaderi
Kohortta -8.40R (en zararli), S3'le 0.63 korelasyon + %76 ayni-gun
(en az bagimsiz). ON-KARAR KURALI (simdiden): strategy_lab tarihsel
tavanli net beklentisi < 0 VE kohort katkisi negatif VE S3'le korelasyon
> 0.5 ise KILIT-3 roster'indan cikarilir/S3 ile birlestirilir.

### F3 — Cikis modeli gerilimi
Backtest "hedefi kaldir" (+48.5->+151.5R) dedi; canli V0 (sabit hedef)
tum varyantlari yeniyor (V0 -3.20 vs V3 -21.6, V4 -17.0). Hipotez:
dusen/yatay rejimde erken kar alma kurtariyor; backtest boga doneminde
olculmustu. Cikti: rejime kosullu cikis mi, V0 mi - esit-kosullu ortak
kume dolunca (v3.19 kurali islemeye devam).

### F4 — R muhasebesi: dolum riski mi tasarim riski mi?
JNJ vakasi (+7.91R dolum-riskiyle, +2.29R tasarim-riskiyle; 80 dolumun
34'u bolge disi). Fiili-risk normalizasyonu "pozisyon boyu fiili doluma
gore buyutulur" varsayimina dayaniyor - elle emirde dogrulanmamis.
IKIZ TARAMASI SONUCU (21 Agu, ikiz-depo-notu G1): bybit'te gap dali YOK
ve tasarim/fiili risk orani hicbir kayitta 1.0'i asmiyor - R sismesi
yapisal olarak imkansiz (kontrol grubu). Karsit-olgu: midas'in gap
kurali bybit defterine uygulansa +4.03R -> +350.89R illuzyon uretirdi
(ust sinir; asimetri: zarar -1R'ye capali, kazanc payda kuculdukce
serbest). JNJ'siz kilit-2 dususu 9.05R olurdu - yanlislama karari
JNJ muhasebesine dayanmiyor, tersine derinlesiyor.
Cikti: KILIT-3 defteri icin R tanimi karari (guclu aday: tasarim-riski
R ana olcu + fiili-dolum R yan sutun).

### F4b — Giris bandi / dolum orani (23 Agu gozlemi)
Dolum orani %78.9 (ayna ile birebir ayni - model dogrulanmis); 21 Agu
dogumlu 4 kayit 1-2 islem gunudur PENDING. Soru: bant (dolum kurali +
bolge tasarimi) dogru islemleri mi kaciriyor? Veri kaynagi: NOT_FILLED
anatomisi (bybit aletinin tasinmasi - envanterde acik) + ayna
NOT_FILLED/CANCELLED kiyasi. M3'un simetrigi: M3 "dolanlar pesin
zararli mi" sorar, F4b "dolmayanlar kacan kazanc mi" sorar. Karar
kurali yazilmadan olcum yorumlanmaz.

### F5 — Karartma-temiz yeniden okuma
v4.40 oncesi takvim eksikti; kohort-0/kilit-1 sayilari 5 kirli sinyal
iceriyor. KILIT-2 temizdi. Cikti: tum-kohort tarihsel okumalar bu
dipnotla yeniden cercevelenir (kayit duzeltilmez, not dusulur).

### F6 — S6 Squeeze backtest'i ✔ KAPANDI: RED (24 Agu)
2y gunluk backtest kosuldu (167 sembol / 500 gun / LONG+SHORT / ortak
cikis). On-kayitli dort sarttan ikisi tutmadi: net beklenti -0.044R
(>0 olacakti) ve siralamada 6'da 5. (ilk 3 olacakti). S6 roster'a
ALINMAZ. Ikinci yarinin belirgin duzelmesi (-0.083R -> -0.005R) BILEREK
dikkate alinmadi - sart "beklenti > 0" idi, "duzeliyor mu" degil.
Ayrinti + tam tablo: research-log.md (F6 HUKUM).

ASIL BULGU (F1/F7'ye girdi): yedi stratejiden ALTISI negatif; tek
pozitif +0.005R ve 143.8R geri cekilmeli, yani gurultu. Ustune hayatta
kalma yanliligi tum LONG tarafini yukari cekiyor - gercegi daha kotu.
Motorun gunluk vekili -0.050R; canli golge defter de negatif. Iki
BAGIMSIZ olcum ayni yone isaret ediyor: 20 Agu yanlislanmasi sanssizlik
degil. KILIT-3 tasarimi bunu veri olarak alacak.

YAN BULGU 1 (kapandi): eski duzenek /home/claude/bt/*.pkl okuyordu -
kapanmis gecici bir ortam - yani harness KOSULAMAZ durumdaydi. Veri
katmani depo icine alindi (research/data.py).
YAN BULGU 2 (kapandi): arastirma evreni canli evrenden sessizce
ayrismisti (SQ -> XYZ; ayrica BRK.B bicim tuzagi uretimde 30 Tem'de
cozulmustu, arastirma kendi yolunu yazdigi icin geri gelmisti).
Duzeltildi + tools/universe_drift.py denetcisi eklendi.
IKIZ: bybit her iki konuda da ONDEYDI (veri indiricisi depo ici +
butunluk raporu; backtest evreni UniverseProvider'dan). Kayit
ikiz-depo-notu.md 24 Agu bolumunde; bybit'in butunluk raporunun
midas'a tasinmasi ACIK.

### F7 — Secim kurali (H-D): momentum agirlikli aday siralamasi
Bulgu 1+3 birlesimi (tek kanitli edge 12-1 momentum; "tavan degil secim
kurali belirleyici"). Karar kurali yazilacak, backtest research/'ta.

### F8 — Ayna donemi hukmu (28 Agu kapisi, on-kayitli esikler)
v4.32-C esikleri ve hipotez 7 kurali aynen isler; Faz 4'e girdi olur
(dolum modeli karari F4 ile birlesir).

OKUMA NOTU - 28 Agu 14:00 UTC, YENI SAYILAR GORULMEDEN yazildi.
Kapi gunu su UC soru sirayla okunur; sirayi sonradan degistirmek
"hangi siralamayla gecerdi" oynamasi olur:

1) ORNEKLEM SARTI: >=20 eslesmis cift VE >=14 gun.
   24 Agu itibariyla matched=21, sure doldu -> sart SAGLANIYOR.
   Saglanmazsa: sure uzatilir, YORUM YAPILMAZ (kismi veriye hukum yok).
2) SAPMA (v4.32-C, cift yonlu): dolum orani farki >=%20 VEYA ortalama
   fiyat avantaji >=0.15R ise kademe 2 = KARAR TOPLANTISI.
   |fark| >=0.10 / >=0.08R ise kademe 1 = izleme notu, EYLEM YOK.
   24 Agu olcumu: dolum farki 0.000, fiyat +0.01R -> kademe 0.
   HATIRLATMA: kademe bir OLGUNLUK merdiveni degil SAPMA merdivenidir;
   tier=0 "bozuk" degil "ayrisma yok" demektir (24 Agu notu).
3) HIPOTEZ 7 (sonuc uyusmazligi): uyusmazlik orani >= %25 ise dolum
   modeli karar toplantisina tasinir. Olcusu artik KODDA:
   `AlpacaMirror.disagreement()` + `tools/mirror_disagreement.py`
   (salt-okur, deploy gerektirmez - seans ici kosulabilir).
   Payda = iki tarafi da SONUCLANMIS ciftler (ayna pozisyonu hala
   acikken sayilmaz); "dolmadi" bir sonuc SINIFIDIR, yani "biri girdi
   digeri girmedi" uyusmazliktir (hipotez 7 FTNT vakasindan dogdu).

HUKUM SEKILLERI (ucu de mesru, dordu yok):
 a) Sapma yok + uyusmazlik <%25 -> DOLUM MODELI DOGRULANDI. Defterin R
    muhasebesi bagimsiz ikinci gorusle ortusuyor; F4'un "tasarim riski
    mi fiili risk mi" tartismasi bu dogrulamayi girdi olarak alir.
 b) Kademe 2 VEYA uyusmazlik >=%25 -> KARAR TOPLANTISI acilir.
    Otomatik hicbir sey degismez (izolasyon md. 5).
 c) Ornekleme ragmen veri tutarsiz/eksik (ornekler bos, sinif
    dagitimi anlamsiz) -> hukum ERTELENIR ve sebebi yazilir.
Ayna paper hesabinin kendisi de bir simulasyondur (NBBO dokunusu =
dolum varsayimi): "mutlak gercek" degil, bagimsiz ikinci gorustur.
Bu cumle hukum metnine de girecek.

### F9 — Kill-switch firsat maliyeti (24 Agu gozlemi)
24 Agu'da endeks kill-switch'i QQQ'da 17 kez tetikledi (-%1.11 ... -%1.65)
ve sonra birakti; NTRA sinyali ENGELLENMEDI, GECIKTI - ayni gun daha kotu
fiyattan yeniden dogdu. Yani frenin maliyeti "uretilmeyen sinyal" degil
"daha kotu dogan sinyal" olabilir; bu simdiye dek hic olculmedi.
Veri kaynagi HAZIR, ek kod GEREKMIYOR: blocked=3 kohortu (kill-switch,
~25 kayit) hypo_r uzerinden zaten akiyor (session_guard modul basligi:
"koruma gercekten R kurtariyor mu, tahmin degil VERI olsun").
Soru: kill-switch kac kotu islemi engelledi, kac iyi islemi geciktirdi -
ve geciken islemlerin giris fiyati ne kadar bozuldu?
ON-KARAR KURALI (simdiden, sonuca bakilmadan): blocked=3 kohortunun
hipotetik net-R'si <= 0 ise fren KAZANDIRIYOR, aynen kalir. > 0 ise
"engelleme" ile "geciktirme" ayristirilir: ayni gun yeniden dogan
kayitlarda fiili giris - hipotetik giris farki R cinsinden hesaplanir;
gecikme maliyeti toplam blocked=3 kazancinin yarisindan buyukse
KILIT-3'te fren "sinyal iptali" yerine "sinyal erteleme + bant koruma"
olarak yeniden tasarlanir. n < 20 ise hukum yok, olcum surer.
Not: bu bir OLCUM maddesidir; v3.9 kill-switch'i KILIT-3 ilanina kadar
oldugu gibi calisir (zemin kurali 1).

## Cikti
Faz 4 raporu -> KILIT-3 tasarim onerisi (roster + cikis + R tanimi +
secim kurali) -> Serhat onayi -> yeni kilit ilani + sayaclar sifirdan.
