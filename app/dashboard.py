"""
Dashboard v2 - bybit-signal-bot dashboard'unun ABD hisse uyarlamasi, KOYU tema.
Panel duzeni referansla ayni: Strateji sozlesmesi, Filtre Boru Hatti (tiklanabilir),
Portfoy Simulasyonu (golge-bilesik), Equity, Yon Bilancosu (tikla->filtre),
Sinyaller (satir->detay), Piyasa Nabzi, Degerlendirme (kural tabanli),
Haber Akisi (canli, dis kaynak), Nasil okunur?
Veri kaynaklari: /performance /signals /status /watchlist /regime /backup/info
/universe /diag /news. Sunucu tarafinda DURUM OZETI satiri + server-diag JSON
blogu enjekte edilir (app/server.py) - uzaktan tani sozlesmesi DEGISMEZ.
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>midas-signal-bot // dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#141110; --card:#1D1916; --card2:#272119; --line:#332C23;
    --text:#EAE3D3; --muted:#9C917C; --accent:#E0A82E;
    --green:#4ADE80; --green-bg:#182E1E; --green-ink:#A9E8BD;
    --red:#F87171;   --red-bg:#341B18;   --red-ink:#F5B5AC;
    --amber:#FBBF24; --amber-bg:#322609; --amber-ink:#F8DFA0;
    --blue:#60A5FA;  --blue-bg:#152238;  --blue-ink:#BBD3F8;
    --grey-bg:#2A241D;
    --sans:Inter,Roboto,-apple-system,"SF Pro Text","Segoe UI",sans-serif;
    --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    --shadow:0 1px 2px rgba(0,0,0,.35),0 6px 16px rgba(0,0,0,.25);
  }
  *{box-sizing:border-box;margin:0}
  body{background:var(--bg);color:var(--text);font-family:var(--sans);
       font-size:13px;line-height:1.5;font-variant-numeric:tabular-nums;
       padding:12px;max-width:1560px;margin:0 auto}
  .card{background:var(--card);border:1px solid var(--line);border-radius:11px;
        box-shadow:var(--shadow);padding:12px 14px}
  h2{font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;
     color:var(--muted);margin-bottom:8px;font-weight:600}
  h2 .tag{font-size:10px;letter-spacing:0;text-transform:none;
     background:var(--grey-bg);border-radius:99px;padding:1px 7px;margin-left:6px}
  a{color:var(--blue)}
  /* header */
  .hdr{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px}
  .logo{font-weight:700;font-size:16px}.logo b{color:var(--accent)}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--green);
       display:inline-block;margin-right:6px;box-shadow:0 0 6px var(--green)}
  .dot.err{background:var(--red);box-shadow:0 0 6px var(--red)}
  .clock{color:var(--muted)} .clock b{color:var(--text)}
  .hinfo{color:var(--muted);flex:1;min-width:200px}
  .hinfo b{color:var(--text)}
  button,select,input{background:var(--card2);color:var(--text);
    border:1px solid var(--line);border-radius:8px;padding:6px 10px;
    font-family:var(--sans);font-size:12px;cursor:pointer}
  button:hover{border-color:var(--accent)}
  input{width:90px;cursor:text}
  /* kpi */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
        gap:10px;margin-bottom:10px}
  .kpi .v{font-size:21px;font-weight:700;letter-spacing:-.02em}
  .kpi .l{color:var(--muted);font-size:11.5px}
  .kpi.good .v{color:var(--green)} .kpi.bad .v{color:var(--red)}
  /* layout */
  .grid{display:grid;grid-template-columns:250px minmax(0,1fr) 320px;gap:10px}
  @media(max-width:1050px){.grid{grid-template-columns:1fr}}
  .col{display:flex;flex-direction:column;gap:10px;min-width:0}
  /* strateji */
  .contract{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:6px;margin-top:6px}
  .contract div{background:var(--card2);border-radius:7px;padding:5px 9px;
    font-size:12px}
  .contract b{display:block;color:var(--muted);font-weight:600;font-size:10.5px;
    text-transform:uppercase;letter-spacing:.05em}
  /* pipeline */
  .stage{display:flex;justify-content:space-between;align-items:center;
    padding:5px 9px;border-radius:7px;margin-bottom:4px;background:var(--card2);
    cursor:pointer;border:1px solid transparent}
  .stage:hover{border-color:var(--accent)}
  .stage b{font-size:11.5px}
  .stage .n{font-weight:700}
  .stage.sig{background:var(--green-bg);color:var(--green-ink);cursor:default}
  .stagelist{display:none;font-size:11.5px;color:var(--muted);margin:-2px 0 6px;
    padding:4px 9px;background:var(--bg);border-radius:7px;
    word-break:break-word}
  /* badges */
  .b{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;
     font-weight:600}
  .b.long{background:var(--green-bg);color:var(--green-ink)}
  .b.short{background:var(--red-bg);color:var(--red-ink)}
  .b.win{background:var(--green-bg);color:var(--green-ink)}
  .b.loss{background:var(--red-bg);color:var(--red-ink)}
  .b.open{background:var(--blue-bg);color:var(--blue-ink)}
  .b.grey{background:var(--grey-bg);color:var(--muted)}
  .b.amber{background:var(--amber-bg);color:var(--amber-ink)}
  /* table */
  table{width:100%;border-collapse:collapse}
  th{font-size:10.5px;text-transform:uppercase;color:var(--muted);
     text-align:left;padding:5px 6px;border-bottom:1px solid var(--line)}
  td{padding:6px;border-bottom:1px solid var(--card2);font-size:12.5px}
  tbody tr{cursor:pointer}
  tbody tr:hover td{background:var(--card2)}
  .num{text-align:right;font-family:var(--mono);font-size:.94em;
       letter-spacing:-.01em}
  .clock b{font-family:var(--mono);font-weight:500}
  /* KPI tooltip balonu (hover) */
  .kpi{position:relative}
  .kpi[data-tip]:hover::after{content:attr(data-tip);position:absolute;
    top:calc(100% + 6px);left:0;z-index:40;background:#0C0A08;
    border:1px solid var(--line);color:var(--text);padding:8px 11px;
    border-radius:9px;font-size:11.8px;line-height:1.45;font-weight:400;
    width:max-content;max-width:250px;white-space:normal;
    box-shadow:0 8px 20px rgba(0,0,0,.5)}
  /* kart basligi bilgi balonu */
  .tipwrap{position:relative;cursor:help;border-bottom:1px dotted var(--muted)}
  .tipwrap .i{color:var(--blue);font-size:10px;vertical-align:1px}
  .tipwrap:hover::after{content:attr(data-tip);position:absolute;
    top:calc(100% + 6px);left:0;z-index:40;background:#0C0A08;
    border:1px solid var(--line);color:var(--text);padding:9px 12px;
    border-radius:9px;font-size:11.8px;line-height:1.5;font-weight:400;
    width:max-content;max-width:310px;white-space:normal;text-transform:none;
    letter-spacing:0;box-shadow:0 8px 20px rgba(0,0,0,.5)}
  /* boru hatti asama tooltip'i */
  .stage{position:relative}
  .stage[data-tip]:hover::after{content:attr(data-tip);position:absolute;
    left:calc(100% + 8px);top:0;z-index:40;background:#0C0A08;
    border:1px solid var(--line);color:var(--text);padding:8px 11px;
    border-radius:9px;font-size:11.5px;line-height:1.45;font-weight:400;
    width:230px;white-space:normal;box-shadow:0 8px 20px rgba(0,0,0,.5)}
  @media(max-width:1050px){.stage[data-tip]:hover::after{left:0;top:100%}}
  .tabs{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
  .tabs button.on{border-color:var(--blue);background:var(--blue-bg);
                  color:var(--blue-ink)}
  .muted{color:var(--muted)}
  .pre{white-space:pre-wrap;font-size:12px}
  .wl{display:flex;flex-wrap:wrap;gap:5px}
  .foot{margin-top:10px;color:var(--muted);font-size:11.5px}
  canvas{max-height:230px}
  /* simulasyon */
  .simrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
  .simout{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));
    gap:8px}
  .simout div{background:var(--card2);border-radius:7px;padding:6px 9px}
  .simout b{display:block;font-size:10.5px;color:var(--muted);
    text-transform:uppercase}
  .simout span{font-size:16px;font-weight:700}
  /* haber */
  .news{max-height:340px;overflow-y:auto;display:flex;flex-direction:column;gap:7px}
  .news a{color:var(--text);text-decoration:none;font-size:12.3px;line-height:1.35;
    display:block}
  .news a:hover{color:var(--accent)}
  .news .meta{color:var(--muted);font-size:10.5px}
  .news .sym{color:var(--accent);font-weight:600}
  /* modal */
  .overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);
    z-index:50;align-items:center;justify-content:center;padding:16px}
  .overlay.on{display:flex}
  .modal{background:var(--card);border:1px solid var(--line);border-radius:12px;
    max-width:480px;width:100%;max-height:85vh;overflow-y:auto;padding:16px}
  .kvrow{display:flex;justify-content:space-between;padding:4px 0;
    border-bottom:1px solid var(--card2);font-size:12.5px}
  .kvrow b{color:var(--muted);font-weight:600}
  details{margin-bottom:8px}
  summary{cursor:pointer;font-weight:600;font-size:12.5px}
  details p{color:var(--muted);font-size:12px;margin:4px 0 0 14px}
</style>
</head>
<body>
  <div class="hdr card">
    <span class="logo"><span class="dot" id="dot"></span>midas-<b>signal</b>-bot</span>
    <span class="clock">NY <b id="clkNY">--:--</b> · TR <b id="clkTR">--:--</b></span>
    <span class="hinfo" id="hinfo">yukleniyor...</span>
    <span><button onclick="fontStep(-1)" title="yazi kucult">A&#8722;</button>
    <button onclick="fontStep(1)" title="yazi buyut">A+</button></span>
    <select id="refsel">
      <option value="30000">30 sn</option>
      <option value="60000" selected>60 sn</option>
      <option value="300000">5 dk</option>
    </select>
    <button onclick="loadAll()">&#10227; Yenile</button>
  </div>

  <div class="card" style="margin-bottom:10px">
    <h2>Strateji <span class="tag">strateji sozlesmesi</span></h2>
    <div><b>Kisa vadeli swing (1-3 gun, time-stop 4 islem gunu).</b> Yapi once
    gelir; rejim + trend + bilanco filtreleri gecilmeden setup'a bakilmaz.
    Kenar net degilse karar <b>NO_TRADE</b>. Emirler Midas'tan manuel girilir.</div>
    <div class="contract">
      <div><b>Zaman dilimi</b>1D &#8594; 1h</div>
      <div><b>Hacim teyidi</b>&#8805; 1.3&#215; ort.</div>
      <div><b>Min risk/odul</b>2.0 (TP2)</div>
      <div><b>Setup</b>pullback &#183; breakout+retest</div>
      <div><b>Maliyet filtresi</b>TP1 &#8805; %2</div>
      <div><b>Bilanco</b>&#177;2 gun yasak</div>
      <div><b>Evren</b>Midas + likidite</div>
      <div><b>Short</b>yalniz BEAR + zayif RS</div>
    </div>
  </div>

  <div class="card" style="margin-bottom:10px">
    <h2><span class="tipwrap" data-tip="Acik golge sinyallerin canli fiyatla durumu. R su an = (fiyat-dolum)/risk. Oneriler kural tabanlidir; karar her zaman senindir. Fiyatlar 60 sn onbelleklidir.">Aksiyon Paneli <span class="i">&#9432;</span></span> <span class="tag">canli fiyat &#183; kural tabanli oneri</span></h2>
    <div style="overflow-x:auto"><table>
      <thead><tr><th>Sembol</th><th>Yon</th><th>Durum</th>
        <th class="num">Fiyat</th><th class="num">R su an</th>
        <th class="num">Stop'a</th><th class="num">TP1'e</th>
        <th>Time-stop</th><th>Oneri</th></tr></thead>
      <tbody id="liveRows"><tr><td colspan="9" class="muted">acik sinyal yok -
        ilk sinyalle birlikte dolar</td></tr></tbody>
    </table></div>
  </div>

  <div class="card" style="margin-bottom:10px">
    <h2>Takvim Seridi <span class="tag">5 islem gunu</span></h2>
    <div id="calStrip" class="wl muted">-</div>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="grid">
    <div class="col">
      <div class="card">
        <h2>Filtre Boru Hatti <span class="tag">tikla &#8594; elenenler</span></h2>
        <div id="pipeline" class="muted">tarama bekleniyor...</div>
      </div>
      <div class="card">
        <h2>Rejim</h2>
        <div id="regime" class="muted">-</div>
      </div>
      <div class="card">
        <h2>Piyasa Nabzi <span class="tag">gunluk not</span></h2>
        <div id="mnote" class="muted pre">Hazirlik taramasiyla olusur (15:45 TR).</div>
      </div>
      <div class="card">
        <h2><span class="tipwrap" data-tip="Her islem gunu acilis-30dk penceresinde acik pozisyonlar ve guclu adaylar pre-market fiyatlariyla yoklanir. Stop otesinde acilis = 'limit emirle cikisi degerlendir' uyarisi. Seans disi sinyal URETILMEZ.">Gap Nobeti <span class="i">&#9432;</span></span> <span class="tag">acilis oncesi</span></h2>
        <div id="gapw" class="muted pre">Bugun henuz kosmadi
(acilis-30dk penceresi).</div>
      </div>
      <div class="card">
        <h2>Izleme listesi</h2>
        <div id="watch" class="wl muted">-</div>
      </div>
      <div class="card">
        <h2>Gist yedek</h2>
        <div id="backup" class="muted">-</div>
      </div>
    </div>

    <div class="col">
      <div class="card">
        <h2><span class="tipwrap" data-tip="Sonuclanan golge sinyaller kapanis sirasiyla bilesik islenir: her islemde bakiyenin risk %'i kadar tutar riske atilir, sonuc RxRisk olarak eklenir. Kapasite modu: sermaye slot sayisina bolunur; defter doluyken gelen sinyal ATLANIR - gercek hesabin yasayacagi kisiti taklit eder. Komisyon/kayma yok; gercek para degildir.">Portfoy Simulasyonu <span class="i">&#9432;</span></span> <span class="tag">golge &#183; bilesik</span></h2>
        <div class="simrow">
          <label>Baslangic $ <input id="simStart" type="number" value="1000"></label>
          <label>Risk % <input id="simRisk" type="number" value="1" step="0.5"></label>
        </div>
        <div class="simout" id="simOut"><div><b>durum</b><span class="muted">hesaplaniyor...</span></div></div>
      </div>
      <div class="card">
        <h2>Kumulatif R (Equity) <span class="tag">yesil WIN &#183; kirmizi LOSS</span></h2>
        <canvas id="equity"></canvas>
        <div id="eqEmpty" class="muted" style="display:none">
          Henuz sonuclanmis islem yok. Golge mod veri biriktiriyor.</div>
      </div>
      <div class="card">
        <h2>Sinyaller &#183; Golge Takip <span class="tag">satira tikla &#8594; detay</span></h2>
        <div class="tabs" id="tabs">
          <button data-f="all" class="on">Tumu</button>
          <button data-f="open">Acik</button>
          <button data-f="closed">Sonuclanan</button>
          <button data-f="nf">Dolmayan</button>
          <span id="dirFiltNote" class="muted" style="align-self:center"></span>
        </div>
        <div style="overflow-x:auto"><table>
          <thead><tr><th>Sembol</th><th>Yon</th><th>Kalite</th><th>Durum</th>
            <th class="num">Canli</th><th class="num">Giris</th>
            <th class="num">Stop</th><th class="num">TP1</th>
            <th class="num">R</th><th>Acilis</th></tr></thead>
          <tbody id="sigRows"><tr><td colspan="10" class="muted">yukleniyor...</td></tr></tbody>
        </table></div>
      </div>
    </div>

    <div class="col">
      <div class="card">
        <h2><span class="tipwrap" data-tip="Sonuclanan sinyallerin LONG/SHORT kirilimi (adet ve toplam R). ABD hisselerinin yapisal yukari egilimi nedeniyle short tarafinin uzun vadede daha zayif kalmasi beklenir; veri bunu dogrularsa esikler sikilastirilir.">Yon Bilancosu <span class="i">&#9432;</span></span> <span class="tag">tikla &#8594; yon filtresi</span></h2>
        <div id="dir" class="muted">-</div>
      </div>
      <div class="card">
        <h2>Degerlendirme <span class="tag">kural tabanli &#183; saatlik</span></h2>
        <div id="cmt" class="muted pre">Ilk degerlendirme seans icinde uretilir.</div>
      </div>
      <div class="card">
        <h2>Haber Akisi <span class="tag">izlenen hisseler &#183; dis kaynak</span></h2>
        <div id="news" class="news muted">yukleniyor...</div>
      </div>
      <div class="card">
        <h2>Nasil okunur?</h2>
        <details><summary>R (risk katsayisi)</summary>
          <p>Her islemin sonucu riske atilan birim cinsinden: kayip &#8776; -1R
          (gap'te daha derin olabilir), kazanc = odul/risk orani kadar.</p></details>
        <details><summary>Win rate ve basabas</summary>
          <p>Kazanclar kayiplardan buyukse %50 isabet gerekmez.
          Basabas = 1 / (1 + ort. kazanc R).</p></details>
        <details><summary>Filtre boru hatti</summary>
          <p>DATA &#8594; REJIM &#8594; TREND &#8594; BILANCO &#8594; SETUP &#8594;
          HACIM &#8594; RR; biri gecilemezse NO_TRADE. Asamaya tiklayinca
          elenen semboller listelenir.</p></details>
        <details><summary>PENDING &#8594; FILLED &#8594; WIN/LOSS</summary>
          <p>Girise gelmesi ~2 seans beklenir; gelirse ~4 seans (time-stop)
          izlenir. Once stop = LOSS, once TP1 = WIN; ayni barda ikisi sayilmaz.
          NOT_FILLED orana dahil edilmez.</p></details>
        <details><summary>Gap muhasebesi</summary>
          <p>Hisseler gece gap yapar; bar stop/TP'nin otesinde acilirsa cikis
          ACILIS fiyatindan sayilir. Stop garantisi yoktur - kayit -1R'den
          derin dusebilir.</p></details>
        <div class="muted" style="font-size:11.5px;margin-top:6px">
          Tum sonuclar <b>golge muhasebedir</b>: varsayimsal giris,
          komisyon/spread yok, gercek emir yok. Piyasa Nabzi ve Degerlendirme
          kural tabanli otomatik uretimdir (canli insan/LLM yorumu degildir).
          Haber basliklari dis kaynaktan aynen aktarilir. Gecmis performans
          garanti degildir; yatirim tavsiyesi degildir.</div>
      </div>
    </div>
  </div>
  <div class="foot">Karar destegi - yatirim tavsiyesi degildir. Emirler Midas'tan manuel girilir.</div>

  <div class="overlay" id="ovl" onclick="if(event.target===this)closeModal()">
    <div class="modal">
      <h2 id="mTitle">Detay</h2>
      <canvas id="mChart" width="440" height="220"
        style="width:100%;background:var(--bg);border-radius:8px"></canvas>
      <div class="muted" id="mChartNote" style="font-size:10.5px;margin:2px 0 8px"></div>
      <div class="card2" style="background:var(--card2);border-radius:8px;
        padding:8px 10px;margin-bottom:8px">
        <h2 style="margin-bottom:4px">Pozisyon buyuklugu</h2>
        <div class="simrow" style="margin-bottom:6px">
          <label>Hesap $ <input id="psAcct" type="number" value="1000"></label>
          <label>Risk % <input id="psRisk" type="number" value="1" step="0.5"></label>
        </div>
        <div id="psOut" class="muted" style="font-size:12.5px">-</div>
      </div>
      <div id="mBody"></div>
      <div style="margin-top:10px;text-align:right">
        <button onclick="closeModal()">Kapat</button></div>
    </div>
  </div>

<script>
let SIG=[], FILT="all", DIRF="ALL", CHART=null, STAGES={}, TIMER=null;

function tickClock(){
  const f=tz=>new Date().toLocaleTimeString('tr-TR',
    {timeZone:tz,hour:'2-digit',minute:'2-digit',second:'2-digit'});
  document.getElementById('clkNY').textContent=f('America/New_York');
  document.getElementById('clkTR').textContent=f('Europe/Istanbul');
}
setInterval(tickClock,1000);tickClock();

async function j(u){try{const r=await fetch(u);if(!r.ok)return null;
  return await r.json();}catch(e){return null}}

function kpi(l,v,cls,tip){return `<div class="card kpi ${cls||''}"${tip?` data-tip="${tip}"`:''}>
  <div class="v">${v}</div><div class="l">${l}</div></div>`}
function fontStep(d){
  const html=document.documentElement;
  const cur=parseFloat(getComputedStyle(html).fontSize)||16;
  html.style.fontSize=Math.min(20,Math.max(13,cur+d))+'px';
}

async function loadAll(){
  const [perf,sigs,status,watch,regime,backup,uni,dg,news,live]=await Promise.all([
    j('/performance'),j('/signals?limit=300'),j('/status'),j('/watchlist'),
    j('/regime'),j('/backup/info'),j('/universe'),j('/diag'),j('/news'),
    j('/live')]);
  renderLive(live);
  if(dg){renderSession(dg.session);renderCal(dg.calendar_strip);
    renderGapWatch(dg.gap_watch);}
  document.getElementById('dot').className='dot'+(status?'':' err');

  const meta=(status&&status.meta)||{};
  document.getElementById('hinfo').innerHTML=
    `Son tarama: <b>${meta.last_scan_utc||'-'}</b> &#183; #${meta.scan_count??'-'}`+
    (uni?` &#183; Evren: <b>${uni.filtered_count??'-'}</b> (${uni.source||'-'})`:'');

  if(perf){
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
      watch.map(w=>`<span class="b ${w.state==='SIGNAL'?'win':'grey'}"
        title="${w.blocked_by||''}">${w.symbol}</span>`).join('')
      :'<span class="muted">bos</span>';
  }
  if(dg){
    document.getElementById('mnote').textContent =
      dg.market_note || 'Hazirlik taramasiyla olusur (15:45 TR).';
    const c=dg.commentary_latest;
    document.getElementById('cmt').textContent =
      c ? `[${(c.ts_utc||'').slice(0,16).replace('T',' ')} UTC]\n${c.text}`
        : 'Ilk degerlendirme seans icinde uretilir.';
  }
  renderNews(news);
  if(sigs){SIG=sigs;renderSigs();renderEquity();renderSim();}
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
  const el=document.getElementById('sessBadge'); if(!SESS){el.textContent='seans: -';return;}
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

let LIVEPX={};
function renderLive(live){
  const rows=(live&&live.rows)||[];
  LIVEPX={};rows.forEach(r=>{if(r.quote!=null)LIVEPX[r.symbol]=r.quote;});
  const el=document.getElementById('liveRows');
  if(!rows.length){el.innerHTML='<tr><td colspan="9" class="muted">acik sinyal yok'+
    ' - ilk sinyalle birlikte dolar</td></tr>';return;}
  const pct=v=>v==null?'\u2014':v.toFixed(1)+'%';
  const act=a=>{
    const hot=a.includes('IHLALI')||a.includes('KOVALAMAK')||a.includes('doldu');
    const good=a.includes('TP1')||a.includes('BOLGES');
    return `<span class="b ${hot?'loss':good?'win':'grey'}">${a}</span>`;};
  el.innerHTML=rows.map(r=>
    `<tr onclick="openSigBySym('${r.symbol}')"><td><b>${r.symbol}</b></td>
     <td><span class="b ${r.direction==='LONG'?'long':'short'}">${r.direction}</span></td>
     <td><span class="b open">${r.status}</span></td>
     <td class="num">${r.quote??'\u2014'}</td>
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
    if(d.holiday)return `<div class="stage" style="cursor:default;flex-direction:column;align-items:flex-start;min-width:120px">
      <b>${gun[d.weekday]||d.weekday} ${d.date.slice(5)}</b>
      <span class="b grey">TATIL</span></div>`;
    const ev=[];
    if(d.early_close)ev.push('<span class="b amber">erken kapanis 13:00</span>');
    d.time_stops.forEach(s=>ev.push(`<span class="b loss">T-stop: ${s}</span>`));
    d.earnings.forEach(s=>ev.push(`<span class="b amber">Bilanco: ${s}</span>`));
    return `<div class="stage" style="cursor:default;flex-direction:column;align-items:flex-start;gap:3px;min-width:120px">
      <b>${gun[d.weekday]||d.weekday} ${d.date.slice(5)}</b>
      <span style="display:flex;flex-wrap:wrap;gap:3px">${ev.join('')||'<span class="muted">-</span>'}</span></div>`;
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
  document.getElementById('pipeline').innerHTML=
    `<div class="stage" style="cursor:default"><b>Taranan</b><span class="n">${total}</span></div>`+
    stages.map(s=>`<div class="stage" data-tip="${STAGE_TIPS[s]||''}" onclick="toggleStage('${s}')">
      <b>${s}</b><span class="n">${(STAGES[s]||[]).length}</span></div>
      <div class="stagelist" id="st-${s}"></div>`).join('')+
    `<div class="stage sig"><b>SIGNAL</b><span class="n">${signals}</span></div>`;
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
    `<tr onclick="openSig(${s.id})"><td><b>${s.symbol}</b></td>
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
document.getElementById('psAcct').addEventListener('input',renderPS);
document.getElementById('psRisk').addEventListener('input',renderPS);

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
  ctx.fillStyle='rgba(96,165,250,.14)';
  ctx.fillRect(P,y(s.entry_max),W-P-4,y(s.entry_min)-y(s.entry_max));
  line(s.stop_loss,'#F87171');line(s.tp1,'#4ADE80',[4,3]);
  line(s.tp2,'#4ADE80',[2,4]);
  // mumlar
  data.forEach((c,i)=>{
    const x=P+i*step+step/2,up=c.close>=c.open;
    ctx.strokeStyle=ctx.fillStyle=up?'#4ADE80':'#F87171';
    ctx.beginPath();ctx.moveTo(x,y(c.high));ctx.lineTo(x,y(c.low));ctx.stroke();
    const top=y(Math.max(c.open,c.close)),bot=y(Math.min(c.open,c.close));
    ctx.fillRect(x-bw/2,top,bw,Math.max(1,bot-top));});
  // y ekseni etiketleri
  ctx.fillStyle='#9C917C';ctx.font='10px sans-serif';
  [lo+pad,(lo+hi)/2,hi-pad].forEach(v=>ctx.fillText(v.toFixed(1),2,y(v)+3));
}
function closeModal(){document.getElementById('ovl').classList.remove('on')}

function decidedSorted(){
  return SIG.filter(s=>s.status==='CLOSED'&&s.r_multiple!=null&&
    s.outcome!=='NOT_FILLED'&&s.outcome!=='AMBIGUOUS')
    .sort((a,b)=>(a.closed_utc||'').localeCompare(b.closed_utc||''));
}

function renderSim(){
  const start=parseFloat(document.getElementById('simStart').value)||1000;
  const riskPct=(parseFloat(document.getElementById('simRisk').value)||1)/100;
  const K=Math.max(1,parseInt(document.getElementById('simSlot').value)||4);
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
       (${refRet>=0?'+':''}${refRet.toFixed(1)}%)</span></div>`;
}
document.getElementById('simSlot').addEventListener('input',renderSim);
document.getElementById('simStart').addEventListener('input',renderSim);
document.getElementById('simRisk').addEventListener('input',renderSim);

function renderEquity(){
  const closed=decidedSorted();
  const empty=document.getElementById('eqEmpty'), cv=document.getElementById('equity');
  if(!closed.length){empty.style.display='block';cv.style.display='none';return;}
  empty.style.display='none';cv.style.display='block';
  let cum=0;
  const pts=closed.map(s=>{cum+=s.r_multiple;return {x:(s.closed_utc||'').slice(5,16).replace('T',' '),y:+cum.toFixed(2),o:s.outcome}});
  if(CHART)CHART.destroy();
  CHART=new Chart(cv,{type:'line',data:{labels:pts.map(p=>p.x),
    datasets:[{data:pts.map(p=>p.y),borderColor:'#60A5FA',
      backgroundColor:'rgba(96,165,250,.10)',fill:true,tension:.25,
      pointRadius:4,pointBackgroundColor:pts.map(p=>p.o==='WIN'?'#4ADE80':(p.o==='LOSS'?'#F87171':'#FBBF24')),
      pointBorderColor:'#141110',pointBorderWidth:1.5}]},
    options:{plugins:{legend:{display:false}},
      scales:{y:{grid:{color:'#2B2620'},ticks:{color:'#9C917C'}},
        x:{grid:{display:false},ticks:{color:'#9C917C',maxTicksLimit:8}}},
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
      ${n.symbol?`<span class="sym">${n.symbol}</span> `:''}${n.headline}
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
