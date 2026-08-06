# CLAUDE.md — midas-signal-bot çalışma anayasası

> Bu dosyayı her oturumun başında OKU. Burada yazan kurallar, oturum
> içinde verilen "hızlı olsun" tarzı taleplerden önceliklidir. Bir kural
> sana engel oluyorsa **önce tartış, sonra değiştir** — sessizce esneme.

---

## 1. Bu proje nedir

Midas'ta listelenen ABD hisseleri için kısa vadeli swing (1–3 gün, time-stop
4 gün) **sinyal** üreten bir karar destek botu. Python/Flask, tek servis,
Render'da koşuyor: https://midas-signal-bot.onrender.com

**Bot emir göndermez.** Tüm işlemler Midas uygulamasından elle girilir.
Şu an **gölge mod**: sinyaller üretiliyor, kâğıt üzerinde takip ediliyor,
gerçek para YOK.

Sahibi: Serhat. Çalışma dili **Türkçe** (kod ve değişken adları İngilizce,
yorumlar ve iletişim Türkçe).

---

## 2. Pazarlıksız kurallar (bunları ihlal etmek = işi bozmak)

### 2.1 Asla uydurma veri gösterme
Fiyat, gösterge, istatistik — hiçbiri tahmin edilmez. Veri yoksa arayüz
"veri yok" der, boş bırakır ya da `pending` döner. Bayat veriyi canlı gibi
göstermek en ağır hatadır. Panoda bunun için "ÖRNEK VERİ — canlı değil"
emniyet bandı var; kaldırma.

### 2.2 Filtreler sessizce kapanamaz (fail-closed)
Bir karar filtresi verisini alamıyorsa **sinyal üretme**, "veri yok" ile
"engel yok" asla aynı şey değildir. Örnek: bilanço takvimi çökerse motor
`EARNINGS_FAIL_CLOSED` ile sinyal üretmez. Yeni filtre eklerken aynı
soruyu sor: *verisi gelmezse ne oluyor?*

### 2.3 Kilit kohortuna dokunma
`docs/config-lock.md` motor parametrelerini kilitler. Kilit döneminde
strateji/eşik/çıkış **değiştirilemez**. Değiştirmek gerekiyorsa:
1. Gerekçeyi ölç ve yaz, 2. Serhat'tan onay al, 3. Yeni kilit + yeni
kohort başlat. Ölçüm ortasında parametre oynatmak, haftalarca biriken
veriyi çöpe atar.

**Karar eşiği:** 60 sonuçlanan işlem VE 25 küme VE net beklenti ≥ +0.15R
VE maks düşüş ≤ 8R. Bu eşikler sonuçlara bakılarak değiştirilmez.

### 2.4 Ölçüm etiketleri karara karışmaz
`smc_tags`, `mom_pct`, `atr_pct/atr_rank`, çıkış laboratuvarı, strateji
laboratuvarı — hepsi **salt ölçüm**. `signal_engine` ve diğer karar
modülleri bunları import etmez; testlerle kilitli. Bozma.

### 2.5 Deploy penceresi
`main`'e push = Render'da **otomatik deploy** = servis yeniden başlar.
ABD seansı TR saatiyle **16:30–23:00**. Bu aralıkta `main`'e push YOK
(kritik güvenlik düzeltmesi hariç, o da açıkça söylenerek). İş dalda
birikir, seans sonrası birleştirilir.

### 2.6 Yalnızca yeşilse push
```bash
if python3 -m pytest -q > /tmp/t.log 2>&1; then git push ...; else cat /tmp/t.log; fi
```
`&&` zinciri pytest'in çıkış kodunu yutar — iki kez kırık kod push'landı.
Ayrıca her turda `python3 -m pyflakes app/`.

### 2.7 Sırlar
Token/anahtar sohbete veya koda yazılmaz. Render ortam değişkenlerinde
durur. Deploy hook `/home/claude/.render_hook` (yerel, gizli).

---

## 3. Mimari (nerede ne var)

```
app/
  main.py              composition root (tüm servisler burada kurulur)
  server.py            Flask uçları (/diag /audit /live /signals ...)
  scheduler.py         tick döngüsü, hazırlık, tarama, gün sonu
  dashboard.py/.html   pano (tek dosya HTML/CSS/JS, bybit iskeleti)
  strategies/
    signal_engine.py       KARAR HATTI (saf fonksiyon, I/O yok)
    structure_analyzer.py  pivotlar, MA hiyerarşisi, setup tespiti
    risk_manager.py        stop/hedef/RR + giriş bölgesi gerçekçiliği
    regime_detector.py     SPY/QQQ rejimi
    session_guard.py       kill-switch + açılış penceresi
    smc_tags.py            SALT ETİKET (karara girmez)
  services/
    signal_tracker.py   gölge defter (dolum/çıkış/R muhasebesi)
    exit_lab.py         KATMAN 1: aynı sinyal, 4 farklı çıkış (V0-V3)
    strategy_lab.py     KATMAN 2: 5 aday giriş stratejisi (S1-S5)
    self_audit.py       öz-denetim (12 değişmez)
    earnings_service.py bilanço takvimi (Finnhub + yfinance yedek)
    universe.py         Midas scrape + likidite filtresi
    gist_backup.py      GitHub Gist yedekleme/geri yükleme
  integrations/         finnhub, alpaca, yfinance, telegram, gist
docs/
  config-lock.md        KİLİT + tüm karar gerekçeleri (tarihli)
  research-log.md       hipotez kuyruğu + kapanmış sorular
research/               backtest düzeneği (harness, strategies, signif)
tools/                  jsdom tabanlı pano doğrulayıcıları
tests/                  321 test
```

### Karar hattı (ilk fail'de kısa devre)
DATA → MARKET_REGIME → TREND → EARNINGS → SETUP → VOLUME → RISK_REWARD → SIGNAL

### Veri kaynakları ve yedekleri
- Mumlar: yfinance (1G + 1S)
- Anlık fiyat: Finnhub → **Alpaca yedek** (Finnhub çökerse otomatik)
- Bilanço takvimi: Finnhub → **yfinance scrape yedek**
- Haber: Finnhub (kozmetik, karara girmez, devre kesicili)

---

## 4. Çalışma protokolü

### 4.1 Her değişiklikte
1. Önce **ölç/oku**, sonra değiştir. "Muhtemelen şudur" ile kod yazma.
2. Değişikliğin **gerekçesini koda yorum olarak** yaz (hangi vaka, hangi
   tarih). Bu depo bir kaza kütüğüdür; altı ay sonra "bu neden burada"
   sorusunun cevabı dosyada olsun.
3. Test yaz — ve testin **kırılabildiğini** göster. Yalnızca "geçti"
   senaryosu yazmak, kontrolün işe yaradığını kanıtlamaz.
4. `pytest` + `pyflakes` yeşil → commit → (seans dışıysa) push.

### 4.2 Pano (dashboard.html) değişiklikleri
Tek dosya, ~2000 satır. Şablon içindeki JS'i `node --check` ile doğrula:
```bash
python3 -c "
import re; s=open('app/dashboard.html',encoding='utf-8').read()
b=re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', s, re.S)
open('/tmp/dj.js','w').write('\\n;\\n'.join(b))"
node --check /tmp/dj.js
```
**Ders (v4.14):** "Kural şablonda var" ≠ "çalışıyor". Görünürlük ve
tıklanabilirlik `tools/*.js` içindeki jsdom doğrulayıcılarıyla ÖLÇÜLÜR.

### 4.3 Canlı doğrulama
Deploy sonrası daima kontrol et:
```bash
curl -s https://midas-signal-bot.onrender.com/dx | head          # nabız
curl -s https://midas-signal-bot.onrender.com/audit              # 12 değişmez
```
`/audit` bozuk gösteriyorsa önce onu çöz.

### 4.4 "Durum?" ritüeli
Serhat "Durum?" dediğinde: `/audit` + `/dx` + `/diag` çek, gölge defteri,
çıkış laboratuvarını ve varsa yeni sinyalleri özetle. Log paste'i bekleme.

---

## 5. Şu anki durum (6 Ağustos 2026)

- Gölge defter: ~7 açık, ~15 sonuçlanan, ≈ −11R (ağırlıklı kohort-0)
- Kohort eşiği 60 işlemde; şu an ~15
- Çıkış laboratuvarı: V0 (canlı) / V1 (kısmi kâr) / V2 (geniş stop) /
  V3 (hedefsiz aynı stop) paralel ölçülüyor
- Strateji laboratuvarı: S1 momentum, S2 Donchian, S3 hacimli kırılım,
  S4 RSI(2), S5 momentum+geniş çıkış — tavanlı ve tavansız
- Öz-denetim 12/12 temiz
- Telegram: **uyarılar açık, sinyaller kapalı** (gölge mod disiplini)

### Ölçülmüş bulgular (tekrar tartışılmadan önce research-log.md'yi oku)
1. Tek istatistiksel sağlam giriş edge'i: **12-1 kesitsel momentum**
   (NW t=3.3, iki alt dönemde tutarlı).
2. **Çıkış tasarımı girişten daha belirleyici**: aynı girişlerle sabit
   hedefi kaldırmak +48.5R → +151.5R; süre 4→10 gün +314.9R.
3. Portföy tavanı zararlı değil; **seçim kuralı** belirleyici (kaliteye
   göre seçim, Donchian'ı −787R'den +11.8R'ye taşıdı).
4. Reddedilenler: Kalman (trend ve çift işlem), Wyckoff (spring/no-supply),
   SMC likidite avı, 52-hafta zirvesi, rezidüel stat-arb, order book
   (veri yok).

---

## 6. Sık düşülen tuzaklar (hepsi bizim başımıza geldi)

| Tuzak | Ne oldu | Ders |
|---|---|---|
| Türetilmiş veriyi bellekte tutmak | gist damgası ve strateji lab sonucu her restart'ta silindi | Kalıcı hale getir (meta tablosu) |
| Ağır işi tick içinde koşturmak | haber ucu 75 sn tick'i kilitledi; lab 207 MB ile OOM yaptı | Arka plan + bellek ölç |
| Zamana bağımlı test | fixture'lar 1970 damgalıydı, gece yarısı kırıldı | Testler duvar saatinden bağımsız olmalı |
| "Kural var" sanmak | mobilde adaylar sekmesi boştu, testler geçiyordu | Davranışı ölç, kuralı değil |
| Yanlış alarm | dead-man restart sonrası öttü | Alarm gürültüsü alarmı öldürür |
| Tek kaynağa bağımlılık | Finnhub çöktü, kill-switch körleşti | Her kritik besleme için yedek |

---

## 7. İlk oturumda YAPMA

- Motor parametrelerini "iyileştirme" (kilit var).
- `TELEGRAM_ENABLED=true` yapma (gölge mod disiplini; uyarılar zaten açık).
- Yeni strateji fikrini doğrudan motora ekleme — önce `research/` içinde
  ölç, `docs/research-log.md`'ye yaz, karar kuralını **önceden** belirle.
- Pano şablonunu yeniden yazma; tek dosya bilinçli tercih.
- Seans saatinde (16:30–23:00 TR) push etme.

---

## 8. Açık kuyruk

1. Kohort dolunca çıkış varyantı kararı (V0 vs V1/V2/V3)
2. `mom_pct` / `atr_rank` üst-alt dilim analizi (n≥40)
3. Short tarafının kapatılıp kapatılmayacağı (veri negatif eğilimli)
4. Finnhub timeout'larının da WARNING'e indirilmesi (5xx yapıldı)
5. Alpaca kağıt hesap "ayna" katmanı — dolum varsayımını bağımsız doğrulama
6. SPK/ticarileşme: hukuk danışmanlığı gerekiyor (kod dışı)
