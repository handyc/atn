#!/usr/bin/env python3
# build_lab9.py — generate dissemination/glider-lab9.html, a mini "CA Photoshop": load an
# arbitrary image, posterize it to the 4-state grid, apply CA rulesets as FILTERS organized by
# the retain.py taxonomy (Preserve/Wipe/Dissolve/Glitch/Stylize), and stitch clips into a .webm
# VIDEO (pure JS: MediaRecorder + canvas.captureStream). Real rulehub LUTs embedded (verified
# byte-identical) so each effect is the genuine CA behaviour, not a Photoshop imitation.
import json
PRESETS = json.load(open("/tmp/presets.json"))
PJSON = json.dumps(PRESETS)

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glider Lab 9 — CA Photoshop + video reel</title>
<style>
  :root{--bg:#0e1116;--panel:#161b22;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#5ed18a}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
  .wrap{max-width:1060px;margin:0 auto;padding:18px}
  h1{font-size:22px;margin:0 0 2px} h1 small{color:var(--mut);font-weight:400;font-size:14px}
  p{color:var(--mut);max-width:900px;margin:6px 0}
  .row{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;margin-top:10px}
  canvas.view{background:#05070a;border:1px solid #2a3340;border-radius:6px;display:block;image-rendering:pixelated;width:360px;height:284px}
  .cap{font-size:12px;color:var(--mut);text-align:center;margin-top:4px}
  button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:6px 10px;cursor:pointer;font-size:13px}
  button.act{background:var(--b);color:#04121f;border:none;font-weight:600}
  button:disabled{opacity:.45;cursor:default}
  label.file{background:#2a6;color:#04210f;border-radius:6px;padding:6px 10px;cursor:pointer;font-size:13px;font-weight:600}
  .filters{display:flex;flex-direction:column;gap:6px;min-width:300px}
  .grp{font-size:11px;letter-spacing:.5px;text-transform:uppercase;color:var(--mut);margin-top:6px}
  .fbtns{display:flex;gap:6px;flex-wrap:wrap}
  .fbtns button.on{background:var(--a);color:#1a1205;font-weight:700;border-color:var(--a)}
  .ctl{display:flex;flex-direction:column;gap:8px;min-width:260px}
  input[type=range]{width:100%}
  .stat{font-size:12px;color:var(--mut);font-variant-numeric:tabular-nums} .stat b{color:var(--a)}
  .note{font-size:12px;color:var(--ink);background:#0b0e13;border:1px solid #2a3340;border-radius:6px;padding:6px 9px;min-height:34px}
  .reelbox{border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:12px;background:#11161d}
  .reelbox h3{margin:0 0 6px;font-size:14px;color:var(--a)}
  #reel{display:flex;gap:6px;flex-wrap:wrap;min-height:30px;margin:6px 0}
  #reel button{background:#1d2733;border-color:#33414f}
  .hint{font-size:12px;color:var(--mut);max-width:900px} code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}
  .legend{font-size:12px;color:var(--mut)} .sw{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:middle;margin:0 2px}
</style>
</head>
<body>
<div class="wrap">
  <h1>Glider Lab 9 <small>— a CA "Photoshop", with a video reel</small></h1>
  <p>Load any picture. It's posterized to 4 levels and becomes the <b>starting grid</b>; then a CA <b>ruleset</b>
  runs on it. Rules sort into behaviours (see <code>retain.py</code>) that are exactly image effects:
  <b>Preserve</b> (hold — wires/memory), <b>Wipe</b> (pan in a direction — transport), <b>Dissolve</b>
  (flood — growth), <b>Glitch</b> (churn — chaos), <b>Stylize</b> (settle to a stable pattern). Every filter is a
  <i>real, verified</i> rule across four fractal families. Queue clips into the <b>reel</b> and export a video.</p>

  <div class="row">
    <div><canvas class="view" id="orig" width="190" height="150"></canvas><div class="cap">original (posterized)</div></div>
    <div><canvas class="view" id="out" width="190" height="150"></canvas><div class="cap">filtered — step <b id="cap2">0</b></div></div>
    <div class="ctl">
      <div class="row" style="margin:0">
        <label class="file">📷 load image<input type="file" id="file" accept="image/*" style="display:none"></label>
        <button id="defimg">test image</button>
      </div>
      <label>amount (CA steps): <b id="amt" style="color:var(--a)">0</b></label>
      <input type="range" id="steps" min="0" max="60" value="0" step="1">
      <div class="row" style="margin:0">
        <button class="act" id="play">▶ animate</button>
        <button id="bake">⤵ bake (stack)</button>
        <button id="reset">reset</button>
      </div>
      <div class="row" style="margin:0">
        <button id="save">💾 PNG</button>
        <button id="addreel">＋ add clip to reel</button>
        <button id="pal">🎨</button>
      </div>
      <div class="note" id="note">pick a filter →</div>
      <div class="legend">states:<span class="sw" id="l0"></span><span class="sw" id="l1"></span><span class="sw" id="l2"></span><span class="sw" id="l3"></span></div>
    </div>
  </div>

  <div class="row">
    <div class="filters">
      <div class="grp">Preserve · retain (wire/memory)</div><div class="fbtns" id="gRETAIN"></div>
      <div class="grp">Wipe · shift (directional transport)</div><div class="fbtns" id="gSHIFT/WIPE"></div>
      <div class="grp">Dissolve · grow (flooding carrier)</div><div class="fbtns" id="gGROW"></div>
      <div class="grp">Glitch · chaos</div><div class="fbtns" id="gCHAOS"></div>
      <div class="grp">Stylize · settles to a stable pattern</div><div class="fbtns" id="gSTYLIZE"></div>
    </div>
  </div>

  <div class="reelbox">
    <h3>🎬 Video reel</h3>
    <p style="margin:2px 0">Pick a filter, set its <b>amount</b>, hit <b>＋ add clip to reel</b>. Clips play in order,
    each continuing from the previous one's output (stitched), and render to a downloadable <code>.webm</code>.</p>
    <div id="reel"></div>
    <div class="row" style="margin:4px 0">
      <button class="act" id="render">🎬 render reel → video</button>
      <button id="clearreel">clear reel</button>
      <span class="stat" id="rstat"></span>
    </div>
  </div>
  <p class="hint">Scrub <b>amount</b> to run a rule more steps (frames cached → instant). <b>Bake</b> freezes the
  result as the new input so you can stack filters live. The reel records from a 3× hi-res canvas using only
  <code>MediaRecorder</code> + <code>captureStream</code> (no libraries; works in Chrome/Firefox). Same image→grid
  pipeline as <code>retain.py</code>; the taxonomy powering the CA-computer search is here as a creative tool.</p>
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
const AW=190, AH=150, MAXF=60;
let PAL=["#0b0f17","#3a6ea5","#ffd27f","#e06c5a"];
function imgToGrid(im){const t=document.createElement("canvas");t.width=AW;t.height=AH;const tx=t.getContext("2d");
  tx.drawImage(im,0,0,AW,AH);const d=tx.getImageData(0,0,AW,AH).data,g=new Float64Array(AW*AH);
  for(let p=0;p<AW*AH;p++)g[p]=0.299*d[p*4]+0.587*d[p*4+1]+0.114*d[p*4+2];
  const s=[...g].sort((a,b)=>a-b),q1=s[(AW*AH)>>2],q2=s[(AW*AH)>>1],q3=s[(3*AW*AH)>>2],seed=new Uint8Array(AW*AH);
  for(let p=0;p<AW*AH;p++){const v=g[p];seed[p]=v<q1?0:v<q2?1:v<q3?2:3;}return seed;}
function testImage(){const seed=new Uint8Array(AW*AH);
  for(let r=0;r<AH;r++)for(let c=0;c<AW;c++){const dx=c-AW/2,dy=r-AH/2,d=Math.hypot(dx,dy);
    let v=((d/9)|0)%4;if(Math.abs(r-c)<5||Math.abs((AW-c)-r)<5)v=3;if(((r/12)|0)%4===0&&v===0)v=1;seed[r*AW+c]=v;}return seed;}
let active=null, seed=testImage(), frames=[seed], idx=0, playing=false, reel=[], rendering=false;
const oc=document.getElementById("orig").getContext("2d"), ec=document.getElementById("out").getContext("2d");
const $=id=>document.getElementById(id);
function rgbOf(col){return [parseInt(col.slice(1,3),16),parseInt(col.slice(3,5),16),parseInt(col.slice(5,7),16)];}
function draw(ctx,g){const im=ctx.createImageData(AW,AH);for(let p=0;p<AW*AH;p++){const[r,gr,b]=rgbOf(PAL[g[p]]);
  im.data[p*4]=r;im.data[p*4+1]=gr;im.data[p*4+2]=b;im.data[p*4+3]=255;}ctx.putImageData(im,0,0);}
function ensure(n){while(frames.length<=n && active){frames.push(step(frames[frames.length-1],active.LUT,AW,AH));}}
function cur(){return frames[Math.min(idx,frames.length-1)];}
function show(){ensure(idx);draw(ec,cur());$("cap2").textContent=idx;$("amt").textContent=idx;$("steps").value=idx;}
function reseed(s){seed=s;frames=[seed];idx=0;draw(oc,seed);show();}
function pickFilter(p,btn){active=p;frames=[seed];
  document.querySelectorAll(".fbtns button").forEach(b=>b.classList.remove("on"));btn.classList.add("on");
  $("note").innerHTML=`<b>${p.name}</b> — ${p.note}<br><span style="color:var(--mut)">${p.fam}(${p.cx}, ${p.cy}, ${p.span})</span>`;
  if(idx===0)idx=10;show();}
PRESETS.forEach(p=>{const g=document.getElementById("g"+p.cat);if(!g)return;
  const b=document.createElement("button");b.textContent=p.name;b.onclick=()=>pickFilter(p,b);g.appendChild(b);});
$("steps").oninput=e=>{idx=+e.target.value;show();};
$("play").onclick=function(){if(!active||rendering)return;playing=!playing;this.textContent=playing?"⏸ pause":"▶ animate";
  const tick=()=>{if(!playing)return;idx=idx>=MAXF?0:idx+1;show();setTimeout(tick,110);};if(playing)tick();};
$("bake").onclick=()=>{if(active){reseed(cur().slice());$("note").innerHTML+="<br><span style='color:var(--ok)'>baked ✓</span>";}};
$("reset").onclick=()=>{idx=0;frames=[seed];show();};
$("defimg").onclick=()=>reseed(testImage());
$("file").onchange=e=>{const f=e.target.files[0];if(!f)return;const url=URL.createObjectURL(f),im=new Image();
  im.onload=()=>{reseed(imgToGrid(im));URL.revokeObjectURL(url);};im.src=url;};
$("save").onclick=()=>{const t=document.createElement("canvas");t.width=AW;t.height=AH;draw(t.getContext("2d"),cur());
  const a=document.createElement("a");a.download="ca-filtered.png";a.href=t.toDataURL("image/png");a.click();};
$("pal").onclick=()=>{const h=Math.random()*360,f=p=>Math.round(120+110*Math.cos((h+p)*Math.PI/180)).toString(16).padStart(2,"0");
  PAL=["#0b0f17","#"+f(0)+f(120)+f(240),"#"+f(90)+f(210)+f(330),"#"+f(180)+f(300)+f(60)];syncLegend();draw(oc,seed);show();};
function syncLegend(){for(let i=0;i<4;i++)$("l"+i).style.background=PAL[i];}
// ---- video reel ----
function renderReelChips(){const el=$("reel");el.innerHTML="";if(!reel.length){el.innerHTML="<span class='stat'>(empty — add clips)</span>";return;}
  reel.forEach((it,i)=>{const c=document.createElement("button");c.textContent=`${i+1}. ${it.name} · ${it.steps} ✕`;
    c.title="click to remove";c.onclick=()=>{if(!rendering){reel.splice(i,1);renderReelChips();}};el.appendChild(c);});}
$("addreel").onclick=()=>{if(!active){$("rstat").textContent="pick a filter first";return;}
  reel.push({name:active.name,steps:Math.max(1,idx)});renderReelChips();$("rstat").textContent=`${reel.length} clip(s) queued`;};
$("clearreel").onclick=()=>{if(!rendering){reel=[];renderReelChips();$("rstat").textContent="";}};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const recCanvas=document.createElement("canvas"),REC=3;recCanvas.width=AW*REC;recCanvas.height=AH*REC;
const rctx=recCanvas.getContext("2d");rctx.imageSmoothingEnabled=false;
const tiny=document.createElement("canvas");tiny.width=AW;tiny.height=AH;const tctx=tiny.getContext("2d");
function drawRec(g){draw(tctx,g);rctx.drawImage(tiny,0,0,recCanvas.width,recCanvas.height);}
async function renderReel(){
  if(rendering)return;
  if(!reel.length){$("rstat").textContent="add clips to the reel first";return;}
  const mime=["video/webm;codecs=vp9","video/webm;codecs=vp8","video/webm"].find(m=>window.MediaRecorder&&MediaRecorder.isTypeSupported(m));
  if(!mime){$("rstat").textContent="MediaRecorder/webm not supported — try Chrome or Firefox";return;}
  rendering=true;playing=false;$("render").disabled=true;$("clearreel").disabled=true;
  const fps=20,stream=recCanvas.captureStream(fps),rec=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:8e6});
  const chunks=[];rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
  const stopped=new Promise(res=>rec.onstop=res);rec.start();
  let g=seed.slice();drawRec(g);await sleep(350);
  for(let ci=0;ci<reel.length;ci++){const p=PRESETS.find(x=>x.name===reel[ci].name);
    for(let s=0;s<reel[ci].steps;s++){g=step(g,p.LUT,AW,AH);drawRec(g);
      $("rstat").textContent=`recording clip ${ci+1}/${reel.length} — step ${s+1}/${reel[ci].steps}`;await sleep(1000/fps);}
    for(let h=0;h<8;h++){drawRec(g);await sleep(1000/fps);}}      // brief hold between clips
  rec.stop();await stopped;
  const blob=new Blob(chunks,{type:mime}),a=document.createElement("a");
  a.href=URL.createObjectURL(blob);a.download="ca-reel.webm";a.click();
  $("rstat").textContent=`done — exported ${(blob.size/1024|0)} KB .webm`;
  rendering=false;$("render").disabled=false;$("clearreel").disabled=false;}
$("render").onclick=renderReel;
syncLegend();renderReelChips();reseed(testImage());
</script>
</body>
</html>
'''
HTML = HTML.replace("__PRESETS__", PJSON)
open("dissemination/glider-lab9.html", "w").write(HTML)
print("wrote dissemination/glider-lab9.html", len(HTML), "bytes,", len(PRESETS), "filters")
