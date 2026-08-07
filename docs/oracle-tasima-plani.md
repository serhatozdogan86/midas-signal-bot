# Oracle VM Tasima Plani (Render -> Oracle)

> Amac: veri kaliciligi (gercek disk, Gist restore dansinin bitmesi) +
> Render kota/RAM tavanindan kurtulmak. Motora dokunulmaz: bu bir ALTYAPI
> tasimasi, engine_sha ve kilit kohortu aynen devam eder (anayasa 2.3).
> Icra: Claude Code (VM'e SSH oradan). Kesim MUTLAKA seans disi (2.5).

## Faz 0 - Envanter (10 dk, GO/NO-GO kapisi)

```bash
free -m && df -h / && nproc && python3.12 --version || python3 --version
systemctl status bybit* --no-pager | head -20   # mevcut botun servisi
ps -eo rss,comm --sort=-rss | head -10           # RAM envanteri
timedatectl | grep "Time zone"
sudo ss -tlnp | grep -E ':(8100|10000)' || echo "8100 bos"
```

GO kriteri: en az ~700 MB bos RAM (Render'da 512'ye sigiyorduk; tampon
payi) + 2 GB bos disk + python3.10+. Saglanmiyorsa: swap ekle (2G) veya
NO-GO -> alternatif (Litestream/ucretli Render) konusulur.

## Faz 1 - Paralel sessiz dogrulama (2-3 islem gunu)

Amac: yfinance + Finnhub'in Oracle IP'sinden ayni kaliteyle cevap
verdigini KESIMDEN ONCE kanitlamak. Kopya tamamen sessizdir: Telegram
kapali, Gist kapali, taze DB - kanonik hicbir kaynaga yazmaz.

```bash
sudo git clone https://github.com/serhatozdogan86/midas-signal-bot /opt/midas-signal-bot
cd /opt/midas-signal-bot && sudo chown -R ubuntu: .
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q                    # yesil olmali
cp ops/oracle/midas.env.example ops/oracle/midas.env && chmod 600 ops/oracle/midas.env
# midas.env'i duzenle: secrets doldur + "VERIFY:" satirlarini AC
sudo cp ops/oracle/midas-signal-bot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now midas-signal-bot
curl -s http://127.0.0.1:8100/healthz
sudo ufw allow 8100/tcp                          # dashboard'a disaridan bakmak icin
```

Her aksam (seans sonrasi) karsilastir - Render/diag vs VM/diag:
- universe sayisi (+-5), regime AYNI, watchlist kesisimi yuksek
- gun ici SIGNAL kumesi ayni (sembol+yon; seviyelerde kucuk fark olabilir,
  dakika farkli taramalar normal)
- DATA_MISSING orani ve Finnhub hata sayaci Render'dan belirgin kotu DEGIL

GO kriteri: 2 ardisik gun sinyal kumesi eslesiyor / farklar aciklanabilir.
Eslesme yoksa kok neden bulunmadan Faz 2'ye GECILMEZ.

## Faz 2 - Kesim (seans disi, ~30 dk)

1. Render /diag: gist last_sync tazeligini teyit et (age < 1 saat;
   ideali 23:15 EOD gorevlerinden sonrasi - defter gunu kapanmis olur).
2. Render dashboard'dan servisi SUSPEND et (silme - geri donus kapisi).
3. VM'de: `sudo systemctl stop midas-signal-bot`
   midas.env'de VERIFY satirlarini kapat, normalleri ac (alerts=true,
   GIST_SYNC=true, DB_PATH=data/bot.db). `rm -f data/verify.db data/bot.db`
4. `sudo systemctl start midas-signal-bot` -> bot bos DB gorup Gist'ten
   kanonik state'i restore eder. Dogrula:
   `curl -s localhost:8100/diag` -> decided_trades ve open_signals
   Render'daki son degerlerle AYNI olmali (defter kesintisiz tasindi).
5. Telegram alert kanalina test uyarisinin dustugunu gor (ilk denetim).
6. Yeni adres: http://VM_IP:8100 - telefona/yer imlerine kaydet ve
   Claude'a soyle ("Durum?" kontrolleri artik bu adrese gider).

## Faz 3 - Geri donus (gerekirse, 5 dk)

`sudo systemctl stop midas-signal-bot` -> Render'da servisi RESUME et.
Kanonik kaynak her zaman Gist: hangi taraf acilirsa oradan restore eder.
Cift calisma YASAK (ayni gist'e iki yazar = bozulma); once durdur, sonra ac.

## Kesim sonrasi (ilk hafta)

- Gunluk yerel yedek (Gist artik felaket yedegi roluine iner):
  `crontab -e` -> `10 3 * * * cp /opt/midas-signal-bot/data/bot.db /opt/midas-signal-bot/data/backup/bot-$(date +\%a).db`
- Render servisini 1 hafta suspend beklet, sonra sil.
- Deploy artik: `ops/oracle/deploy.sh` (seans kilidi + test kapisi gomulu).
- 1 hafta sonra gozden gecir: RAM kullanimi (MemoryHigh 600M yeterli mi),
  Finnhub/yfinance hata sayaclari, journalctl'de restart dongusu var mi.
