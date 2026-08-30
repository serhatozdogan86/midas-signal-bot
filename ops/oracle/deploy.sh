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
# v4.34: tek atis 5 sn yanlis alarm veriyordu -> deneme dongusu.
# v4.41 (18 Agu OLCUMU): acilis ~71 sn surdu (gist restore 55 sn +
# takvim/evren) ve 30 sn'lik dongu YINE yanlis alarm verdi. Tolerans
# olculen degerin ~2 kati: 3'er sn arayla 50 deneme = 150 sn. Gercek
# cokus zaten "active olamadi/healthz hic gelmedi" olarak ayrisir.
sudo systemctl restart midas-signal-bot
ready=0
for i in $(seq 1 50); do
    sleep 3
    if curl -sf "http://127.0.0.1:${PORT:-8100}/healthz" >/dev/null; then
        echo "OK: servis ayakta (${i}. denemede, ~$((i*3)) sn)."
        ready=1
        break
    fi
done
if [ "$ready" != "1" ]; then
    echo "RED: healthz 150 sn'de cevap vermedi! journalctl -u midas-signal-bot -n 50"
    exit 1
fi
# v4.48 (30 Agu SAHA GOZLEMI): asagidaki rejim beklemesi HAFTA SONU
# HER ZAMAN bosa doner. Sebep scheduler.tick'te: hafta sonu/tatilde
# session_times(today) None -> tick erken cikar -> run_prep hic kosmaz
# -> _regime "UNKNOWN (not computed)" olarak KALIR. Yani Pazar gunu
# yapilan deploy 6 dakika bekleyip "bot su an KOR" diye YANLIS ALARM
# basiyordu (30 Agu Pazar deploy'unda birebir yasandi: 200. sn'de hala
# UNKNOWN). Anayasa 6: alarm gurultusu alarmi oldurur. Bu yuzden once
# botun KENDI takvimine sorulur; seans yoksa beklemeden dogru cumle
# yazilir. Ayni sekilde hazirlik saatinden (acilis - PREP_LEAD_MIN)
# once de rejim heniz hesaplanmis olmaz.
skip_regime=$("$VENV/python" - <<'PY'
from datetime import timedelta
from app.config.settings import Settings
from app.services.market_calendar import MarketCalendar
cal, s = MarketCalendar(), Settings()
now = cal.now_et()
ses = cal.session_times(now.date())
if ses is None:
    print(f"BUGUN SEANS YOK (hafta sonu/tatil). Rejim, bir sonraki islem "
          f"gunu hazirlik taramasinda ({cal.next_trading_day(now.date())}) "
          f"yerlesecek - bu KORLUK DEGIL, takvim boyle.")
elif now < ses[0] - timedelta(minutes=s.PREP_LEAD_MIN):
    print("HAZIRLIK SAATI HENUZ GELMEDI. Rejim, acilistan "
          f"{s.PREP_LEAD_MIN} dk once hesaplanacak.")
PY
)
if [ -n "$skip_regime" ]; then
    echo "OK: deploy tamam. $skip_regime"
    exit 0
fi

# v4.46 (21 Agu gozlemi): "saglikli" != "HAZIR". healthz 12 sn'de yesil
# derken bot ~4.5 dk rejim=UNKNOWN + evren cekimiyle kor kaldi. Seans
# disi zararsiz; seans ici --force deploy'da yaniltici. Rejim yerlesene
# kadar (en cok 6 dk) bekle ve durumu ACIKCA soyle - basarisizlik degil
# bilgidir, cikis kodu degismez.
for i in $(seq 1 24); do
    regime=$(curl -sf "http://127.0.0.1:${PORT:-8100}/diag" \
        | "$VENV/python" -c "import json,sys; d=json.load(sys.stdin); print((d.get('regime') or {}).get('regime',''))" 2>/dev/null)
    if [ -n "$regime" ] && [ "$regime" != "UNKNOWN" ]; then
        echo "HAZIR: rejim yerlesti ($regime, ~$((i*15)) sn). Deploy tamam."
        exit 0
    fi
    sleep 15
done
echo "NOT: servis ayakta ama rejim 6 dk'da yerlesmedi (veri cekimi"
echo "surebilir). Seans ICI deploy yaptiysan bot su an KOR - /diag'dan"
echo "rejimi izle. Deploy tamam sayildi."
exit 0
