const {JSDOM}=require('jsdom'); const fs=require('fs');
let html=fs.readFileSync(process.env.DASH||'app/dashboard.html','utf8')
  .replace(/<sc-(if|for)[^>]*>/g,'').replace(/<\/sc-(if|for)>/g,'');
// MOBIL taklidi: medya sorgusunu kosulsuz hale getir (jsdom media desteklemez)
html=html.replace('@media (max-width:760px){','@media all{');
const dom=new JSDOM(html,{pretendToBeVisual:true});
const w=dom.window,d=w.document;
function vis(el){
  while(el && el.nodeType===1){
    if(w.getComputedStyle(el).display==='none') return false;
    el=el.parentElement;
  }
  return true;
}
const card=d.querySelector('.card[data-tab="adaylar"]');
const chal=d.getElementById('chalBody'), slab=d.getElementById('slabBody');
function setTab(name){
  d.querySelectorAll('.col[data-tab],.card[data-tab]').forEach(el=>
    el.classList.toggle('on', el.dataset.tab===name));
  d.body.dataset.tab=name;
}
let fail=[];
for(const t of ['ozet','sinyaller','adaylar','piyasa','ayar']){
  setTab(t);
  const ok = (t==='adaylar') ? (vis(card)&&vis(chal)&&vis(slab)) : !vis(card);
  if(!ok) fail.push(t);
  console.log(t.padEnd(10), 'aday karti gorunur:', vis(card));
}
console.log(fail.length?('VIS_FAIL '+fail.join(',')):'VIS_OK');
process.exit(0);
