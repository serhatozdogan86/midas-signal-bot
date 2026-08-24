# İkiz Depo Notu — midas ↔ bybit

> Bu dosyanın ikizi `bybit-signal-bot/docs/ikiz-depo-notu.md` içindedir ve
> aynı içeriği taşır. Biri değişirse diğeri de güncellenir.
>
> Oluşturma: 2026-08-12, iki depoyu birlikte inceleyen dış oturum.

## Neden bu dosya var

`midas-signal-bot`, `bybit-signal-bot` iskeletinden doğdu. İkisi aynı boru
hattını (rejim → yapı → kurulum → hacim → risk/ödül → sinyal), aynı gölge
defter mantığını ve aynı ön-kayıt kültürünü paylaşıyor.

Bunun pratik sonucu şu: **birinde bulunan bir kusur, diğerinde de aday
kusurdur.** Ama bu bugüne kadar tek yönlü işledi — bybit'ten midas'a bilgi
taşındı, midas'ta öğrenilenler bybit'e geri taşınmadı.

### Kanıt: retest kusuru

`detect_breakout_retest` içinde kırılım sonrası dilimler `break_i`'den
başlıyordu. Kırılım mumunun kapanışı tanımı gereği seviyenin doğru
tarafındadır, ve o mum seviyeyi aşağıdan geçtiği için low'u neredeyse her
zaman tolerans altındadır. Sonuç: acceptance sayacı 2 yerine fiilen 1, ve
**retest şartı tamamen boş** — yani "breakout+retest", retestsiz kovalama
girişi.

| | |
|---|---|
| midas'ta düzeltildi | 2026-08-08 (v4.23) |
| midas'taki faturası | kilit-1 defterinin 16/17 işlemi, −12R |
| bybit'te düzeltildi | 2026-08-12 (KİLİT-2) — **dört gün sonra** |

Dört gün boyunca aynı kusur, aynı kod, ikinci depoda canlı kaldı. Kimse
bakmadığı için değil; **bakılacak bir yer olmadığı için.**

## Kural: çift yönlü aktarım

Bir depoda şu üç şeyden biri olduğunda, diğer depoda karşılığı **açıkça
kontrol edilir ve sonuç bu dosyaya yazılır** (bulunmasa bile):

1. **Kanıtlı mekanizma hatası** (kilit açan türden)
2. **Ölçüm/muhasebe düzeltmesi** (defterin sayıları değişiyorsa)
3. **Yeni ölçüm veya deney aleti**

Kontrol "okudum, yok" ile kapanmaz — ikizde aynı davranışı tetikleyen bir
test yazılır. Retest kusuru sentetik veriyle böyle kanıtlanmıştı: fiyatın
seviyeyi kırıp bir daha hiç dönmediği seride eski kod setup üretiyor,
düzeltilmiş kod üretmiyordu.

## Yetenek envanteri (2026-08-12)

Örüntü: **midas deney altyapısında, bybit ölçüm altyapısında öne geçmiş.**

| Yetenek | midas | bybit |
|---|---|---|
| Bağımsız sonuç denetçisi (`verifier.py`) | **yok** | var |
| Küme-blok bootstrap güven aralığı | **yok** | var |
| NOT_FILLED anatomisi (`nf_anatomy`) | **yok** | var |
| Kayma senaryolu hayalet R | **yok** | var |
| Güven etiketi permütasyon testi | **yok** | var |
| Önceden ilan edilmiş alarm kaydı | kısmen (`self_audit`) | var (`alarms.py`) |
| Aday strateji yarışı | **yok** | var (`challengers.py`) |
| Çıkış varyantı laboratuvarı | var (`exit_lab`) | **yok** |
| Giriş stratejisi laboratuvarı | var (`strategy_lab`) | **yok** |
| Hipotez kohortu (blocked=5) | var (`hypo_lab`) | **yok** |
| Öz-denetim değişmezleri | var (`self_audit`) | **yok** |
| Bağımsız dolum doğrulama (kâğıt hesap) | var ama **kapalı** (`alpaca_mirror`) | **yok** |

## Açık maddeler — midas tarafı

Aşağıdakiler 2026-08-12 itibarıyla **açık**. Hiçbiri motora dokunmaz;
üçü ölçüm katmanı, biri belge tutarlılığı.

### M1 — Go-live eşiği tesadüfe açık ✔ KAPANDI (v4.30, 2026-08-12)

**Durum: çözüldü.** `v4.30` go-live'a altıncı şartı ekledi: işlem başına net
beklentinin küme-blok bootstrap güven aralığının alt sınırı > 0
(`signal_tracker.cluster_bootstrap_ci`, eşikler `GOLIVE_CI_*`, rapor
`golive_status.criteria.ci_low_r`; 10.000 tur, %95, sabit tohum).
Kapıyı yalnızca sıkılaştırdığı için KİLİT-2 sayacı sıfırlanmadı.
Aşağıdaki ölçüm, o kararın gerekçesi olarak kayıtta kalıyor.



`docs/go-live-kriteri.md` beş şart sayıyor ama hiçbiri **istatistiksel
anlamlılık** istemiyor. bybit'in Faz-1 kapısı istiyor: *≥50 küme VE
küme-bootstrap CI alt sınırı > 0.*

Gerçek defterden ölçüm (22 sonuçlanmış işlem, 2026-08-11):

- işlem başına net-R standart sapması: **1,112**
- 60 işlemde ortalamanın standart hatası: **0,144R**
- yani `GOLIVE_MIN_EXPECTANCY_R = 0.15` eşiği ≈ **1,0 standart hata**

20.000 denemelik bootstrap, gerçek üstünlük = 0 varsayımıyla:

| Gözlem birimi | Tesadüfen ≥ +0,15R çıkma olasılığı |
|---|---|
| 60 işlem | **%15,3** |
| 25 bağımsız küme | **%24,6** |

Yani hiçbir üstünlüğü olmayan bir motor bu kapıdan dörtte bir ihtimalle
geçebilir — ve geçtiği gün gerçek para konur.

**Öneri:** bybit'in `measurement.cluster_bootstrap` fonksiyonu midas'a
taşınsın ve go-live'a altıncı şart eklensin: *küme-CI alt sınırı > 0.*
Bu bir **sıkılaştırmadır**; `config-lock.md` gevşetmeyi yasaklar,
sıkılaştırmayı serbest bırakır. Eşik değerleri değişmediği için kohort
sıfırlanmaz.

### M2 — Bağımsız sonuç denetçisi yok (öncelik: yüksek; `docs/ideas.md`'ye ön-kayıt yapıldı 2026-08-12)

bybit'teki `verifier.py`'nin gerekçesi: *"Tracker'ın kendi değerlendirme
döngüsünü tekrar kullanan bir denetim, o döngüdeki hatayı göremez — hata
kendini doğrular."* Sonucu mumlardan sıfırdan, ayrı bir uygulamayla
yeniden türetip kayıtla karşılaştırır. bybit'te canlı sonuç: 291 kayıt
denetlendi, 0 uyuşmazlık.

midas'ta karşılığı yok — oysa midas'ın gölge muhasebesinde **tek bir
sürümde (v4.22) dört ayrı hata** düzeltildi: gap sırası, dolum barı,
time-stop çapası, net-DD. Yani daha çok hata çıkarmış bir muhasebe ve onu
bağımsız kontrol eden hiçbir şey yok.

**Öneri:** `verifier.py` midas'a uyarlansın (1h bar + gap muhasebesi
farkıyla). Salt ölçüm katmanı, kilit ihlali değil.

### M3 — Dolum kuralı her işleme peşin zarar yazıyor (öncelik: orta, ölçüm gerekli)

`signal_tracker._evaluate_signal`, LONG için:

```python
touched    = c["low"] <= sig["entry_min"]   # TETİK: bölgenin DİBİ
fill_price = sig["entry_max"]               # FİYAT: bölgenin TEPESİ
```

Yani bir işlem ancak fiyat bölgenin dibine indiğinde "girildi" sayılıyor,
ama giriş fiyatı bölgenin tepesi yazılıyor. İşlem defterde doğduğu anda
bölge genişliği kadar zararda başlıyor.

Gerçek defterden ölçüm (26 dolmuş işlem):

| Sonuç | n | Ortalama peşin zarar (bölge/risk) |
|---|---|---|
| WIN | 4 | 0,15R |
| LOSS | 16 | 0,28R |
| EXPIRED | 2 | 1,06R |
| **tümü** | **26** | **0,33R** |

Net beklenti −0,50R iken peşin zarar 0,33R — açığın üçte ikisi buradan.
Ayrıca bölge genişledikçe sonuç kötüleşiyor.

Mevcut korumalar bunu yakalamıyor: `MAX_ENTRY_ZONE_ATR` ve
`WORST_FILL_TP1_R_MIN` bölgeyi **ATR'ye** oranlıyor, **riske**
oranlamıyor. Stop yapısal olduğunda risk 1,2 ATR'den küçük olabiliyor ve
bölge/risk oranı 1,0'ı aşabiliyor (defterde GM 1,10 · V 1,02).

**Uyarı — bu gerçek bir strateji kusuru DA olabilir, ölçüm aracının fazla
kötümser olması DA.** Dolum kuralı bilinçli konmuş (2 Ağu, konsey 5/5;
emirler elle giriliyor, 30-60 sn gecikme). Kodla ayırt edilemez.
Ayırt etmenin tek yolu `alpaca_mirror` — zaten bunun için yazılmış,
4 adımlık planın 2. adımında, şu an kapalı.

**Önerilen hipotez (karar kuralı önceden yazıldı, `research-log.md`
yöntemi):** Kilit-2 kohortu 40 sonuçlanan işleme ulaştığında, bölge/risk
oranı medyanın üstündeki ve altındaki işlemlerin net-R beklentileri
karşılaştırılır. Üst dilim alt dilimden en az **0,20R kötüyse** ve işaret
iki yarı dönemde aynıysa, bölge/risk tavanı (öneri: 0,25R) motora eklenir.
Aksi halde hipotez yanlışlanmış sayılır ve kayda geçer.

### M4 — Rejim filtresinin fırsat maliyeti ölçülmüyor (öncelik: düşük; `docs/ideas.md`'ye ön-kayıt yapıldı 2026-08-12)

bybit'te piyasa kapısı boru hattının **sonunda**: engellenen karar tam
plan seviyeleri taşır ve `blocked=1` karşı-olgu kohortuna yazılır, böylece
kapının koruma mı fırsat maliyeti mi olduğu ölçülebilir.

midas'ta `MARKET_REGIME` **2. sırada** sert kesiyor; plan hiç kurulmuyor,
dolayısıyla filtrenin kaç iyi işlemi engellediği bilinemiyor. İlginç olan:
aynı prensip midas'ta kill-switch (`blocked=3`) ve açılış penceresi
(`blocked=4`) için zaten uygulanmış — sadece ana rejim filtresine
uygulanmamış.

### M5 — Belge kodla çelişiyor ✔ KAPANDI (v4.34, 2026-08-17)

**Durum: çözüldü.** `signal_tracker` docstring'i artık kendi dolum
kuralımızı tarif ediyor (tam katetme + kötü uç; "bölgenin ilk değen
kenarı" cümlesi — bybit davranışının tarifi — kaldırıldı).

## Açık maddeler — bybit tarafı

2026-08-12 itibarıyla, o incelemenin bulduğu üç madde de **kapandı**.
**2026-08-16 eki:** midas'tan taşınan kontrolle yeni bir madde açıldı (B1, aşağıda).


| Bulgu | Durum |
|---|---|
| Retest kusuru | ✔ KİLİT-2 (2026-08-12) ile düzeltildi, sayaçlar 08-13'ten sıfırdan |
| Ölü maksimum düşüş alarmı | ✔ `d198aac` (2026-08-12) ile düzeltildi |
| S1_TSMOM örnekleminin tavanla boğulması | ✔ tavan 40 → 70, bütçe devri (toplam sabit) |

Kalan tek yapısal madde: midas'taki deney altyapısının (çıkış/giriş
laboratuvarı, hipotez kohortu, öz-denetim değişmezleri) bybit'te karşılığı
yok. Öncelik düşük — bybit'in asıl darboğazı ölçüm değil, kenar bulmak.

### B1 — Dolum/izleme penceresi mum sayısına bağlı, duvar saatine değil (kanıtlı; şu an gizil)

**Kaynak:** midas, 2026-08-16. İki sinyal (DAL, UAL) 29 Temmuz'da PENDING
doğdu ve time-stop tarihinden **9 gün sonra** hâlâ açıktı; portföy
tavanından slot yiyorlardı. Sebep: `_evaluate_signal` içinde dolum
penceresi sayacı **mum listesinin indeksi**. Sembol günlük filtrelerden
düştüğü için saatlik mumları çekilmiyordu; mum gelmeyince sayaç ilerlemedi
ve `NOT_FILLED` asla yazılmadı. midas bunu `v4.32` ile kapattı
(`close_expired_pending`: mum gerektirmeyen, `time_stop_date` tabanlı
süpürme).

**bybit'te karşılığı: VAR.** `app/services/signal_tracker.py`,
`_evaluate_signal` içinde:

```python
if not touched:
    if i + 1 >= self._fill_window:      # i = MUM LİSTESİ İNDEKSİ
        self._close(sig["id"], "NOT_FILLED", None, 0.0)
```

Aynı şekil izleme penceresinde de var: `if bars_held >= self._max_track`
(satır ~653) ve `elif i >= self._max_track` (satır ~537). Her ikisi de
mum akışına bağlı.

#### Kanıt (koşturuldu, 4/4 geçti)

`tests/test_ikiz_pencere_sayaci.py` — üretim venv'inde, gerçek
`SignalTracker` ile:

| Test | Ne gösteriyor | Sonuç |
|---|---|---|
| A — eksik mum | pencereden (24) az mum gelirse, fiyat giriş bölgesine hiç girmese bile `NOT_FILLED` yazılmaz | PENDING'de kalıyor |
| B — hiç mum yok | `evaluate_open` içindeki `if candles:` sessizce atlıyor; mumsuz süpürge yok | PENDING'de kalıyor |
| C — bedeli | sıkışan kayıt `heat_check`'te açık sayılıyor; **küme tavanı (2)** kalıcı kapanıyor | tavan kapandı |
| D — kontrol (kapsam sınırı) | mum akışı sağlamken (pencere+2 mum) pencere doğru kapanıyor | `NOT_FILLED` |

D testi önemli: sorun pencere *mantığında* değil, mum yokken hiç
çalışmamasında. Kusurun sınırını bu çiziyor.

#### İki depo arasındaki fark — bybit daha korumasız

| Emniyet | midas | bybit |
|---|---|---|
| Kayıt başına duvar saati son tarihi | var (`time_stop_date`, v4.22) | **yok** (şemada sütun yok) |
| Mum gerektirmeyen süpürme | var (`close_expired_pending`, v4.32) | **yok** |
| Evren dışı kayıt için mum çekip değerlendirme | var (orphan eval) | var (v3.0, IONQ vakası) |

Yani bybit'in tek savunması orphan eval; o da `get_series` veri
döndürmezse (parite borsadan kalkar, işlem durur, API boş döner) çalışmaz.
O durumda kaydı kapatacak **hiçbir** mekanizma kalmıyor.

#### Kilit açısından: bu bir uyum düzeltmesidir, parametre değişikliği değil

`config-lock.md` gölge kuralını **duvar saatiyle** ilan ediyor:
*"giriş 6sa / izleme 48sa"*. Kod bunu mum sayısıyla uyguluyor
(24 × 15dk = 6sa, 192 × 15dk = 48sa) — mum akışı kesilmediği sürece ikisi
aynı şey. Kesildiğinde kod **ilan edilen kuralı çiğniyor**: 6 saatlik giriş
penceresi 30 saate uzuyor. Zaman tabanlı bir süpürge eşikleri
değiştirmez, ilan edilen eşiği *uygular*. Kilit kapsamında "yalnız kritik
bug fix istisna, o da bu dosyaya tarihli not düşülerek" maddesine girer.

#### Şu an ısırıyor mu? Hayır — gizil

Canlı defterde 26 açık kayıt var, hepsi **1 günden yeni**; pencere altında
görünen dördü sıkışmış değil, sadece genç (mumlar birikiyor). Sebep yapısal:
kripto 7/24 işlem görüyor, 15 dakikalık mum günde 96 tane birikiyor, yani
24 barlık pencere 6 saatte doluyor. midas'ta pencere ancak ABD borsası
açıkken doluyordu — bu yüzden orada patladı, burada patlamadı.

#### Geçmişte ısırmış olabilir (temiz atıf yapılamıyor)

1336 kapalı kaydın 295'i `NOT_FILLED`. Normalde ~6 saatte kapanmaları
gerekir. Üç kayıt aşırı uzun kalmış:

| Parite | id | Süre | Arşivdeki mum | Giriş bölgesine temas |
|---|---|---|---|---|
| MSFTUSDT | 4 | 32,8 sa | 132 | hiç |
| BANKUSDT | 129 | 31,4 sa | 127 | hiç |
| GRAMUSDT | 122 | 29,2 sa | 118 | 39. mumda |

Üçü de 2026-07-31 17:36–17:37'de, yani **aynı dakikalarda toplu** kapandı —
`c2ac0f6` deploy'undan (17:33) ~3 dakika sonra. Bu, tek tek zaman aşımının
değil, servis yeniden başlayıp dolu arşivle yeniden değerlendirmenin
imzası: kayıtlar 30 saat boyunca değerlendirilmemiş, restart onları
kurtarmış.

**Ama temiz atıf yapılmıyor:** o tarih aynı zamanda Oracle taşınma
penceresi (`d9ae8f4`, 31 Tem 06:26). Bot o aralıkta duruyor da olabilir.
Bu üç vaka kusurla *tutarlı* bir izdir, kanıtı değildir. Kusurun kanıtı
yukarıdaki testtir.

#### Önerilen düzeltme (uygulanmadı — karar bekliyor)

midas `v4.32`'nin karşılığı: `signals` tablosuna duvar saati son tarihi
(giriş için +6sa, izleme için +48sa) ve tarama sonunda mum gerektirmeyen
bir süpürme. Not: midas'ta bu süpürge yazıldı ama **sahada hiç
tetiklenmedi** — DAL/UAL'i kurtaran orphan eval oldu. Yani süpürge iki
depoda da hâlâ denenmemiş bir emniyet freni; yazılırsa testle
tetiklenmesi gerekir.

## Kaynak

Bu notu üreten inceleme: her iki botun karar üreten katmanlarının satır
satır okunması + canlı uçlardan (`/performance`, `/signals`, `/diag`,
`/alarms`, `/challengers`) doğrulama + iki koşturulmuş kanıt testi
(retest kusuru, ölü alarm). 2026-08-11/12.

## S8 Fonlama Sıkışması — ikiz kontrolü (2026-08-13)

**Sonuç: UYGULANAMAZ (N/A) — gerekçeli.** bybit'e S8_FUNDSQUEEZE adayı
eklendi (aşırı funding + fiyat teyidi, S4'ten derin eşik). midas'ta
karşılığı ARANDI:

- midas bir **ABD hisse** botudur (Alpaca; earnings/fundamentals/premarket/
  market_calendar servisleri). Hisse senedinde **funding oranı YOKTUR** —
  funding perpetual-futures'a özgü bir mekanizmadır.
- midas'ta tek "funding" geçişi bir yorum satırıdır: "funding yerine not"
  (app/server.py) — yani midas funding kavramını bilinçle YOKA sayar.
- Dolayısıyla S8'in midas'ta ne karşılığı ne de "aynı davranışı tetikleyen
  test"i mümkün: tetikleyecek girdi (funding) o evrende mevcut değil.

**Karar:** S8 crypto-perp'e özgüdür; ikiz aktarımı gerekmez. Bu, Kural 3b'nin
"bulunmasa bile yaz" gereğidir — kontrol yapıldı, uygulanamaz olduğu
gerekçesiyle kapandı (S4_CARRY için de aynı mantık geçerlidir; midas'ta
funding ailesi yoktur).

## Korelasyon ölçüm aleti — ikiz kontrolü (2026-08-13) ✔ TAŞINDI (v4.37, 2026-08-17)

**Durum: kapandı.** bybit'e çoklu-strateji korelasyon/örtüşme aleti
eklenmişti (app/services/correlation.py + /correlation; Faz A salt-rapor:
çift korelasyonu, N_eff, aynı-gün-aynı-yön oranı); midas'ta StrategyLab
çoklu paralel strateji işletirken bağımsızlık ölçümü yoktu → **alet
taşındı** (midas `app/services/correlation.py` v4.37). Uyarlama farkları
(bilinçli, modül docstring'inde): veri kaynağı DB değil laboratuvarın
bellek-içi Trade listeleri (midas ham işlemi saklamaz — bellek dersi);
günlük NET R; LONG-only olduğundan yön örtüşmesi "aynı gün sinyal"
oranına indirgenir. Anahtar testler: karar modülleri import edemez (AST)
+ kendi kendini doğrulama (S1|S5 aynı giriş → korelasyon 1.0 çıkmalı).
bybit'in evren-tutarlılığı düzeltmesi (N_eff yalnız ölçülen çiftlerden)
aynen taşındı. (S9_GECE stratejisi 3b kapsamı DIŞI — mekanizma
hatası/ölçüm düzeltmesi değil, yeni bahis; hisse piyasası gece kapalıyken
kriptonun 21–23 UTC penceresi midas evreninde tanımsız.)

2026-08-16 eki (B1): midas v4.32/v4.33 dağıtımı sırasında yapılan ikiz kontrolü — bybit `signal_tracker` okuması, üretim venv'inde koşturulan 4 kanıt testi, canlı defterden 26 açık kayıt ve 1336 kapalı kaydın süre analizi.

## Sağlayıcı sessiz kırpması — ikiz kontrolü (2026-08-18) · **BULUNDU**

**Kaynak: midas v4.40.** Finnhub bilanço takvimi ucu ~1500 satırda
**sessizce** kırpıyordu: HTTP 200, `retCode` yok, hata yok — eksik veri tam
sanıldı. Düşen uç **eski** uçtu. midas düzeltmesi: pencereyi 3 günlük
dilimlere böl + 1400 satırlık kırpma kanaryası (`cap_suspect`, denetim
kırmızı yakar).

Kural 3b gereği bybit'te karşılığı arandı. **Kalıp bulundu** — üç uç
VM'den canlı ölçüldü (2026-08-18):

| Uç | İstendi | Geldi | Hata verdi mi? |
|---|---|---|---|
| `/v5/market/kline` | limit=1500 | **1000 satır** | hayır, `retCode=0` |
| `/v5/market/funding/history` | 200 gün | **66.3 gün** (200 satır) | hayır, `retCode=0` |
| `/v5/market/tickers` | tümü | 829 sembol, cursor yok | — (kırpma yok) |

`instruments-info` tek sayfada 824 sembol döndü (cursor YOK), tickers'ta
eksik yok — **enstrüman listesinde kırpma yok**. Sayfalama gerekmedi ama
sınır yakın (829/1000): evren büyürse cursor gerekecek.

### Asıl bulgu: funding geçmişi bir MUHASEBE hatası

`signal_tracker._backfill_funding` kapanmış her işlem için gerçek funding
maliyetini toplayıp `funding_r_real` olarak deftere yazıyor. Uç tek istekte
en çok 200 kayıt ve **yalnız en yeni uçtan** veriyor; `startTime` ne kadar
geriye verilirse verilsin eskiler sessizce düşüyor. Sonuç zinciri:

> eksik funding → maliyet olduğundan **küçük** → net-R olduğundan **iyi**
> → küme-CI olduğundan **yüksek** → **go-live kapısı yanlış yönde açılır**

Kırpma eşiği pariteye göre değişiyor (824 paritede ölçüldü):

| Funding aralığı | Parite | 200 kayıt kaç günü kapsar |
|---|---|---|
| 8 saat | 374 | 66,7 gün |
| **4 saat** | **408** | **33,3 gün** |
| 1 saat | 2 | 8,3 gün |

Yani evrenin **yarısından fazlası** 33 günlük pencereyle sınırlıydı.

### Fiilen zarar verdi mi? — HAYIR (ölçüldü)

Canlı defterdeki 305 kapanmış işlem (WIN/LOSS, dolmuş) tarandı:
en uzun işlem **5,79 gün** (VVVUSDT), ortanca 0,14 gün. En dar kırpma
eşiği 8,3 gün. **Hiçbir kayıt etkilenmemiş** — `funding_r_real` sayıları
sağlam, defter yeniden hesaplanmayı gerektirmiyor.

Bu bir **mayın**: motor bugünkü time-stop'uyla eşiğe değmiyor, ama S10
(haftalık 52w sepeti) gibi uzun tutuşlu bir aday veya time-stop'un
gevşetilmesi eşiği aşar ve hata sessizce deftere girer.

### Yapılan

- `tests/test_invariants.py`: sınıfı kapatan üç değişmezlik testi
  (`test_funding_history_completes_range_despite_provider_cap`,
  `test_funding_history_single_page_makes_one_call`,
  `test_kline_request_never_exceeds_provider_cap`). Sahte uç, gerçek
  davranışı taklit ediyor: tavan kadar satır, **en yeni uçtan**.
  Düzeltmesiz kodda ikisi KIRMIZI (200/270 kayıt; `_KLINE_CAP` yok).
- `bybit_client.get_funding_history`: sayfalama — tavana dayanan her
  sayfadan sonra `endTime` en eski kaydın bir öncesine çekilir, aralık
  tamamlanır. Sayfalar arası hata olursa **None** döner (yarım veri
  döndürmek sessiz muhasebe hatasıdır; fail-close 2.2).
- `bybit_client.get_kline_rows`: tavan üstü limit isteği `_KLINE_CAP`'e
  çekilir ve `bybit_limit_capped` uyarısı loglanır.

**Gerçek uçta doğrulandı** (VM, düzeltilmiş istemci): BTCUSDT 200 gün →
**600 kayıt / 199,7 gün** (önce 200 kayıt / 66,3 gün), ETHUSDT 120 gün →
360 kayıt / 119,7 gün; sıralı, mükerrersiz. kline limit=1500 → uyarı
basıldı, 1000'e çekildi.

### Ters yön: midas'a taşınabilir mi?

midas kendi kırpmasını v4.40'ta kapattı, ama oradaki çözüm **takvim ucuna
özel** (dilimleme + kanarya). Buradaki genel ders — *"sağlayıcı tavanına
dayanan yanıt tam sayılamaz"* — midas'ın **diğer** uçları için
kontrol edilmedi: Alpaca bar sayfalaması, `/v2/stocks/bars` limit'i ve
fundamentals uçları aynı sınıfa açık. midas oturumuna **açık iş**.

## Gap dolumu ve R paydası — ikiz kontrolü (2026-08-21)

**Sonuç: G1 bybit'te BULUNMADI (yapısal olarak bağışık). G2 ters yönde
BULUNDU — midas'ın 2 Ağustos düzeltmesi bybit'e hiç taşınmamış.**

Tetikleyen bulgu: midas kilit-2 kohortunda JNJ **+7,91R**. Dolum bölgenin
altında (256,00 · bölge 258,02–259,03) oluştuğu için R paydası tasarım
riski 4,00 yerine **1,475**'e düştü. Aynı çıkışla bölge içi dolumda
+2,29R, bölgenin kötü ucunda +1,92R olurdu.

### Kural farkı

```python
# midas  signal_tracker._evaluate_signal
touched    = c["low"] <= sig["entry_min"]        # TETİK: bölgenin DİBİ (tam katetme)
fill_price = sig["entry_max"]                    # FİYAT: bölgenin tepesi
if is_long and c["open"] < sig["entry_min"]:     # GAP DALI
    fill_price = c["open"]                       #   → dolum açılıştan

# bybit  signal_tracker._evaluate_signal
touched    = c["low"] <= sig["entry_max"]        # TETİK: bölgenin TEPESİ (tek tık)
fill_price = sig["entry_max"]                    # FİYAT: her zaman kenar — GAP DALI YOK
```

İki bağımsız fark var ve **zıt yönlere** çalışıyorlar: midas tetikte
katı ama fiyatta gap'e açık; bybit tetikte gevşek ama fiyatta sabit.

---

### G1 — Gap dalı: bybit'te YOK, defter temiz

Ölçüm (bybit canlı defteri, kapanmış ve dolmuş 1337 kayıt):

| Kontrol | Sonuç |
|---|---|
| Dolum fiyatı tam bölge kenarında | **1337 / 1337** |
| Bölge dışı dolum | **0** |
| Tasarım riski / fiili risk oranı | min 0,75 · ortanca 0,853 · **maks 1,00** |
| Oranı 1,10'un üstünde olan kayıt | **0** |

Oran hiçbir kayıtta 1,00'ı aşmıyor: bybit'te fiili risk **her zaman**
tasarım riskinden büyük ya da eşit. R paydası kısalamıyor, dolayısıyla
şişme mekanizması burada doğamaz.

**Karşı-olgusal — midas kuralı bu deftere uygulansaydı** (aynı 1337
kayıt, arşivlenmiş 15 dk mumlarla yeniden oynatıldı):

| | n | gerçek R | midas kuralıyla | fark |
|---|---:|---:|---:|---:|
| LOSS | 125 | −125,00 | −111,00 | +14,00 |
| WIN | 48 | +129,03 | **+461,89** | +332,86 |
| **toplam** | **173** (%12,9) | **+4,03** | **+350,89** | **+346,86** |

Beklenti 0,023 R/işlem → **2,028 R/işlem**. Kazananlarda ortalama
2,69R → 9,62R (**3,6 kat**); payda ortalama **3,39 kat** küçülüyor.
Uç örnekler: MRVLUSDT 2,85R → 77,36R · CAPUSDT 4,80R → 64,76R ·
UBUSDT 2,32R → 37,76R.

**Asimetri — asıl mesele bu.** Zarar tanımı gereği stop'a kadardır, yani
dolum nereye kayarsa kaysın ≈ −1R'ye çapalıdır (tabloda 125 zarar
−125,00 → −111,00, neredeyse sabit). Kazanç ise payda küçüldükçe
serbestçe büyür. Kural beklentiyi **yalnızca yukarı** itebilir; gap yoğun
bir kohortta defter yapısal olarak iyimserdir.

**Karşı-olgusalın sınırı (dürüst kayıt):** çıkış fiyatları bybit'in kendi
dolumuyla oluştu. Gerçekte dolum stop'a yaklaşsaydı **daha çok işlem
stop'a çarpardı** ve kazananların bir kısmı hiç hayatta kalmazdı. Yani
+350,89R bir tahmin değil, **üst sınırdır**. Mekanizmanın yönü ve
asimetrisi kesin; büyüklüğü abartılıdır.

**midas tarafı:** bu, M3'ün (dolum kuralı her işleme peşin zarar yazıyor)
**ters bacağıdır**. Aynı kural normal durumda kötümser (bölgenin kötü
ucundan doldurur), gap durumunda iyimser (stop'un dibinden doldurur).
İki bacağın net etkisi ölçülmedi. Kilit-2 kohortunda gap dolumlu tek
kazanan JNJ; o +2,29R olsaydı kohort NET'i −3,43R yerine ≈ −9,05R,
maksimum düşüş 8,90R yerine ≈ 9,05R olurdu (yani 8R aşımı JNJ'ye bağlı
değil, JNJ olmadan **daha derin**).

---

### G2 — Ters yön: tetik kuralı. bybit'te AÇIK MADDE

midas 2 Ağustos'ta (konsey 5/5, "%100 dolum iyimserliği") tetiği bölgenin
dibine çekti: *bölgenin yakın ucuna bir tık dokunmak dolum saymaz;
emirler elle giriliyor, 30–60 sn gecikme var.* **Bu düzeltme bybit'e hiç
taşınmadı** — bybit hâlâ tek tık dokunuşta dolum yazıyor.

Ölçüm (bybit defteri, 1338 kapanmış dolum — G1 koşusundan sonra bir
işlem daha kapandığı için sayı bir fazla):

| | n | toplam R |
|---|---:|---:|
| midas tetiğiyle **dolmayacak** kayıt | **149** (%11,1) | **+178,87** |
| — WIN | 92 | +217,02 |
| — LOSS | 49 | −49,00 |
| — EXPIRED | 8 | +10,85 |

Bu alt küme çıkarılsaydı defter **+6,96R → −171,91R**, beklenti
+0,005 → **−0,145 R/işlem**. Yalnız temiz kohortta (blocked=0): 340 işlem
+64,36R, bunun +66,86R'si bu 45 kayıttan — yani temiz kohort da
**eksiye** düşerdi (≈ −2,50R).

Başka bir deyişle: **bybit defterinin artıda görünmesinin tamamı, midas'ın
üç hafta önce iyimser bulup terk ettiği tetik kuralından geliyor.**

Bu bir hüküm değil, bir soru: bölgeye asılı **duran limit emri** varsa tek
tık dokunuş gerçekten doldurur (borsa emri sırayla eşler). Elle, sinyal
geldikten sonra giriliyorsa doldurmaz. midas'ın konseyi ikincisine karar
vermişti. İki bot da elle giriliyor. **Karar toplantısına.**

---

### Yapılan (kod DEĞİŞTİRİLMEDİ)

- `midas/tests/test_ikiz_gap_dolum.py` — 4 test, davranışı sabitler:
  gap dalının tetiklendiği, paydanın 2,50'den 1,00'a düştüğü, aynı
  çıkışta R'nin 1,00R yerine 5,00R yazıldığı, ve **zarar kolunda iki
  kuralın da tam −1R verdiği** (asimetri kanıtı).
  Kırmızı kanıtı: gap dalı kapatılmış kopyada 2 test KIRILDI
  (`assert 4.0 < 0.01` — R 5,00 yerine 1,00).
- `bybit/tests/test_invariants.py::test_gap_acilisinda_bile_dolum_bolge_kenarindan`
  — dolumun bölge kenarına bağlı kalmasını zorunlu kılar; gap dalının
  sonradan buraya taşınmasını engeller.
  Kırmızı kanıtı: midas gap dalı eklenmiş kopyada test KIRILDI
  (dolum 99,0 geldi, 101,0 bekleniyordu).
- G2 için **test yazılmadı**: orada bir kusur değil, iki meşru kural
  arasında bir **seçim** var. Karar verilmeden değişmezlik yazmak, kararı
  test dosyasına gizlice gömmek olur.

### Açık iş

1. **bybit:** G2 kararı — tetik bölgenin dibine mi çekilecek? Defterin
   tamamının işaretini değiştirdiği için kilit süreci konusudur.
2. **midas:** M3 + G1 birlikte ölçülmeli. Dolum kuralının iki bacağının
   net etkisi bilinmiyor; `alpaca_mirror` tam da bunu ayırt etmek için
   yazılmıştı (13 çift, kademe 1).

## Backtest düzeneğinin yeniden üretilebilirliği + S6/S11 tanım hizası — ikiz kontrolü (2026-08-24)

**Kaynak: midas F6.** Hipotez 9'un (Squeeze) backtest'ine başlarken
`research/run.py`'ın `/home/claude/bt/daily.pkl` okuduğu görüldü — o yol
kapanmış geçici bir analiz ortamındaydı. Yani düzenek **koşulamaz**
durumdaydı ve bunu kimse fark etmemişti; ölçüm aleti yeniden
üretilemiyorsa ölçüm de yeniden üretilemez.

### Bulgu 1 — ikizde AYNI KUSUR YOK (kontrol edildi, bulunamadı)
bybit'te backtest verisi depo içindeki `tools/download_backtest_data.py`
ile indiriliyor: `--out` argümanı, sembol başına CSV, ayrıca **bütünlük
raporu** (satır sayısı, beklenen sayı, tekrar/dedup, zaman boşlukları,
tarih aralığı → `_report.json`). Sabit kodlanmış geçici yol yok; analiz
betikleri `data_dir` parametresi alıyor. Yani bybit bu konuda midas'ın
**önündeydi**.
→ Ters yön uygulandı: midas'a `research/data.py` yazıldı (evren depodan,
önbellek `research/_data/`, .gitignore'da). Eksik sembol sessizce
atlanmıyor, ekrana yazılıyor; SPY yoksa fail-closed. **Açık iş:** bybit'in
bütünlük raporunun (boşluk/tekrar sayımı) midas tarafında karşılığı henüz
yok — bir sonraki turda taşınacak.

### Bulgu 2 — S6 (midas) ile S11 (bybit) tanımları AYRIŞIYOR
İki bot aynı mekanizmayı bağımsız ön-kayıtla aldı; tanımlar birebir
değil. Fark bilinçli olarak KORUNDU, çünkü her iki tarafın ön-kaydı da
sonuç görülmeden yazılmıştı ve sonuca bakıp hizalamak kural esnetmesi
olurdu:

| | midas S6 (hipotez 9, 17 Ağu) | bybit S11 (17 Ağu) |
|---|---|---|
| Tetik anı | sıkışma ≥6 bar sürdükten sonra aralık dışı kapanış (çözülme ŞART DEĞİL) | yalnızca sıkışma ÇÖZÜLÜNCE |
| Momentum teyidi | yok | var (LazyBear lin-reg momentum aynı yönde) |
| Zaman dilimi | günlük | 4 saatlik |
| Stop | ortak ATR mekaniği (kıyas için); S6 kendi stop'u strategy_lab'e kalır | sıkışma aralığının karşı ucu |

**Tanımda düzeltilen tek şey** (sonuca bakılmadan, 24 Ağu): midas'ta KC
merkezi başta EMA20'ydi, BB merkezi SMA20. Merkezler farklı olunca "BB,
KC'nin içinde" sınavı genişliğe değil merkez kaymasına da duyarlı hale
geliyordu — yani sıkışmayı değil sıkışma+eğilim karışımını ölçüyordu.
İki merkez de SMA20'ye çekildi; bu hem LazyBear kanoniği hem de ikizin
kullandığı biçim (bybit yorumu: "orta bant iki kanalda da aynı olduğundan
bu, 'BB tamamen KC içinde' koşulunun birebir eşdeğeridir").

Kalan farklar sonuç alındıktan sonra "ikiz varyantı" olarak AYRI bir
hipotezle ölçülebilir; ön-kayıt metinleri değiştirilmeyecek.

### Senkron notu
Bu kayıt şu an yalnız midas kopyasında. bybit kopyasına aynısı
yazılmalı (açık kuyruk md. 8: iki notun sessizce ayrışması — 13 Ağu'da
yaşanmıştı). Bulut oturumunun bybit'e yazma yetkisi yok; taşıma yerel
oturuma bırakıldı.

### Ek (aynı gün, F6 koşumundan sonra): evren kaynağı — bybit yine önde
F6'nın ilk koşumu iki eksik sembol raporladı; ikisi de "araştırma
evreni canlı evrenden ayrıştı" sınıfından (SQ→XYZ bayatlığı; BRK.B
biçim tuzağı — üretimde 30 Tem'de çözülmüş, araştırma kendi yolunu
yazdığı için geri gelmişti).

bybit'te bu yapısal olarak imkânsız: `tools/download_backtest_data.py`
evreni **UniverseProvider'ı yeniden kullanarak** seçiyor (kendi
docstring'i: "canlı botla AYNI kural"). midas'ta araştırma katmanı
evreni statik yedek dosyadan okuyordu.
→ Düzeltildi: `research/data.py` artık önce canlı evren önbelleğini
(`data/universe_cache.json`) okur, sembol dönüşümünde üretimin
`YFinanceClient._to_yahoo` kuralını kullanır; statik liste yalnız
yedektir. Ayrıca `tools/universe_drift.py` (yedek↔canlı karşılaştırıcı,
salt-okur) eklendi — bybit'te bu denetçinin karşılığı YOK, ters yönde
taşınabilir (statik yedek listesi varsa aynı bayatlama riski orada da
vardır; kontrol edilmeli).

Özet: bu turda ikiz karşılaştırması üç şey verdi — biri bizde kusur
(veri yolu), biri bizde kusur (evren kaynağı), biri onlarda eksik
(kayma denetçisi). Kural 3b'nin iki yönlü çalıştığının örneği.
