"""
OZ-DENETIM (v4.8) - botun kendi kendini kontrol etmesi.

NEDEN: bugune kadarki her ciddi hatayi ben ELLE "Durum?" bakarken
yakaladim (bilanco filtresinin sessizce kapanmasi, gap nobetinin
sessiz atlamasi, evrenin bayatlamasi, OOM restartlari). Elle bakmak
olceklenmez ve ben yokken kimse bakmiyor. Bu modul o kontrolleri
DEGISMEZ (invariant) haline getirir: her gun sonu kosar, bozulani
Telegram'a bildirir.

TASARIM ILKESI: her kontrol tek bir soruya "evet/hayir" cevabi verir
ve BOZULDUGUNDA NE YAPILACAGINI soyler. "Uyari" degil, "sunu kontrol
et" der. Kontroller SAF: durum okur, hicbir sey degistirmez.

Siniflar:
  VERI     - besleme tazeligi (evren, bilanco, gunluk mum)
  KARAR    - filtrelerin gercekten calisip calismadigi
  DEFTER   - golge defterin ic tutarliligi
  KOHORT   - kilit butunlugu (engine_sha kaymasi, tavan ihlali)
  YEDEK    - gist yedeginin yasi
  LABORATUVAR - olcum katmanlarinin beslenip beslenmedigi
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.logging_setup import kv

log = logging.getLogger("self_audit")


@dataclass
class Check:
    name: str
    group: str
    ok: bool
    detail: str
    action: str = ""            # bozulduysa NE YAPILMALI
    severity: str = "warn"      # warn | critical


@dataclass
class AuditReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict:
        return {"ok": self.ok, "failed": len(self.failures),
                "total": len(self.checks),
                "checks": [c.__dict__ for c in self.checks]}

    def telegram_text(self) -> str:
        crit = [c for c in self.failures if c.severity == "critical"]
        head = ("OZ-DENETIM: %d/%d kontrol BASARISIZ"
                % (len(self.failures), len(self.checks)))
        if crit:
            head = "KRITIK " + head
        lines = [head]
        for c in self.failures:
            mark = "!!" if c.severity == "critical" else "*"
            lines.append(f"{mark} [{c.group}] {c.name}: {c.detail}")
            if c.action:
                lines.append(f"   -> {c.action}")
        return "\n".join(lines)


def _iso_age_hours(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        import datetime as dt
        t = dt.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600
    except Exception:
        return None


def run_audit(db, tracker=None, universe=None, earnings=None,
              gist=None, exit_lab=None, strategy_lab=None,
              engine_sha: str | None = None, settings=None,
              notifier=None, telegram=None) -> AuditReport:
    """Tum degismezleri kontrol eder. Hicbir sey DEGISTIRMEZ."""
    rep = AuditReport()

    def add(name, group, ok, detail, action="", severity="warn"):
        rep.checks.append(Check(name, group, bool(ok), detail, action,
                                severity))

    # ---------------- VERI ----------------
    if universe is not None:
        try:
            u = universe.describe()
            stale = u.get("stale_days")
            add("evren tazeligi", "VERI", stale is not None and stale <= 2,
                f"bayatlik {stale} gun, {u.get('filtered_count')} sembol",
                "Midas scrape veya likidite filtresi bozuk olabilir; "
                "/universe ve loglara bak", "critical")
        except Exception as e:
            add("evren tazeligi", "VERI", False, f"okunamadi: {e!r}")

    if earnings is not None:
        try:
            st = earnings.status()
            add("bilanco takvimi", "VERI", st.get("ready"),
                f"ready={st.get('ready')} sembol={st.get('symbols')} "
                f"fail_streak={st.get('fail_streak')}",
                "Takvim yoksa motor fail-closed'a gecer ve SINYAL "
                "URETMEZ; Finnhub/yedek kaynagi kontrol et", "critical")
        except Exception as e:
            add("bilanco takvimi", "VERI", False, f"okunamadi: {e!r}")

    # ---------------- KARAR ----------------
    # Bilanco filtresi kapaliyken sinyal dogmus mu? (3 Agu vakasi)
    # v4.22: kontrol "SU AN ready mi" degil "sinyal DOGARKEN ready miydi"
    # sorusuna bakar (dogum ani damgasi, tracker.maybe_track). Eski hal
    # gun-ici restart'ta yanlis KRITIK alarm (7 Agu, 3 sinyal + restart),
    # kesinti gun sonuna kadar toparlanirsa gercek ihlali GIZLEME
    # uretiyordu. Damgasiz eski satirlar yargisiz birakilir.
    try:
        bad = db.query(
            "SELECT COUNT(*) AS n FROM signals WHERE blocked=0 "
            "AND contract_json LIKE '%\"earnings_ready\": false%'")
        n_bad = bad[0]["n"] if bad else 0
        ready = earnings.status().get("ready") if earnings else True
        add("bilanco korumasi", "KARAR", n_bad == 0,
            f"takvim-kapaliyken-dogan sinyal: {n_bad} (takvim su an "
            f"ready={ready})",
            "Takvim yokken sinyal dogmus - fail-closed calismiyor, "
            "signal_engine EARNINGS blogunu incele", "critical")
    except Exception as e:
        add("bilanco korumasi", "KARAR", False, f"okunamadi: {e!r}")

    # ---------------- DEFTER ----------------
    if tracker is not None:
        try:
            bad = db.query(
                "SELECT COUNT(*) AS n FROM signals WHERE status='FILLED' "
                "AND fill_price IS NULL")
            add("dolum tutarliligi", "DEFTER", (bad[0]["n"] if bad else 0) == 0,
                f"fill_price'i bos FILLED kayit: {bad[0]['n'] if bad else '?'}",
                "SignalTracker._evaluate_signal dolum yolunu incele")

            orphan = db.query(
                "SELECT COUNT(*) AS n FROM signals WHERE r_multiple IS NOT NULL "
                "AND status <> 'CLOSED'")
            add("kapanis tutarliligi", "DEFTER",
                (orphan[0]["n"] if orphan else 0) == 0,
                f"R'si olup CLOSED olmayan kayit: "
                f"{orphan[0]['n'] if orphan else '?'}",
                "Kapanis yolunda yarim kalmis guncelleme var")

            dup = db.query(
                "SELECT symbol, direction, COUNT(*) AS n FROM signals "
                "WHERE blocked=0 AND status IN ('PENDING','FILLED') "
                "GROUP BY symbol, direction HAVING n > 1")
            add("mukerrer acik sinyal", "DEFTER", not dup,
                f"{len(dup)} sembol/yon ciftinde birden fazla acik kayit"
                if dup else "yok",
                "Dedup mantigi bozulmus olabilir (3 Agu cift kayit vakasi)")
        except Exception as e:
            add("defter kontrolleri", "DEFTER", False, f"okunamadi: {e!r}")

    # 13. degismez (v4.19): AYNA IZOLASYONU. Alpaca ayna katmani salt
    # olcumdur; ayna verisi yalniz kendi tablosunda (mirror_fills) yasar.
    # signals semasina mirror/alpaca alani girerse tek yonlu veri akisi
    # delinmis, ayna P&L'i defter muhasebesine sizabilir demektir
    # (tasarim sozlesmesi: app/services/alpaca_mirror.py docstring).
    try:
        cols = [r["name"] for r in db.query("PRAGMA table_info(signals)")]
        leak = [c for c in cols
                if "mirror" in c.lower() or "alpaca" in c.lower()]
        add("ayna izolasyonu", "DEFTER", not leak,
            f"signals icinde ayna alani: {leak}" if leak else "sema ayrik",
            "Ayna izolasyon sozlesmesi ihlal - alpaca_mirror docstring'e "
            "bak, sutunu kaldir ve sizinti yolunu kapat", "critical")
    except Exception as e:
        add("ayna izolasyonu", "DEFTER", False, f"okunamadi: {e!r}")

    # ---------------- KOHORT ----------------
    if engine_sha:
        try:
            # v4.23: bilincli yeni kilitte eski kohortun ACIK sinyalleri
            # (eski sha) ihlal degildir; yalniz kilit ANINDAN SONRA dogan
            # farkli sha kohort kirlenmesidir. Kilit ani yoksa eski
            # davranis (tum acik sinyallar) korunur.
            lock = getattr(settings, "CONFIG_LOCK_UTC", None) if settings else None
            q = ("SELECT DISTINCT engine_sha FROM signals WHERE blocked=0 "
                 "AND status IN ('PENDING','FILLED') AND engine_sha IS NOT NULL")
            qargs: tuple = ()
            if lock:
                q += " AND created_utc>=?"
                qargs = (lock,)
            shas = db.query(q, qargs)
            others = [r["engine_sha"] for r in shas
                      if r["engine_sha"] != engine_sha]
            add("motor surumu", "KOHORT", not others,
                f"acik sinyallerde farkli engine_sha: {others}" if others
                else f"tek surum ({engine_sha[:8]})",
                "Kilit doneminde motor degismis; kohort karisik - "
                "docs/config-lock.md ile karsilastir", "critical")
        except Exception as e:
            add("motor surumu", "KOHORT", False, f"okunamadi: {e!r}")

    if settings is not None:
        try:
            openn = db.query(
                "SELECT COUNT(*) AS n FROM signals WHERE blocked=0 "
                "AND status IN ('PENDING','FILLED')")[0]["n"]
            cap = getattr(settings, "MAX_OPEN_SIGNALS", 10)
            add("portfoy tavani", "KOHORT", openn <= cap,
                f"{openn} acik / tavan {cap}",
                "Tavan asilmis: _entry_block mantigini incele")
        except Exception as e:
            add("portfoy tavani", "KOHORT", False, f"okunamadi: {e!r}")

    # ---------------- BILDIRIM ----------------
    # v4.9 vakasi: TELEGRAM_ENABLED=false oldugu icin KRITIK uyarilar da
    # sessizce yutuluyordu ve bunu haftalarca kimse fark etmedi. Denetimin
    # kendisi de telegramla bildirildigi icin, bildirim kanali BOZUKSA
    # denetim de sessiz kalir - bu yuzden ayrica /audit'te gorunur.
    if telegram is not None:
        try:
            add("uyari kanali", "BILDIRIM",
                bool(telegram.get("configured") and telegram.get("alerts_on")),
                f"yapilandirildi={telegram.get('configured')} "
                f"uyarilar_acik={telegram.get('alerts_on')} "
                f"susturulan={telegram.get('muted')} "
                f"gonderilemeyen={telegram.get('failed')}",
                "Uyarilar kapaliysa kritik olaylari EKRAN BASINDA "
                "olmadan ogrenemezsin; TELEGRAM_ALERTS_ENABLED ve "
                "TELEGRAM_BOT_TOKEN/CHAT_ID kontrol et", "critical")
        except Exception as e:
            add("uyari kanali", "BILDIRIM", False, f"okunamadi: {e!r}")

    # ---------------- YEDEK ----------------
    if gist is not None:
        try:
            info = gist.info()
            age = _iso_age_hours(info.get("last_sync_utc"))
            add("gist yedegi", "YEDEK", age is not None and age < 36,
                f"son yedek {age:.1f} saat once" if age is not None
                else "yedek zamani bilinmiyor",
                "Yedek durursa restart'ta defter kaybedilir; "
                "GITHUB_TOKEN ve /backup/info kontrol et", "critical")
        except Exception as e:
            add("gist yedegi", "YEDEK", False, f"okunamadi: {e!r}")

    # ---------------- LABORATUVAR ----------------
    if exit_lab is not None:
        try:
            s = exit_lab.summary()
            n_sig = s.get("signals", 0)
            v = s.get("variants", {})
            covered = all(k in v for k in ("V0_CANLI", "V1_KISMI",
                                           "V2_GENIS", "V3_ORTA"))
            add("cikis laboratuvari", "LABORATUVAR", covered,
                f"{n_sig} sinyal, varyantlar: {sorted(v)}",
                "Varyant eksikse kiyas bozulur - exit_lab.run loglarina bak")
        except Exception as e:
            add("cikis laboratuvari", "LABORATUVAR", False, f"okunamadi: {e!r}")

    if strategy_lab is not None:
        try:
            last = getattr(strategy_lab, "last", {}) or {}
            add("strateji laboratuvari", "LABORATUVAR", bool(last),
                f"evren {last.get('universe')} sembol" if last
                else "henuz kosmadi",
                "Gun sonu kosumu calismiyor olabilir")
        except Exception as e:
            add("strateji laboratuvari", "LABORATUVAR", False, f"hata: {e!r}")

    log.info(kv(event="self_audit", total=len(rep.checks),
                failed=len(rep.failures)))
    return rep


def _today_iso() -> str:
    return time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime())
