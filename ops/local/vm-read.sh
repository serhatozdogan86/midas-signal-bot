#!/usr/bin/env bash
# VM SALT-OKUR KOPRUSU (anayasa 4.5'in "posta kutusu anahtari")
#
# NEDEN VAR (1 Eyl 2026): yerel oturum VM'e her bakisinda Serhat'a komut
# yapistirtiyor; bu, "komut kosturmayi Serhat'tan isteme" kuralinin tam
# tersi. Cozum olarak "ssh *" kalibina kalici izin verilemez - anayasa
# 4.5 bunu ACIKCA yasaklar, cunku o kalibin icinden SILEN/DEGISTIREN
# komut da gecer. Bu betik aradaki dogru yol: izin BU DOSYAYA verilir,
# ssh'in tamamina degil. Ic kismi SABIT bir komut listesidir; disaridan
# gelen metin uzak kabuga GECMEZ.
#
# NE YAPAR (yalniz bunlar):
#   durum      /dx     - nabiz
#   audit      /audit  - oz-denetim degismezleri
#   diag       /diag   - tam teshis (rejim, ayna, golive)
#   zarar      zarar anatomisi raporu (F1)
#   ayna       ayna uyusmazlik orani (hipotez 7)
#   anatomi    ayna uyusmazlik anatomisi (nufuz orani)
#   surum      calisan commit + servis durumu
#   log        son 50 satir servis gunlugu
#
# NE YAPMAZ: deploy, restart, git pull/push, dosya silme, env duzenleme,
# rasgele komut. Bunlarin hepsi ONAYA TABI kalir (4.5) ve deploy.sh ile
# yapilir - seans kilidi orada (2.5).
#
# KURULUM (bir kez, yerel makinede):
#   cp ops/local/vm.env.example ops/local/vm.env   # ve icini doldur
#   chmod +x ops/local/vm-read.sh
# vm.env git'e GIRMEZ (.gitignore); icinde sir yok ama makineye ozel
# yol/adres bilgisi var.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
[ -f "$here/vm.env" ] && . "$here/vm.env"

VM_HOST="${VM_HOST:-}"
VM_KEY="${VM_KEY:-}"
VM_DIR="${VM_DIR:-/opt/midas-signal-bot}"
VM_PORT="${VM_PORT:-8100}"

if [ -z "$VM_HOST" ] || [ -z "$VM_KEY" ]; then
    echo "HATA: VM_HOST/VM_KEY tanimli degil."
    echo "Once ops/local/vm.env dosyasini olustur (ornek: vm.env.example)."
    exit 2
fi

usage() {
    echo "kullanim: vm-read.sh {durum|audit|diag|zarar|ayna|anatomi|surum|log}"
    exit 2
}
[ $# -eq 1 ] || usage

# Uzak tarafta kosacak SABIT komutlar. Disaridan parametre almazlar -
# tirnak icindeki metin bu dosyada yazilidir, cagiran secemez.
case "$1" in
    durum)   remote="curl -sf http://127.0.0.1:$VM_PORT/dx" ;;
    audit)   remote="curl -sf http://127.0.0.1:$VM_PORT/audit" ;;
    diag)    remote="curl -sf http://127.0.0.1:$VM_PORT/diag" ;;
    zarar)   remote="cd $VM_DIR && python3 tools/loss_anatomy.py --db data/bot.db" ;;
    ayna)    remote="cd $VM_DIR && python3 tools/mirror_disagreement.py --db data/bot.db" ;;
    anatomi) remote="cd $VM_DIR && python3 tools/mirror_pair_anatomy.py --db data/bot.db" ;;
    surum)   remote="cd $VM_DIR && git log --oneline -1 && systemctl is-active midas-signal-bot" ;;
    log)     remote="journalctl -u midas-signal-bot -n 50 --no-pager" ;;
    *)       usage ;;
esac

exec ssh -i "$VM_KEY" -o BatchMode=yes -o ConnectTimeout=15 \
    "$VM_HOST" "$remote"
