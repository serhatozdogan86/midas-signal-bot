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
sudo systemctl restart midas-signal-bot
sleep 5
curl -sf "http://127.0.0.1:${PORT:-8100}/healthz" >/dev/null \
    && echo "OK: deploy tamam, servis saglikli." \
    || { echo "RED: healthz cevap vermiyor! journalctl -u midas-signal-bot -n 50"; exit 1; }
