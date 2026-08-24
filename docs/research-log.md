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
