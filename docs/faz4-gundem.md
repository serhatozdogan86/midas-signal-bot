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

### F6 — S6 Squeeze backtest'i (hipotez 9, on-kayitli)
research/ duzeneginde 2y; karar kurali research-log'da yazili.
KILIT-3 roster adayi.
DURUM (24 Agu): DUZENEK HAZIR, sonuc YOK. Sinyal kurali
(strategies.squeeze_breakout), karar kurali (harness.verdict_h9) ve
veri katmani (research/data.py) yazildi + testlerle kilitlendi;
kosmak icin piyasa verisi gerekiyor ve bulut oturumunun agi kapali
(Yahoo CONNECT 403) - backtest'i agi olan oturum kosar.
YAN BULGU (kayda deger): eski duzenek /home/claude/bt/*.pkl okuyordu,
yani gecici bir analiz ortamina bagliydi ve o ortam kapandiginda
KOSULAMAZ hale gelmisti. Olcum aleti yeniden uretilemiyorsa olcum de
yeniden uretilemez; veri katmani bu yuzden depo icine alindi.
IKIZ SORUSU: ayni kusur bybit'in research/ duzeneginde de var mi
(ikiz-depo-notu.md'ye tasinacak).

### F7 — Secim kurali (H-D): momentum agirlikli aday siralamasi
Bulgu 1+3 birlesimi (tek kanitli edge 12-1 momentum; "tavan degil secim
kurali belirleyici"). Karar kurali yazilacak, backtest research/'ta.

### F8 — Ayna donemi hukmu (28 Agu kapisi, on-kayitli esikler)
v4.32-C esikleri ve hipotez 7 kurali aynen isler; Faz 4'e girdi olur
(dolum modeli karari F4 ile birlesir).

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
