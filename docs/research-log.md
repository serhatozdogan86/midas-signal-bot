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
