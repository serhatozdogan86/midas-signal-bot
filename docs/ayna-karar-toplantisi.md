# AYNA KARAR TOPLANTISI — dolum modeli (açıldı: 2026-08-30)

> **Neden açıldı:** 28 Ağustos ayna kapısı ön-kayıtlı eşiği aştı.
> Uyuşmazlık oranı **%31.0** (29 karşılaştırılan çiftin 9'u), eşik %25.
> Kural: faz4-gundem.md F8 → hüküm (b) = karar toplantısı açılır,
> **otomatik hiçbir şey değişmez** (izolasyon sözleşmesi md. 5).
> Ölçüm: `tools/mirror_disagreement.py`, 30 Ağu Pazar VM koşumu.

## 1. Ölçülen ne

| | |
|---|---|
| Karşılaştırılan çift | 29 (ön şart ≥20 ✔) |
| Henüz sonuçlanmamış | 5 (paydaya girmez) |
| Uyuşmayan | 9 |
| **Uyuşmazlık oranı** | **%31.0** (eşik %25 → AŞILDI) |
| Sapma kademesi (v4.32-C) | 0 — dolum oranı farkı 0.000, fiyat +0.01R |

**Dikkat çeken şekil:** uyuşmazlıkların gövdesi "biri girdi, diğeri
girmedi" ekseninde (ABBV / EQIX / NTRA: defter DOLMADI, ayna KAZANC).
Yani ayna, bizim defterin "girmedi" dediği işlemlere girdi ve kazandı.
Bu, hipotez 7'yi doğuran FTNT vakasının aynı şekli.

**Görünürdeki çelişki, gerçek değil:** kademe 0 ile %31 uyuşmazlık aynı
anda doğru olabilir, çünkü ikisi FARKLI şeyi ölçüyor. Kademe, dolum
ORANLARININ toplamda ne kadar ayrıştığına bakar (iki taraf da ~%76
doldu → fark 0.000); uyuşmazlık ise ÇİFT ÇİFT aynı sonuca varıp
varmadıklarına bakar. İki defter aynı oranda doluyor ama **farklı
işlemlerde** doluyor. Bu ayrımın kendisi bulgudur.

## 2. Toplantının tek sorusu

> Gölge defterin dolum modeli (bölgenin TAMAMEN katedilmesi + en kötü
> uç fiyat) gerçek emir mekaniğine göre fazla mı katı — ve bu yüzden
> kazanan işlemleri sistematik olarak mı eliyor?

## 3. Karşı argüman — bu toplantının en önemli maddesi

Ayna "girdi ve kazandı" diyor diye tetiği gevşetmek, **bu depoda daha
önce ölçülmüş ve reddedilmiş** bir yola girmektir:

1. **2 Ağustos konsey kararı (5/5):** "bölgeye bir tık dokunmak dolum
   saymaz; emirler ELLE giriliyor, 30–60 sn gecikme var." Tetik o gün
   bilerek bölgenin dibine çekildi.
2. **İkiz kanıtı (G2, 21 Ağu):** bybit hâlâ tek-dokunuş tetiğini
   kullanıyor ve **defterinin artıda görünmesinin TAMAMI oradan
   geliyor**: o alt küme çıkarılınca +6.96R → −171.91R, beklenti
   +0.005 → −0.145 R/işlem. Yani "gevşek tetik = kâr" tam olarak
   bizim ikizde illüzyon olarak yakaladığımız şey.
3. **Alpaca paper'ın kendisi gevşek tarafta:** NBBO'ya dokunulunca
   dolum varsayar — yani ölçtüğümüz "ayna", tam da 2 Ağustos'ta
   reddettiğimiz iyimser modelin bir uygulaması. Ayna mutlak gerçek
   DEĞİL, bağımsız ikinci görüştür ve bu görüşün kendi yanlılığı var.

Kısacası: ayna ile defter arasındaki fark, **iki farklı dolum
varsayımının farkı** olabilir — gerçeğin defterden yana mı aynadan yana
mı olduğunu bu ölçüm TEK BAŞINA söylemez.

## 4. Gerçeği ayırt edebilecek tek kanıt

Elle girilen GERÇEK emirlerde ne oluyor? Şu an bu veri **yok**: bot emir
göndermiyor, Serhat işlemleri Midas'tan elle giriyor ve gölge modda
gerçek emir girilmiyor. Dolayısıyla:

- Ayna (Alpaca paper) = iyimser uç
- Gölge defter = temkinli uç
- Gerçek = ikisinin arasında, yeri ÖLÇÜLMEMİŞ

## 5. Masaya konan seçenekler (karar Serhat'ın)

**A. Hiçbir şey değiştirme, ölçmeye devam et.** Uyuşmazlık kayda
geçer, KİLİT-3 tasarımına girdi olur. Gerekçe: gevşetme yönündeki
kanıt, ikizde illüzyon çıkmış bir mekanizmadan geliyor.

**B. Uyuşmazlık kohortunu anatomik incele (önerilen ilk adım).** 9
uyuşmazlığın her birinde fiyat bölgenin neresine kadar geldi? "Bölgeye
girdi ama tam katetmedi" mi, yoksa "hiç yaklaşmadı ama ayna yine de
doldu" mu? Birincisi modelin katılığına, ikincisi Alpaca'nın
gevşekliğine işaret eder. **Ek kod gerektirir, ama karar vermeden önce
tek anlamlı adım budur.** F4b ile birebir aynı soru.

**C. Küçük ölçekli gerçek emir denemesi.** Sinyal geldiğinde Midas'ta
gerçekten limit emir bırakılır (minimum tutar), dolup dolmadığı
kaydedilir. Tek kesin kanıt yolu bu — ama gerçek para ve Serhat'ın
elle iş yükü demek. Gölge mod disiplininden sapma sayılır mı, karar
gerektirir.

**D. Dolum kuralını gevşet.** ŞU AN ÖNERİLMİYOR: G2 kanıtı bunun
defteri yapay olarak artıya çevirebileceğini gösteriyor ve KİLİT-3
ilanına kadar parametre değişikliği zaten YASAK (Faz 4 zemin kuralı 1).

## 6. Karar kaydı

- [ ] Serhat kararı: ……
- [ ] Karar tarihi: ……
- [ ] Uygulama: config-lock.md'ye tarihli not; parametre değişikliği
      varsa KİLİT-3 ilanıyla birlikte, sayaçlar sıfırdan.

## 7. İkiz notu

Bu bulgu bybit'i doğrudan ilgilendiriyor: G2'nin "karar toplantısına"
diye bıraktığı soru (tek dokunuş dolduruyor mu?) burada ters yönden,
canlı ayna verisiyle yeniden karşımıza çıktı. İki deponun aynı soruyu
farklı kanıtlarla sorduğu bir kesişme — `ikiz-depo-notu.md`'ye
işlenecek (bulut oturumunun bybit'e yazma yetkisi yok).

---

## 8. YENİ DELİL (1 Eylül 2026 ölçümü) — üç parça

### 8.1 Yeniden ölçüm: 38 çift, 9 uyuşmazlık, **%23,7**
Kapı gününden (29 çift / %31,0) bu yana dokuz yeni çift geldi ve
**hiçbiri uyuşmazlık üretmedi**. Sınıflar terminal durumlara bakar,
yani eski çiftlerin sınıfı sonradan değişmez — pay sabit kaldı, payda
büyüdü.

**Bu, kapının hükmünü GERİ ALMAZ.** Eşik ön-kayıtlı tarihte ölçüldü,
%31 çıktı, hüküm (b) verildi. "Şimdi ölçtük, altına düştü" demek tam
olarak ön-kayıt disiplininin engellemek için var olduğu davranıştır
(eşik altına düşene kadar ölçmeye devam etme). Toplantı açık kalır.

Ama yeni sayı meşru bir delildir ve şunu söyler: %31'in bir kısmı
küçük örneklem gürültüsüymüş, ve uyuşmazlıklar zamana yayılmıyor —
belli bir döneme yığılmış görünüyor. İkisi ayrı tutulur.

### 8.2 Uyuşmazlık tek bir şey değil, ÜÇ ayrı olay
| grup | n | vakalar | şekil |
|---|---:|---|---|
| Ayna girdi, defter giremedi | 3 | ABBV, EQIX, NTRA | üçünde de ayna KAZANDI |
| Defter girdi, ayna giremedi | 2 | DE, JNJ | JNJ'de defter kazandı |
| İkisi de girdi, sonuç ayrıştı | 4 | GD, SHW, C, TER | **dördünde de ayna ZARAR** |

**Üçüncü grup bu toplantının eksik yarısıydı.** Ayna sadece daha çok
girmiyor, daha çok da kapatıyor: bizim "süre doldu" veya "belirsiz"
diye bıraktığımız dört işlemi gerçekleşmiş zarara çeviriyor. Yani
aynanın avantajı giriş tarafında, dezavantajı çıkış tarafında — ve
ikisi de **aynı gevşeklikten** doğuyor. Bu, G2'nin (+6,96R → −171,91R)
imzasının canlı veride görünmesidir.

### 8.3 Kademe hâlâ 0 — "aynı oranda, farklı işlemlerde"
Dolum oranı farkı 0,026 (defter 0,789 / ayna 0,816), fiyat avantajı
+0,004R (28 çift). config-lock'taki çözüm sahada doğrulandı.

## 9. B adımının ölçüsü artık KODDA (1 Eyl)
Toplantının önerilen ilk adımı — "fiyat bölgenin neresine kadar geldi?"
— artık tahmin değil ölçüm:
- `app/services/mirror_anatomy.py` → **nüfuz oranı**
  (LONG: `(entry_max − dönem_en_düşük) / (entry_max − entry_min)`).
  0,0 = bölgeye değmedi bile · 1,0 = **tam katetti** (defterin 2 Ağustos
  dolum şartı) · >1,0 = ötesine geçti. Pencere, defterin dolum
  penceresiyle birebir aynı (14 × 1s mum).
- `tools/mirror_pair_anatomy.py` → salt-okur CLI, deploy gerektirmez.
- **YORUM KURALI, sonuçlara bakılmadan yazıldı (1 Eyl):** medyan nüfuz
  ≥ 0,85 → (a) model katılığı lehine kanıt, dolum kuralı KİLİT-3
  gündemine; ≤ 0,50 → (b) ayna gevşekliği lehine, **defter değişmez**;
  arada → hüküm yok, örnek artırılır.
- Hükme yalnız "defterin kaçırdığı" vakalar girer (ABBV/EQIX/NTRA
  ekseni); çıkış ayrışması (GD/SHW/C/TER) ayrı sayılır — yoksa "biz mi
  kaçırdık" sorusunun paydası kirlenir.
- 9 test, üçü mutasyonla kırıldı (mum yokken 0,0 uydurma, çıkış
  ayrışmasını hükme katma, eşiği gevşetme).

## 10. Toplantının değişen ağırlık merkezi
Aynı gün ölçülen canlı karne bu tartışmayı yeniden çerçeveliyor:
beklenen değer **−0,384R**, maksimum düşüş **12,47R** (yanlışlanma
anında 8,90R'ydi — **derinleşiyor**), 48 kararda kazanma oranı %14,6,
net −16,42R.

Bu şu demek: "ayna daha çok girseydi daha çok kazanırdık" cümlesi,
**kaybeden bir stratejinin daha çok işlem yapmasını önermek** olabilir.
Dolum kuralı tartışması, stratejinin kendisinin negatif beklentili
olduğu gerçeğinin önüne geçmemeli. Dolum modeli KİLİT-3'ün bir
parçasıdır; asıl soru (F1/F7) neden kaybettiğimizdir.

## 11. B ADIMI SONUCU (1 Eylül 2026 VM ölçümü)

Defterin kaçırdığı üç vakada fiyat, giriş bölgesine şu kadar girmiş:

| sembol | nüfuz | okuma |
|---|---:|---|
| NTRA | 0,66 | bölgenin üçte ikisi |
| EQIX | 0,852 | neredeyse tamamı |
| ABBV | 0,97 | kıl payı kaldı |

**Medyan 0,852 → ön-kayıtlı kural (a) diyor:** model katılığı lehine
kanıt, dolum kuralı KİLİT-3 gündemine yazılır. Bugün hiçbir parametre
değişmez.

### Ama hükmün dayanıklılığı ZAYIF — bunu kendimiz ilan ediyoruz
Eşik 0,85, medyan 0,852. Aradaki fark **0,002** ve üç sayının medyanı
demek **tek gözlem** (EQIX) demek. EQIX'te fiyat yarım sent daha az
girseydi aynı araç aynı kuralla "ARADA — hüküm yok" yazacaktı.

Kural ön-kayıtlıydı ve dürüstçe uygulandı; hüküm geçerlidir. Ama
"dayanak" diye sunulamaz. Zayıflığı burada ilan ediyoruz ki örnek
sayısı artıp yön değişirse bu **fikir değiştirme değil**, önceden
duyurulmuş bir kırılganlığın gerçekleşmesi olsun. Araç artık bu uyarıyı
kendi çıktısında da basıyor (`dayaniklilik`: n < 7 veya eşiğe mesafe
< 0,05 ise **ZAYIF**).

### Yine de yönü tesadüf değil
Üç vakanın hiçbiri "bölgeye ucundan değdi" değil — en düşüğü 0,66. Yani
ayna bu üç işlemi havadan uydurmadı; fiyat gerçekten oraya gitti, biz
"tam katetme" şartı aradığımız için almadık. Bu, 2 Ağustos'ta terk
edilen "tek tık dolum" senaryosunun tersi.

### Etiket düzeltmesi (v4.50)
Araç önce "çıkış ayrışması: 6" diyordu; **doğrusu 4**. DE ve JNJ'de
ayrışan şey çıkış değil, ters yönlü bir giriş: bu kez **ayna** giremedi.
Kod artık üç kovayı ayrı sayıyor (defterin kaçırdığı 3 / aynanın
kaçırdığı 2 / çıkış ayrışması 4). Hüküm etkilenmiyor (medyan yalnız ilk
kovayı kullanır) ama madde 8.2'deki "çıkışta ayna 4/4 zarar yazdı"
argümanı 4 üzerinden okunmalı — 6 değil.

### Sıradaki adım
Örnek sayısını artırmak. Kaçırılan vaka 3'ten 7-8'e çıkana kadar bu
hüküm bir **yön işareti**, dayanak değil. Bu arada hiçbir parametre
değişmiyor (Faz 4 zemin kuralı 1 zaten yasaklıyor).
