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
