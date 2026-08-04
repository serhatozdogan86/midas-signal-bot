const {JSDOM}=require('jsdom'); const fs=require('fs');
const html=fs.readFileSync(process.env.DASH||'app/dashboard.html','utf8');
const map={'/performance':'api_performance.json','/signals':'api_signals_limit_500.json',
 '/status':'api_status.json','/universe':'api_universe.json','/news':'api_news.json',
 '/challengers':'api_challengers.json','/market':'api_market.json','/prices':'api_prices.json',
 '/live':'api_live.json','/strategy-lab':'api_strategy_lab.json'};
const errs=[];
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://x.test/',
  beforeParse(w){
    w.matchMedia=q=>({matches:/max-width:\s*760/.test(q)?false:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
    w.scrollTo=()=>{};
    // canvas yok -> ctx sahtesi (grafik cizimi testin konusu degil)
    w.HTMLCanvasElement.prototype.getContext=function(){
      const noop=()=>{};
      const grad={addColorStop:noop};
      return new Proxy({},{get:(t,k)=>{
        if(k==='createLinearGradient'||k==='createRadialGradient') return ()=>grad;
        if(k==='canvas') return {width:600,height:300};
        if(k==='measureText') return ()=>({width:10});
        if(k==='getImageData') return ()=>({data:[]});
        return noop;}});
    };
    w.Chart=function(){return {destroy(){},update(){},data:{},options:{}};};
    w.Chart.register=()=>{};
    w.fetch=async(u)=>{
      const key=Object.keys(map).find(k=>String(u).startsWith(k));
      if(!key) return {ok:true,json:async()=>null};
      try{return {ok:true,json:async()=>JSON.parse(fs.readFileSync((process.env.FIXDIR||'/tmp/')+map[key],'utf8'))};}
      catch(e){return {ok:true,json:async()=>null};}
    };
    w.addEventListener('error',e=>errs.push('window.error: '+e.message));
  }});
const w=dom.window;
setTimeout(async()=>{
  try{ await w.load(); }catch(e){ errs.push('load() THROW: '+e.message+' @ '+(e.stack||'').split('\n')[1]); }
  const d=w.document;
  const g=id=>{const el=d.getElementById(id);return el?el.innerHTML.replace(/\s+/g,' ').slice(0,110):'ELEMAN YOK';};
  const rows0=w.document.querySelectorAll('#signals tbody tr').length;
  const fail=errs.filter(e=>!/w.load is not a function/.test(e));
  console.log('--- HATALAR ---'); console.log(fail.length?fail.join('\n'):'(yok)');
  if(fail.length||rows0===0){ console.log('SMOKE_FAIL'); } else { console.log('SMOKE_OK'); }
  for(const id of ['signals','chalBody','kpis','news','market','pipe','eqStats'])
    console.log(id.padEnd(9)+':', g(id));
  const rows=d.querySelectorAll('#signals tbody tr').length;
  console.log('sinyal satiri:', rows);
  process.exit(0);
}, 400);
