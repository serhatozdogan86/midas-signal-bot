# Araştırma Günlüğü ve Hipotez Kuyruğu

Amaç: fikirleri tartışmayla değil **ölçümle** kapatmak, ve kapanmış
soruların bir daha açılmaması. Her satır: hipotez → önceden yazılmış
karar kuralı → sonuç → karar.

## Yöntem kuralları (bunlar tartışmaya kapalı)
1. Hipotez ve karar kuralı **ölçümden ÖNCE** yazılır.
2. Parametre optimize edilmez; literatürdeki kanonik değer kullanılır.
   (Optimize edersek "geçmişe en iyi uydurulanı" ölçmüş oluruz.)
3. Anlamlılık **portföy düzeyinde Newey-West** ile; ham t şişkindir.
4. Eşik: |t| > 2 **ve** iki alt dönemde aynı işaret.
5. Her yeni test çoklu karşılaştırma riskini artırır → canlıya alınan
   varyant sayısı sınırlı tutulur (şu an 4 çıkış + 5 giriş).
6. Backtest **kanıt değil ipucudur**; karar canlı kohorttan verilir.

## Kapanmış sorular

| Tarih | Hipotez | Sonuç | Karar |
|---|---|---|---|
| 03-08 | Kesitsel momentum 12-1 edge taşır | 5g +0.86% t=3.30; 20g +2.64% t=3.39; iki yarıda tutarlı | **KABUL** → S1/S5 adayı |
| 03-08 | Bizim giriş vekilimiz edge taşır | 5g +0.10% t=0.51 | RED (kanıtlanmadı) |
| 03-08 | Donchian kırılımı | t≈0 | RED |
| 03-08 | RSI(2) dönüş | 5g t≈0.3 | RED |
| 03-08 | 52-hafta zirvesi | negatif | RED |
| 03-08 | Rezidüel stat-arb (SPY'a göre) | −0.41% t=−2.60 (ters yönde anlamlı) | RED |
| 03-08 | SMC likidite avı | 5g +0.05% t=0.64 | ETİKET (karara girmez) |
| 04-08 | Hacimli kırılım | 20g +1.58% t=1.98 (sınırda) | BEKLEMEDE |
| 04-08 | Kalman trend/eğim/dönüş | 5g −0.21% t=−2.11 | RED |
| 04-08 | Kalman çift işlem (dinamik hedge) | trans_cov'a aşırı duyarlı: 1e-5 → +7.2%/yıl, 1e-3 → −10.8%/yıl | RED (ayara uydurma riski + short bacağı gerekiyor) |
| 04-08 | Wyckoff spring | 20g +0.73% t=1.50 | RED |
| 04-08 | Wyckoff no-supply | 5g −0.20% t=−1.74 | RED |
| 04-08 | Wyckoff absorbsiyon | 20g +0.99% t=0.97, n=263 | ETİKET (ölçülemedi, veri az) |
| 04-08 | Çıkış tasarımı girişten daha mı önemli? | Aynı girişlerle: hedefi kaldırmak +48.5R→+151.5R; süre 4→10 gün +315R | **CANLI ÖLÇÜME** → V2/V3 |
| 04-08 | Portföy tavanı zararlı mı? | Tavan+kaliteli seçim, tavansızdan İYİ (Donchian −787R→+11.8R) | RED (tavan kalsın, seçim kaliteye göre) |

## Açık kuyruk (sıradaki hipotezler)

| Öncelik | Hipotez | Karar kuralı | Durum |
|---|---|---|---|
| 1 | Hedefsiz çıkış (V3) canlıda V0'ı geçer | 60 işlem/25 küme; hem toplam hem beklenti + iki yarı tutarlı | ÖLÇÜLÜYOR |
| 7 | Gölge dolum zamanlaması sonucu değiştiriyor (FTNT vakası, 17 Ağu) | Ayna dönemi sonunda (28 Ağu + ≥20 çift): gölge/ayna sonuç UYUŞMAZLIĞI oranı ve yönü raporlanır; uyuşmazlık ≥ %25 ise dolum modeli karar toplantısına taşınır | AYNA ÖLÇÜYOR |
| 8 | ATR iz-süren çıkış (V4) sabit-hedefli V0'ı geçer — ÖN-KAYIT 17 Ağu, perakende araştırması + "çıkış > giriş" bulgusu; iki botun bağımsız araştırması kesişti | V4 = hedefsiz, stop = izlenen en yüksek kapanış − 3.0×ATR(14), yalnız lehte yönde hareket eder, time-stop V0 ile aynı. exit_lab'e eklenir, V0-V3 ile AYNI sinyal kümesinde ölçülür. Karar v3.19 simetriği: V4 hem toplam net-R hem beklenti olarak V0'ı geçmeli VE işaret iki yarı dönemde tutarlı olmalı (60 işlem / 25 küme dolunca) | KODLANACAK (salt ölçüm) |
| 9 | Volatilite sıkışması kırılımı (Squeeze, S6 adayı) pozitif beklenti taşır — ÖN-KAYIT 17 Ağu; TradingView'ın en beğenilen mekanizması + volatilite kümelenmesi literatürü; bybit araştırmasının da 1. tercihi | Tanım: BB(20,2) bantları KC(20,1.5) İÇİNE girince "sıkışık"; sıkışma ≥6 bar sürüp fiyat sıkışma aralığının üstünde kapatınca LONG tetik; stop aralığın alt ucu; RR/maliyet filtreleri mevcut kurallarla. Önce research/ 2y backtest: ≥100 işlem VE net beklenti > 0 VE iki yarı tutarlı VE tavansız kıyasta S1-S5 arasında ilk 3 → strategy_lab'e S6; aksi RED ve günlüğe | DÜZENEK HAZIR — VERİ BEKLİYOR (24 Ağu) |
| 10 | Açılış aralığı (OPENING_RANGE) fazında doğan sinyaller sistematik olarak daha kötü — ÖN-KAYIT 18 Eyl; F1 raporunda 14 işlem −12,24R, kazanma %7,1 (toplam zararın ~yarısı tek fazdan) ama n küçük ve karar kuralı YOKTU | Faz başına net-R ve kazanma oranı; n ≥ 30 dolunca okunur. OPENING_RANGE net beklentisi diğer fazların ortalamasından **en az 0,30R düşük** VE kendi içinde negatif ise → KİLİT-3'te "açılış aralığında sinyal üretme" penceresi gündeme alınır (v3.9 açılış penceresi freninin GENİŞLETİLMESİ olarak). Aksi halde RED ve günlüğe. n < 30 iken yorum YAPILMAZ | VERİ BİRİKİYOR |
| 2 | Momentum üst dilimindeki sinyaller daha iyi | mom_pct üst/alt yarı karşılaştırması, n≥40 | VERİ BİRİKİYOR |
| 3 | Oynak hisselerdeki sinyaller daha iyi | atr_rank üst/alt yarı, n≥40 | VERİ BİRİKİYOR |
| 4 | Absorbsiyon etiketi taşıyanlar daha iyi | etiketli vs etiketsiz, n≥30 | VERİ BİRİKİYOR |
| 5 | Short tarafı zarar veriyor | short kohortu net-R < 0 ve n≥20 → short kapatılır | VERİ BİRİKİYOR |
| 6 | Sektör yoğunlaşması riski | aynı sektörde >3 açık pozisyon oranı | ÖLÇÜLMEDİ |

## Reddedilmiş yaklaşımlar (tekrar açılmasın)
- **Order book / L2 stratejileri**: veri yok, ölçülemez.
- **MCP finans bağlayıcıları** (FactSet/Morningstar/LSEG): kurumsal
  lisans + MCP≠REST; bot 7/24 kendi başına çalışır, sohbet içi
  bağlayıcı kullanamaz.
- **Bloomberg terminal klonu (repo)**: Next.js/Redis yığını + veri
  katmanı `Math.random()` ile simüle fiyat üretiyor.

## Saha gözlemi: FTNT — aynı sinyal, iki defterde iki ayrı işlem (2026-08-17)
Sinyal 14 Ağu 13:30 mumunda doğdu. AYNA (gerçek zamanlı): 13:46'da
164.04'ten doldu, 14:17'de 159.16'dan STOP — giriş mumunun İÇİNDE stop
seviyesi zaten kırılmıştı (mum dibi 159.10 < stop 159.3335). GÖLGE (mum
tabanlı): bir SONRAKİ mumdan 161.50 ile doldu, Cuma boyunca stop'a hiç
değmedi (Cuma dibi 159.61), Pazartesi açılış boşluğunda stop → −1.0R.
Aynı sinyal, iki farklı giriş anı, iki farklı fiyat, iki farklı gün.
Ders: gölge defterin "sonraki mum" dolum modeli yalnız FİYATI değil
İŞLEMİN KENDİSİNİ de değiştirebiliyor. Bu tek vaka hüküm değildir —
hükmü hipotez #7'nin karar kuralı verecek (ayna dönemi sonu).

## Perakende motor araştırması — kesişim kaydı (2026-08-17)
İki bağımsız araştırma (bu oturum + bybit oturumu, aynı soru) kesiştirildi:
- ÇİFTE ONAY: volatilite sıkışması kırılımı (Squeeze) — iki listenin de
  tepesinde. Hipotez 9 olarak ön-kayıtlı.
- MIDAS ÖNCELİĞİ: ATR iz-süren çıkış — bybit'te "kenara not" (çıkış
  laboratuvarı yok), bizde 1. sıra (exit_lab hazır + "çıkış > giriş"
  ölçülmüş bulgusu). Hipotez 8 olarak ön-kayıtlı.
- ORTAK RED: SMC/ICT ailesi (bizim ölçümle reddimizle örtüştü), UT
  Bot/QQE/Ichimoku/SuperTrend-giriş (S1/S2 ambalajı), grid/martingale
  (MQL5'in en çok satan robotu gizli martingale; tek ayda %70 erime),
  Lorentzian ML (test edilemez kara kutu — ön-kayıt disiplinine aykırı).
- KUYRUK: çapalı VWAP pullback (H-C) ve seçim kuralı deneyi (H-D +
  "olağandışı günlük hacim" kapısı, bybit 2. tercihiyle birleşik) —
  karar kuralları sıra geldiğinde yazılacak.
- DERS (iki araştırma da aynı sonuca vardı): "en çok satan" listesi
  alışveriş listesi değil TUZAK HARİTASIDIR; pazarlama gücü kârlılık
  kanıtı değildir. Kaynak raporu bybit deposunda:
  docs/perakende-arastirmasi-2026-08-17.md.

## Saha bulgusu: aynı giriş, %19.8 net-R korelasyonu (2026-08-18)
İlk canlı korelasyon raporu: S1 ve S5 GİRİŞİ birebir paylaşır
(same_day_signal = 1.000, 32/32 gün — aletin öz-doğrulaması geçti) ama
günlük net-R korelasyonları yalnız **0.198**. Tek fark çıkış kuralı
(S1→V0 tarzı, S5→V2 geniş). Yani aynı girişten doğan iki stratejinin
kâr eğrileri neredeyse bağımsız: **P&L'i giriş değil ÇIKIŞ belirliyor.**
"Çıkış tasarımı girişten önemli" bulgusunun ÜÇÜNCÜ bağımsız kanıtı
(1: tarama backtest'i +48.5R→+151.5R; 2: iki botun perakende araştırması
kesişimi; 3: bu canlı ölçüm). Diğer değerler: N_eff 3.21, ort. korelasyon
0.139, en yüksek çift S2|S3 = 0.631 (aynı-gün örtüşme %74.6). Karar
üretilmedi — V4/V0 kıyası kendi önceden yazılmış kuralıyla sürüyor.

## F6 düzeneği: S6 Squeeze backtest'i kuruldu (2026-08-24)
Hipotez 9'un ölçüm düzeneği yazıldı; **sonuç henüz YOK** — bulut
oturumunun ağı piyasa verisine kapalı (Yahoo CONNECT 403), backtest'i
ağı olan oturum koşacak. Kurulan parçalar:
- `research/strategies.py::squeeze_breakout` — tanım ön-kayıttan aynen
  (BB(20,2) ⊂ KC(20,1.5), ≥6 bar, aralık üstü kapanış). Look-ahead yok,
  aynı sıkışmadan tek sinyal. Davranış testleri:
  `tests/test_research_squeeze.py` (mutasyonla kırılabildiği ölçüldü:
  spam koruması kaldırılınca 1→3 sinyal, look-ahead enjekte edilince
  tetik kayıyor).
- `research/harness.py::verdict_h9` — dört şartlı karar kuralı KODDA.
  `tests/test_research_h9_verdict.py` altı senaryoyla kilitliyor
  (n eşiği, negatif beklenti, tek yarıdan gelen kâr, sıralamada 4.'lük).
- `research/data.py` — veri artık depo içinden üretilebiliyor. Eski
  düzenek `/home/claude/bt/*.pkl` okuyordu; o geçici analiz ortamı
  kapandığı için harness **koşulamaz** durumdaydı (24 Ağu'da fark
  edildi). Ölçüm aleti yeniden üretilemiyorsa ölçüm de yeniden
  üretilemez — bu, kayıt altına alınacak bir kusurdu.
- YORUM ÖN-KAYDI (sonuca bakılmadan, 24 Ağu): ön-kayıttaki "S1–S5
  arasında ilk 3" sıralaması **net beklenti (R/işlem)** üzerinden
  okunur; toplam R yalnız bilgi olarak raporlanır. Gerekçe: depoda
  headline ölçü her yerde beklentidir. Bu not, sonuç geldiğinde
  "hangi sıralamayı kullansam geçerdi" oynamasını kapatır.
Bir sonraki adım: ağı olan oturumda `python3 -m research.data --years 2`
+ `python3 -m research.run`, çıktı bu günlüğe hüküm olarak yazılır.

## F6 HÜKÜM: Hipotez 9 (S6 Squeeze) — **RED** (2026-08-24)
2 yıllık günlük backtest (167 sembol, 500 gün, LONG+SHORT, ortak çıkış
mekaniği) koşuldu. Ön-kayıtlı dört şarttan ikisi tutmadı:

| Şart | Sonuç | |
|---|---|---|
| işlem ≥ 100 | 802 | ✅ |
| net beklenti > 0 | **−0.044R** | ❌ |
| iki yarı tutarlı | ikisi de negatif | ✅ |
| S1–S5 içinde ilk 3 | 6'da **5.** | ❌ |

S6 strategy_lab'e ALINMAZ. TradingView'ın en beğenilen mekanizması,
bizim evrenimizde ve bizim çıkış mekaniğimizle para kazandırmıyor.
Perakende araştırmasının dersi ("en çok satan liste = tuzak haritası")
bir kez daha, bu kez kendi verimizle doğrulandı.

**İkinci yarı uyarısı — bilerek dikkate ALINMADI.** S6'nın ikinci yarısı
belirgin şekilde daha iyi (−0.083R → −0.005R, isabet %49.4 → %55.4) ve
"düzeliyor, bir şans daha" demek çok kolay olurdu. Ön-kayıtlı kuralın
varlık sebebi tam olarak bu an: şart "net beklenti > 0" idi, "ikinci
yarıda iyileşiyor mu" değil. Kural sonuca bakılarak gevşetilirse
ön-kayıt anlamını kaybeder. RED, RED'dir. (İyileşme merak konusu olarak
kalır; istenirse AYRI ve ÖNCEDEN yazılmış bir hipotezle sorulur.)

### Asıl bulgu S6 değil, tablonun tamamı
| strateji | işlem | beklenti_R | toplam_R | maxDD_R |
|---|---|---|---|---|
| 4_REZIDUEL_STATARB | 4774 | **+0.005** | +22.8 | 143.8 |
| 3_RSI2_DONUS | 4481 | −0.001 | −4.1 | 122.7 |
| 5_52H_ZIRVE | 1506 | −0.008 | −12.7 | 78.6 |
| 2_KESITSEL_MOMENTUM | 1551 | −0.036 | −56.5 | 87.5 |
| 6_SQUEEZE_KIRILIM | 802 | −0.044 | −35.3 | 42.8 |
| 0_BIZIM_VEKIL | 858 | −0.050 | −42.6 | 66.4 |
| 1_DONCHIAN_KIRILIM | 10506 | −0.068 | −717.0 | 727.8 |

Yedi stratejiden altısı negatif; tek pozitif (+0.005R) 143.8R geri
çekilmeyle gürültüden ayırt edilemez. Üstüne düzeneğin kendi uyarısı
var: evren BUGÜNKÜ liste, yani hayatta kalma yanlılığı tüm LONG
tarafını YUKARI çekiyor — gerçek rakamlar bu tablodan daha kötü.
Yani "en iyi" S4 bile büyük olasılıkla sıfırın altında.

**Bu tablo canlı defteri doğruluyor.** Motorun günlük vekili
(0_BIZIM_VEKIL) −0.050R veriyor; canlı gölge defter de negatif beklenti
gösteriyor. İki BAĞIMSIZ ölçüm aynı yöne işaret ediyor: 20 Ağustos
yanlışlanması şanssızlık değil, kurulumun kendisiyle ilgili. KİLİT-3
tasarımı bunu veri olarak almalı — F1 (zarar anatomisi) ve F7 (seçim
kuralı) bu tablonun ışığında okunacak. Not: bu düzenek GÜNLÜK mumla ve
ortak ATR çıkışıyla çalışır; canlı motor 1s setup + kendi çıkışını
kullanır, yani vekil birebir motor değildir — yön göstergesidir, hüküm
değil.

## Araştırma evreni canlı evrenden ayrışmış (2026-08-24, F6 yan bulgusu)
İlk koşumda iki sembol veri getirmedi ve ikisi de "borsadan kalkmış"
DEĞİLDİ:
- **BRK.B** — biçim hatası. Yahoo nokta değil tire ister (BRK-B).
  Üretim bunu 30 Tem'de zaten çözmüştü (`YFinanceClient._to_yahoo`);
  araştırma katmanı kendi veri yolunu yazdığı için **çözülmüş bir hata
  geri geldi**. Ders paralel uygulamayla ilgili: aynı işi iki yerde
  yazarsan, birinde öğrendiğini diğerinde yeniden öğrenirsin.
- **SQ** — gerçekten bayat. Block Inc. sembolünü XYZ yaptı; canlı
  scrape zaten XYZ getiriyordu, bayat olan yalnız statik YEDEK listeydi.

Yapılan: (1) `research/data.py` artık üretimin sembol kuralını yeniden
kullanıyor ve evreni önce **canlı evren önbelleğinden** alıyor (statik
liste yalnız yedek); (2) statik listede SQ → XYZ; (3)
`tools/universe_drift.py` — yedek liste ile canlı evreni karşılaştıran
salt-okur denetçi (haftalık bakım adımı, kayma varsa çıkış kodu 1);
(4) `tests/test_universe_drift.py` (9 test, mutasyonla kırılabilirliği
ölçüldü).

Bu koşumdaki etkisi küçüktü (170'te 2 sembol) ve RED kararını
değiştirmez — S6 beklentide geniş farkla eleniyor. Ama yedek liste
ancak scrape VE cache birlikte çöktüğünde devreye girer: yani en kötü
günde. O gün bayat listeyle çalışmak, "yedeğim var" sanıp yedeksiz
kalmaktır. Bulgu, `research/data.py`'ın eksik sembolü ekrana yazdığı
için yakalandı (ilke 2.1 işini yaptı).

## F7 düzeneği: portföy katmanı + seçim kuralı (2026-09-08)
**Sonuç YOK — düzenek kuruldu, karar kuralı önceden yazıldı.**

Bulgu 3 ("portföy tavanı zararlı değil; seçim kuralı belirleyici —
kaliteye göre seçim Donchian'ı −787R'den +11.8R'ye taşıdı") kapanmış bir
analiz ortamında ölçülmüştü, yani **yeniden üretilemiyordu**. F6'da aynı
dersi almıştık: ölçüm aleti yeniden üretilemiyorsa ölçüm de üretilemez.
Artık depo içinde: `research/portfolio.py`.

Ne yapıyor: harness'ın "her sinyale gir" dünyası yerine gerçek kısıtı
uyguluyor — günlük ≤6 yeni giriş, eşzamanlı ≤10 açık pozisyon (canlı
botla aynı; tavanlar **değiştirilmiyor**). Aynı işlem havuzunu iki
dünyada koşuyor: adaylar 12-1 momentum yüzdeliğine göre **sıralanarak**
seçildiğinde, ve sıralama olmadan (ilk-gelen). Elenen işlem silinmiyor,
işaretleniyor — kaçan kazanç da ölçülebilsin.

ÖN-KAYITLI KARAR KURALI (sonuçlara bakılmadan): dördü birden gerekli —
(1) seçilen işlem ≥100, (2) seçimli beklenti > taban, (3) işaret iki
yarı dönemde tutarlı, (4) **en az iki stratejide** iyileşme.

Dördüncü şart bilerek sert: bulgu 3 tek strateji üzerinden doğmuştu.
Tek stratejide çıkan fark, o stratejinin kendine özgü davranışı
olabilir; genellenebilirliği ayrı bir sorudur ve şimdi soruluyor.

9 test; üç mutasyon yakalandı (eşzamanlı tavanı devre dışı bırakma,
sıralamayı yapmama, "iki strateji" şartını bire düşürme).

## F1 İLK ÖLÇÜM: "neden kaybediyoruz" (2026-09-18, VM koşumu)

96 kapanan kayıt / 78 dolum / 39 ölçülebilir zarar.

**Q1 (giriş mi çıkış mı) → KARIŞIK.** Medyan MFE ön-kayıtlı iki eşiğin
arasında kaldı, yani kural gereği **tek hüküm verilmiyor**. Bu bir
başarısızlık değil, beklenen sonuçlardan biri: zararlar tek cins değil.
Bir kısmı hiç kâra geçmemiş, bir kısmı 1,5–3,9R'ye ulaşıp geri vermiş
(CIEN, TMO, QCOM, DE, TGT). Ortalama bu iki cinsi tek sayıya eziyor.

→ Devamı koda yazıldı: `q1_arms` iki kolu ayrı sayar (soğuk ≤0,3R /
ara / sıcak ≥0,8R — **Q1'in kendi eşikleri, yeni eşik uydurulmadı**) ve
**pay + toplam R** olmak üzere iki şarta birden bakar. Okuma kuralı kol
payları görülmeden yazıldı (18 Eyl): sıcak pay ≥%40 VE zararın
yarısından fazlasını taşıyorsa → iz süren çıkış/kısmi kâr tasarımı
KİLİT-3 gündemine (F3 ile birleşir); pay ≤%20 → giriş/seçim baskın
(F7 öne çıkar); arada → iki kol da ayrı madde, tek "suçlu" ilan
edilmez.

**Q2 setup:** breakout_retest 58 işlem −11,39R (kazanma %24);
trend_pullback 20 işlem. İkisi de KİLİT-3 incelemesine bayraklandı.

**Q3 short: n = 0.** Beklenen bulgu bu değildi. Short tarafı *zarar
ettirmiyor* — **hiç işlem üretmiyor**. 78 dolumun tamamı LONG. Açık
kuyruk md. 3'ün ("short kapatılsın mı") cevabı bu kohort için
"kapatılacak bir şey yok"tur; soru **neden hiç short doğmadığına**
dönüşür (rejim BULL → trend filtresi short'u geçirmiyor olabilir).

**Bu tablonun en rahatsız edici cümlesi:** yükselen piyasada
(rejim BULL, 53 işlem), yalnızca LONG tarafta, −25,74R'deyiz. Yani
kaybı "yanlış yöne oynadık" veya "piyasa düştü" ile açıklayamıyoruz.

**Veri boşluğu:** 25 işlemin rejimi kayıtlı değil (contract_json'da
market_regime yok — muhtemelen alan eklenmeden önce doğan kayıtlar).
Düzeltilmez, not düşülür; rejim kırılımı bu dipnotla okunur.

**Q4 gözlemi ve yeni ön-kayıt:** OPENING_RANGE fazı 14 işlemde
−12,24R, kazanma %7,1 — toplam zararın kabaca yarısı tek fazdan.
Karar kuralı YOKTU, dolayısıyla bugün hüküm de yok. Hipotez 10 olarak
ön-kayda alındı (n ≥ 30, eşik: diğer fazların ortalamasından ≥0,30R
düşük VE kendi içinde negatif).

## F1 İKİ KOL ÖLÇÜMÜ (2026-09-20, VM koşumu) — hüküm ARADA, ama sınırda

39 ölçülebilir zarar, medyan MFE **0,44R**:

| kol | işlem | okuma |
|---|---:|---|
| soğuk (MFE ≤ 0,3R) | 15 | hiç çalışmadı |
| ara (0,3–0,8R) | 16 | kıpırdadı, tutmadı |
| **sıcak (MFE ≥ 0,8R)** | **8** | çalıştı, hepsini geri verdi |

**ÖN-KAYITLI HÜKÜM: ARADA** — iki kol da KİLİT-3 gündemine ayrı madde
olarak girer, tek "suçlu" ilan edilmez.

### Hükmün kırılganlığını kendimiz ilan ediyoruz
Sıcak kolun payı **%20,5** (8/39); kuralın "giriş/seçim baskın" eşiği
**≤%20**. Aradaki fark **tek bir işlem**: 7/39 olsaydı (%17,9) hüküm
"GİRİŞ/SEÇİM BASKIN" çıkacaktı. Kural ön-kayıtlıydı ve dürüstçe
uygulandı — hüküm geçerlidir — ama dayanak diye sunulamaz. Bu, ayna
anatomisindeki 0,002'lik sınır vakasının ikinci örneği; ölçü tasarımı
eşiğe yakın sonuçlar üretmeye yatkın, örneklem büyüyene kadar hükümler
**yön işareti** sayılacak.

### Yön işareti nereyi gösteriyor
Hüküm "arada" olsa da üç bağımsız ölçüm aynı yöne bakıyor:
1. Sıcak kol, zararların en fazla **beşte biri** (8/39, ~8R / 25,74R).
   Yani mükemmel bir çıkış tasarımı bile kaybın çoğunu kurtaramaz.
2. Çıkış laboratuvarının **beş varyantı da negatif** (−22,6 … −64,3R),
   en iyisi hâlâ canlı V0. "Kârı koru" (V1 kısmi kâr), "stop'u genişlet"
   (V2), "hedefi kaldır" (V3), "iz sür" (V4) — hepsi ölçüldü, hiçbiri
   kurtarmadı. Sıcak kolun karşı-olgusu **zaten ölçülmüş**.
3. F6 backtest tablosu: yedi stratejiden altısı negatif, motorun günlük
   vekili −0,050R.

Sonuç cümlesi (hüküm değil, yön): **kayıp esas olarak bir çıkış sorunu
değil.** Ağırlık seçim/giriş tarafına kayıyor → F7 öne alınır.

### Q2: bayrak tek setupta değil, HEPSİNDE
trend_pullback −14,35R ve breakout_retest −11,39R — ikisi de KİLİT-3
incelemesine gitti. Yani "şu bir setup bozuk" diyemiyoruz; roster'ın
tamamı negatif. F6'nın "yedide altısı negatif" tablosuyla aynı şekil.

### Sıcak kolun kimliği
8 işlemin hepsi tam −1R: CTVA, SHW, CIEN, TMO, QCOM, DE, TGT, PSX.
Yani ≥0,8R kâra ulaşıp **stop'a kadar** geri verdiler — kısmi kâr veya
iz süren stop bunları kurtarırdı. Ama (2) gereği o karşı-olgu ölçüldü
ve kazandırmadı; tek tek vakaların çekiciliğine kapılmıyoruz.

## F7 İLK KOŞUM (2026-09-21) — hüküm eksik uygulanmıştı, tamamlandı

İlk koşumun çıktısı "ADAY" dedi. **O hüküm geçersiz sayılmalı** — çünkü
dört şartın yalnız ikisi (örneklem + iki-strateji) hesaplanıyordu;
2. şart (tabana üstünlük) ve 3. şart (iki yarı tutarlılığı) hiç
ölçülmüyor, "ayrıntıya bak" deniyordu. Kural doğruydu, **uygulaması
eksikti**; yerel oturum bunu doğru tespit etti.

Tamamlandı (21 Eyl): `compare` artık iki yarı dönemin farkını da
döndürür, `verdict_f7` dördünü birden ölçer ve "ADAY" diye bir ara
sonuç YOK — ya geçer ya RED.

**Koşul 2'nin okunuşu — belirsizliği açıkça ilan ediyorum.** 8 Eylül
metni "seçimli beklenti > taban" diyor ama çok stratejili kurulumda
*hangi* beklenti olduğu yazılmamış. 21 Eylül'de sabitlenen okuma:
**strateji başına farkların ortalaması > 0**. Gerekçe: tek bir
stratejiyi (örneğin kendi vekilimizi) seçip sonucu istenen yöne çevirme
imkânı kalmasın. Alternatif okuma (iyileşen sayısı > kötüleşen sayısı)
da her koşumda **ayrıca raporlanır** — böylece "hangi okumayla geçerdi"
sessizce seçilemez.

### İlk koşumun ham verisi (hüküm yeniden koşulacak)
- İyileşen: 2 KESİTSEL MOMENTUM, 3 RSI2, 4 REZİDÜEL STATARB
- Kötüleşen: 1 DONCHIAN belirgin şekilde (−34,5 → −71 R)
- Botun kendi vekili: −0,057 → −0,040 R (iyileşti ama **hâlâ negatif**)
- Tek pozitif kalem: KESİTSEL MOMENTUM +0,070 (tabanı −0,075)
- Yanlılık hatırlatması: evren bugünkü listeden, hayatta kalma
  yanlılığı tüm LONG tarafını yukarı çekiyor. **Buna rağmen** tablo
  çoğunlukla negatif.

### İkinci kusur: araştırma evreni yine canlı evren değildi
Koşum "evren: statik yedek liste" diyerek kendi kusurunu bildirdi.
Sebep: `research/data.py` canlı evren önbelleğini okuyor ama o dosya
**sunucuda** yaşıyor; backtest ise **yerel makinede** koşuyor ve orada
bulunmayınca yedeğe düşüyor. 24 Ağustos'ta "düzelttim" dediğim şey,
ölçümün fiilen koştuğu yerde çalışmıyormuş.

Çözüm: köprüye `evren` komutu eklendi —
`./ops/local/vm-read.sh evren > data/universe_cache.json` ile canlı
liste yerele alınır, sonra backtest koşulur. Bir sonraki F7 koşumu bu
sırayla yapılacak ve hüküm o koşumdan okunacak.
