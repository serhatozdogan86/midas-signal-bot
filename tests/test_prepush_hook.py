"""tools/hooks/pre-push davranis testleri (v4.19).

"Kural var" != "calisiyor" dersi geregi hook'un kendisi OLCULUR: date ve
python3 PATH stub'lariyla degistirilir, boylece testler duvar saatinden
ve gercek test takimindan bagimsizdir (zamana bagimli test tuzagi).

Olculen davranislar:
- NYSE seansi acikken main push ENGELLENIR (2.5); KRITIK_FIX=1 gecirir.
- Seans disi / hafta sonu / dal push'u engellenmez.
- pytest veya pyflakes kirmiziysa HER push engellenir (2.6).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "tools" / "hooks" / "pre-push"

_DATE_STUB = """#!/usr/bin/env bash
# test stub: FAKE_DOW / FAKE_HM ortam degiskenlerinden cevap verir
case "$1" in
  +%u)   echo "${FAKE_DOW:-3}" ;;
  +%H%M) echo "${FAKE_HM:-1200}" ;;
  *)     echo 0 ;;
esac
"""

_PY_STUB = """#!/usr/bin/env bash
# test stub: pytest/pyflakes sonucunu STUB_*_RC ortamindan taklit eder
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "pytest" ]; then exit "${STUB_PYTEST_RC:-0}"; fi
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "pyflakes" ]; then exit "${STUB_PYFLAKES_RC:-0}"; fi
exit 0
"""


def _run(tmp_path, ref="refs/heads/feature", dow=3, hm="1200",
         pytest_rc=0, pyflakes_rc=0, kritik=None):
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    for name, body in (("date", _DATE_STUB), ("python3", _PY_STUB)):
        p = stubs / name
        p.write_text(body)
        p.chmod(0o755)
    env = dict(os.environ,
               PATH=f"{stubs}:{os.environ['PATH']}",
               FAKE_DOW=str(dow), FAKE_HM=str(hm),
               STUB_PYTEST_RC=str(pytest_rc),
               STUB_PYFLAKES_RC=str(pyflakes_rc))
    env.pop("KRITIK_FIX", None)
    if kritik is not None:
        env["KRITIK_FIX"] = kritik
    line = f"refs/heads/x abc {ref} def\n"
    # v4.26: cwd=tmp_path - hook artik repo kokundeki .venv'i tercih ediyor;
    # test, .venv'siz bir dizinden kosarak PATH stub'inin (python3)
    # kullanildigini garanti eder (gercek pytest'i ozyinelemeli cagirmasin).
    return subprocess.run(["bash", str(HOOK), "origin", "url"],
                          input=line, text=True, capture_output=True, env=env,
                          cwd=tmp_path)


def test_seans_icinde_main_push_serbest_ama_hatirlatmali(tmp_path):
    """v4.35 (17 Agu hizalamasi): kesim sonrasi main push deploy degildir
    (CLAUDE.md 2.5, v4.31) - kanca ENGELLEMEZ, hatirlatma birakir. Seans
    kilidi artik deploy.sh'de (botun takvimiyle). Eski kancada bu test
    rc=1 beklerdi; celiski 17 Agu'da sahada yakalandi."""
    r = _run(tmp_path, ref="refs/heads/main", dow=3, hm="1200")
    assert r.returncode == 0
    assert "NOT (2.5)" in r.stdout


def test_seans_disi_main_push_hatirlatmasiz(tmp_path):
    r = _run(tmp_path, ref="refs/heads/main", dow=3, hm="2000")
    assert r.returncode == 0
    assert "NOT (2.5)" not in r.stdout


def test_hafta_sonu_main_push_hatirlatmasiz(tmp_path):
    r = _run(tmp_path, ref="refs/heads/main", dow=6, hm="1200")
    assert r.returncode == 0
    assert "NOT (2.5)" not in r.stdout


def test_seans_sinirlari(tmp_path):
    # hatirlatma yalniz 09:30-15:59 ET araliginda gorunur
    assert "NOT (2.5)" not in _run(tmp_path, ref="refs/heads/main",
                                   hm="0929").stdout
    assert "NOT (2.5)" in _run(tmp_path, ref="refs/heads/main",
                               hm="0930").stdout
    assert "NOT (2.5)" in _run(tmp_path, ref="refs/heads/main",
                               hm="1559").stdout
    assert "NOT (2.5)" not in _run(tmp_path, ref="refs/heads/main",
                                   hm="1600").stdout


def test_dal_pushu_seans_icinde_serbest(tmp_path):
    r = _run(tmp_path, ref="refs/heads/feature", dow=3, hm="1200")
    assert r.returncode == 0


def test_pytest_kirmiziysa_dal_pushu_da_engellenir(tmp_path):
    r = _run(tmp_path, ref="refs/heads/feature", pytest_rc=1)
    assert r.returncode == 1
    assert "ENGEL (2.6)" in r.stdout


def test_pyflakes_kirmiziysa_engellenir(tmp_path):
    r = _run(tmp_path, ref="refs/heads/feature", pyflakes_rc=1)
    assert r.returncode == 1
    assert "pyflakes" in r.stdout
