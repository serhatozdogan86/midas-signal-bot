# -*- coding: utf-8 -*-
"""Midas Sinyal Bot - Kullanici El Kitabi icin ogretici grafikler."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D
import numpy as np

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
})

GREEN = "#1a9850"
RED = "#d73027"
BLUE = "#3060c0"
GOLD = "#c98a1a"
GRAY = "#666666"
LIGHT = "#f2f2f2"
INK = "#1a1a2e"

OUT = "/home/claude/handbook/charts"

# ============================================================
# 1) PIPELINE FLOWCHART - 9 filtreli karar hatti
# ============================================================
def chart_pipeline():
    fig, ax = plt.subplots(figsize=(9, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 30)
    ax.axis("off")

    steps = [
        ("1. DATA", "Yeterli mum var mi?\n(min. bar sayisi)", "#4a4a6a"),
        ("2. MARKET_REGIME", "SPY & QQQ 200 gunluk\nortalamaya gore BULL / BEAR / NEUTRAL", "#2a5a8a"),
        ("3. TREND", "Hisse kendi trendinde mi?\n(MA sirasi + HH/HL veya LH/LL)", "#2a5a8a"),
        ("4. EARNINGS", "Bilancoya \u00b12 gun\niçinde mi? (varsa dur)", "#7a4a2a"),
        ("5. SETUP (1 saatlik)", "Geri cekilme (pullback) veya\nkirilim + yeniden test (breakout)", "#2a5a8a"),
        ("6. VOLUME", "Tetik mumunda hacim\nyeterince yuksek mi?", "#2a5a8a"),
        ("7. CONFLUENCE", "(Filtre degil - guven puani)\nGoreceli guc + sektor + 52H yakinlik", "#6a2a8a"),
        ("8. RISK_REWARD", "Risk/Odul yeterli mi?\nHedef, maliyeti asiyor mu?", "#2a5a8a"),
        ("9. SIGNAL", "SINYAL URETILDI\nGiris, Stop, TP1/TP2, R/R, Guven", GREEN),
    ]
    y0 = 28.5
    dy = 3.05
    box_w, box_h = 7.2, 2.15
    cx = 4.4
    for i, (title, desc, color) in enumerate(steps):
        y = y0 - i * dy
        is_last = (i == len(steps) - 1)
        box = FancyBboxPatch((cx - box_w/2, y - box_h/2), box_w, box_h,
                              boxstyle="round,pad=0.08,rounding_size=0.18",
                              linewidth=1.4, edgecolor=color,
                              facecolor=(color if is_last else "white"), alpha=1.0)
        ax.add_patch(box)
        txt_color = "white" if is_last else "#111111"
        ax.text(cx, y + 0.42, title, ha="center", va="center",
                fontsize=13, fontweight="bold", color=(color if not is_last else "white"))
        ax.text(cx, y - 0.42, desc, ha="center", va="center", fontsize=9.3, color=txt_color)

        if i < len(steps) - 1:
            ax.annotate("", xy=(cx, y - box_h/2 - 0.9), xytext=(cx, y - box_h/2),
                        arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.6))
            # basarisiz / fail dali (CONFLUENCE haric)
            if title != "7. CONFLUENCE":
                fail_label = "NO_TRADE" if i < 4 else ("NO_TRADE" if i != 6 else "")
                ax.annotate("", xy=(cx + box_w/2 + 1.7, y), xytext=(cx + box_w/2, y),
                            arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.3))
                ax.text(cx + box_w/2 + 1.85, y, "NO_TRADE" if title != "7. CONFLUENCE" else "",
                        fontsize=8.5, color=RED, va="center", fontweight="bold")

    ax.text(cx, 30.3, "Karar Hatti: 9 Basamakli Elemeli Sistem",
            ha="center", fontsize=15, fontweight="bold", color=INK)
    ax.text(cx, -0.6, "Herhangi bir basamakta FAIL olursa hisse elenir (kisa devre);\n"
            "sinyal SADECE tum basamaklar gecilirse uretilir.",
            ha="center", fontsize=9.5, color=GRAY, style="italic")
    plt.tight_layout()
    plt.savefig(f"{OUT}/01_pipeline.png", dpi=155, bbox_inches="tight", facecolor="white")
    plt.close()


# ============================================================
# 2) PULLBACK SETUP - ornek mum grafigi
# ============================================================
def draw_candles(ax, opens, highs, lows, closes, x=None, width=0.6):
    if x is None:
        x = np.arange(len(opens))
    for i in range(len(opens)):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        color = GREEN if c >= o else RED
        ax.plot([x[i], x[i]], [l, h], color=color, linewidth=1.1, zorder=2)
        y0, y1 = min(o, c), max(o, c)
        ax.add_patch(Rectangle((x[i]-width/2, y0), width, max(y1-y0, 0.05),
                                facecolor=color, edgecolor=color, zorder=3))


def chart_pullback():
    rng = np.random.default_rng(7)
    n = 46
    # yukselen trend + EMA'ya geri cekilme + donus mumu + devam
    base = np.concatenate([
        np.linspace(100, 118, 22),                  # yukselis
        np.linspace(118, 109, 10),                   # geri cekilme (EMA'ya dogru)
        np.array([108.6, 108.2, 109.4]),              # donus mumlari (RSI asiri satim + toparlama)
        np.linspace(110, 124, 11),                    # devam
    ])
    noise = rng.normal(0, 0.55, n)
    closes = base + noise
    opens = np.r_[closes[0]-0.4, closes[:-1] + rng.normal(0, 0.3, n-1)]
    highs = np.maximum(opens, closes) + np.abs(rng.normal(0.5, 0.35, n))
    lows = np.minimum(opens, closes) - np.abs(rng.normal(0.5, 0.35, n))

    ema = np.zeros(n)
    ema[0] = closes[0]
    k = 2/(20+1)
    for i in range(1, n):
        ema[i] = closes[i]*k + ema[i-1]*(1-k)

    fig, ax = plt.subplots(figsize=(11, 6.2))
    draw_candles(ax, opens, highs, lows, closes)
    ax.plot(ema, color=BLUE, linewidth=2.0, label="Yukselen 20 EMA", zorder=4)

    entry_i = 34
    entry_price = closes[entry_i] + 0.3
    stop_price = min(lows[31:35]) - 0.4
    tp1_price = entry_price + (entry_price - stop_price) * 1.0
    tp2_price = entry_price + (entry_price - stop_price) * 2.0

    ax.axhline(entry_price, color="#333333", linewidth=1, linestyle="--")
    ax.axhline(stop_price, color=RED, linewidth=1.3, linestyle="--")
    ax.axhline(tp1_price, color=GREEN, linewidth=1.1, linestyle=":")
    ax.axhline(tp2_price, color=GREEN, linewidth=1.1, linestyle=":")

    ax.text(n-0.5, entry_price, "  GIRIŞ", va="center", fontsize=10, fontweight="bold")
    ax.text(n-0.5, stop_price, "  STOP (-1R)", va="center", fontsize=10, color=RED, fontweight="bold")
    ax.text(n-0.5, tp1_price, "  TP1 (+1R)", va="center", fontsize=10, color=GREEN, fontweight="bold")
    ax.text(n-0.5, tp2_price, "  TP2 (+2R)", va="center", fontsize=10, color=GREEN, fontweight="bold")

    ax.annotate("Geri çekilme:\nRSI(3) aşırı satım\n+ dönüş mumu",
                xy=(32, closes[32]-1), xytext=(20, 96),
                fontsize=9.5, ha="center",
                arrowprops=dict(arrowstyle="->", color="#333333"),
                bbox=dict(boxstyle="round,pad=0.35", fc="#fff7e6", ec="#c98a1a"))
    ax.annotate("Yukselen trend:\nfiyat > 50MA > 200MA\nHH / HL yapisi",
                xy=(10, closes[10]+3), xytext=(4, 125),
                fontsize=9.5, ha="center",
                arrowprops=dict(arrowstyle="->", color="#333333"),
                bbox=dict(boxstyle="round,pad=0.35", fc="#eaf5ea", ec=GREEN))

    ax.set_xlim(-1, n+8)
    ax.set_title("SETUP Örneği A: Trend İçi Geri Çekilme (\"Pullback\")", fontsize=14, fontweight="bold")
    ax.set_ylabel("Fiyat ($)")
    ax.set_xticks([])
    ax.legend(loc="lower right", fontsize=10, frameon=True)
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(f"{OUT}/02_pullback.png", dpi=155, facecolor="white")
    plt.close()


# ============================================================
# 3) BREAKOUT + RETEST - ornek mum grafigi
# ============================================================
def chart_breakout():
    rng = np.random.default_rng(21)
    n = 44
    resistance = 112.0
    base = np.concatenate([
        100 + 8*np.sin(np.linspace(0, 3.4, 24)) * 0.55 + 6,   # yatay sikisma (konsolidasyon)
        np.linspace(112.5, 121, 6),                             # kirilim
        np.linspace(121, 112.8, 6),                              # yeniden test
        np.linspace(113.5, 124, 8),                               # devam
    ])
    noise = rng.normal(0, 0.4, n)
    closes = base + noise
    opens = np.r_[closes[0]-0.3, closes[:-1] + rng.normal(0, 0.25, n-1)]
    highs = np.maximum(opens, closes) + np.abs(rng.normal(0.45, 0.3, n))
    lows = np.minimum(opens, closes) - np.abs(rng.normal(0.45, 0.3, n))

    fig, ax = plt.subplots(figsize=(11, 6.2))
    draw_candles(ax, opens, highs, lows, closes)
    ax.axhline(resistance, color=GOLD, linewidth=1.8, linestyle="-",
               label="Kırılım seviyesi (direnç)")

    entry_i = 34
    entry_price = closes[entry_i] + 0.25
    stop_price = resistance - 1.1
    tp1_price = entry_price + (entry_price - stop_price) * 1.0
    tp2_price = entry_price + (entry_price - stop_price) * 2.0

    ax.axhline(entry_price, color="#333333", linewidth=1, linestyle="--")
    ax.axhline(stop_price, color=RED, linewidth=1.3, linestyle="--")
    ax.axhline(tp1_price, color=GREEN, linewidth=1.1, linestyle=":")
    ax.axhline(tp2_price, color=GREEN, linewidth=1.1, linestyle=":")

    ax.text(n-0.5, entry_price, "  GIRIŞ", va="center", fontsize=10, fontweight="bold")
    ax.text(n-0.5, stop_price, "  STOP (-1R)", va="center", fontsize=10, color=RED, fontweight="bold")
    ax.text(n-0.5, tp1_price, "  TP1 (+1R)", va="center", fontsize=10, color=GREEN, fontweight="bold")
    ax.text(n-0.5, tp2_price, "  TP2 (+2R)", va="center", fontsize=10, color=GREEN, fontweight="bold")

    ax.annotate("Kırılım:\nseviyeyi hacimle geçti",
                xy=(26, 118), xytext=(14, 128),
                fontsize=9.5, ha="center",
                arrowprops=dict(arrowstyle="->", color="#333333"),
                bbox=dict(boxstyle="round,pad=0.35", fc="#fff7e6", ec=GOLD))
    ax.annotate("Yeniden test:\neski direnç şimdi\ndestek oluyor",
                xy=(33, stop_price+1.2), xytext=(37, 100),
                fontsize=9.5, ha="center",
                arrowprops=dict(arrowstyle="->", color="#333333"),
                bbox=dict(boxstyle="round,pad=0.35", fc="#eaf5ea", ec=GREEN))

    ax.set_xlim(-1, n+8)
    ax.set_title("SETUP Örneği B: Kırılım + Yeniden Test (\"Breakout + Retest\")",
                 fontsize=14, fontweight="bold")
    ax.set_ylabel("Fiyat ($)")
    ax.set_xticks([])
    ax.legend(loc="upper left", fontsize=10, frameon=True)
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(f"{OUT}/03_breakout.png", dpi=155, facecolor="white")
    plt.close()


# ============================================================
# 4) R-MULTIPLE DIAGRAM
# ============================================================
def chart_r_multiple():
    fig, ax = plt.subplots(figsize=(9, 6))
    entry, stop, tp1, tp2 = 100, 96, 104, 108
    ax.axhspan(stop, entry, xmin=0.15, xmax=0.85, color=RED, alpha=0.18)
    ax.axhspan(entry, tp1, xmin=0.15, xmax=0.85, color=GREEN, alpha=0.15)
    ax.axhspan(tp1, tp2, xmin=0.15, xmax=0.85, color=GREEN, alpha=0.28)

    for y, label, color, weight in [
        (tp2, "TP2  ·  +2R", GREEN, "bold"),
        (tp1, "TP1  ·  +1R", GREEN, "bold"),
        (entry, "GİRİŞ  ·  0R", "#111111", "bold"),
        (stop, "STOP  ·  −1R", RED, "bold"),
    ]:
        ax.axhline(y, color=color, linewidth=1.6)
        ax.text(0.87, y, label, transform=ax.get_yaxis_transform(), fontsize=12.5,
                color=color, fontweight=weight, va="center")

    ax.annotate("", xy=(0.5, entry), xytext=(0.5, stop),
                xycoords=("axes fraction", "data"),
                arrowprops=dict(arrowstyle="<->", color=RED, lw=1.8))
    ax.text(0.44, (entry+stop)/2, "1R\n(riske attığın)", ha="right", va="center",
            fontsize=10.5, color=RED, transform=ax.get_yaxis_transform())

    ax.annotate("", xy=(0.5, tp1), xytext=(0.5, entry),
                xycoords=("axes fraction", "data"),
                arrowprops=dict(arrowstyle="<->", color=GREEN, lw=1.8))
    ax.text(0.44, (tp1+entry)/2, "1R\n(TP1 ödülü)", ha="right", va="center",
            fontsize=10.5, color=GREEN, transform=ax.get_yaxis_transform())

    ax.set_ylim(stop-2, tp2+2)
    ax.set_xlim(0, 1)
    ax.axis("off")
    ax.set_title("R Nedir? Riskin Evrensel Ölçü Birimi", fontsize=15, fontweight="bold", pad=18)
    ax.text(0.5, -0.06, "Örnek: Giriş $100, Stop $96 → risk = $4 = \"1R\".\n"
            "TP1 $104 = +1R kazanç, TP2 $108 = +2R kazanç. Hesap büyüklüğünden bağımsız,\n"
            "her işlemi aynı cetvelle karşılaştırmanı sağlar.",
            transform=ax.transAxes, ha="center", fontsize=10.3, color=GRAY)
    plt.tight_layout()
    plt.savefig(f"{OUT}/04_r_multiple.png", dpi=155, facecolor="white")
    plt.close()


# ============================================================
# 5) REJIM TESPITI + HISTEREZIS BANDI
# ============================================================
def chart_regime():
    rng = np.random.default_rng(3)
    n = 140
    trend = np.concatenate([
        np.linspace(400, 440, 50),
        np.linspace(440, 428, 30),
        np.linspace(428, 460, 60),
    ])
    price = trend + rng.normal(0, 2.2, n).cumsum() * 0.15
    ma200 = np.convolve(price, np.ones(20)/20, mode="same")
    ma200[:10] = ma200[10]
    ma200[-10:] = ma200[-11]

    band_pct = 0.012
    upper = ma200 * (1 + band_pct)
    lower = ma200 * (1 - band_pct)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(price, color="#333333", linewidth=1.3, label="SPY / QQQ endeks fiyatı")
    ax.plot(ma200, color=BLUE, linewidth=2, label="200 günlük ortalama")
    ax.fill_between(range(n), lower, upper, color=GOLD, alpha=0.22,
                     label="Histerezis bandı (±%0.5) — \"gürültü bölgesi\"")

    ax.axvspan(0, 45, color=GREEN, alpha=0.07)
    ax.axvspan(45, 95, color=GOLD, alpha=0.07)
    ax.axvspan(95, n, color=GREEN, alpha=0.07)
    ax.text(20, 468, "BULL", fontsize=13, fontweight="bold", color=GREEN, ha="center")
    ax.text(70, 468, "NEUTRAL\n(bant içi/geçiş)", fontsize=11, fontweight="bold",
            color="#8a6a10", ha="center")
    ax.text(118, 468, "BULL", fontsize=13, fontweight="bold", color=GREEN, ha="center")

    ax.set_title("Piyasa Rejimi Tespiti: 200 Günlük Ortalama + Histerezis Bandı",
                 fontsize=14, fontweight="bold")
    ax.set_xticks([])
    ax.set_ylabel("Endeks seviyesi")
    ax.legend(loc="lower right", fontsize=9.5, frameon=True)
    ax.grid(axis="y", alpha=0.2)
    ax.text(0.5, -0.1, "Rejim değişimi için son 2 kapanışın da bandın DIŞINDA olması gerekir;\n"
            "tek bir sert gün rejimi anında değiştiremez (\"testere\" hareketine karşı fren).",
            transform=ax.transAxes, ha="center", fontsize=9.8, color=GRAY)
    plt.tight_layout()
    plt.savefig(f"{OUT}/05_regime.png", dpi=155, facecolor="white")
    plt.close()


# ============================================================
# 6) PORTFOY ISI MOTORU - tavanlar
# ============================================================
def chart_heat():
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    caps = [
        ("Eşzamanlı toplam\n(MAX_OPEN_SIGNALS)", 10),
        ("Günlük yeni sinyal\n(MAX_DAILY_SIGNALS)", 6),
        ("Aynı yön\n(MAX_DIR_SIGNALS)", 8),
        ("Aynı küme (yön+gün)\n(MAX_CLUSTER_SIGNALS)", 3),
    ]
    labels = [c[0] for c in caps]
    values = [c[1] for c in caps]
    colors = [BLUE, GOLD, "#7a4aa0", RED]
    bars = ax.barh(labels, values, color=colors, height=0.55)
    for b, v in zip(bars, values):
        ax.text(v + 0.15, b.get_y() + b.get_height()/2, str(v),
                va="center", fontsize=13, fontweight="bold")
    ax.set_xlim(0, 12)
    ax.set_xlabel("Eşzamanlı izin verilen sinyal sayısı")
    ax.set_title("Portföy Isı Motoru: Dört Kat Fren", fontsize=14, fontweight="bold")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.25)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    plt.tight_layout()
    plt.savefig(f"{OUT}/06_heat.png", dpi=155, facecolor="white")
    plt.close()


# ============================================================
# 7) NET-R MALIYET MODELI - dar vs genis stop
# ============================================================
def chart_cost_model():
    fig, ax = plt.subplots(figsize=(9, 5.8))
    scenarios = ["Dar stop\n(%0.5 mesafe)", "Orta stop\n(%2 mesafe)", "Geniş stop\n(%5 mesafe)"]
    # sabit $250 risk, komisyon 2x1.50$+5bp kayma -> buyuk nosyonel dar stop'ta
    risk_usd = 250
    dists = [0.005, 0.02, 0.05]
    costs = []
    for d in dists:
        notional = risk_usd / d
        cost = 2*1.50 + notional * 0.0005
        costs.append(cost / risk_usd)  # R cinsinden maliyet

    bars = ax.bar(scenarios, costs, color=[RED, GOLD, GREEN], width=0.55)
    for b, c in zip(bars, costs):
        ax.text(b.get_x()+b.get_width()/2, c+0.002, f"{c:.3f}R",
                ha="center", fontsize=12.5, fontweight="bold")
    ax.set_ylabel("İşlem maliyeti (R cinsinden)")
    ax.set_title("Neden Dar Stop Bazen Daha \"Pahalı\"?", fontsize=14, fontweight="bold")
    ax.grid(axis="y", alpha=0.25)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.text(0.5, -0.22,
            "Aynı $250 risk için: dar stopta aynı riski taşımak daha BÜYÜK pozisyon\n"
            "gerektirir → Midas'ın sabit $1,50×2 komisyonu + kayma, göreceli olarak\n"
            "R'nin daha büyük bir dilimini yer.",
            transform=ax.transAxes, ha="center", fontsize=9.8, color=GRAY)
    plt.tight_layout()
    plt.savefig(f"{OUT}/07_cost_model.png", dpi=155, facecolor="white")
    plt.close()


# ============================================================
# 8) GUNLUK ZAMAN CIZELGESI
# ============================================================
def chart_schedule():
    fig, ax = plt.subplots(figsize=(11, 3.6))
    events = [
        (15.75, "15:45\nHazırlık", BLUE),
        (16.0, "16:00\nGap Nöbeti", GOLD),
        (16.5, "16:30\nSeans Açılış", GREEN),
        (23.0, "23:00\nSeans Kapanış", RED),
        (23.25, "23:15\nGün Sonu Raporu", "#7a4aa0"),
    ]
    ax.axhline(0, color="#999999", linewidth=2, zorder=1)
    ax.set_xlim(15.5, 23.6)
    ax.set_ylim(-1, 1.6)
    ax.axis("off")

    ax.annotate("", xy=(23.0, 0), xytext=(16.5, 0),
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=10, alpha=0.25))
    ax.text((16.5+23.0)/2, 0.85, "SEANS: Kaba tarama (15 dk'da bir, tüm evren)\n"
            "+ İnce tarama (~1 dk'da bir, izleme listesi)",
            ha="center", fontsize=10, color="#1a6a1a", fontweight="bold")

    for x, label, color in events:
        ax.plot([x, x], [-0.15, 0.15], color=color, linewidth=3)
        ax.scatter([x], [0], color=color, s=90, zorder=5, edgecolor="white", linewidth=1.2)
        y_txt = -0.55 if x in (16.0, 23.25) else -0.9
        ax.text(x, y_txt, label, ha="center", fontsize=9.6, fontweight="bold", color=color)

    ax.set_title("Botun Günlük Ritmi (Türkiye Saati)", fontsize=14, fontweight="bold", pad=6)
    plt.tight_layout()
    plt.savefig(f"{OUT}/08_schedule.png", dpi=155, facecolor="white")
    plt.close()


# ============================================================
# 9) EKUITI EGRISI / DUSUS ORNEGI
# ============================================================
def chart_equity():
    rng = np.random.default_rng(11)
    trades = rng.choice([1.8, 1.2, -1.0, -1.0, 2.4, -1.0, 0.9, -1.0, -1.0, 1.5,
                         -1.0, 1.1, 2.0, -1.0, -1.0, 1.3, -1.0, 1.9, -1.0, 1.0], 20)
    cum = np.cumsum(trades)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd_i = np.argmax(dd)
    peak_i = np.argmax(cum[:max_dd_i+1]) if max_dd_i > 0 else 0

    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    ax.plot(range(1, 21), cum, color=BLUE, linewidth=2.2, marker="o", markersize=4)
    ax.axhline(0, color="#999999", linewidth=1)
    ax.fill_between(range(1, 21), cum, peak, where=(peak > cum), color=RED, alpha=0.18,
                     label="Düşüş (drawdown) bölgesi")
    ax.annotate(f"Maks. düşüş: {dd[max_dd_i]:.1f}R",
                xy=(max_dd_i+1, cum[max_dd_i]), xytext=(max_dd_i-3.6, cum[max_dd_i]-2.6),
                fontsize=10.5, fontweight="bold", color=RED,
                arrowprops=dict(arrowstyle="->", color=RED))
    ax.axhline(8, color=GOLD, linewidth=1.3, linestyle="--")
    ax.text(0.6, 8.3, "Kilit eşiği: 8R (aşılırsa gölge mod durur)", fontsize=9, color="#8a6a10")

    ax.set_xlabel("İşlem sırası (sonuçlanma sırasına göre)")
    ax.set_ylabel("Kümülatif R")
    ax.set_title("Örnek Kümülatif R Eğrisi ve Düşüş (Drawdown) Ölçümü",
                 fontsize=14, fontweight="bold")
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(f"{OUT}/09_equity.png", dpi=155, facecolor="white")
    plt.close()


if __name__ == "__main__":
    chart_pipeline()
    chart_pullback()
    chart_breakout()
    chart_r_multiple()
    chart_regime()
    chart_heat()
    chart_cost_model()
    chart_schedule()
    chart_equity()
    print("9 grafik uretildi.")
