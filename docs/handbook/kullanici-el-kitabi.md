# MİDAS SİNYAL BOTU
## Kullanıcı El Kitabı — Strateji, Mekanizma ve Karar Süreci

*Sıfırdan anlatım. Teknik terimler açıklanır, teori örnek grafiklerle desteklenir.*

---

# Önsöz

Bu kitap, Midas Sinyal Botu'nun *ne yaptığını*, *nasıl çalıştığını* ve *bir kararı neden aldığını*
en baştan anlatmak için yazıldı. Borsa, hisse senedi veya yazılım konusunda hiç bilgisi olmayan
biri de bu kitabı baştan sona okuyup botun ekranında gördüğü her rakamın, her rengin ve her
kelimenin ne anlama geldiğini öğrenebilmeli.

İki katmanda ilerliyoruz:

- **Teori** — bir kavramın ne olduğu, neden var olduğu, hangi soruna çözüm ürettiği.
- **Pratik** — o kavramın botun kodunda tam olarak nasıl uygulandığı, hangi sayının,
  hangi eşiğin kullanıldığı.

Kitap boyunca gerçek benzeri örnek grafikler kullanılır. Bunlar botun canlı ürettiği sinyaller
değil, botun mantığını görselleştirmek için hazırlanmış öğretici örneklerdir.

> **Önemli uyarı:** Bu bot bir *karar destek aracıdır*. Hiçbir emir göndermez, hiçbir hisse
> almaz veya satmaz. Ürettiği her şey bir öneridir; nihai kararı ve emri her zaman sen,
> Midas uygulaması üzerinden elle verirsin. Bu kitaptaki hiçbir bilgi yatırım tavsiyesi
> değildir.

---

# Bölüm 1 — Botun Felsefesi: Ne Yapar, Ne Yapmaz

## 1.1 Bot bir "sinyal fabrikası"dır, bir "otomatik tüccar" değildir

Piyasada iki tür bot vardır:

1. **Otomatik işlem botları** — kendi başlarına emir gönderir, parayı yönetir, senin hiçbir
   onayın olmadan alım-satım yapar.
2. **Karar destek botları** — piyasayı sürekli tarar, kurallarına uyan fırsatları tespit eder,
   sana "şu hisse, şu seviyeden, şu risk ile ilginç görünüyor" der ve orada durur.

Midas Sinyal Botu **ikinci gruptadır.** Bunun iki nedeni var:

- **Güvenlik:** Bir yazılım hatası, bir veri kesintisi veya beklenmedik bir piyasa hareketi
  otomatik bir botun gerçek parayla yanlış karar vermesine yol açabilir. Karar destek modelinde
  en kötü ihtimalle *kaçırılan bir fırsat* olur; otomatik modelde en kötü ihtimalle *gerçekleşmiş
  bir zarar* olur.
- **Öğrenme:** Sen her sinyali gördüğünde botun mantığını da görürsün — neden bu hisse, neden bu
  seviye, neden bu risk. Zamanla botun güçlü ve zayıf yönlerini sen de öğrenirsin.

## 1.2 "Gölge Mod" nedir?

Bot şu anda **gölge modda** çalışıyor. Bu, botun ürettiği her sinyalin gerçek parayla değil,
**hayali (kağıt üzerinde) bir hesapla** takip edildiği anlamına gelir. Bot "şu fiyattan alırdım"
der, bir defter tutar, o hayali işlemin sonucunu (kazandı mı kaybetti mi, kaç R kazandı/kaybetti)
kayda geçirir — ama gerçekte hiçbir emir gitmez.

Bunun nedeni basit: **bir stratejinin gerçekten işe yarayıp yaramadığını, gerçek para riske
atmadan önce anlamak.** Bu kitabın ilerleyen bölümlerinde ("Gölge Mod ve Gerçek Paraya Geçiş
Kriteri") bu sürecin nasıl işlediğini ve gerçek paraya ne zaman geçileceğine nasıl karar
verildiğini detaylıca anlatacağız.

## 1.3 Botun kapsamı: ABD hisseleri, kısa vadeli "swing" işlemler

Bot, Midas platformunda işlem gören ABD hisseleri için sinyal üretir. Hedeflediği işlem süresi
**1-3 gün** — yani "gün içi" (aynı gün alıp satmak) değil, "uzun vadeli yatırım" (yıllarca
tutmak) da değil, ortası: **swing trade** (salınım işlemi). Hedefe ulaşılırsa aynı gün çıkılabilir;
ulaşılamazsa en geç 3-5 işlem gününde pozisyon kapatılır ("zaman-stopu", ilerleyen bölümlerde
anlatılacak).

---

# Bölüm 2 — Temel Kavramlar Sözlüğü

Bu bölümde, kitabın geri kalanında sürekli karşına çıkacak temel terimleri, en basit
tanımlarından başlayarak açıklıyoruz. İlk okumada bazıları soyut gelebilir — merak etme,
Bölüm 4'te (Karar Hattı) hepsini gerçek örneklerle tekrar göreceksin.

### Mum Grafiği (Candlestick) ve OHLC
Bir hissenin fiyatı sürekli değişir. Bu değişimi belirli bir zaman aralığında (örneğin 1 saat
veya 1 gün) özetlemenin en yaygın yolu **mum grafiğidir.** Her "mum" dört sayıyı taşır:

- **O (Open / Açılış):** O aralığın başındaki fiyat
- **H (High / En Yüksek):** O aralıkta görülen en yüksek fiyat
- **L (Low / En Düşük):** O aralıkta görülen en düşük fiyat
- **C (Close / Kapanış):** O aralığın sonundaki fiyat

Kapanış açılıştan yüksekse mum **yeşil** (fiyat yükseldi), düşükse **kırmızı** (fiyat düştü)
çizilir. Mumun ince çizgisi (fitil) o aralıktaki en yüksek ve en düşük noktaları gösterir.

### Zaman Dilimi (Timeframe)
Botun kullandığı üç farklı "çözünürlük" vardır:

| Kısaltma | Anlamı | Botta ne için kullanılır |
|---|---|---|
| **1D** (Günlük) | Her mum bir işlem gününü temsil eder | Piyasa rejimi ve hissenin genel trendi |
| **1H** (Saatlik) | Her mum bir saati temsil eder | Giriş yapısı (setup), hassas seviye tespiti |
| **Gerçek zamanlı** | Anlık fiyat | Giriş tetiğinin tam o anda kırılıp kırılmadığı |

### LONG ve SHORT
- **LONG (uzun):** "Düşük fiyattan al, yüksek fiyattan sat" — fiyatın **yükseleceğini**
  düşünerek alım yapmak. Geleneksel, herkesin bildiği yön.
- **SHORT (kısa):** Fiyatın **düşeceğini** düşünerek, önce (ödünç alınan hisseyi) satıp
  sonra daha düşük fiyattan geri almak. Ters yönlü bahis.

### Destek ve Direnç
- **Direnç:** Fiyatın yukarı çıkarken defalarca "tosladığı", geçmekte zorlandığı seviye —
  sanki görünmez bir tavan gibi.
- **Destek:** Fiyatın aşağı inerken defalarca "sekip" durduğu, tutunduğu seviye — görünmez
  bir zemin gibi.

### Hareketli Ortalama (Moving Average / MA)
Son *N* günün/mumun kapanış fiyatlarının ortalaması. "50 günlük ortalama" son 50 günün
ortalama kapanışıdır. Fiyattaki günlük gürültüyü yumuşatıp **asıl yönü (trendi)** görmeyi
sağlar. Bot en çok **50 günlük** ve **200 günlük** ortalamaları kullanır.

### Trend
Fiyatın genel gidişat yönü. Basitçe:
- **Yükselen trend:** fiyat, kısa vadeli ortalama > uzun vadeli ortalamanın üstünde,
  her yeni tepe eskisinden yüksek (**HH** = Higher High), her yeni dip eskisinden
  yüksek (**HL** = Higher Low).
- **Düşen trend:** tam tersi — her yeni tepe eskisinden alçak (**LH** = Lower High),
  her yeni dip eskisinden alçak (**LL** = Lower Low).

### Stop-Loss (Zarar-Durdur) ve Take-Profit (Kâr-Al)
- **Stop-Loss (Stop):** "Buraya gelirse yanıldığımı kabul edip çıkarım" dediğin fiyat seviyesi.
  Kaybı sınırlamak için var.
- **Take-Profit (TP):** "Buraya gelirse kârımı realize ederim" dediğin fiyat seviyesi. Bot
  iki hedef kullanır: **TP1** (ilk, daha yakın hedef) ve **TP2** (ikinci, daha uzak hedef).

### Giriş Bölgesi (Entry Zone)
Bot tek bir fiyat değil, bir **aralık** verir (örneğin $17,82–$18,05). Çünkü gerçek piyasada
"tam olarak şu kuruştan al" demek gerçekçi değildir; makul bir bant içinde girmek yeterlidir.

### R — Riskin Evrensel Ölçü Birimi ⭐
Bu, botun tüm muhasebesinin temelini oluşturan **en önemli kavramdır.**

**Tanım:** Bir işlemde riske attığın miktar "**1R**" olarak adlandırılır. Eğer giriş $100,
stop $96 ise, riskin $4'tür — bu senin "1R"ndir. İşlem $104'e (yani girişin 1R üstüne)
giderse **+1R kazandın**; $92'ye (girişin 2R altına, teorik olarak) giderse **−2R kaybettin**
demektir. Stop'a düşersen tam olarak **−1R** kaybedersin (çünkü stop, tanımı gereği 1R
uzaklıktadır).

**Neden R kullanılır, dolar değil?** Çünkü hesabın büyüklüğünden bağımsızdır. 1.000 dolarlık
bir hesapta da, 100.000 dolarlık bir hesapta da "+2R'lik bir işlem yaptım" demek aynı **oransal**
başarıyı ifade eder. Bu sayede botun performansı, kimin ne kadar parayla işlem yaptığından
bağımsız, evrensel bir dille ölçülebilir.

Aşağıdaki grafik bu mantığı özetliyor:

**[GRAFİK 4 — R Nedir? Riskin Evrensel Ölçü Birimi]**

### RR (Risk/Ödül) Oranı
"Ne kadar risk alıp ne kadar ödül hedefliyorum?" sorusunun cevabı. RR = 2,5 demek, riske
attığın her 1 birime karşılık 2,5 birim kazanç hedeflediğin anlamına gelir. Bot, düşük RR'li
(riski ödülüne göre çok yüksek) sinyalleri otomatik eler.

### ATR (Average True Range / Ortalama Gerçek Aralık)
Bir hissenin **günlük olarak ortalama ne kadar oynadığının** ölçüsü. Volatilitesi yüksek bir
hissenin ATR'si büyük, "sakin" bir hissenin ATR'si küçüktür. Bot, stop ve hedef mesafelerini
sabit bir yüzde yerine **hissenin kendi ATR'sine göre** ayarlar — volatil bir hisseye dar bir
stop koymak anlamsızdır, çünkü normal günlük oynaklığıyla bile stop'a çarpar.

### RSI (Relative Strength Index / Göreceli Güç Endeksi)
0-100 arası bir sayı; hissenin kısa vadede "aşırı alınmış" mı yoksa "aşırı satılmış" mı
olduğunu gösterir. Bot, RSI'ın çok kısa periyodunu (RSI(3)) kullanarak bir geri çekilmenin
"yeterince satılmış" olup olmadığını ölçer (Bölüm 4.5'te detaylı).

### Relative Strength (RS) — Göreceli Güç Sıralaması
RSI ile karıştırılmamalı. Bu, bir hissenin **kendi sektörüne veya piyasaya göre** ne kadar
güçlü performans gösterdiğinin sıralamasıdır. "Piyasa %2 düşerken bu hisse sadece %0,5 düştü"
demek, o hissenin göreceli gücünün yüksek olduğunu gösterir — bu da bir güven artırıcı sinyaldir.

### Rejim (Regime): BULL / BEAR / NEUTRAL
Piyasanın (SPY ve QQQ endekslerinin) genel gidişatı. Bot bu üç durumdan birini tespit eder ve
LONG/SHORT üretimini buna göre sınırlar (Bölüm 4.2 ve Bölüm 7'de detaylı).

### Gap (Fiyat Boşluğu)
Bir hissenin bir önceki kapanışı ile bugünkü açılışı arasında oluşan ani sıçrama. Örneğin
hisse $50'de kapandı ama ertesi sabah $47'de açıldıysa, aradaki $3'lük fark **gap**tır (genellikle
gece çıkan bir haberden kaynaklanır). Gap'ler tehlikelidir çünkü **stop-loss'un "kesin çalışacağı"
varsayımını bozar** — fiyat stop seviyeni "atlayarak" geçebilir (Bölüm 4.4 ve 6'da detaylı).

### Likidite ve Dolar Hacmi
Bir hissenin ne kadar kolay alınıp satılabildiğinin ölçüsü. **Dolar hacmi** = günlük işlem
gören hisse adedi × fiyat. Bot, çok düşük likiditeli (günde çok az işlem gören) hisseleri
evreninden baştan eler — çünkü böyle hisselerde makul bir fiyattan alım/satım yapmak zordur.

### Confidence (Güven): H / M / L
Her sinyalin yanında bir güven etiketi bulunur:
- **H (High / Yüksek):** Birden fazla olumlu faktör aynı anda hizalanmış
- **M (Medium / Orta):** Standart, temel şartları sağlayan sinyal
- **L (Low / Düşük):** Şartları sağlıyor ama destekleyici faktörler zayıf

### Cluster (Küme) ve Kohort
- **Küme (cluster):** Aynı gün, aynı yönde (örneğin hepsi LONG) doğan sinyaller bir küme
  sayılır. Neden önemli? Çünkü bunlar **istatistiksel olarak bağımsız değildir** — piyasa o
  gün genel olarak yükseldiği için hepsi birden sinyal vermiş olabilir. Bir küme kazanırsa
  hep birlikte kazanır, kaybederse hep birlikte kaybeder.
- **Kohort:** Belirli bir kural setiyle (motor sürümüyle) üretilmiş sinyallerin tamamı.
  Motorun kuralları değiştiğinde yeni bir kohort başlar — eski kohortun performansı yeni
  kohortun karnesine karıştırılmaz (Bölüm 9'da detaylı).

### Net-R ve Komisyon Modeli
Bir işlemin **kâğıt üzerindeki** R'si ile **komisyon düşüldükten sonraki gerçek** R'si farklıdır.
Bot bu farkı ayrıca hesaplar (Bölüm 8'de detaylı).

---

# Bölüm 3 — Botun Mimarisi: Günlük Ritim

Bot, her işlem günü aynı ritmi izler. Bu ritmi anlamak, dashboard'da gördüğün "Son tarama",
"Gap Nöbeti" gibi ifadelerin ne anlama geldiğini çözer.

**[GRAFİK 8 — Botun Günlük Ritmi]**

## 3.1 15:45 — Hazırlık
Seans açılmadan önce bot üç şey yapar:
1. **Evreni günceller:** Midas'ta işlem gören ABD hisselerinin güncel listesini çeker, çok
   düşük fiyatlı veya çok düşük hacimli olanları eler (yaklaşık 1.600 hisseden ~300'e iner).
2. **Günlük analiz:** Kalan hisselerin trend ve rejim durumunu hesaplar.
3. **İlk izleme listesi:** En umut verici 20-40 hisseyi bir "izleme listesi"ne alır.

## 3.2 16:00-16:30 — Gap Nöbeti
Seans açılmadan hemen önceki bu pencerede bot, **açık pozisyonların** gece bir gap ile
stop'unu (veya hedefini) geçip geçmediğini kontrol eder. Bu, gece çıkan bir haberin sabah
pozisyonuna nasıl yansıdığını erkenden görmeni sağlar.

## 3.3 16:30-23:00 (TR saati) — Seans
ABD borsa seansı boyunca bot **iki hızda** tarama yapar:

- **Kaba Tarama (15 dakikada bir):** Tüm evreni (~300 hisse) yeniden tarar. Yeni oluşan
  fırsatları yakalar, izleme listesini tazeler.
- **İnce Tarama (~1 dakikada bir):** Sadece izleme listesindeki hisseleri, gerçek zamanlı
  fiyatla kontrol eder. Bir hissenin giriş seviyesi tam o an kırılırsa, sinyal **anında**
  üretilir ve Telegram'a düşer.

Bu iki kademeli yapının nedeni basit: 300 hisseyi saniyede bir kontrol etmek hem gereksiz hem
de veri kaynaklarının (API) limitlerini zorlar. Ama asıl fırsatların olduğu dar bir listeyi
sık sık kontrol etmek hem mümkün hem de anlamlıdır.

## 3.4 23:15 — Gün Sonu Raporu
Seans kapandıktan sonra bot bir özet çıkarır: o gün açılan/kapanan sinyaller, güncel karne,
SPY karşılaştırması, ertesi gün izlenecekler.

## 3.5 Pazar 21:00'den sonra — Haftalık Rapor
Haftanın toplam performansı, en iyi/en kötü işlem, gerçek paraya geçiş sayacındaki ilerleme.

---

# Bölüm 4 — Karar Hattı: Bir Sinyal Nasıl Doğar

Bu, kitabın kalbidir. Bot bir hisseyi değerlendirirken **9 basamaklı bir elemeli sistem**
kullanır. Her basamak bir soru sorar; cevap "hayır" ise hisse elenir ve bir sonraki basamağa
hiç geçilmez (buna **kısa devre** denir — gereksiz hesaplama yapılmaz).

**[GRAFİK 1 — Karar Hattı: 9 Basamaklı Elemeli Sistem]**

## 4.1 Basamak 1 — DATA (Veri Yeterliliği)
**Soru:** Bu hisse için yeterli geçmiş mum verisi var mı?

Yeni halka arz olmuş veya veri sağlayıcısında eksik kaydı olan hisseler burada elenir. Analiz
yapabilmek için önce analiz edilecek yeterli veri lazım — en temel, en can alıcı kontrol.

## 4.2 Basamak 2 — MARKET_REGIME (Piyasa Rejimi)
**Soru:** Genel piyasa şu an yükseliş mi, düşüş mü, yoksa kararsız mı?

Bot bunu **SPY** (S&P 500 endeks fonu) ve **QQQ** (Nasdaq 100 endeks fonu) üzerinden,
**200 günlük ortalama** ile ölçer:

- Fiyat, yükselen bir 200 günlük ortalamanın üstündeyse → **BULL** (yükseliş rejimi)
- Fiyat, düşen bir 200 günlük ortalamanın altındaysa → **BEAR** (düşüş rejimi)
- Diğer tüm durumlar → **NEUTRAL** (kararsız)

**Neden önemli?** Çünkü tek tek hisselerin çoğu, genel piyasa yönüne göre hareket eder.
BULL rejiminde **sadece LONG** sinyalleri üretilir; BEAR rejiminde **sadece SHORT.** NEUTRAL'da
her iki yön de üretilebilir ama eşikler sıkılaşır (daha seçici davranılır).

**Histerezis — piyasa "testere" yapmasın diye fren:** Ham bir 200 günlük ortalama kontrolü,
fiyat tam o çizginin etrafında dolaştığında rejimi gün be gün BULL-NEUTRAL-BULL diye
zıplatabilir. Bot bunu önlemek için bir **±%0,5'lik "gürültü bandı"** kullanır ve rejim
değişimi için **son 2 kapanışın da** bu bandın tamamen dışında olmasını ister.

**[GRAFİK 5 — Piyasa Rejimi Tespiti: 200 Günlük Ortalama + Histerezis Bandı]**

## 4.3 Basamak 3 — TREND (Hissenin Kendi Trendi)
**Soru:** Bu hisse kendi başına net bir trend içinde mi?

**LONG için:** Fiyat > 50 günlük ortalama > 200 günlük ortalama (ortalamalar doğru sırada) +
HH/HL yapısı (yükselen tepeler ve dipler).

**SHORT için:** Tam tersi — fiyat < 50 günlük ortalama < 200 günlük ortalama + LH/LL yapısı,
ayrıca hissenin göreceli gücünün de zayıf olması istenir.

Piyasa geneli iyi olsa bile (BULL rejimi), tek tek her hisse kendi başına yükseliş trendinde
olmayabilir — bu basamak o farkı ayıklar.

## 4.4 Basamak 4 — EARNINGS (Bilanço Takvimi)
**Soru:** Bu hissenin bilanço açıklaması yakın mı?

Şirketler çeyreklik olarak finansal sonuçlarını (bilançosunu) açıklar. Bu açıklamalar fiyatta
büyük, öngörülemez sıçramalara (gap'lere) yol açabilir — bilanço iyi gelirse fiyat sabah
%10 yukarı açılabilir, kötü gelirse %10 aşağı. Bu, teknik analizin **öngöremeyeceği** bir
risktir.

Bot, bilanço tarihine **±2 işlem günü** kala o hisse için sinyal üretmeyi durdurur. Amaç,
teknik bir kurulumun bir gecede haber riskiyle boşa çıkmasını engellemek.

## 4.5 Basamak 5 — SETUP (Giriş Yapısı) — İki Model
**Soru:** Şu an, saatlik grafikte, gerçekten "girilebilir" bir yapı var mı?

Bot iki farklı giriş modeli tanır:

### Model A: Trend İçi Geri Çekilme ("Pullback")
Hisse zaten net bir yükseliş trendindeyken, kısa süreliğine **yükselen 20 saatlik ortalamaya
doğru geri çekilir.** Bu geri çekilme sırasında RSI(3) "aşırı satım" bölgesine girer ve
ardından bir **dönüş mumu** (fiyatın tekrar yukarı dönmeye başladığını gösteren mum) oluşursa,
bu bir giriş fırsatı sayılır.

**Mantık:** "Trend hâlâ sağlam, sadece kısa bir soluklanma oldu; ucuza binme fırsatı."

**[GRAFİK 2 — SETUP Örneği A: Trend İçi Geri Çekilme (Pullback)]**

### Model B: Kırılım + Yeniden Test ("Breakout + Retest")
Hisse bir süre yatay bir bantta sıkışır (bir direnç seviyesinin altında). Sonra bu direnci
**hacimle birlikte yukarı kırar.** Kırılımın hemen ardından fiyat genellikle o eski direnç
seviyesine **bir kez daha dokunur** (artık destek olmuştur) — işte bu "yeniden test" anı
giriş fırsatıdır.

**Mantık:** "Yeni bir seviyeye geçiş oldu, piyasa bunu onaylıyor mu diye bir kez daha test
ediyor; onaylarsa devam eder."

**[GRAFİK 3 — SETUP Örneği B: Kırılım + Yeniden Test (Breakout + Retest)]**

**SHORT tarafında bu iki model aynen ayna görüntüsüyle çalışır** (düşen ortalamaya geri
sıçrama + RSI aşırı alım + dönüş mumu; veya bir destek seviyesinin kırılıp aşağı yönlü
yeniden test edilmesi).

## 4.6 Basamak 6 — VOLUME (Hacim Teyidi)
**Soru:** Bu hareketin arkasında yeterli işlem hacmi var mı?

Bir kırılım veya dönüş, düşük hacimle (yani az sayıda kişinin katılımıyla) gerçekleşiyorsa
güvenilirliği düşüktür — kolayca geri dönebilir. Bot, tetik mumunda **göreceli hacmin**
(o anki hacmin, o hissenin normal ortalama hacmine oranının) belirli bir eşiğin üstünde
olmasını arar. NEUTRAL rejiminde bu eşik daha da yükseltilir (daha seçici davranılır).

## 4.7 Basamak 7 — CONFLUENCE (Güven Puanı — Filtre Değil!)
Bu basamak diğerlerinden farklıdır: bir hisseyi **elemez**, sadece sinyalin **güven puanını**
(H/M/L) belirler. Üç şeye bakar:

1. **Göreceli güç sıralaması** — hisse, sektörüne/piyasaya göre ne kadar güçlü?
2. **Sektör ETF gücü** — hissenin ait olduğu sektör genel olarak güçlü mü?
3. **52 haftalık zirveye yakınlık** — hisse, son bir yılın en yüksek seviyesine yakın mı?
   (Yakınsa, "önünde satış baskısı yapacak eski yatırımcı" azdır — teknik olarak olumlu
   sayılır.)

## 4.8 Basamak 8 — RISK_REWARD (Risk/Ödül Yeterliliği)
**Soru:** Bu işlemin potansiyel kazancı, riskine ve maliyetine değer mi?

İki ayrı kontrol yapılır:
1. **RR oranı** belirli bir minimum eşiğin üstünde olmalı (yani hedef, riskin yeterince
   katı olmalı).
2. **Maliyet filtresi:** Hedef mesafesi, Midas'ın işlem başına sabit 1,50 dolarlık ücretini
   (gidiş-dönüş toplamda 3 dolar + kayma) anlamlı şekilde aşmalı. Çok küçük bir hareket
   hedefleniyorsa, kazanç komisyona gider — böyle sinyaller elenir.

## 4.9 Basamak 9 — SIGNAL (Nihai Çıktı)
Tüm basamaklar geçildiyse, bot artık somut bir sinyal üretir. Bu sinyal şunları içerir:

- **Giriş bölgesi** (bir fiyat aralığı)
- **Stop-Loss** seviyesi
- **TP1 ve TP2** hedefleri
- **RR oranı**
- **Güven etiketi** (H/M/L)
- **Zaman-stopu tarihi** (en geç ne zaman kapanacağı)
- **Gap uyarısı** (varsa)

Bu bilgi paketi Telegram'a gönderilir ve dashboard'a işlenir.

---

# Bölüm 5 — SHORT (Kısa) Pozisyonlar: Neden Daha Sıkı Kurallar?

ABD hisse senedi piyasasının **yapısal olarak yukarı eğilimli** olduğu, uzun vadeli, iyi
belgelenmiş bir gerçektir (ekonomik büyüme, şirket kârlarının uzun vadede artması gibi
nedenlerle). Bu, "aşağı yönlü bahisler"in (SHORT) istatistiksel olarak "yukarı yönlü
bahisler"den (LONG) daha dezavantajlı bir zeminde oynadığı anlamına gelir.

Bu yüzden bot, SHORT sinyalleri için **daha sıkı** eşikler kullanır:
- SHORT sinyalleri **yalnızca** MARKET_REGIME açıkça BEAR olduğunda veya hissenin düşüş
  yapısı son derece netken üretilir.
- Hacim ve göreceli zayıflık eşikleri LONG'a göre daha yüksek tutulur.

---

# Bölüm 6 — Portföy Risk Yönetimi: "Isı Motoru"

Tek bir sinyalin iyi olması yetmez — **birçok sinyalin aynı anda açık olması** kendi başına
bir risktir. Bunu somut bir örnekle açıklayalım:

> **Gerçek bir ders (30 Temmuz vakası):** Botun geliştirme sürecinde bir gün, piyasa genel
> olarak sert bir düşüş yaşadı. O gün açık olan pozisyonların neredeyse tamamı **aynı yöndeydi
> (LONG)** ve hepsi aynı gün doğmuştu — yani birbirinden **bağımsız değillerdi.** Piyasa
> düştüğünde hepsi birlikte, aynı anda zarar etti. Kayıp kendi başına sistemin "bozuk" olduğu
> anlamına gelmiyordu — sorun, çok fazla **korele** (birbirine bağlı) pozisyonun aynı anda
> açık olmasıydı.

Bu dersten sonra bot, **dört katmanlı bir "ısı motoru"** ile donatıldı:

**[GRAFİK 6 — Portföy Isı Motoru: Dört Kat Fren]**

| Sınır | Değer | Ne demek |
|---|---|---|
| Eşzamanlı toplam açık sinyal | 10 | Aynı anda en fazla 10 sinyal takip edilir |
| Günlük yeni sinyal | 6 | Bir günde en fazla 6 yeni sinyal üretilir |
| Aynı yönde eşzamanlı | 8 | Aynı anda en fazla 8 sinyal aynı yönde (hepsi LONG gibi) olabilir |
| Aynı kümede (yön+gün) | 3 | Aynı gün, aynı yönde doğan sinyallerden en fazla 3'ü aktif olabilir |

Bu tavanlardan biri dolduğunda, motor yeni bir sinyal **üretmeye devam eder** (veriye kaydedilir,
analiz için saklanır) ama o sinyal **takibe alınmaz ve Telegram'a bildirilmez.** Böylece
"tavanın bize maliyeti ne oldu" sorusu da ayrıca ölçülebilir — belki tavan bizi büyük bir
kayıptan korudu, belki de iyi bir fırsatı kaçırdık; veri birikince ikisi de görülebilir.

---

# Bölüm 7 — Maliyet Modeli ve "Net-R": Gerçek Kâr Neye Göre Ölçülür?

Bir işlemin kâğıt üzerindeki R'si ile cebine gerçekten giren R'si arasında bir fark vardır:
**komisyon.** Midas'ta her işlem **sabit 1,50 dolarlık** bir ücrete tabidir; bir alım + bir
satım (gidiş-dönüş) toplamda **3 dolar** eder, buna küçük bir **kayma (slippage)** payı da
eklenir (stop'a çarpıldığında fiyatın tam o seviyeden değil, biraz ötesinden gerçekleşme
ihtimali).

**Sezgiye aykırı ama önemli bir gerçek:** Çünkü bu ücret **sabittir** (yüzde değil), **dar
stoplu işlemler orantılı olarak daha pahalıya gelir.** Neden? Aynı miktarda dolar riski
almak için, stop'un dar olduğu bir işlemde çok daha **büyük bir pozisyon** almak gerekir —
ve komisyon, pozisyon büyüklüğüne (dolaylı olarak) bağlıdır.

**[GRAFİK 7 — Neden Dar Stop Bazen Daha "Pahalı"?]**

Bot bu yüzden her kapanan işlem için iki rakam tutar:
- **Brüt R:** Ham, komisyon düşülmemiş sonuç.
- **Net R:** Komisyon ve kayma düşüldükten sonraki gerçek sonuç.

Gerçek paraya geçiş kararı **her zaman Net R** üzerinden değerlendirilir — çünkü hesabına
gerçekten giren rakam odur.

---

# Bölüm 8 — Gölge Mod ve Gerçek Paraya Geçiş Kriteri

Gerçek paraya ne zaman geçilir? Bu kararın **duygularla değil, önceden yazılmış kurallarla**
verilmesi gerekir — yoksa "bugün moralim iyi, geçelim" ya da "üst üste 3 kayıp geldi, bu iş
olmuyor" gibi anlık kararlar devreye girer.

## 8.1 Yazılı Kriter (üçü birden sağlanmalı)
1. **En az 40 sonuçlanmış işlem** (kazanan/kaybeden/zaman-stopu ile kapanan — doldurulmamış
   sinyaller sayılmaz).
2. **Net beklenti ≥ +0,15R/işlem** (ortalama olarak her işlem, komisyon sonrası en az
   0,15R kâr getirmeli).
3. **Maksimum düşüş (drawdown) ≤ 8R** (kümülatif R eğrisinin zirvesinden en fazla 8R
   gerileme yaşanmış olmalı).

**[GRAFİK 9 — Örnek Kümülatif R Eğrisi ve Düşüş Ölçümü]**

## 8.2 Yanlışlama Kriteri (başarısızlığın da önceden tanımlanması)
Başarı gibi başarısızlık da önceden tanımlanmıştır: 40 işlemde net beklenti −0,10R'nin altına
düşerse veya düşüş 8R'yi aşarsa, gölge üretim **durdurulur** ve strateji yeniden gözden
geçirilir. "Belki biraz daha devam ederse düzelir" diye bir kurtarma denemesi **yapılmaz.**

## 8.3 Kohort Mantığı
Motorun kuralları her değiştiğinde (örneğin yeni bir filtre eklendiğinde), bu **yeni bir
kohort** başlatır ve sayaç sıfırdan başlar. Eski kuralların ürettiği sinyaller, yeni kuralların
karnesine karıştırılmaz — çünkü artık farklı bir sistemi değerlendiriyoruzdur.

---

# Bölüm 9 — Dashboard Kullanım Kılavuzu

Şimdi ekranda gördüğün her bölümü tek tek açıklayalım.

## 9.1 Üst Bar
- **CANLI** göstergesi ve saat bilgileri: NY (New York) ve TR (Türkiye) saatleri, seans
  durumu, verinin kaç saniye önce güncellendiği.
- **HESAP** düğmesi: Ayrıntılı bir kâr/zarar hesap makinesi açar (Bölüm 9.7).
- **Yenile:** Sayfayı manuel tazeler.

## 9.2 "Şu An En Acil" Şeridi
Dikkatini hemen gerektiren en öncelikli durumu gösterir — örneğin bir pozisyonun stop'u ihlal
etmiş olması.

## 9.3 Çıkış Nöbeti
Aksiyon gerektirebilecek açık pozisyonları listeler — örneğin stop'a çok yaklaşmış veya
hedefine çok yaklaşmış pozisyonlar.

## 9.4 Açık Pozisyonlar
Dolmuş (fiyattan girilmiş) tüm sinyalleri listeler: giriş, güncel fiyat, şu anki R durumu,
stop'a/hedefe uzaklık.

## 9.5 Bekleyen Sinyaller
Henüz giriş bölgesine gelmemiş, "izlemede" olan sinyaller.

## 9.6 Cüzdan
Bunlar bot sinyalleri **değil** — kendi elindeki hisseleri (ve Midas'ta işlem gören ETF'leri)
kişisel takip etmen için. Sembolü ara, adet + giriş fiyatını gir; canlı fiyat, maliyet, güncel
değer ve kâr/zararını (istersen bir satış hedefiyle "hedefte net kâr/zarar"ı da) gör. Bu veri
sadece senin cihazında saklanır.

## 9.7 Kâr/Zarar Hesaplayıcı
Bir sinyal seçip "Seçili sinyalden doldur" dersen alanlar otomatik dolar; ya da elle
hesap büyüklüğü, risk yüzdesi, giriş/stop/hedef gir. Çıktılar: alınacak adet, pozisyon
değeri, riske edilen tutar, stop/hedef durumunda net kâr-zarar, R/R oranı, başabaş fiyatı.
Üst bardaki **HESAP** düğmesi, LONG/SHORT seçimi ve iki yönlü mod (riskten adede veya
adetten riske) sunan daha kapsamlı bir modal açar.

## 9.8 Bot Karnesi
Dört ölçüte göre bir hüküm verir (Pozitif beklenti / SPY'yi geçiyor / Kazanç>kayıp /
Yeterli örneklem) ve toplam R'yi (brüt ve net) gösterir.

## 9.9 Haber Akışı, Geçmiş, Gap Nöbeti, Durum & Log
Sırasıyla: izlenen hisselerle ilgili haberler; kapanmış işlemlerin dökümü; sabah gap
kontrolünün özeti; sistem sağlığı (uyarı/hata sayaçları, son tarama zamanı).

---

# Bölüm 10 — Sık Sorulan Sorular

**S: Bot benim adıma otomatik emir veriyor mu?**
Hayır. Hiçbir zaman. Her emri sen, Midas uygulamasından elle veriyorsun.

**S: Neden bazı günler hiç sinyal yok?**
Piyasa rejimi NEUTRAL veya BEAR'daysa (ve hisseler net bir yapı sunmuyorsa), bot sinyal
üretmemeyi tercih eder. "Her gün mutlaka bir şey bulmak" bir hedef değildir; kaliteyi
düşürmemek hedeftir.

**S: Rejim neden bazen "UNKNOWN" görünüyor?**
Hafta sonu/tatil günlerinde veya endeks verisi geçici olarak alınamadığında bot güvenli
tarafta kalır ve rejimi belirsiz sayar — bu durumda sinyal üretimi de durur.

**S: Bir sinyal "TUT" diyor, bu ne demek?**
Pozisyon henüz ne stop'a ne hedefe yakın; mevcut haliyle beklenmesi gerektiği anlamına gelir.

---

# Bölüm 11 — Sözlük (A'dan Z'ye)

- **ATR:** Ortalama Gerçek Aralık; bir hissenin günlük tipik oynaklık ölçüsü.
- **BEAR / BULL / NEUTRAL:** Piyasa rejimi durumları (düşüş / yükseliş / kararsız).
- **Breakout + Retest:** Bir direncin kırılıp hemen ardından o seviyenin destek olarak
  yeniden test edilmesi.
- **Cluster (Küme):** Aynı gün + aynı yönde doğan, birbirinden istatistiksel olarak bağımsız
  olmayan sinyaller grubu.
- **Confidence (Güven):** Sinyalin H/M/L güven etiketi.
- **Dolar Hacmi:** Günlük işlem gören hisse adedi × fiyat; likidite ölçüsü.
- **Entry Zone (Giriş Bölgesi):** Sinyalin önerdiği giriş fiyat aralığı.
- **Gap:** Önceki kapanış ile bugünkü açılış arasındaki ani fiyat sıçraması.
- **Histerezis:** Rejim tespitinde ani zıplamaları önlemek için kullanılan "gürültü bandı".
- **Kohort:** Belirli bir motor kuralı setiyle üretilmiş sinyallerin bütünü.
- **Likidite:** Bir hissenin kolay alınıp satılabilme derecesi.
- **LONG:** Fiyatın yükseleceğine dayalı alım pozisyonu.
- **MA (Moving Average):** Hareketli ortalama.
- **Net-R:** Komisyon/kayma düşüldükten sonraki gerçek R sonucu.
- **Pullback:** Yükselen trend içinde yaşanan kısa geri çekilme.
- **R:** Riskin evrensel ölçü birimi (Bölüm 2'de detaylı).
- **Rejim (Regime):** Genel piyasanın BULL/BEAR/NEUTRAL durumu.
- **RR (Risk/Ödül):** Hedeflenen kazancın riske oranı.
- **RSI:** Göreceli Güç Endeksi; aşırı alım/satım ölçüsü.
- **SHORT:** Fiyatın düşeceğine dayalı satış pozisyonu.
- **SetUp:** Saatlik grafikte tespit edilen giriş yapısı (pullback veya breakout+retest).
- **Stop-Loss:** Zararı sınırlamak için belirlenen çıkış seviyesi.
- **Take-Profit (TP1/TP2):** Kâr almak için belirlenen hedef seviyeleri.
- **Zaman-Stopu:** Bir pozisyonun en geç kaç işlem gününde kapatılacağı.

---

# Sorumluluk Reddi

Bu kitap ve bahsi geçen bot, **yatırım tavsiyesi değildir.** Botun ürettiği hiçbir sinyal,
"al" veya "sat" emri anlamına gelmez; sadece belirli kurallara göre tespit edilmiş bir teknik
gözlemdir. Geçmiş performans (gölge mod dahil) gelecekteki sonuçların garantisi değildir.
Kendi araştırmanı yap, riskini kendin değerlendir.
