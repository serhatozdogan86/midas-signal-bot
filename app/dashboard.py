"""
Dashboard - midas-signal-bot golge mod izleme ekrani.
Kripto projesindeki (bybit-signal-bot) sicak "linen" temanin ABD hisse uyarlamasi:
- KPI kartlari: Win Rate, Toplam R, Acik sinyal, Giris isabeti, Evren
- Equity egrisi (kumulatif R, Chart.js)
- Boru hatti: son taramada her filtrede elenen sembol sayisi
- Sinyal tablosu (Tumu/Acik/Sonuclanan/Dolmayan filtresi, LONG/SHORT rozetleri)
- Rejim + izleme listesi + gist yedek durumu panelleri
Veriyi canli API'den ceker: /performance /signals /status /watchlist /regime
/backup/info /universe. Sunum app/server.py'de /dashboard yolundadir.
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>midas-signal-bot // dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#F5F1E8; --card:#FFFEFA; --card2:#F9F5EC; --line:#E6DECE;
    --text:#2A241B; --muted:#8A7F6C;
    --green:#16A34A; --green-bg:#E2F2E2; --green-ink:#14532D;
    --red:#DC2626;   --red-bg:#FBE7E2;   --red-ink:#7F1D1D;
    --amber:#D97706; --amber-bg:#FBEFD4; --amber-ink:#78350F;
    --blue:#2563EB;  --blue-bg:#E3EBFA;  --blue-ink:#1E3A8A;
    --grey:#98907F;  --grey-bg:#F0EBDF;
    --sans:Inter,Roboto,-apple-system,"SF Pro Text","Segoe UI",sans-serif;
    --shadow:0 1px 2px rgba(88,70,38,.06),0 5px 14px rgba(88,70,38,.05);
  }
  *{box-sizing:border-box;margin:0}
  body{background:var(--bg);color:var(--text);font-family:var(--sans);
       font-size:13px;line-height:1.5;font-variant-numeric:tabular-nums;
       padding:12px;max-width:1500px;margin:0 auto}
  .card{background:var(--card);border:1px solid var(--line);border-radius:11px;
        box-shadow:var(--shadow);padding:12px 14px}
  h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;
     color:var(--muted);margin-bottom:8px;font-weight:600}
  /* header */
  .hdr{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:10px}
  .logo{font-weight:700;font-size:16px}.logo b{color:var(--blue)}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--green);
       display:inline-block;margin-right:6px}
  .dot.err{background:var(--red)}
  .hinfo{color:var(--muted);flex:1}
  .hinfo b{color:var(--text)}
  button{background:var(--card);color:var(--text);border:1px solid var(--line);
    border-radius:8px;padding:6px 12px;font-family:var(--sans);font-size:12px;
    cursor:pointer}
  button:hover{border-color:var(--blue)}
  /* kpi */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
        gap:10px;margin-bottom:10px}
  .kpi .v{font-size:22px;font-weight:700;letter-spacing:-.02em}
  .kpi .l{color:var(--muted);font-size:11.5px}
  .kpi.good .v{color:var(--green)} .kpi.bad .v{color:var(--red)}
  /* layout */
  .grid{display:grid;grid-template-columns:230px minmax(0,1fr) 290px;gap:10px}
  @media(max-width:1000px){.grid{grid-template-columns:1fr}}
  .col{display:flex;flex-direction:column;gap:10px;min-width:0}
  /* pipeline */
  .stage{display:flex;justify-content:space-between;align-items:center;
         padding:5px 8px;border-radius:7px;margin-bottom:4px;background:var(--card2)}
  .stage b{font-size:12px}
  .stage .n{font-weight:700}
  .stage.sig{background:var(--green-bg);color:var(--green-ink)}
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
  th{font-size:11px;text-transform:uppercase;color:var(--muted);text-align:left;
     padding:5px 6px;border-bottom:1px solid var(--line)}
  td{padding:6px;border-bottom:1px solid var(--card2);font-size:12.5px}
  tr:hover td{background:var(--card2)}
  .num{text-align:right}
  .tabs{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
  .tabs button.on{border-color:var(--blue);background:var(--blue-bg);
                  color:var(--blue-ink)}
  .muted{color:var(--muted)}
  .wl{display:flex;flex-wrap:wrap;gap:5px}
  .foot{margin-top:10px;color:var(--muted);font-size:11.5px}
  canvas{max-height:220px}
  a{color:var(--blue)}
</style>
</head>
<body>
  <div class="hdr card">
    <span class="logo"><span class="dot" id="dot"></span>midas-<b>signal</b>-bot</span>
    <span class="hinfo" id="hinfo">yukleniyor…</span>
    <button onclick="loadAll()">Yenile</button>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="grid">
    <div class="col">
      <div class="card">
        <h2>Karar hatti (son tarama)</h2>
        <div id="pipeline" class="muted">veri yok</div>
      </div>
      <div class="card">
        <h2>Rejim</h2>
        <div id="regime" class="muted">-</div>
      </div>
      <div class="card">
        <h2>Gist yedek</h2>
        <div id="backup" class="muted">-</div>
      </div>
    </div>

    <div class="col">
      <div class="card">
        <h2>Equity (kumulatif R — golge muhasebe)</h2>
        <canvas id="equity"></canvas>
        <div id="eqEmpty" class="muted" style="display:none">
          Henuz sonuclanmis islem yok. Golge mod veri biriktiriyor.</div>
      </div>
      <div class="card">
        <h2>Sinyaller</h2>
        <div class="tabs" id="tabs">
          <button data-f="all" class="on">Tumu</button>
          <button data-f="open">Acik</button>
          <button data-f="closed">Sonuclanan</button>
          <button data-f="nf">Dolmayan</button>
        </div>
        <div style="overflow-x:auto"><table>
          <thead><tr><th>Sembol</th><th>Yon</th><th>Durum</th>
            <th class="num">Giris</th><th class="num">Stop</th>
            <th class="num">TP1</th><th class="num">R</th>
            <th>Acilis</th></tr></thead>
          <tbody id="sigRows"><tr><td colspan="8" class="muted">yukleniyor…</td></tr></tbody>
        </table></div>
      </div>
    </div>

    <div class="col">
      <div class="card">
        <h2>Izleme listesi</h2>
        <div id="watch" class="wl muted">-</div>
      </div>
      <div class="card">
        <h2>Yon bilancosu</h2>
        <div id="dir" class="muted">-</div>
      </div>
      <div class="card">
        <h2>Piyasa notu (gunluk)</h2>
        <div id="mnote" class="muted" style="white-space:pre-wrap;font-size:12px">-</div>
      </div>
      <div class="card">
        <h2>Bot degerlendirmesi <span class="b grey">kural tabanli</span></h2>
        <div id="cmt" class="muted" style="white-space:pre-wrap;font-size:12px">-</div>
      </div>
      <div class="card">
        <h2>Metodoloji</h2>
        <div class="muted" style="font-size:11.5px">
          Golge muhasebe: girise gelmesi ~2 seans beklenir; dolarsa ~4 seans
          (time-stop) izlenir. Once stop = LOSS, once TP1 = WIN; ayni barda
          ikisi = sayilmaz. Gap'te cikis ACILIS fiyatindan hesaplanir — stop
          garantisi yoktur. Komisyon/spread haric; gercek islem sonucu degildir.
        </div>
      </div>
    </div>
  </div>
  <div class="foot">Karar destegi — yatirim tavsiyesi degildir. Emirler Midas'tan manuel girilir.</div>

<script>
let SIG=[], FILT="all", CHART=null;
async function j(u){try{const r=await fetch(u);if(!r.ok)return null;
  return await r.json();}catch(e){return null}}

function kpi(l,v,cls){return `<div class="card kpi ${cls||''}">
  <div class="v">${v}</div><div class="l">${l}</div></div>`}

async function loadAll(){
  const [perf,sigs,status,watch,regime,backup,uni,dg]=await Promise.all([
    j('/performance'),j('/signals?limit=300'),j('/status'),j('/watchlist'),
    j('/regime'),j('/backup/info'),j('/universe'),j('/diag')]);
  document.getElementById('dot').className='dot'+(status?'':' err');

  // header
  const meta=(status&&status.meta)||{};
  document.getElementById('hinfo').innerHTML=
    `Son tarama: <b>${meta.last_scan_utc||'-'}</b> · Tarama sayisi: <b>${meta.scan_count??'-'}</b>`+
    (uni?` · Evren: <b>${uni.filtered_count??'-'}</b> sembol (${uni.source||'-'})`:'');

  // kpis
  if(perf){
    const wr=perf.win_rate==null?'—':(perf.win_rate*100).toFixed(0)+'%';
    const tr=perf.total_r_multiple??0;
    const co=perf.closed_by_outcome||{};
    const filled=(co.WIN?.count||0)+(co.LOSS?.count||0)+(co.EXPIRED?.count||0)+(co.AMBIGUOUS?.count||0);
    const nf=co.NOT_FILLED?.count||0;
    const fillRate=(filled+nf)?Math.round(100*filled/(filled+nf))+'%':'—';
    document.getElementById('kpis').innerHTML=
      kpi('Win Rate',wr, perf.win_rate>=0.5?'good':(perf.win_rate!=null?'bad':''))+
      kpi('Toplam R',(tr>0?'+':'')+tr, tr>0?'good':(tr<0?'bad':''))+
      kpi('Sonuclanan',perf.decided_trades??0)+
      kpi('Acik sinyal',perf.open_signals??0)+
      kpi('Giris isabeti',fillRate)+
      kpi('Kayitli karar',perf.dataset?.decisions_recorded??0);
    // yon bilancosu
    const dirs={};
    (perf.by_direction||[]).forEach(r=>{
      dirs[r.direction]=dirs[r.direction]||{n:0,r:0};
      dirs[r.direction].n+=r.n; dirs[r.direction].r+=(r.sum_r||0);});
    document.getElementById('dir').innerHTML=
      Object.keys(dirs).length?Object.entries(dirs).map(([d,v])=>
        `<div class="stage"><b><span class="b ${d==='LONG'?'long':'short'}">${d}</span></b>
         <span>${v.n} islem · ${v.r>=0?'+':''}${v.r.toFixed(2)}R</span></div>`).join('')
      :'<span class="muted">henuz yok</span>';
  }

  // pipeline (son tarama sonuclarindan)
  if(status&&status.results){
    const stages=['DATA','MARKET_REGIME','TREND','EARNINGS','SETUP','VOLUME','RISK_REWARD'];
    const cnt={}; let signals=0, total=0;
    Object.values(status.results).forEach(r=>{
      total++;
      if(r.decision==='SIGNAL'){signals++;return;}
      const f=(r.failed_filters&&r.failed_filters[0])||'DATA';
      cnt[f]=(cnt[f]||0)+1;});
    document.getElementById('pipeline').innerHTML=
      `<div class="stage"><b>Taranan</b><span class="n">${total}</span></div>`+
      stages.map(s=>`<div class="stage"><b>${s}</b><span class="n">${cnt[s]||0}</span></div>`).join('')+
      `<div class="stage sig"><b>SIGNAL</b><span class="n">${signals}</span></div>`;
  }

  // regime
  if(regime){
    const map={BULL:'long',BEAR:'short',NEUTRAL:'amber',UNKNOWN:'grey'};
    document.getElementById('regime').innerHTML=
      `<span class="b ${map[regime.regime]||'grey'}">${regime.regime}</span>
       <div class="muted" style="margin-top:6px;font-size:11.5px">${regime.detail||''}</div>`;
  }

  // backup
  document.getElementById('backup').innerHTML = backup&&!backup.error?
    `Son sync: <b>${backup.last_sync_utc||'henuz yok'}</b><br>
     ${backup.gist_url?`<a href="${backup.gist_url}" target="_blank">Gist arsivini ac</a>`:'gist henuz olusmadi'}`
    :'<span class="muted">kapali (GITHUB_TOKEN yok)</span>';

  // watchlist
  if(watch){
    document.getElementById('watch').innerHTML = watch.length?
      watch.map(w=>`<span class="b ${w.state==='SIGNAL'?'win':'grey'}"
        title="${w.blocked_by||''}">${w.symbol}</span>`).join('')
      :'<span class="muted">bos</span>';
  }

  // piyasa notu + bot degerlendirmesi
  if(dg){
    document.getElementById('mnote').textContent =
      dg.market_note || 'Hazirlik taramasiyla olusur (15:45 TR).';
    const c = dg.commentary_latest;
    document.getElementById('cmt').textContent =
      c ? `[${(c.ts_utc||'').slice(0,16).replace('T',' ')} UTC]\n${c.text}`
        : 'Ilk degerlendirme seans icinde uretilir.';
  }

  // signals + equity
  if(sigs){SIG=sigs;renderSigs();renderEquity();}
}

function renderSigs(){
  let rows=SIG;
  if(FILT==='open')rows=rows.filter(s=>s.status!=='CLOSED');
  if(FILT==='closed')rows=rows.filter(s=>s.status==='CLOSED'&&s.outcome!=='NOT_FILLED');
  if(FILT==='nf')rows=rows.filter(s=>s.outcome==='NOT_FILLED');
  const badge=s=>{
    if(s.status!=='CLOSED')return `<span class="b open">${s.status}</span>`;
    const m={WIN:'win',LOSS:'loss',NOT_FILLED:'grey',AMBIGUOUS:'grey',EXPIRED:'amber'};
    return `<span class="b ${m[s.outcome]||'grey'}">${s.outcome}</span>`;};
  document.getElementById('sigRows').innerHTML = rows.length? rows.map(s=>
    `<tr><td><b>${s.symbol}</b></td>
     <td><span class="b ${s.direction==='LONG'?'long':'short'}">${s.direction}</span></td>
     <td>${badge(s)}</td>
     <td class="num">${s.entry_min?.toFixed(2)}–${s.entry_max?.toFixed(2)}</td>
     <td class="num">${s.stop_loss?.toFixed(2)??'-'}</td>
     <td class="num">${s.tp1?.toFixed(2)??'-'}</td>
     <td class="num">${s.r_multiple!=null?(s.r_multiple>0?'+':'')+s.r_multiple:'—'}</td>
     <td class="muted">${(s.created_utc||'').slice(0,16).replace('T',' ')}</td></tr>`).join('')
   :'<tr><td colspan="8" class="muted">kayit yok</td></tr>';
}

function renderEquity(){
  const closed=SIG.filter(s=>s.status==='CLOSED'&&s.r_multiple!=null&&
    s.outcome!=='NOT_FILLED').sort((a,b)=>(a.closed_utc||'').localeCompare(b.closed_utc||''));
  const empty=document.getElementById('eqEmpty'), cv=document.getElementById('equity');
  if(!closed.length){empty.style.display='block';cv.style.display='none';return;}
  empty.style.display='none';cv.style.display='block';
  let cum=0;
  const pts=closed.map(s=>{cum+=s.r_multiple;return {x:(s.closed_utc||'').slice(5,16).replace('T',' '),y:+cum.toFixed(2),o:s.outcome}});
  if(CHART)CHART.destroy();
  CHART=new Chart(cv,{type:'line',data:{labels:pts.map(p=>p.x),
    datasets:[{data:pts.map(p=>p.y),borderColor:'#2563EB',
      backgroundColor:'rgba(37,99,235,.08)',fill:true,tension:.25,
      pointRadius:4,pointBackgroundColor:pts.map(p=>p.o==='WIN'?'#16A34A':(p.o==='LOSS'?'#DC2626':'#D97706')),
      pointBorderColor:'#fff',pointBorderWidth:1.5}]},
    options:{plugins:{legend:{display:false}},
      scales:{y:{grid:{color:'#EFE9DB'}},x:{grid:{display:false},
        ticks:{maxTicksLimit:8}}},maintainAspectRatio:false}});
}

document.getElementById('tabs').addEventListener('click',e=>{
  if(e.target.dataset.f===undefined)return;
  FILT=e.target.dataset.f;
  document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b===e.target));
  renderSigs();});

loadAll();
setInterval(loadAll,60000);
</script>
</body>
</html>"""
