const {JSDOM}=require('jsdom'); const fs=require('fs');
let html=fs.readFileSync(process.env.DASH||'/home/claude/midas-signal-bot/app/dashboard.html','utf8')
  .replace(/<sc-(if|for)[^>]*>/g,'').replace(/<\/sc-(if|for)>/g,'');
const map={'/performance':'api_performance.json','/signals':'api_signals_limit_500.json',
 '/status':'api_status.json','/universe':'api_universe.json','/news':'api_news.json',
 '/challengers':'api_challengers.json','/market':'api_market.json','/prices':'api_prices.json',
 '/live':'api_live.json','/strategy-lab':'api_strategy_lab.json','/volatility':'api_volatility.json'};
const errs=[];
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://x.test/',
 beforeParse(w){
  w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
  w.scrollTo=()=>{};
  w.HTMLCanvasElement.prototype.getContext=function(){const n=()=>{};const g={addColorStop:n};
    return new Proxy({},{get:(t,k)=>k==='createLinearGradient'?()=>g:(k==='canvas'?{width:600,height:300}:
      (k==='measureText'?()=>({width:10}):n))});};
  w.Chart=function(){return{destroy(){},update(){}};}; w.Chart.register=()=>{};
  w.fetch=async(u)=>{const key=Object.keys(map).find(k=>String(u).startsWith(k));
    if(!key) return {ok:true,json:async()=>null};
    try{return {ok:true,json:async()=>JSON.parse(fs.readFileSync((process.env.FIXDIR||'/tmp/')+map[key],'utf8'))};}
    catch(e){return {ok:true,json:async()=>null};}};
  w.addEventListener('error',e=>errs.push('ERR: '+e.message));
 }});
const w=dom.window,d=w.document;
setTimeout(()=>{
  const rows=d.querySelectorAll('tr.aday-satir');
  console.log('tiklanabilir satir:', rows.length);
  let ok=0, bos=[];
  rows.forEach(r=>{
    r.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    const t=d.getElementById('modalTitle').textContent.trim();
    const b=d.getElementById('modalBody').innerHTML;
    const acik=d.getElementById('modal').classList.contains('show');
    const dolu=acik && t && b.includes('Nasıl çalışır') && b.includes('Parametreler');
    if(dolu) ok++; else bos.push(r.dataset.aday+' ('+t+')');
    d.getElementById('modal').classList.remove('show');
  });
  console.log('detay acilan:', ok+'/'+rows.length, bos.length?('EKSIK: '+bos.join(', ')):'');
  console.log(errs.length?errs.join('\n'):'JS hatasi yok');
  console.log((rows.length>=9 && ok===rows.length && !errs.length)?'ADAY_OK':'ADAY_FAIL');
  process.exit(0);
},400);
