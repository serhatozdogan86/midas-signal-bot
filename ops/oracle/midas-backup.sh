#!/usr/bin/env bash
# Gunluk yerel DB yedegi (kesim sonrasi devrede) - v4.26d
# NEDEN BOYLE (9 Agu Faz 1 saha bulgulari, ucu de VM'de OLCULDU):
#   A) cron bu imajda (OCI Ubuntu 24.04) kurulu degil -> systemd timer
#   B) hedef klasor yokken cp sessizce basarisiz olurdu ("yedek var"
#      sanilir, hic olusmamistir) -> mkdir -p
#   C) canli SQLite'i cp'lemek yarim islemi yakalayabilir (bozuk yedek,
#      fark ancak restore aninda anlasilir) -> sqlite3 backup API
#      (atomik; venv python'daki modul yeterli, sqlite3 CLI gerekmez)
# 7 gunluk donusum: bot-Mon..bot-Sun.db uzerine yazilarak.
set -eu
SRC=/opt/midas-signal-bot/data/bot.db
DEST=/opt/midas-signal-bot/data/backup
mkdir -p "$DEST"
if [ ! -f "$SRC" ]; then
    # Faz 1'de kanonik DB yok (verify.db calisir) - sessiz ve zararsiz.
    echo "kaynak DB yok, yedek atlanildi: $SRC"
    exit 0
fi
OUT="$DEST/bot-$(date +%a).db"
/opt/midas-signal-bot/.venv/bin/python - "$OUT" <<'PY'
import sqlite3
import sys

src = sqlite3.connect("/opt/midas-signal-bot/data/bot.db")
dst = sqlite3.connect(sys.argv[1])
with dst:
    src.backup(dst)          # atomik; canli DB'de yazma varken de guvenli
dst.close()
src.close()
PY
echo "OK: $OUT"
