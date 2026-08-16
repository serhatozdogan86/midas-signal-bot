#!/usr/bin/env bash
# Oracle VM deploy: git pull + test + restart. Anayasa kurallari gomulu:
#   2.5 seans icinde restart YOK (--force ile bilincli asilabilir)
#   2.6 pytest yesil degilse deploy YOK (asilamaz)
# Kullanim: ops/oracle/deploy.sh [--force]
set -euo pipefail
cd "$(dirname "$0")/../.."

FORCE="${1:-}"
VENV=".venv/bin"

# 1) Seans kilidi - botun KENDI takvimiyle (tatiller dahil)
if [ "$FORCE" != "--force" ]; then
    if ! "$VENV/python" - <<'PY'
from app.services.market_calendar import MarketCalendar
import sys
sys.exit(2 if MarketCalendar().is_session_open() else 0)
PY
    then
        echo "RED: seans acik (anayasa 2.5). Seans disini bekle veya --force."
        exit 2
    fi
fi

# 2) Guncelle + bagimliliklar
git pull --ff-only
"$VENV/pip" install -q -r requirements.txt

# 3) Test kapisi (asilamaz - anayasa 2.6)
if ! "$VENV/python" -m pytest -q; then
    echo "RED: testler kirmizi, deploy iptal. Servis eski surumle calismaya devam ediyor."
    exit 1
fi

# 4) Restart + saglik kontrolu
# v4.34 (16 Agu yanlis alarmi): acilis 5 sn'den uzun surebiliyor (gist
# restore + takvim). Tek atis yerine 30 sn'ye kadar 3'er sn arayla dene;
# gercek cokusle yavas acilis ayrismis olur.
sudo systemctl restart midas-signal-bot
for i in $(seq 1 10); do
    sleep 3
    if curl -sf "http://127.0.0.1:${PORT:-8100}/healthz" >/dev/null; then
        echo "OK: deploy tamam, servis saglikli (${i}. denemede, ~$((i*3)) sn)."
        exit 0
    fi
done
echo "RED: healthz 30 sn'de cevap vermedi! journalctl -u midas-signal-bot -n 50"
exit 1
