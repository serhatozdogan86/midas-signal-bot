# CLAUDE.md — midas-signal-bot çalışma anayasası

> Bu dosyayı her oturumun başında OKU. Burada yazan kurallar, oturum
> içinde verilen "hızlı olsun" tarzı taleplerden önceliklidir. Bir kural
> sana engel oluyorsa **önce tartış, sonra değiştir** — sessizce esneme.

---

## 1. Bu proje nedir

Midas'ta listelenen ABD hisseleri için kısa vadeli swing (1–3 gün, time-stop
4 gün) **sinyal** üreten bir karar destek botu. Python/Flask, tek servis.
**12 Ağu 2026 Faz 2 kesiminden beri Oracle VM'de koşuyor** (systemd:
`midas-signal-bot.service`). Uçlar/pano internete AÇIK DEĞİL; erişim
Serhat'ın makinesinden SSH tüneliyle `http://localhost:8100`. Eski ev
Render **askıda** (SUSPEND) — geri dönüş planı oracle-tasima-plani.md
Faz 3; **çift yazar yasak**: Render'ı resume etmeden VM durdurulmalı.

**Bot emir göndermez.** Tüm işlemler Midas uygulamasından elle girilir.
Şu an **gölge mod**: sinyaller üretiliyor, kâğıt üzerinde takip ediliyor,
gerçek para YOK.

Sahibi: Serhat. Çalışma dili **Türkçe** (kod ve değişken adları İngilizce,
yorumlar ve iletişim Türkçe).

**Serhat yazılımcı DEĞİL** (9 Ağu isteği): ona bir şey yaptıracaksan
adımları basit dille, tek tek, jargonsuz anlat — "curl at" değil "şu
mesajı yapıştır" de. Komut koşturmayı mümkünse ondan isteme; ya kendin
koş ya da yereldeki Claude oturumuna yaptır, Serhat'a yalnız kopyala-
yapıştır mesajlar ve evet/hayır kararları bırak. Teknik terim
kullanacaksan bir kez, yanında günlük karşılığıyla kullan.

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

**Belgelenmiş tek istisna:** v3.9 endeks kill-switch'i veri yokken
**fail-open + WARNING** çalışır — o bir karar filtresi değil, filtrelerin
ÜSTÜNE eklenmiş ek bir frendir; veri yok diye tüm taramayı durdurmak
orantısız olur (gerekçe: config-lock.md v3.9). Bu istisna geneli bozmaz:
yeni bir bileşen fail-open olacaksa aynı şekilde burada ve config-lock'ta
gerekçesiyle listelenmek zorundadır.

### 2.3 Kilit kohortuna dokunma
**İKİZ DEPO:** bu bot ile `bybit-signal-bot` aynı iskeletten doğdu. Kanıtlı
mekanizma hatası, ölçüm/muhasebe düzeltmesi veya yeni ölçüm aleti çıktığında
**ikizde karşılığı açıkça kontrol edilir** ve sonuç `docs/ikiz-depo-notu.md`'ye
yazılır (bulunmasa bile). Kontrol "okudum, yok" ile kapanmaz; ikizde aynı
davranışı tetikleyen test yazılır. Gerekçe: retest kusuru burada 8 Ağustos'ta
düzeltilmişti, bybit'te 12 Ağustos'a kadar canlı kaldı — bakılacak bir yer
olmadığı için. Açık maddeler (M1–M5) o dosyada.

`docs/config-lock.md` motor parametrelerini kilitler. Kilit döneminde
strateji/eşik/çıkış **değiştirilemez**. Değiştirmek gerekiyorsa:
1. Gerekçeyi ölç ve yaz, 2. Serhat'tan onay al, 3. Yeni kilit + yeni
kohort başlat. Ölçüm ortasında parametre oynatmak, haftalarca biriken
veriyi çöpe atar.

**Eşiklerin tek doğruluk kaynağı** `app/config/settings.py` +
`docs/go-live-kriteri.md`'dir; buradaki özet bilgilendiricidir, çelişkide
onlar kazanır. İki AYRI karar vardır, karıştırma:
1. **Go-live kararı** (gölge → gerçek para): ≥60 sonuçlanan işlem VE ≥25
   küme VE tek kümenin payı ≤%25 VE net beklenti ≥ +0.15R VE maks düşüş
   ≤ 8R VE küme-blok bootstrap %95 GA alt sınırı > 0 (altılı VE;
   istatistik şartı 12 Ağu, ayrıntı go-live-kriteri.md).
2. **Çıkış varyantı kararı** (V0 → V1/V2/V3): kohort 60 işlem / 25 kümeye
   ulaşınca; varyant hem toplam net-R hem beklenti olarak V0'ı geçmeli
   VE işaret iki yarı-dönemde tutarlı olmalı (config-lock.md v3.19).

Bu eşikler sonuçlara bakılarak değiştirilmez.

### 2.4 Ölçüm etiketleri karara karışmaz
`smc_tags`, `mom_pct`, `atr_pct/atr_rank`, çıkış laboratuvarı, strateji
laboratuvarı — hepsi **salt ölçüm**. `signal_engine` ve diğer karar
modülleri bunları import etmez; testlerle kilitli. Bozma.

### 2.5 Deploy penceresi
**Kesim sonrası (12 Ağu) dağıtım modeli:** `main`'e push artık tek başına
deploy DEĞİLDİR (Render askıda). Dağıtım VM'de elle yapılır:
`git pull` + servis restart (`ops/oracle/deploy.sh`) — ve servis restart'ı
canlı botu yeniden başlattığı için pencere kuralı artık **VM dağıtımına**
uygulanır. Pencere ABD seansına göre tanımlıdır: **NYSE 09:30–16:00 ET**
açıkken VM'de deploy/restart YOK (kritik güvenlik düzeltmesi hariç, o da
açıkça söylenerek). `main`'e push seans içinde de serbesttir (hiçbir şeyi
yeniden başlatmaz) ama VM'ye çekilmesi seans sonrasına bırakılır.

**TR saatine güvenme, ET'ye bak:** Türkiye yaz saati kullanmaz, ABD
kullanır. Yaz döneminde seans TR 16:30–23:00, kış döneminde (Kasım–Mart)
TR 17:30–00:00'dır. Sabit "16:30–23:00 TR" ezberi Kasım'da yanlışlanır.
Kontrol: `TZ=America/New_York date` (tatiller için `market_calendar`).

**Geri dönüş (rollback) tarifi** — kötü deploy anında doğaçlama yapma:
1. Birincil yol: `git revert <kotu-commit>` → pytest yeşilse `main`'e
   push → VM'de `git pull` + restart (seans içindeyse bu "kritik
   düzeltme" istisnasıdır, açıkça yaz). `git push --force` ile tarih
   silme YOK; revert izlenebilirlik bırakır.
2. Alternatif (VM'de acil): servis durdurulur, `git checkout
   <onceki-iyi-commit>` + restart — ama `main` hâlâ bozuk kodu gösterir;
   revert'i yine yap, yoksa bir sonraki pull bozuk kodu geri getirir.
3. Deploy sonrası 4.3'teki canlı doğrulamayı MUTLAKA koş.

### 2.6 Yalnızca yeşilse push
```bash
if python3 -m pytest -q > /tmp/t.log 2>&1; then git push ...; else cat /tmp/t.log; fi
```
`&&` zinciri pytest'in çıkış kodunu yutar — iki kez kırık kod push'landı.
Ayrıca her turda `python3 -m pyflakes app/`.

**Mekanik uygulama (v4.35 hizalaması):** 2.6 `tools/hooks/pre-push` ile,
2.5 (seans kilidi) VM'deki `ops/oracle/deploy.sh` ile zorlanır (botun
kendi takvimiyle; bilinçli aşma: `--force`). Kanca seans içinde main
push'unu artık engellemez, yalnız hatırlatır. Kurulum (klon başına bir
kez):
```bash
git config core.hooksPath tools/hooks
```
Sınırları bil: `--no-verify` ile atlanabilir ve yalnız kurulu klonu
korur — emniyet kemeridir, kilit değil (davranışı
`tests/test_prepush_hook.py` ölçer). Not (12 Ağu kesimi): Render'a
CI-gated deploy iskeleti (`deploy.yml` + `RENDER_DEPLOY_HOOK`) kesimle
anlamsızlaştı; CI-yeşili şartının VM dağıtımına uyarlanması açık
kuyrukta (§8) — o gelene dek güvence pre-push hook + el disiplinidir.

### 2.7 Sırlar
Token/anahtar sohbete veya koda yazılmaz. Kesim sonrası sırların evi
VM'deki `ops/oracle/midas.env` (git'e girmez); Render env'i askıdaki
kopyada yedek olarak durur. Aktarım gerekirse "Notepad dosyası + yerel
oturum işler + dosya silinir" yöntemi (12 Ağu kesimi böyle yapıldı).

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
    self_audit.py       öz-denetim (15 değişmez)
    earnings_service.py bilanço takvimi (Finnhub + yfinance yedek)
    universe.py         Midas scrape + likidite filtresi
    gist_backup.py      GitHub Gist yedekleme/geri yükleme
    alpaca_mirror.py    AYNA adım 1 (salt ölçüm; dolum doğrulama, karara girmez)
  integrations/         finnhub, alpaca, yfinance, telegram, gist
docs/
  config-lock.md        KİLİT + tüm karar gerekçeleri (tarihli)
  research-log.md       hipotez kuyruğu + kapanmış sorular
  ikiz-depo-notu.md     bybit ile ortak kusurlar + açık maddeler (M1-M5); ikizi
                        bybit-signal-bot/docs/ altında, aynı içerik
research/               backtest düzeneği (harness, strategies, signif)
tools/                  jsdom tabanlı pano doğrulayıcıları
tests/                  davranış testleri (sayı için `pytest --co -q`)
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
Deploy sonrası daima kontrol et (kesim sonrası uçlar yalnız VM'de;
yerel oturumdan, SSH tüneli/`vm-read.sh` üzerinden):
```bash
curl -s http://localhost:8100/dx | head          # nabız
curl -s http://localhost:8100/audit              # öz-denetim değişmezleri
```
`/audit` bozuk gösteriyorsa önce onu çöz. Bulut oturumları VM'e
erişemez — canlı doğrulamayı yerel oturuma yaptırıp çıktıyı ister.

### 4.4 "Durum?" ritüeli
Serhat "Durum?" dediğinde: `/audit` + `/dx` + `/diag` çek (VM'den, 4.3
yolu), gölge defteri, çıkış laboratuvarını ve varsa yeni sinyalleri
özetle. Log paste'i bekleme; bulut oturumuysan gereken çıktıyı yerel
oturumdan iste.

### 4.5 Yerel oturum izin düzeni (11 Ağu kararı)
Serhat'ın makinesinde/VM'de koşan Claude oturumları izinleri şöyle kurar:
- **Salt-okunur** komutlara (dosya listeleme/okuma, `git log/status/diff`,
  ssh üzerinden yalnız BAKAN komutlar: `free/df/ps/cat/systemctl status`
  vb.) kalıcı izin ver (`/permissions`) — her seferinde sorma.
- **Yazan/değiştiren** her şey (kurulum, silme, `systemctl
  start/stop/enable`, env düzenleme, `git push`, emir/config değişikliği)
  onaya tabi KALIR. `ssh *` gibi geniş kalıplara kalıcı izin verilmez
  (içinden yazan komut da geçer).
- `--dangerously-skip-permissions` kullanılmaz. Gerekçe: onay anları bu
  hafta üç gerçek hatayı yakaladı (VERIFY env gösterimi, iptables kararı,
  gist kimliği); frenler ucuz, kazalar pahalı.

---

## 5. Şu anki durum (12 Ağustos 2026, kesim gecesi)

> **Bu bölüm tarihli bir anlık görüntüdür, canlı veri DEĞİLDİR** (bkz.
> 2.1). Güncel durum daima `/dx` + `/audit` + `/diag` uçlarından alınır
> (4.4 ritüeli); buradaki sayılarla canlı uçlar çelişirse uçlar kazanır.

- **12 Ağu gecesi Faz 2 kesimi yapıldı**: kanonik sistem artık Oracle VM
  (commit 873ac85 / v4.31); Render askıda. Defter kesimde birebir taşındı
  (8 açık; WIN 4 / LOSS 18 / EXPIRED 4 / NOT_FILLED 4; −9.65R brüt).
  Karar arşivi gist revizyonlarından 22.500 satır olarak geri toplandı.
- Kohort: KİLİT-2 (8 Ağu'dan beri) 60 işlem eşiğinde birikiyor
- Çıkış laboratuvarı: V0 (canlı) / V1 (kısmi kâr) / V2 (geniş stop) /
  V3 (hedefsiz aynı stop) paralel ölçülüyor
- Strateji laboratuvarı: S1 momentum, S2 Donchian, S3 hacimli kırılım,
  S4 RSI(2), S5 momentum+geniş çıkış — tavanlı ve tavansız
- Öz-denetim 13/13 temiz
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
- NYSE seansı açıkken (09:30–16:00 ET; bkz. 2.5) VM'de deploy/restart
  yapma (`main`'e push serbest ama VM'ye seans içinde çekilmez).

---

## 8. Açık kuyruk

1. Kohort dolunca çıkış varyantı kararı (V0 vs V1/V2/V3)
2. `mom_pct` / `atr_rank` üst-alt dilim analizi (n≥40)
3. Short tarafının kapatılıp kapatılmayacağı (veri negatif eğilimli)
4. Finnhub timeout'larının da WARNING'e indirilmesi (5xx yapıldı)
5. Alpaca kağıt hesap "ayna" katmanı — adım 1+2 tamam (iskelet,
   izolasyon kilitleri, emir döngüsü sahte istemciyle; v4.19/v4.24).
   Sırada adım 3: emir yetkili paper API anahtarı VM env'ine →
   canlı istemci + 2 hafta alarmsız izleme → sapma eşikleri ÖNCEDEN
   (eşik önerisi 12 Ağu toplantı notlarında, onay bekliyor)
6. CI-yeşili şartının VM dağıtımına uyarlanması (deploy.sh yalnız
   yeşil CI'da çeksin; Render iskeleti kesimle anlamsızlaştı)
7. ~~Korelasyon ölçüm aleti~~ ✔ TAŞINDI (v4.37, 17 Ağu) — StrategyLab
   bağımsızlık raporu artık lab özetiyle birlikte üretiliyor
   (`app/services/correlation.py`; ikiz-depo-notu.md kaydı kapandı).
8. İkiz not eşitliği mekanizması: iki deponun ikiz-depo-notu.md'si
   sessizce ayrışabiliyor (13 Ağu'da yaşandı); senkron damgası/denetim
   fikri değerlendirilecek.
9. SPK/ticarileşme: hukuk danışmanlığı gerekiyor (kod dışı)
