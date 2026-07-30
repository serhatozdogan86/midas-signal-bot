"""
Dashboard v3 - MIDAS SIGNAL terminal.
Tasarim: murekkep-mavisi grafit + eski altin imza (Midas), Space Grotesk /
Inter / IBM Plex Mono, kart golgesi yok, 1px cizgiler, yogun izgara.
Imza oge: sunucunun DURUM OZETI satiri sayfanin tepesinde altin "durum
bandi" olarak yasar (<!--TAPE--> yer tutucusuna app/server.py enjekte eder).
Id sozlesmesi (35 element) ve JS mantigi v2.x ile ayni; yalniz gorunum
katmani yeniden yazildi.
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MIDAS SIGNAL // terminal</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  /* ============ MIDAS SIGNAL terminal — tasarim belirtimi ============
     Zemin: murekkep-mavisi grafit (saf siyah degil). Imza: ESKI ALTIN —
     yalniz marka, kesit isaretleri ve durum bandinda. Tipografi:
     Space Grotesk (marka) / Inter (govde) / IBM Plex Mono (tum rakamlar).
     Duzen: kart golgesi yok; 1px cizgiler, 6px max radius, yogun izgara. */
  :root{
    --ink0:#0B0E14; --ink1:#10141D; --ink2:#161B26; --hair:#222A38;
    --txt:#D9DFEA; --dim:#7A8496; --faint:#4A5364;
    --gold:#D7B15F; --gold-dim:#8A7440;
    --up:#2FBF71; --up-bg:#0F241A; --dn:#E5484D; --dn-bg:#2A1417;
    --warn:#E0A336; --warn-bg:#291F0E; --info:#5B93FF; --info-bg:#131E33;
    --disp:"Space Grotesk",Inter,sans-serif;
    --sans:Inter,-apple-system,"Segoe UI",sans-serif;
    --mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box;margin:0}
  html{scrollbar-color:var(--hair) var(--ink0)}
  body{background:var(--ink0);color:var(--txt);font-family:var(--sans);
       font-size:13px;line-height:1.5;-webkit-font-smoothing:antialiased}
  a{color:var(--info);text-decoration:none}
  a:hover{text-decoration:underline}
  button,select,input{background:var(--ink1);color:var(--txt);
    border:1px solid var(--hair);border-radius:5px;padding:5px 10px;
    font-family:var(--sans);font-size:12px;cursor:pointer}
  button:hover,select:hover{border-color:var(--gold-dim)}
  :focus-visible{outline:2px solid var(--gold);outline-offset:1px}
  input{cursor:text;font-family:var(--mono);width:84px}
  @media (prefers-reduced-motion: reduce){*{transition:none!important;
    animation:none!important}}
  @keyframes flup{0%{background:rgba(47,191,113,.28)}100%{background:transparent}}
  @keyframes fldn{0%{background:rgba(229,72,77,.28)}100%{background:transparent}}
  .flup{animation:flup 1.2s ease-out}
  .fldn{animation:fldn 1.2s ease-out}
  .ndx-up{color:var(--up)} .ndx-dn{color:var(--dn)}

  /* -------- komut cubugu -------- */
  .cmd{position:sticky;top:0;z-index:30;display:flex;align-items:center;
    gap:14px;padding:0 18px;height:46px;background:var(--ink0);
    border-bottom:1px solid var(--hair)}
  .brand{font-family:var(--disp);font-weight:700;font-size:15px;
    letter-spacing:.02em;white-space:nowrap}
  .brand b{color:var(--gold)}
  .brand .v{font-family:var(--mono);font-size:9.5px;font-weight:400;
    color:var(--faint);margin-left:6px;letter-spacing:.08em}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--up);
    display:inline-block;margin-right:8px;vertical-align:1px}
  .dot.err{background:var(--dn)}
  .clock{font-family:var(--mono);font-size:12px;color:var(--dim);
    white-space:nowrap}
  .clock b{color:var(--txt);font-weight:500}
  .cmd .sp{flex:1;min-width:8px}
  #hinfo{font-size:12px;color:var(--dim);overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap}
  #hinfo b{color:var(--txt);font-family:var(--mono);font-weight:500}

  /* -------- durum bandi (imza oge: sunucunun gercek satiri) -------- */
  .tape{font-family:var(--mono);font-size:11.5px;letter-spacing:.01em;
    color:var(--gold);background:linear-gradient(180deg,#141208,#0F0E09);
    border-bottom:1px solid var(--gold-dim);padding:7px 18px;
    white-space:nowrap;overflow-x:auto}
  .tape a{color:var(--gold)}
  .tape::-webkit-scrollbar{height:0}

  /* -------- kesitler -------- */
  .wrap{max-width:1680px;margin:0 auto;padding:0 18px 40px}
  section{border:1px solid var(--hair);border-radius:6px;
    background:var(--ink1);margin-top:14px;overflow:hidden}
  .sec-h{display:flex;align-items:center;gap:10px;padding:9px 14px;
    border-bottom:1px solid var(--hair)}
  .sec-h h2{font-family:var(--disp);font-size:11px;font-weight:600;
    letter-spacing:.14em;text-transform:uppercase;color:var(--dim)}
  .sec-h h2::before{content:"";display:inline-block;width:3px;height:11px;
    background:var(--gold);margin-right:9px;vertical-align:-1px}
  .sec-h .tag{font-size:10.5px;color:var(--faint)}
  .sec-b{padding:12px 14px}
  .sec-b.flush{padding:0}

  /* -------- stat rayi -------- */
  .kpis{display:grid;grid-template-columns:repeat(6,1fr);
    border:1px solid var(--hair);border-radius:6px;background:var(--ink1);
    margin-top:14px;overflow:hidden}
  @media(max-width:900px){.kpis{grid-template-columns:repeat(3,1fr)}}
  .kpi{position:relative;padding:12px 16px;border-right:1px solid var(--hair)}
  .kpi:last-child{border-right:0}
  .kpi .l{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
    color:var(--faint);margin-bottom:3px}
  .kpi .v{font-family:var(--mono);font-size:21px;font-weight:600;
    letter-spacing:-.02em}
  .kpi.good .v{color:var(--up)} .kpi.bad .v{color:var(--dn)}
  .kpi[data-tip]:hover::after{content:attr(data-tip);position:absolute;
    top:calc(100% - 4px);left:12px;z-index:40;background:var(--ink0);
    border:1px solid var(--hair);color:var(--txt);padding:8px 11px;
    border-radius:4px;font-size:11.5px;font-family:var(--sans);
    line-height:1.5;width:max-content;max-width:260px;white-space:normal;
    text-transform:none;letter-spacing:0;box-shadow:0 10px 24px rgba(0,0,0,.5)}

  /* -------- izgara -------- */
  .grid{display:grid;grid-template-columns:264px minmax(0,1fr) 312px;gap:14px}
  @media(max-width:1080px){.grid{grid-template-columns:1fr}}
  .col{display:flex;flex-direction:column;min-width:0}
  .col section{margin-top:14px}
  .col section:first-child{margin-top:14px}

  /* -------- tablolar -------- */
  table{width:100%;border-collapse:collapse}
  th{font-size:10px;letter-spacing:.09em;text-transform:uppercase;
    color:var(--faint);text-align:left;padding:7px 12px;
    border-bottom:1px solid var(--hair);white-space:nowrap}
  td{padding:6px 12px;border-bottom:1px solid var(--ink2);font-size:12.5px;
    white-space:nowrap}
  tbody tr:last-child td{border-bottom:0}
  tbody tr{cursor:pointer;transition:background .12s}
  tbody tr:hover td{background:var(--ink2)}
  .num{text-align:right;font-family:var(--mono);font-size:12px}
  .sym{font-family:var(--mono);font-weight:600;letter-spacing:.02em}

  /* -------- rozetler -------- */
  .b{display:inline-block;padding:0 7px;border-radius:3px;font-size:10.5px;
    font-weight:600;line-height:18px;letter-spacing:.03em;
    font-family:var(--mono)}
  .b.long{background:var(--up-bg);color:var(--up)}
  .b.short{background:var(--dn-bg);color:var(--dn)}
  .b.win{background:var(--up-bg);color:var(--up)}
  .b.loss{background:var(--dn-bg);color:var(--dn)}
  .b.open{background:var(--info-bg);color:var(--info)}
  .b.grey{background:var(--ink2);color:var(--dim)}
  .b.amber{background:var(--warn-bg);color:var(--warn)}

  /* -------- boru hatti: veri cubuklari -------- */
  .stage{position:relative;display:grid;
    grid-template-columns:98px 1fr 34px;gap:8px;align-items:center;
    padding:4px 0;cursor:pointer;border-radius:3px}
  .stage:hover{background:var(--ink2)}
  .stage b{font-size:10.5px;letter-spacing:.05em;color:var(--dim);
    font-weight:600;padding-left:4px}
  .stage .bar{height:8px;border-radius:2px;background:var(--ink2);
    overflow:hidden}
  .stage .bar i{display:block;height:100%;background:var(--gold-dim)}
  .stage.sig .bar i{background:var(--up)}
  .stage.sig b{color:var(--up)}
  .stage .n{font-family:var(--mono);font-size:11.5px;text-align:right;
    color:var(--txt);padding-right:4px}
  .stage[data-tip]:hover::after{content:attr(data-tip);position:absolute;
    left:0;top:100%;z-index:40;background:var(--ink0);
    border:1px solid var(--hair);color:var(--txt);padding:8px 11px;
    border-radius:4px;font-size:11.5px;line-height:1.45;width:236px;
    white-space:normal;box-shadow:0 10px 24px rgba(0,0,0,.5)}
  .stagelist{display:none;font-size:11px;color:var(--dim);margin:2px 0 6px;
    padding:6px 8px;background:var(--ink0);border:1px solid var(--hair);
    border-radius:4px;word-break:break-word;font-family:var(--mono)}

  /* -------- baslik bilgi balonu -------- */
  .tipwrap{position:relative;cursor:help}
  .tipwrap .i{color:var(--gold-dim);font-size:10px;margin-left:4px}
  .tipwrap:hover::after{content:attr(data-tip);position:absolute;
    top:calc(100% + 8px);left:0;z-index:40;background:var(--ink0);
    border:1px solid var(--hair);color:var(--txt);padding:9px 12px;
    border-radius:4px;font-size:11.5px;font-family:var(--sans);
    font-weight:400;line-height:1.55;width:max-content;max-width:320px;
    white-space:normal;text-transform:none;letter-spacing:0;
    box-shadow:0 10px 24px rgba(0,0,0,.5)}

  /* -------- takvim -------- */
  .wl{display:flex;flex-wrap:wrap;gap:6px}
  .day{border:1px solid var(--hair);border-radius:5px;background:var(--ink0);
    padding:7px 10px;min-width:118px}
  .day b{font-family:var(--mono);font-size:11px;color:var(--txt);
    display:block;margin-bottom:4px}
  .day .ev{display:flex;flex-wrap:wrap;gap:3px}

  /* -------- simulasyon -------- */
  .simrow{display:flex;gap:12px;align-items:center;flex-wrap:wrap;
    margin-bottom:10px}
  .simrow label{font-size:11px;color:var(--dim)}
  .simout{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));
    gap:1px;background:var(--hair);border:1px solid var(--hair);
    border-radius:5px;overflow:hidden}
  .simout>div{background:var(--ink0);padding:8px 11px}
  .simout b{display:block;font-size:9.5px;letter-spacing:.09em;
    color:var(--faint);text-transform:uppercase;margin-bottom:2px}
  .simout span{font-family:var(--mono);font-size:15px;font-weight:600}

  /* -------- haber -------- */
  .news{max-height:360px;overflow-y:auto;display:flex;flex-direction:column}
  .news a{color:var(--txt);font-size:12.3px;line-height:1.4;display:block;
    padding:7px 0;border-bottom:1px solid var(--ink2)}
  .news a:last-child{border-bottom:0}
  .news a:hover{color:var(--gold);text-decoration:none}
  .news .meta{color:var(--faint);font-size:10.5px;font-family:var(--mono)}
  .news .nsym{color:var(--gold);font-family:var(--mono);font-weight:600;
    font-size:11px}

  /* -------- modal -------- */
  .overlay{display:none;position:fixed;inset:0;background:rgba(4,6,10,.72);
    z-index:50;align-items:center;justify-content:center;padding:16px}
  .overlay.on{display:flex}
  .modal{background:var(--ink1);border:1px solid var(--hair);border-radius:8px;
    max-width:500px;width:100%;max-height:88vh;overflow-y:auto;padding:18px}
  .modal h2{font-family:var(--disp);font-size:14px;letter-spacing:.04em;
    margin-bottom:10px}
  .kvrow{display:flex;justify-content:space-between;gap:14px;padding:5px 0;
    border-bottom:1px solid var(--ink2);font-size:12.5px}
  .kvrow b{color:var(--dim);font-weight:500}
  .kvrow span{font-family:var(--mono)}
  details{border-bottom:1px solid var(--ink2);padding:7px 0}
  details:last-of-type{border-bottom:0}
  summary{cursor:pointer;font-weight:600;font-size:12px;color:var(--txt)}
  details p{color:var(--dim);font-size:11.8px;margin:5px 0 2px 14px;
    line-height:1.55}
  .muted{color:var(--dim)}
  .pre{white-space:pre-wrap;font-size:11.8px;line-height:1.6}
  .foot{margin:20px 0 8px;color:var(--faint);font-size:11px;text-align:center}
  canvas{max-height:230px}
  .legal{font-size:11px;color:var(--faint);line-height:1.55;
    border-top:1px solid var(--hair);padding-top:8px;margin-top:8px}
</style>
</head>
<body>
  <header class="cmd">
    <span class="brand"><span class="dot" id="dot"></span>MIDAS<b>SIGNAL</b><span class="v">TERMINAL v3.0</span></span>
    <span class="clock">NY <b id="clkNY">--:--:--</b></span>
    <span class="clock">TR <b id="clkTR">--:--:--</b></span>
    <span class="b grey" id="sessBadge">seans: -</span>
    <span id="ndx" class="clock"></span>
    <span id="upd" class="clock" style="font-size:10.5px"></span>
    <span class="sp"></span>
    <span id="hinfo">baglaniyor...</span>
    <button onclick="fontStep(-1)" title="yazi kucult">A&#8722;</button>
    <button onclick="fontStep(1)" title="yazi buyut">A+</button>
    <select id="refsel" title="yenileme araligi">
      <option value="30000">30 sn</option>
      <option value="60000" selected>60 sn</option>
      <option value="300000">5 dk</option>
    </select>
    <button onclick="loadAll()">Yenile</button>
  </header>
  <!--TAPE-->

  <div class="wrap">

    <div class="kpis" id="kpis"></div>

    <section>
      <div class="sec-h">
        <h2><span class="tipwrap" data-tip="Acik golge sinyallerin canli fiyatla durumu. R su an = (fiyat - dolum) / risk. Oneriler kural tabanlidir; karar her zaman senindir. Fiyatlar 60 sn onbelleklidir.">Aksiyon Paneli<span class="i">&#9432;</span></span></h2>
        <span class="tag">canli fiyat &#183; kural tabanli oneri</span>
      </div>
      <div class="sec-b flush" style="overflow-x:auto"><table>
        <thead><tr><th>Sembol</th><th>Yon</th><th>Durum</th>
          <th class="num">Fiyat</th><th class="num">R su an</th>
          <th class="num">Stop'a</th><th class="num">TP1'e</th>
          <th>Time-stop</th><th>Oneri</th></tr></thead>
        <tbody id="liveRows"><tr><td colspan="9" class="muted">Henuz acik
          sinyal yok. Ilk sinyal geldiginde bu tablo canli fiyatla dolar.
          </td></tr></tbody>
      </table></div>
    </section>

    <section>
      <div class="sec-h"><h2>Takvim Seridi</h2>
        <span class="tag">5 islem gunu &#183; time-stop / bilanco / tatil</span></div>
      <div class="sec-b"><div id="calStrip" class="wl muted">-</div></div>
    </section>

    <div class="grid">
      <div class="col">
        <section>
          <div class="sec-h"><h2>Filtre Boru Hatti</h2>
            <span class="tag">tikla &#8594; elenenler</span></div>
          <div class="sec-b" id="pipeline"><span class="muted">Ilk taramayla
            dolar. Her cubuk o asamada elenen sembol sayisidir.</span></div>
        </section>
        <section>
          <div class="sec-h"><h2>Rejim</h2></div>
          <div class="sec-b" id="regime"><span class="muted">-</span></div>
        </section>
        <section>
          <div class="sec-h"><h2>Piyasa Nabzi</h2>
            <span class="tag">gunluk not</span></div>
          <div class="sec-b pre muted" id="mnote">Hazirlik taramasiyla
olusur (15:45 TR).</div>
        </section>
        <section>
          <div class="sec-h">
            <h2><span class="tipwrap" data-tip="Her islem gunu acilis-30dk penceresinde acik pozisyonlar ve guclu adaylar pre-market fiyatlariyla yoklanir. Stop otesinde acilis = 'limit emirle cikisi degerlendir' uyarisi. Seans disi sinyal URETILMEZ.">Gap Nobeti<span class="i">&#9432;</span></span></h2>
            <span class="tag">acilis oncesi</span></div>
          <div class="sec-b pre muted" id="gapw">Bugun henuz kosmadi
(acilis-30dk penceresi).</div>
        </section>
        <section>
          <div class="sec-h"><h2>Izleme Listesi</h2></div>
          <div class="sec-b"><div id="watch" class="wl muted">-</div></div>
        </section>
        <section>
          <div class="sec-h"><h2>Gist Yedek</h2></div>
          <div class="sec-b" id="backup"><span class="muted">-</span></div>
        </section>
      </div>

      <div class="col">
        <section>
          <div class="sec-h">
            <h2><span class="tipwrap" data-tip="Sonuclanan golge sinyaller kapanis sirasiyla bilesik islenir: her islemde bakiyenin risk %'i kadar tutar riske atilir. Kapasite modu: sermaye slot sayisina bolunur; defter doluyken gelen sinyal ATLANIR. Komisyon/kayma yok; gercek para degildir.">Portfoy Simulasyonu<span class="i">&#9432;</span></span></h2>
            <span class="tag">golge &#183; bilesik &#183; kapasiteli</span></div>
          <div class="sec-b">
            <div class="simrow">
              <label>Baslangic $ <input id="simStart" type="number" value="10000"></label>
              <label>Risk % <input id="simRisk" type="number" value="1" step="0.5"></label>
              <label>Slot <input id="simSlot" type="number" value="4" min="1" max="20"></label>
            </div>
            <div class="simout" id="simOut"><div><b>durum</b>
              <span class="muted" style="font-size:12px">ilk sonuclanan
              sinyalle hesaplanir</span></div></div>
          </div>
        </section>
        <section>
          <div class="sec-h"><h2>Kumulatif R &#183; Equity</h2>
            <span class="tag">yesil WIN &#183; kirmizi LOSS &#183; sari EXPIRED</span></div>
          <div class="sec-b">
            <canvas id="equity"></canvas>
            <div id="eqEmpty" class="muted" style="display:none">Henuz
              sonuclanmis islem yok. Golge mod veri biriktiriyor; ilk
              WIN/LOSS ile egri baslar.</div>
          </div>
        </section>
        <section>
          <div class="sec-h"><h2>Sinyaller &#183; Golge Takip</h2>
            <span class="tag">satira tikla &#8594; detay + mum grafigi</span></div>
          <div class="sec-b">
            <div class="simrow" id="tabs" style="margin-bottom:6px">
              <button data-f="all">Tumu</button>
              <button data-f="open">Acik</button>
              <button data-f="closed">Sonuclanan</button>
              <button data-f="nf">Dolmayan</button>
              <span id="dirFiltNote" class="muted" style="font-size:11px"></span>
            </div>
          </div>
          <div class="sec-b flush" style="overflow-x:auto;border-top:1px solid var(--hair)"><table>
            <thead><tr><th>Sembol</th><th>Yon</th><th>Kalite</th><th>Durum</th>
              <th class="num">Canli</th><th class="num">Giris</th>
              <th class="num">Stop</th><th class="num">TP1</th>
              <th class="num">R</th><th>Acilis</th></tr></thead>
            <tbody id="sigRows"><tr><td colspan="10" class="muted">yukleniyor...</td></tr></tbody>
          </table></div>
        </section>
      </div>

      <div class="col">
        <section>
          <div class="sec-h">
            <h2><span class="tipwrap" data-tip="Sonuclanan sinyallerin LONG/SHORT kirilimi (adet ve toplam R). ABD hisselerinin yapisal yukari egilimi nedeniyle short tarafinin uzun vadede daha zayif kalmasi beklenir.">Yon Bilancosu<span class="i">&#9432;</span></span></h2>
            <span class="tag">tikla &#8594; filtre</span></div>
          <div class="sec-b" id="dir"><span class="muted">-</span></div>
        </section>
        <section>
          <div class="sec-h"><h2>Degerlendirme</h2>
            <span class="tag">kural tabanli &#183; saatlik</span></div>
          <div class="sec-b pre muted" id="cmt">Ilk degerlendirme seans
icinde uretilir.</div>
        </section>
        <section>
          <div class="sec-h"><h2>Haber Akisi</h2>
            <span class="tag">izlenen hisseler &#183; dis kaynak</span></div>
          <div class="sec-b"><div id="news" class="news muted">yukleniyor...</div></div>
        </section>
        <section>
          <div class="sec-h"><h2>Nasil Okunur?</h2></div>
          <div class="sec-b">
            <details><summary>R (risk katsayisi)</summary>
              <p>Her islemin sonucu riske atilan birim cinsinden: kayip
              &#8776; -1R (gap'te daha derin olabilir), kazanc = odul/risk
              orani kadar.</p></details>
            <details><summary>Win rate ve basabas</summary>
              <p>Kazanclar kayiplardan buyukse %50 isabet gerekmez.
              Basabas = 1 / (1 + ort. kazanc R).</p></details>
            <details><summary>Filtre boru hatti</summary>
              <p>DATA &#8594; REJIM &#8594; TREND &#8594; BILANCO &#8594;
              SETUP &#8594; HACIM &#8594; RR; biri gecilemezse NO_TRADE.
              Cubuga tiklayinca elenen semboller listelenir.</p></details>
            <details><summary>PENDING &#8594; FILLED &#8594; WIN/LOSS</summary>
              <p>Girise gelmesi ~2 seans beklenir; gelirse ~4 seans
              (time-stop) izlenir. Once stop = LOSS, once TP1 = WIN; ayni
              barda ikisi sayilmaz. NOT_FILLED orana dahil edilmez.</p></details>
            <details><summary>Gap muhasebesi</summary>
              <p>Hisseler gece gap yapar; bar stop/TP'nin otesinde acilirsa
              cikis ACILIS fiyatindan sayilir. Stop garantisi yoktur.</p></details>
            <div class="legal">Tum sonuclar <b>golge muhasebedir</b>:
              varsayimsal giris, komisyon/spread yok, gercek emir yok.
              Piyasa Nabzi ve Degerlendirme kural tabanli otomatik uretimdir.
              Haber basliklari dis kaynaktan aynen aktarilir. Gecmis
              performans garanti degildir; yatirim tavsiyesi degildir.</div>
          </div>
        </section>
      </div>
    </div>

    <div class="foot">MIDAS SIGNAL &#183; karar destegi &#8212; yatirim
      tavsiyesi degildir &#183; emirler Midas'tan manuel girilir</div>
  </div>

  <div class="overlay" id="ovl" onclick="if(event.target===this)closeModal()">
    <div class="modal">
      <h2 id="mTitle">Detay</h2>
      <canvas id="mChart" width="460" height="220"
        style="width:100%;background:var(--ink0);border-radius:5px;
        border:1px solid var(--hair)"></canvas>
      <div class="muted" id="mChartNote"
        style="font-size:10.5px;font-family:var(--mono);margin:4px 0 10px"></div>
      <div style="border:1px solid var(--hair);border-radius:5px;
        padding:10px 12px;margin-bottom:10px;background:var(--ink0)">
        <div class="sec-h" style="border:0;padding:0 0 6px">
          <h2>Pozisyon Buyuklugu</h2></div>
        <div class="simrow" style="margin-bottom:6px">
          <label>Hesap $ <input id="psAcct" type="number" value="10000"></label>
          <label>Risk % <input id="psRisk" type="number" value="1" step="0.5"></label>
        </div>
        <div id="psOut" class="muted" style="font-size:12.3px">-</div>
      </div>
      <div id="mBody"></div>
      <div style="margin-top:12px;text-align:right">
        <button onclick="closeModal()">Kapat</button></div>
    </div>
  </div>

<script>
let SIG=[], FILT="all", DIRF="ALL", CHART=null, STAGES={}, TIMER=null, PERF=null;
function on(id,ev,fn){const el=document.getElementById(id);
  if(el)el.addEventListener(ev,fn);}
window.onerror=function(msg,src_,line){
  const el=document.getElementById('hinfo');
  if(el)el.innerHTML=`<span class="b loss">ARAYUZ HATASI: ${msg} (satir ${line}) - bu mesaji Claude'a ilet</span>`;
};

function tickFresh(){
  const el=document.getElementById('upd'); if(!el)return;
  if(!LAST_OK){el.textContent='';return;}
  const s=Math.round((Date.now()-LAST_OK)/1000);
  el.textContent=s<3?'canli':s+' sn once';
  el.style.color=s>90?'var(--warn)':'var(--faint)';
}
setInterval(tickFresh,1000);
function tickClock(){
  const f=tz=>new Date().toLocaleTimeString('tr-TR',
    {timeZone:tz,hour:'2-digit',minute:'2-digit',second:'2-digit'});
  document.getElementById('clkNY').textContent=f('America/New_York');
  document.getElementById('clkTR').textContent=f('Europe/Istanbul');
}
setInterval(tickClock,1000);tickClock();

async function j(u){
  u += (u.includes('?')?'&':'?') + '_=' + Date.now();  // edge-cache atlatici
  const ctl=new AbortController();
  const t=setTimeout(()=>ctl.abort(),12000);   // tek yavas uc sayfayi kilitleyemez
  try{const r=await fetch(u,{signal:ctl.signal,cache:'no-store'});
    if(!r.ok)return null;return await r.json();}
  catch(e){return null}
  finally{clearTimeout(t)}}

function kpi(l,v,cls,tip){return `<div class="kpi ${cls||''}"${tip?` data-tip="${tip}"`:''}>
  <div class="l">${l}</div><div class="v">${v}</div></div>`}
let ZOOM=1;
function fontStep(d){
  ZOOM=Math.min(1.35,Math.max(0.8,ZOOM+d*0.08));
  document.body.style.zoom=ZOOM;
  if(!document.body.style.zoom)                      // Firefox yedegi
    document.body.style.fontSize=(13*ZOOM)+'px';
}

async function loadAll(){
 try{
  const [perf,sigs,status,watch,regime,backup,uni,dg,news,live]=await Promise.all([
    j('/performance'),j('/signals?limit=300'),j('/status'),j('/watchlist'),
    j('/regime'),j('/backup/info'),j('/universe'),j('/diag'),j('/news'),
    j('/live')]);
  renderLive(live);
  if(dg){renderSession(dg.session);renderCal(dg.calendar_strip);
    renderGapWatch(dg.gap_watch);}
  document.getElementById('dot').className='dot'+(status?'':' err');

  const meta=(status&&status.meta)||{};
  const prog=dg&&dg.progress?`<span class="b amber">&#9881; ${dg.progress}</span> `:'';
  document.getElementById('hinfo').innerHTML=prog+
    `Son tarama: <b>${meta.last_scan_utc||'-'}</b> &#183; #${meta.scan_count??'-'}`+
    (uni?` &#183; Evren: <b>${uni.filtered_count??'-'}</b> (${uni.source||'-'})`:'');

  if(perf){
    PERF=perf;
    const wr=perf.win_rate==null?'&#8212;':(perf.win_rate*100).toFixed(0)+'%';
    const tr=perf.total_r_multiple??0;
    const co=perf.closed_by_outcome||{};
    const filled=(co.WIN?.count||0)+(co.LOSS?.count||0)+(co.EXPIRED?.count||0)+(co.AMBIGUOUS?.count||0);
    const nf=co.NOT_FILLED?.count||0;
    const fillRate=(filled+nf)?Math.round(100*filled/(filled+nf))+'%':'&#8212;';
    document.getElementById('kpis').innerHTML=
      kpi('Win Rate',wr, perf.win_rate>=0.5?'good':(perf.win_rate!=null?'bad':''),
        'WIN/(WIN+LOSS). Tek basina yanilticidir: kazanclar buyukse dusuk isabet de karli olabilir. Basabas = 1/(1+ort.kazanc R).')+
      kpi('Toplam R',(tr>0?'+':'')+tr, tr>0?'good':(tr<0?'bad':''),
        'Tum sonuclanan islemlerin R toplami. +10R = her islemde 100$ riske atilsaydi +1000$ (bilesiksiz). Sistemin gercek karnesi budur.')+
      kpi('Sonuclanan',perf.decided_trades??0,null,
        'WIN veya LOSS ile kapanan islem sayisi. 30-50 altindaki orneklemde hicbir orana guvenme.')+
      kpi('Acik sinyal',perf.open_signals??0,null,
        'Su an izlenen PENDING (girise gelmedi) + FILLED (pozisyonda) sinyaller.')+
      kpi('Giris isabeti',fillRate,null,
        'Sinyallerin ne kadari ~2 seans icinde giris bolgesine geldi. Kalici %40 alti = bolge cok uzak, tartisilir.')+
      kpi('Kayitli karar',perf.dataset?.decisions_recorded??0,null,
        'Arsivlenen tum tarama kararlari (NO_TRADE dahil) - ileriki backtest/kalibrasyon veri seti.');
    renderDir(perf);
  }

  if(status&&status.results)renderPipeline(status.results);
  if(regime){
    const map={BULL:'long',BEAR:'short',NEUTRAL:'amber',UNKNOWN:'grey'};
    document.getElementById('regime').innerHTML=
      `<span class="b ${map[regime.regime]||'grey'}">${regime.regime}</span>
       <div class="muted" style="margin-top:6px;font-size:11.5px">${regime.detail||''}</div>`;
  }
  document.getElementById('backup').innerHTML = backup&&!backup.error?
    `Son sync: <b>${backup.last_sync_utc||'henuz yok'}</b><br>
     ${backup.gist_url?`<a href="${backup.gist_url}" target="_blank">Gist arsivini ac</a>`:'gist henuz olusmadi'}`
    :'<span class="muted">kapali</span>';
  if(watch){
    document.getElementById('watch').innerHTML = watch.length?
      watch.map(w=>`<span class="b ${w.state==='SIGNAL'?'win':(w.trigger_level?'amber':'grey')}"
        title="${w.blocked_by||''}${w.trigger_level?' | tetik '+w.trigger_level:''}">${w.symbol}${w.trigger_level?' \u26A1':''}</span>`).join('')
      :'<span class="muted">Ilk taramayla dolar (16:30 TR). \u26A1 = kirilim tetigi kurulu.</span>';
  }
  if(dg){
    const busy=dg.progress?`\u2699 ${dg.progress}...`:null;
    document.getElementById('mnote').textContent =
      dg.market_note || busy || 'Hazirlik taramasiyla olusur (15:45 TR).';
    if(!(status&&status.results&&Object.keys(status.results).length)&&busy)
      document.getElementById('pipeline').innerHTML=
        `<span class="muted">${busy}</span>`;
    const c=dg.commentary_latest;
    document.getElementById('cmt').textContent =
      c ? `[${(c.ts_utc||'').slice(0,16).replace('T',' ')} UTC]\n${c.text}`
        : 'Ilk degerlendirme seans icinde uretilir.';
  }
  renderNews(news);
  if(sigs){SIG=sigs;renderSigs();renderEquity();renderSim();}
  LAST_OK=Date.now();
 }catch(e){
  document.getElementById('hinfo').innerHTML=
    `<span class="b loss">ARAYUZ HATASI: ${e.message} - bu mesaji Claude'a ilet</span>`;
 }
}

const STAGE_TIPS={
  DATA:'Yeterli gunluk (min ~210 bar) ve saatlik (min ~60 bar) mum var mi? Veri yoksa varsayim yapilmaz.',
  MARKET_REGIME:'SPY+QQQ 200 gunluk MA konumu ve egimi. BULL: yalniz long. BEAR: yalniz short. UNKNOWN: sinyal yok.',
  TREND:'Hisse bazinda MA hiyerarsisi (fiyat>50>200) + HH/HL yapisi. Short icin ayna + SPY karsisinda zayif RS sarti.',
  EARNINGS:'Bilanco tarihine +-2 islem gunu = yasak bolge. Bilanco gecesi gap riski sistematik olarak alinmaz.',
  SETUP:'1h yapida tetiklenebilir kurulum: yukselen EMA20 pullback (RSI3 asirilik + donus mumu) veya kirilim+retest.',
  VOLUME:'Tetik mumunda goreli hacim >= 1.3x (NEUTRAL rejimde 1.5x). Katilimsiz kirilima guven olmaz.',
  RISK_REWARD:'Yapisal stop ile RR >= 2.0 (tavan 6.0 - fantezi RR reddi) VE TP1 mesafesi >= %2 (Midas islem maliyeti).'};
let SESS=null;
function renderSession(s){SESS=s;paintSession();}
function paintSession(){
  const el=document.getElementById('sessBadge'); if(!el)return;
  if(!SESS){el.textContent='seans: -';return;}
  let txt=SESS.phase==='ACIK'?'SEANS ACIK':SESS.phase==='PRE'?'PRE-MARKET':'KAPALI';
  let cls=SESS.phase==='ACIK'?'b win':SESS.phase==='PRE'?'b amber':'b grey';
  if(SESS.next_event_ms){
    const ms=SESS.next_event_ms-Date.now();
    if(ms>0){const h=Math.floor(ms/3600000),m=Math.floor(ms%3600000/60000);
      txt+=` \u00b7 ${SESS.next_event} ${h>0?h+'s ':''}${m}dk`;}
  }
  el.className=cls; el.textContent=txt;
}
setInterval(paintSession,30000);

let LIVEPX={}, PREVPX={}, LAST_OK=0;
function renderLive(live){
  const rows=(live&&live.rows)||[];
  PREVPX=LIVEPX; LIVEPX={};
  rows.forEach(r=>{if(r.quote!=null)LIVEPX[r.symbol]=r.quote;});
  const nx=(live&&live.indices)||[];
  document.getElementById('ndx').innerHTML=nx.map(i=>
    `${i.symbol} <b class="${i.pct>=0?'ndx-up':'ndx-dn'}">${i.pct>=0?'+':''}${i.pct}%</b>`
  ).join(' &#183; ');
  const el=document.getElementById('liveRows');
  if(!rows.length){el.innerHTML='<tr><td colspan="9" class="muted">acik sinyal yok'+
    ' - ilk sinyalle birlikte dolar</td></tr>';return;}
  const pct=v=>v==null?'\u2014':v.toFixed(1)+'%';
  const act=a=>{
    const hot=a.includes('IHLALI')||a.includes('KOVALAMAK')||a.includes('doldu');
    const good=a.includes('TP1')||a.includes('BOLGES');
    return `<span class="b ${hot?'loss':good?'win':'grey'}">${a}</span>`;};
  el.innerHTML=rows.map(r=>
    `<tr onclick="openSigBySym('${r.symbol}')"><td class="sym">${r.symbol}</td>
     <td><span class="b ${r.direction==='LONG'?'long':'short'}">${r.direction}</span></td>
     <td><span class="b open">${r.status}</span></td>
     <td class="num${PREVPX[r.symbol]!=null&&r.quote!=null&&r.quote!==PREVPX[r.symbol]?(r.quote>PREVPX[r.symbol]?' flup':' fldn'):''}">${r.quote??'\u2014'}</td>
     <td class="num">${r.r_now!=null?(r.r_now>0?'+':'')+r.r_now+'R':'\u2014'}</td>
     <td class="num">${pct(r.dist_stop_pct)}</td>
     <td class="num">${pct(r.dist_tp1_pct)}</td>
     <td>${r.time_stop_days_left!=null?r.time_stop_days_left+' gun':'\u2014'}</td>
     <td>${act(r.action)}</td></tr>`).join('');
}
function openSigBySym(sym){
  const s=SIG.find(x=>x.symbol===sym&&x.status!=='CLOSED')||SIG.find(x=>x.symbol===sym);
  if(s)openSig(s.id);
}

function renderCal(strip){
  const el=document.getElementById('calStrip');
  if(!strip||!strip.length){el.textContent='-';return;}
  const gun={Mon:'Pzt',Tue:'Sal',Wed:'Car',Thu:'Per',Fri:'Cum'};
  el.innerHTML=strip.map(d=>{
    if(d.holiday)return `<div class="day"><b>${gun[d.weekday]||d.weekday} ${d.date.slice(5)}</b>
      <div class="ev"><span class="b grey">TATIL</span></div></div>`;
    const ev=[];
    if(d.early_close)ev.push('<span class="b amber">erken 13:00</span>');
    d.time_stops.forEach(s=>ev.push(`<span class="b loss">T-stop ${s}</span>`));
    d.earnings.forEach(s=>ev.push(`<span class="b amber">Bilanco ${s}</span>`));
    return `<div class="day"><b>${gun[d.weekday]||d.weekday} ${d.date.slice(5)}</b>
      <div class="ev">${ev.join('')||'<span class="muted" style="font-size:10.5px">sakin</span>'}</div></div>`;
  }).join('');
}

function renderGapWatch(g){
  const el=document.getElementById('gapw');
  if(!g||!g.date){el.textContent='Bugun henuz kosmadi\n(acilis-30dk penceresi).';return;}
  const pos=g.position_alerts||[], cand=g.candidate_alerts||[];
  if(!pos.length&&!cand.length){
    el.textContent=`${g.date}: ${g.checked} sembol kontrol edildi - kayda deger gap yok.`;
    return;}
  el.textContent=[`${g.date}:`,
    ...pos.map(a=>'! '+a), ...cand.map(a=>'- '+a)].join('\n');
}

function renderPipeline(results){
  const stages=['DATA','MARKET_REGIME','TREND','EARNINGS','SETUP','VOLUME','RISK_REWARD'];
  STAGES={}; let signals=0,total=0;
  Object.entries(results).forEach(([sym,r])=>{
    total++;
    if(r.decision==='SIGNAL'){signals++;return;}
    const f=(r.failed_filters&&r.failed_filters[0])||'DATA';
    (STAGES[f]=STAGES[f]||[]).push(sym);});
  const mx=Math.max(1,...stages.map(s=>(STAGES[s]||[]).length),signals);
  const bar=n=>`<div class="bar"><i style="width:${Math.max(2,Math.round(100*n/mx))}%"></i></div>`;
  document.getElementById('pipeline').innerHTML=
    `<div class="stage" style="cursor:default"><b>TARANAN</b>${bar(0).replace('width:2%','width:0')}<span class="n">${total}</span></div>`+
    stages.map(s=>{const n=(STAGES[s]||[]).length;
      return `<div class="stage" data-tip="${STAGE_TIPS[s]||''}" onclick="toggleStage('${s}')">
      <b>${s.replace('MARKET_','').replace('RISK_REWARD','RR')}</b>${bar(n)}<span class="n">${n}</span></div>
      <div class="stagelist" id="st-${s}"></div>`;}).join('')+
    `<div class="stage sig"><b>SIGNAL</b>${bar(signals)}<span class="n">${signals}</span></div>`;
}
function toggleStage(s){
  const el=document.getElementById('st-'+s);
  const open=el.style.display==='block';
  document.querySelectorAll('.stagelist').forEach(e=>e.style.display='none');
  if(!open){el.textContent=(STAGES[s]||[]).join(', ')||'bu asamada elenen yok';
    el.style.display='block';}
}

function renderDir(perf){
  const dirs={LONG:{n:0,r:0},SHORT:{n:0,r:0}};
  (perf.by_direction||[]).forEach(r=>{
    if(dirs[r.direction]){dirs[r.direction].n+=r.n;dirs[r.direction].r+=(r.sum_r||0);}});
  document.getElementById('dir').innerHTML=
    Object.entries(dirs).map(([d,v])=>
      `<div class="stage" onclick="dirFilter('${d}')">
       <b><span class="b ${d==='LONG'?'long':'short'}">${d}</span></b>
       <span>${v.n} islem &#183; ${v.r>=0?'+':''}${v.r.toFixed(2)}R</span></div>`).join('')
    +`<div class="muted" style="font-size:11px">tikla &#8594; tabloda o yon</div>`;
}
function dirFilter(d){
  DIRF=(DIRF===d)?'ALL':d;
  document.getElementById('dirFiltNote').textContent=
    DIRF==='ALL'?'':`yon filtresi: ${DIRF} (kaldirmak icin tekrar tikla)`;
  renderSigs();
}

function renderSigs(){
  let rows=SIG;
  if(DIRF!=='ALL')rows=rows.filter(s=>s.direction===DIRF);
  if(FILT==='open')rows=rows.filter(s=>s.status!=='CLOSED');
  if(FILT==='closed')rows=rows.filter(s=>s.status==='CLOSED'&&s.outcome!=='NOT_FILLED');
  if(FILT==='nf')rows=rows.filter(s=>s.outcome==='NOT_FILLED');
  const badge=s=>{
    if(s.status!=='CLOSED')return `<span class="b open">${s.status}</span>`;
    const m={WIN:'win',LOSS:'loss',NOT_FILLED:'grey',AMBIGUOUS:'grey',EXPIRED:'amber'};
    return `<span class="b ${m[s.outcome]||'grey'}">${s.outcome}</span>`;};
  const qual=s=>{
    if(!s.confidence&&!s.setup_type)return '<span class="muted">&#8212;</span>';
    const cmap={HIGH:'win',MEDIUM:'amber',MED:'amber',LOW:'grey'};
    const st=(s.setup_type||'').replace('trend_pullback','PB')
      .replace('breakout_retest','BO');
    return `${s.confidence?`<span class="b ${cmap[s.confidence]||'grey'}">${s.confidence}</span>`:''}
      ${st?` <span class="b grey">${st}</span>`:''}`;};
  const livepx=s=>{
    if(s.status==='CLOSED')return '&#8212;';
    const p=LIVEPX[s.symbol];
    return p!=null?p:'&#8212;';};
  document.getElementById('sigRows').innerHTML = rows.length? rows.map((s,i)=>
    `<tr onclick="openSig(${s.id})"><td class="sym">${s.symbol}</td>
     <td><span class="b ${s.direction==='LONG'?'long':'short'}">${s.direction}</span></td>
     <td>${qual(s)}</td>
     <td>${badge(s)}</td>
     <td class="num">${livepx(s)}</td>
     <td class="num">${s.entry_min?.toFixed(2)}&#8211;${s.entry_max?.toFixed(2)}</td>
     <td class="num">${s.stop_loss?.toFixed(2)??'-'}</td>
     <td class="num">${s.tp1?.toFixed(2)??'-'}</td>
     <td class="num">${s.r_multiple!=null?(s.r_multiple>0?'+':'')+s.r_multiple:'&#8212;'}</td>
     <td class="muted">${(s.created_utc||'').slice(0,16).replace('T',' ')}</td></tr>`).join('')
   :'<tr><td colspan="10" class="muted">kayit yok</td></tr>';
}

function openSig(id){
  const s=SIG.find(x=>x.id===id); if(!s)return;
  const rows=[
    ['Sembol',s.symbol],['Yon',s.direction],
    ['Kalite',`${s.confidence||'-'} / ${s.setup_type||'-'}`],['Durum',s.status],
    ['Sonuc',s.outcome||'-'],['Olusum',s.created_utc||'-'],
    ['Giris bolgesi',`${s.entry_min} - ${s.entry_max}`],
    ['Stop',s.stop_loss],['TP1 / TP2',`${s.tp1} / ${s.tp2}`],['RR',s.rr],
    ['Time-stop',s.time_stop_date||'-'],['Dolum fiyati',s.fill_price??'-'],
    ['Cikis fiyati',s.exit_price??'-'],
    ['R katsayisi',s.r_multiple!=null?s.r_multiple+'R':'-'],
    ['Kapanis',s.closed_utc||'-']];
  document.getElementById('mTitle').textContent=`${s.symbol} ${s.direction} sinyali`;
  document.getElementById('mBody').innerHTML=rows.map(([k,v])=>
    `<div class="kvrow"><b>${k}</b><span>${v}</span></div>`).join('');
  CURSIG=s; renderPS(); drawCandles(s);
  document.getElementById('ovl').classList.add('on');
}
let CURSIG=null;
function renderPS(){
  if(!CURSIG)return;
  const acct=parseFloat(document.getElementById('psAcct').value)||0;
  const riskPct=(parseFloat(document.getElementById('psRisk').value)||0)/100;
  const entry=(CURSIG.entry_min+CURSIG.entry_max)/2;
  const perShare=Math.abs(entry-CURSIG.stop_loss);
  const el=document.getElementById('psOut');
  if(!acct||!riskPct||!perShare){el.textContent='-';return;}
  const riskAmt=acct*riskPct, shares=riskAmt/perShare;
  el.innerHTML=`Risk tutari <b>$${riskAmt.toFixed(2)}</b> \u00b7 hisse basi risk
   <b>$${perShare.toFixed(2)}</b> \u2192 <b style="color:var(--accent);font-size:15px">
   ${shares.toFixed(2)} adet</b> (~$${(shares*entry).toFixed(0)} pozisyon).
   Midas kusurat destekler; stop ${CURSIG.stop_loss} disiplinine baglidir.`;
}
on('psAcct','input',renderPS);
on('psRisk','input',renderPS);

async function drawCandles(s){
  const cv=document.getElementById('mChart'),ctx=cv.getContext('2d');
  ctx.clearRect(0,0,cv.width,cv.height);
  const note=document.getElementById('mChartNote');
  const data=await j(`/candles?symbol=${s.symbol}&interval=1h&limit=80`);
  if(!data||data.length<5){note.textContent='mum arsivi henuz olusmadi';return;}
  note.textContent=`${s.symbol} 1h \u00b7 son ${data.length} bar \u00b7 mavi bant: giris, kirmizi: stop, yesil: TP1/TP2`;
  const W=cv.width,H=cv.height,P=34;
  const lows=data.map(c=>c.low),highs=data.map(c=>c.high);
  let lo=Math.min(...lows,s.stop_loss),hi=Math.max(...highs,s.tp2||s.tp1);
  const pad=(hi-lo)*0.05;lo-=pad;hi+=pad;
  const y=v=>H-8-(v-lo)/(hi-lo)*(H-16);
  const n=data.length,bw=Math.max(2,(W-P-6)/n*0.66),step=(W-P-6)/n;
  // seviye cizgileri
  const line=(v,color,dash)=>{if(v==null)return;ctx.strokeStyle=color;
    ctx.setLineDash(dash||[]);ctx.beginPath();ctx.moveTo(P,y(v));
    ctx.lineTo(W-4,y(v));ctx.stroke();ctx.setLineDash([]);};
  ctx.fillStyle='rgba(91,147,255,.13)';
  ctx.fillRect(P,y(s.entry_max),W-P-4,y(s.entry_min)-y(s.entry_max));
  line(s.stop_loss,'#E5484D');line(s.tp1,'#2FBF71',[4,3]);
  line(s.tp2,'#2FBF71',[2,4]);
  // mumlar
  data.forEach((c,i)=>{
    const x=P+i*step+step/2,up=c.close>=c.open;
    ctx.strokeStyle=ctx.fillStyle=up?'#2FBF71':'#E5484D';
    ctx.beginPath();ctx.moveTo(x,y(c.high));ctx.lineTo(x,y(c.low));ctx.stroke();
    const top=y(Math.max(c.open,c.close)),bot=y(Math.min(c.open,c.close));
    ctx.fillRect(x-bw/2,top,bw,Math.max(1,bot-top));});
  // y ekseni etiketleri
  ctx.fillStyle='#7A8496';ctx.font='10px IBM Plex Mono,monospace';
  [lo+pad,(lo+hi)/2,hi-pad].forEach(v=>ctx.fillText(v.toFixed(1),2,y(v)+3));
}
function closeModal(){document.getElementById('ovl').classList.remove('on')}

function decidedSorted(){
  return SIG.filter(s=>s.status==='CLOSED'&&s.r_multiple!=null&&
    s.outcome!=='NOT_FILLED'&&s.outcome!=='AMBIGUOUS')
    .sort((a,b)=>(a.closed_utc||'').localeCompare(b.closed_utc||''));
}

function renderSim(){
  const start=parseFloat(document.getElementById('simStart').value)||10000;
  const riskPct=(parseFloat(document.getElementById('simRisk').value)||1)/100;
  const slotEl=document.getElementById('simSlot');
  const K=Math.max(1,parseInt(slotEl?slotEl.value:'4')||4);
  const rows=decidedSorted();
  // Kapasite-kisitli yurutme (bybit v3.3.1 portu, hisse uyarlamasi:
  // kaldirac yok -> pozisyon nosyoneli slot payini (bakiye/K) asamaz)
  const evs=[];
  rows.forEach(s=>{evs.push([s.created_utc||'',0,s]);
                  evs.push([s.closed_utc||'',1,s]);});
  evs.sort((a,b)=>a[0].localeCompare(b[0])||a[1]-b[1]);
  let eq=start,peak=start,maxdd=0,taken=0,skipped=0;const book={};
  for(const [t,kind,s] of evs){
    if(kind===0){
      if(Object.keys(book).length>=K){skipped++;continue;}
      const e=(s.entry_min+s.entry_max)/2;
      const d=e?Math.abs(e-s.stop_loss)/e:0; if(d<=0)continue;
      let r=eq*riskPct; const notion=r/d, capN=eq/K;
      if(notion>capN)r*=capN/notion;   // slot payi asilirsa risk kucultulur
      book[s.id]=r; taken++;
    }else if(book[s.id]!=null){
      eq+=book[s.id]*s.r_multiple; delete book[s.id];
      peak=Math.max(peak,eq); maxdd=Math.max(maxdd,(peak-eq)/peak);
    }
  }
  // sinirsiz varsayim referansi
  let ref=start; rows.forEach(s=>{ref+=ref*riskPct*s.r_multiple;});
  const ret=(eq/start-1)*100, refRet=(ref/start-1)*100;
  document.getElementById('simOut').innerHTML=
    `<div><b>Bakiye (kapasiteli)</b><span>$${eq.toFixed(0)}</span></div>
     <div><b>Getiri</b><span style="color:${ret>=0?'var(--green)':'var(--red)'}">
       ${ret>=0?'+':''}${ret.toFixed(1)}%</span></div>
     <div><b>Maks DD</b><span>${(maxdd*100).toFixed(1)}%</span></div>
     <div><b>Alinan / Atlanan</b><span>${taken} / ${skipped}</span></div>
     <div><b>Sinirsiz varsayim</b><span class="muted">$${ref.toFixed(0)}
       (${refRet>=0?'+':''}${refRet.toFixed(1)}%)</span></div>
     <div><b>SPY ayni donem</b><span class="muted">${
       PERF&&PERF.benchmark?((PERF.benchmark.spy_return_pct>=0?'+':'')+
       PERF.benchmark.spy_return_pct+'%'):'&#8212;'}</span></div>`;
}
on('simSlot','input',renderSim);
on('simStart','input',renderSim);
on('simRisk','input',renderSim);

function renderEquity(){
  const closed=decidedSorted();
  const empty=document.getElementById('eqEmpty'), cv=document.getElementById('equity');
  if(!closed.length){empty.style.display='block';cv.style.display='none';return;}
  empty.style.display='none';cv.style.display='block';
  let cum=0;
  const pts=closed.map(s=>{cum+=s.r_multiple;return {x:(s.closed_utc||'').slice(5,16).replace('T',' '),y:+cum.toFixed(2),o:s.outcome}});
  if(CHART)CHART.destroy();
  CHART=new Chart(cv,{type:'line',data:{labels:pts.map(p=>p.x),
    datasets:[{data:pts.map(p=>p.y),borderColor:'#5B93FF',
      backgroundColor:'rgba(91,147,255,.08)',fill:true,tension:.25,
      pointRadius:4,pointBackgroundColor:pts.map(p=>p.o==='WIN'?'#2FBF71':(p.o==='LOSS'?'#E5484D':'#E0A336')),
      pointBorderColor:'#0B0E14',pointBorderWidth:1.5}]},
    options:{plugins:{legend:{display:false}},
      scales:{y:{grid:{color:'#222A38'},ticks:{color:'#7A8496'}},
        x:{grid:{display:false},ticks:{color:'#7A8496',maxTicksLimit:8}}},
      maintainAspectRatio:false}});
}

function renderNews(news){
  const el=document.getElementById('news');
  const items=(news&&news.items)||[];
  if(!items.length){
    el.innerHTML='<span class="muted">Haber akisi seans gunlerinde dolar '+
      '(Finnhub). Izlenen sembol olustukca sirket haberleri eklenir.</span>';
    return;}
  el.innerHTML=items.map(n=>{
    const t=n.datetime?new Date(n.datetime*1000).toLocaleTimeString('tr-TR',
      {hour:'2-digit',minute:'2-digit'}):'';
    return `<a href="${n.url}" target="_blank" rel="noopener">
      ${n.symbol?`<span class="nsym">${n.symbol}</span> `:''}${n.headline}
      <div class="meta">${n.source||''} &#183; ${t}</div></a>`;}).join('');
}

document.getElementById('tabs').addEventListener('click',e=>{
  if(e.target.dataset.f===undefined)return;
  FILT=e.target.dataset.f;
  document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b===e.target));
  renderSigs();});

document.getElementById('refsel').addEventListener('change',e=>{
  clearInterval(TIMER);TIMER=setInterval(loadAll,parseInt(e.target.value));});

loadAll();
TIMER=setInterval(loadAll,60000);
</script>
</body>
</html>"""
