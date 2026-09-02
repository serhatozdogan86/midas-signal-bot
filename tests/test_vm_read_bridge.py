"""VM salt-okur koprusu (ops/local/vm-read.sh) - guvenlik sozlesmesi.

Bu betigin VAR OLMA sebebi anayasa 4.5: "ssh *" gibi genis kaliplara
kalici izin VERILMEZ, cunku o kalibin icinden yazan komut da gecer.
Kopru, izni dar bir yuzeye indirir - ama ancak yuzey gercekten darsa.
Buradaki testler o darligi olcer; betik "salt-okur" olmaktan cikarsa
kirmizi yanar (test_prepush_hook.py emsali: emniyet kemerini de olc).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

BETIK = Path("ops/local/vm-read.sh")
ORNEK_ENV = Path("ops/local/vm.env.example")


@pytest.fixture(scope="module")
def kaynak() -> str:
    return BETIK.read_text(encoding="utf-8")


def test_betik_var_ve_calistirilabilir():
    assert BETIK.exists(), "CLAUDE.md 4.3 bu betikten bahsediyor"
    assert BETIK.stat().st_mode & 0o111, "chmod +x yapilmali"


def test_komut_listesi_sabittir_disaridan_metin_gecmez(kaynak):
    """En kritik sart: kullanicidan gelen metin uzak kabuga GECMEZ.
    Uzak komut satirlarinda $1/$@/$* gibi cagiran-kontrollu degiskenler
    bulunmamali - yoksa kopru, 'ssh *' izninin dolambacli hali olur."""
    for satir in kaynak.splitlines():
        s = satir.strip()
        if not s.startswith("remote="):
            continue
        for tehlike in ('"$1"', "$1", "$@", "$*", "${1}"):
            assert tehlike not in s, f"cagiran-kontrollu girdi: {satir}"


def test_yazan_komutlar_bulunmuyor(kaynak):
    """Deploy, restart, git pull/push, silme, env duzenleme YOK -
    hepsi onaya tabi kalir (4.5) ve deploy.sh'ta seans kilidi vardir."""
    govde = "\n".join(l for l in kaynak.splitlines()
                      if not l.strip().startswith("#"))
    yasak = ["systemctl restart", "systemctl start", "systemctl stop",
             "git pull", "git push", "git checkout", "git reset",
             "rm ", "mv ", "chmod ", "chown ", "tee ", "deploy.sh",
             "sudo "]
    for k in yasak:
        assert k not in govde, f"salt-okur kopruda yazan komut: {k}"


def test_bilinmeyen_alt_komut_reddedilir(kaynak):
    """case ifadesinin '*)' dali kullanimi basip cikmali - bilinmeyen
    alt komut sessizce ssh'e devredilmemeli."""
    assert re.search(r"\*\)\s+usage", kaynak), "catch-all dal yok"
    assert "exit 2" in kaynak


def test_sir_gomulu_degil(kaynak):
    """Anahtar/adres koda YAZILMAZ; vm.env'den gelir (2.7)."""
    assert 'VM_KEY="${VM_KEY:-}"' in kaynak
    assert 'VM_HOST="${VM_HOST:-}"' in kaynak
    # Kaba tarama: ozel anahtar govdesi veya token benzeri dizi
    assert "BEGIN OPENSSH PRIVATE KEY" not in kaynak
    assert not re.search(r"gh[pousr]_[A-Za-z0-9]{20,}", kaynak)


def test_eksik_ayarda_calismaz_sessizce_denemez(kaynak):
    """VM_HOST/VM_KEY yoksa ACIK hata verir - 'veri yok' ile 'sorun
    yok' karistirilmaz (2.1/2.2 refleksi)."""
    assert 'if [ -z "$VM_HOST" ] || [ -z "$VM_KEY" ]; then' in kaynak


def test_ornek_env_dosyasi_var_ve_sir_icermez():
    assert ORNEK_ENV.exists()
    icerik = ORNEK_ENV.read_text(encoding="utf-8")
    assert "SUNUCU-ADRESI" in icerik          # yer tutucu, gercek adres degil
    assert "BEGIN OPENSSH PRIVATE KEY" not in icerik


def test_gercek_env_dosyasi_gitignore_da():
    assert "ops/local/vm.env" in Path(".gitignore").read_text(encoding="utf-8")
