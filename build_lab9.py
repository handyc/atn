#!/usr/bin/env python3
# build_lab9.py — generate dissemination/glider-lab9.html, a mini "CA Photoshop": load an
# arbitrary image, posterize it to the 4-state grid, and apply CA rulesets as FILTERS, organized
# by the retain.py taxonomy (Preserve / Wipe / Dissolve / Glitch). Real rulehub LUTs embedded
# (from /tmp/presets.json) so the in-browser effect IS the verified CA behaviour, not a fake.
import json
PRESETS = json.load(open("/tmp/presets.json"))
PJSON = json.dumps(PRESETS)

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glider Lab 9 — CA Photoshop (image filters from the rule taxonomy)</title>
<style>
  :root{--bg:#0e1116;--panel:#161b22;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#5ed18a}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
  .wrap{max-width:1060px;margin:0 auto;padding:18px}
  h1{font-size:22px;margin:0 0 2px} h1 small{color:var(--mut);font-weight:400;font-size:14px}
  p{color:var(--mut);max-width:900px;margin:6px 0}
  .row{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;margin-top:10px}
  canvas{background:#05070a;border:1px solid #2a3340;border-radius:6px;display:block;image-rendering:pixelated;width:380px;height:300px}
  .cap{font-size:12px;color:var(--mut);text-align:center;margin-top:4px}
  .col{display:flex;flex-direction:column;gap:4px}
  button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:6px 10px;cursor:pointer;font-size:13px}
  button.act{background:var(--b);color:#04121f;border:none;font-weight:600}
  label.file{background:#2a6;color:#04210f;border-radius:6px;padding:6px 10px;cursor:pointer;font-size:13px;font-weight:600}
  .filters{display:flex;flex-direction:column;gap:8px;min-width:250px}
  .grp{font-size:11px;letter-spacing:.5px;text-transform:uppercase;color:var(--mut);margin-top:4px}
  .fbtns{display:flex;gap:6px;flex-wrap:wrap}
  .fbtns button.on{background:var(--a);color:#1a1205;font-weight:700;border-color:var(--a)}
  .ctl{display:flex;flex-direction:column;gap:8px;min-width:250px}
  input[type=range]{width:100%}
  .stat{font-size:12px;color:var(--mut);font-variant-numeric:tabular-nums} .stat b{color:var(--a)}
  .note{font-size:12px;color:var(--ink);background:#0b0e13;border:1px solid #2a3340;border-radius:6px;padding:6px 9px;min-height:34px}
  .hint{font-size:12px;color:var(--mut);max-width:900px} code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}
  .legend{font-size:12px;color:var(--mut)} .sw{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:middle;margin:0 2px}
</style>
</head>
<body>
<div class="wrap">
  <h1>Glider Lab 9 <small>— a CA "Photoshop": the filters are cellular-automaton rules</small></h1>
  <p>Load any picture. It's posterized to 4 levels and becomes the <b>starting grid</b>; then a CA <b>ruleset</b>
  runs on it. We learned (see <code>retain.py</code>) that rules sort into behaviours — and those behaviours are
  exactly image effects: <b>Preserve</b> rules hold the picture (wires/memory), <b>Wipe</b> rules pan it in a
  direction (transport), <b>Dissolve</b> rules flood it (growth), <b>Glitch</b> rules churn it (chaos). Each filter
  below is a <i>real, verified</i> rule — the effect you see is the genuine CA dynamics, not a Photoshop fake.</p>

  <div class="row">
    <div><canvas id="orig" width="190" height="150"></canvas><div class="cap">original (posterized)</div></div>
    <div><canvas id="out" width="190" height="150"></canvas><div class="cap">filtered — step <b id="cap2">0</b></div></div>
    <div class="ctl">
      <div class="row" style="margin:0">
        <label class="file">📷 load image<input type="file" id="file" accept="image/*" style="display:none"></label>
        <button id="defimg">test image</button>
      </div>
      <label>amount (CA steps): <b id="amt" style="color:var(--a)">0</b></label>
      <input type="range" id="steps" min="0" max="48" value="0" step="1">
      <div class="row" style="margin:0">
        <button class="act" id="play">▶ animate</button>
        <button id="bake">⤵ bake (stack)</button>
        <button id="reset">reset</button>
      </div>
      <div class="row" style="margin:0">
        <button id="save">💾 export PNG</button>
        <button id="pal">🎨 palette</button>
      </div>
      <div class="note" id="note">pick a filter →</div>
      <div class="legend">states:<span class="sw" id="l0"></span><span class="sw" id="l1"></span><span class="sw" id="l2"></span><span class="sw" id="l3"></span></div>
    </div>
  </div>

  <div class="row">
    <div class="filters">
      <div class="grp">Preserve · retain-rules (wire/memory)</div><div class="fbtns" id="gRETAIN"></div>
      <div class="grp">Wipe · shift-rules (directional transport)</div><div class="fbtns" id="gSHIFT/WIPE"></div>
      <div class="grp">Dissolve · grow-rules (flooding carrier)</div><div class="fbtns" id="gGROW"></div>
      <div class="grp">Glitch · chaos-rules</div><div class="fbtns" id="gCHAOS"></div>
    </div>
  </div>
  <p class="hint">Scrub <b>amount</b> to run the rule more steps (frames are cached, so it's instant). <b>Bake</b>
  freezes the current result as the new input so you can stack filters — a wipe, then a preserve, then a glitch.
  This is the same image→grid pipeline as <code>retain.py</code>; the rule taxonomy that powers the CA-computer
  search (Preserve=wire, Wipe=transport, Dissolve=carrier) is here as a creative tool.</p>
</div>
<script>
"use strict";
const PRESETS = __PRESETS__;
function unpack(b64,n){const raw=atob(b64);const out=new Uint8Array(n);let p=0;
  for(let i=0;i<raw.length&&p<n;i++){const by=raw.charCodeAt(i);for(let k=0;k<4&&p<n;k++)out[p++]=(by>>(k*2))&3;}return out;}
PRESETS.forEach(p=>p.LUT=unpack(p.lut,16384));
function step(b,lut,W,H){const nb=new Uint8Array(W*H);
  for(let r=0;r<H;r++){const rm=(r-1+H)%H,rp=(r+1)%H,ev=(r%2===0);
    for(let c=0;c<W;c++){const cm=(c-1+W)%W,cp=(c+1)%W,s=b[r*W+c],N=b[rm*W+c],Sd=b[rp*W+c],Wc=b[r*W+cm],E=b[r*W+cp];
      let nw,ne,sw,se;if(ev){nw=b[rm*W+cm];ne=N;sw=b[rp*W+cm];se=Sd;}else{nw=N;ne=b[rm*W+cp];sw=Sd;se=b[rp*W+cp];}
      nb[r*W+c]=lut[(s<<12)|(nw<<10)|(ne<<8)|(E<<6)|(se<<4)|(sw<<2)|Wc];}}return nb;}
const AW=190, AH=150, MAXF=48;
let PAL=["#0b0f17","#3a6ea5","#ffd27f","#e06c5a"];
function imgToGrid(im){const t=document.createElement("canvas");t.width=AW;t.height=AH;const tx=t.getContext("2d");
  tx.drawImage(im,0,0,AW,AH);const d=tx.getImageData(0,0,AW,AH).data,g=new Float64Array(AW*AH);
  for(let p=0;p<AW*AH;p++)g[p]=0.299*d[p*4]+0.587*d[p*4+1]+0.114*d[p*4+2];
  const s=[...g].sort((a,b)=>a-b),q1=s[(AW*AH)>>2],q2=s[(AW*AH)>>1],q3=s[(3*AW*AH)>>2],seed=new Uint8Array(AW*AH);
  for(let p=0;p<AW*AH;p++){const v=g[p];seed[p]=v<q1?0:v<q2?1:v<q3?2:3;}return seed;}
function testImage(){const seed=new Uint8Array(AW*AH);
  for(let r=0;r<AH;r++)for(let c=0;c<AW;c++){const dx=c-AW/2,dy=r-AH/2,d=Math.hypot(dx,dy);
    let v=((d/9)|0)%4;if(Math.abs(r-c)<5||Math.abs((AW-c)-r)<5)v=3;if(((r/12)|0)%4===0&&v===0)v=1;seed[r*AW+c]=v;}return seed;}
let active=null, seed=testImage(), frames=[seed], idx=0, playing=false;
const oc=document.getElementById("orig").getContext("2d"), ec=document.getElementById("out").getContext("2d");
const $=id=>document.getElementById(id);
function draw(ctx,g){const im=ctx.createImageData(AW,AH);for(let p=0;p<AW*AH;p++){const col=PAL[g[p]];
  im.data[p*4]=parseInt(col.slice(1,3),16);im.data[p*4+1]=parseInt(col.slice(3,5),16);im.data[p*4+2]=parseInt(col.slice(5,7),16);im.data[p*4+3]=255;}
  ctx.putImageData(im,0,0);}
function ensure(n){while(frames.length<=n && active){frames.push(step(frames[frames.length-1],active.LUT,AW,AH));}}
function show(){ensure(idx);draw(ec,frames[Math.min(idx,frames.length-1)]);$("cap2").textContent=idx;$("amt").textContent=idx;$("steps").value=idx;}
function reseed(s){seed=s;frames=[seed];idx=0;draw(oc,seed);show();}
function pickFilter(p,btn){active=p;frames=[seed];idx=Math.max(idx,1);
  document.querySelectorAll(".fbtns button").forEach(b=>b.classList.remove("on"));btn.classList.add("on");
  $("note").innerHTML=`<b>${p.name}</b> — ${p.note}<br><span style="color:var(--mut)">newton(${p.cx}, ${p.cy}, ${p.span})</span>`;
  if(idx===0)idx=8;show();}
// build filter buttons
PRESETS.forEach(p=>{const g=document.getElementById("g"+p.cat);if(!g)return;
  const b=document.createElement("button");b.textContent=p.name;b.onclick=()=>pickFilter(p,b);g.appendChild(b);});
// controls
$("steps").oninput=e=>{idx=+e.target.value;show();};
$("play").onclick=function(){if(!active)return;playing=!playing;this.textContent=playing?"⏸ pause":"▶ animate";
  const tick=()=>{if(!playing)return;idx=idx>=MAXF?0:idx+1;show();setTimeout(tick,120);};if(playing)tick();};
$("bake").onclick=()=>{if(active){reseed(frames[Math.min(idx,frames.length-1)].slice());$("note").innerHTML+="<br><span style='color:var(--ok)'>baked ✓ — stack another filter</span>";}};
$("reset").onclick=()=>{idx=0;frames=[seed];show();};
$("defimg").onclick=()=>reseed(testImage());
$("file").onchange=e=>{const f=e.target.files[0];if(!f)return;const url=URL.createObjectURL(f),im=new Image();
  im.onload=()=>{reseed(imgToGrid(im));URL.revokeObjectURL(url);};im.src=url;};
$("save").onclick=()=>{const t=document.createElement("canvas");t.width=AW;t.height=AH;draw(t.getContext("2d"),frames[Math.min(idx,frames.length-1)]);
  const a=document.createElement("a");a.download="ca-filtered.png";a.href=t.toDataURL("image/png");a.click();};
$("pal").onclick=()=>{const h=Math.random()*360,f=p=>Math.round(120+110*Math.cos((h+p)*Math.PI/180)).toString(16).padStart(2,"0");
  PAL=["#0b0f17","#"+f(0)+f(120)+f(240),"#"+f(90)+f(210)+f(330),"#"+f(180)+f(300)+f(60)];syncLegend();draw(oc,seed);show();};
function syncLegend(){for(let i=0;i<4;i++)$("l"+i).style.background=PAL[i];}
syncLegend();reseed(testImage());
</script>
</body>
</html>
'''
HTML = HTML.replace("__PRESETS__", PJSON)
open("dissemination/glider-lab9.html", "w").write(HTML)
print("wrote dissemination/glider-lab9.html", len(HTML), "bytes,", len(PRESETS), "filters")
