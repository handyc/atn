#!/usr/bin/env python3
# build_lab10.py — generate dissemination/glider-lab10.html: the COMPLETE CA-computer
# pipeline with every stage running as a LIVE cellular automaton in the browser (real
# embedded LUTs, verified byte-identical to the python). Panels: NAND gate (logic), latch
# (memory bit), circulating register (sequential storage), autonomous wire (routing),
# inverter (the frontier primitive). A header shows how they compose into CA-1 (which runs
# real programs) and the honest open frontier (a 2nd spreading layer for full autonomy).
luts = {}
for line in open("/tmp/pipeluts.txt"):
    k, v = line.strip().split("=", 1); luts[k] = v

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glider Lab 10 — the whole CA computer, live</title>
<style>
  :root{--bg:#0e1116;--panel:#161b22;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--g:#5ed18a;--no:#ff7a7a}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
  .wrap{max-width:1100px;margin:0 auto;padding:18px}
  h1{font-size:23px;margin:0 0 2px} h1 small{color:var(--mut);font-weight:400;font-size:14px}
  p{color:var(--mut);max-width:940px;margin:6px 0}
  .flow{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0;font-size:13px}
  .flow .box{background:#1b2430;border:1px solid #2a3340;border-radius:6px;padding:5px 9px}
  .flow .arr{color:var(--mut)}
  .flow .cap{background:#23311f;border-color:#3a5a30}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;margin-top:12px}
  .card{background:var(--panel);border:1px solid #2a3340;border-radius:10px;padding:12px}
  .card h3{margin:0 0 2px;font-size:15px} .card h3 .tag{font-size:11px;color:var(--mut);font-weight:400}
  .card .desc{font-size:12px;color:var(--mut);min-height:32px;margin:2px 0 6px}
  canvas{background:#05070a;border:1px solid #2a3340;border-radius:6px;display:block;image-rendering:pixelated;width:100%}
  .readout{font-family:ui-monospace,monospace;font-size:13px;margin-top:6px;color:var(--ink)}
  .readout b{color:var(--a)} .truth{font-family:ui-monospace,monospace;font-size:12px;color:var(--mut)} .truth .hit{color:var(--g)}
  .row{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
  button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:5px 9px;cursor:pointer;font-size:12px}
  button.on{background:var(--a);color:#1a1205;font-weight:700;border-color:var(--a)}
  .legend{font-size:11px;color:var(--mut);margin-top:4px} .sw{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle;margin:0 2px}
  .full{grid-column:1/-1}
  code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)} .frontier{border-color:#5a4a2a;background:#1f1b12}
</style>
</head>
<body>
<div class="wrap">
  <h1>Glider Lab 10 <small>— the whole CA computer, every stage a live cellular automaton</small></h1>
  <p>Each panel below is a <b>real CA running in your browser</b> on the verified rule tables — not a diagram.
  Together they are the pipeline that builds a computer out of one mechanism (the mutual-annihilation latch):
  a logic <b>gate</b>, a memory <b>latch</b>, a sequential <b>register</b>, an autonomous <b>wire</b>, and the
  frontier <b>inverter</b>. Composed, they form <b>CA-1</b>, an accumulator machine that runs real programs.</p>
  <div class="flow">
    <span class="box">NAND gate</span><span class="arr">+</span><span class="box">latch (memory)</span>
    <span class="arr">→</span><span class="box">ALU + RAM</span><span class="arr">+</span><span class="box">register (sequential)</span>
    <span class="arr">→</span><span class="cap box">CA-1 runs programs ✓</span>
    <span class="arr">·</span><span class="box">autonomous wire</span><span class="arr">+</span><span class="box">inverter</span>
    <span class="arr">→</span><span class="box">self-wiring (frontier)</span>
  </div>

  <div class="grid">
    <div class="card">
      <h3>1 · NAND gate <span class="tag">— universal logic</span></h3>
      <div class="desc">Bias (amber) vs inputs (blue); winner-take-all. Tune bias-vs-input → a NAND. Cycling the 4 input cases; the truth table fills as the CA settles.</div>
      <canvas id="cg" width="120" height="120"></canvas>
      <div class="readout">inputs <b id="g_in">00</b> → output <b id="g_out">·</b></div>
      <div class="truth" id="g_tt">NAND: 00:· 01:· 10:· 11:·</div>
    </div>

    <div class="card">
      <h3>2 · Latch <span class="tag">— one bit of memory</span></h3>
      <div class="desc">Two layers annihilate where they meet; the larger survives and holds — a flip-flop. Set stores 1 (amber), reset stores 0 (blue); it holds with no decay.</div>
      <canvas id="cl" width="120" height="120"></canvas>
      <div class="readout">stored bit: <b id="l_bit">·</b></div>
      <div class="row"><button id="l_set">set → 1</button><button id="l_rst">reset → 0</button><button id="l_auto" class="on">auto</button></div>
    </div>

    <div class="card">
      <h3>3 · Inverter <span class="tag">— the frontier primitive</span></h3>
      <div class="desc">A self-emitting carrier (green) flows down the channel — unless an input on the opposite layer suppresses it. Emission present ⇔ input absent = NOT. This is the active gate autonomy needs.</div>
      <canvas id="ci" width="96" height="40"></canvas>
      <div class="readout">input <b id="i_in">0</b> → emit (NOT) <b id="i_out">·</b></div>
      <div class="row"><button id="i_tog">toggle input</button><button id="i_auto" class="on">auto</button></div>
    </div>

    <div class="card full">
      <h3>4 · Autonomous wire <span class="tag">— routing with no controller</span></h3>
      <div class="desc">Walls confine a spreading carrier to a channel. Gate&nbsp;1 computes NOR(A,B) on the left; if it fires, the carrier travels the walled channel to gate&nbsp;2 on the right, which reproduces it — a gate-to-gate wire that runs itself. Cycling inputs.</div>
      <canvas id="cw" width="96" height="40"></canvas>
      <div class="readout">inputs A,B = <b id="w_in">00</b> → gate2 reads <b id="w_out">·</b> &nbsp;(= NOR, transported)</div>
      <div class="legend"><span class="sw" style="background:#5ed18a"></span>carrier (signal)<span class="sw" style="background:#ffd27f"></span>bias / walls dark</div>
    </div>

    <div class="card full">
      <h3>5 · Circulating register <span class="tag">— sequential memory (storage + a closed loop)</span></h3>
      <div class="desc">A row of latch cells wired into a ring: each clock the stored pattern rotates one cell and wraps around — a circulating delay-line memory. Every cell is a real latch (amber = 1, blue = 0); the bit string returns to its start every N clocks.</div>
      <canvas id="cr" width="250" height="40"></canvas>
      <div class="readout">stored bits: <b id="r_bits">·····</b> · clock <b id="r_clk">0</b></div>
    </div>
  </div>

  <p class="card frontier" style="margin-top:14px">
    <b>What's real and what's next.</b> Panels 1–2 are CA-1's building blocks: the gate composes into its ALU
    (any boolean function compiles to a verified CA-gate circuit automatically — <code>calayout.py</code>), the
    latch tiles into its RAM, and panel&nbsp;5 is the sequential/storage core. CA-1 runs multiply and sum-<i>1..N</i>
    correctly with a CA-decided branch (<code>cacpu.py</code>) — <i>honest scope:</i> its data + arithmetic are CA,
    its control unit is orchestrated as in any CPU. Panels 3–4 are the autonomous-wiring frontier: routing, fan-out
    and an inverter all work in-substrate; the one remaining primitive for fully-autonomous universal logic is a
    <b>second spreading layer</b> (so internal carriers can invert each other) — a concrete, named next experiment.
  </p>
</div>
<script>
"use strict";
function unpack(b64,n){const raw=atob(b64);const out=new Uint8Array(n);let p=0;
  for(let i=0;i<raw.length&&p<n;i++){const by=raw.charCodeAt(i);for(let k=0;k<4&&p<n;k++)out[p++]=(by>>(k*2))&3;}return out;}
const LO=unpack("__LO__",16384), LZ=unpack("__LZ__",16384), LW=unpack("__LW__",16384);
function step(b,lut,W,H){const nb=new Uint8Array(W*H);
  for(let r=0;r<H;r++){const rm=(r-1+H)%H,rp=(r+1)%H,ev=(r%2===0);
    for(let c=0;c<W;c++){const cm=(c-1+W)%W,cp=(c+1)%W,s=b[r*W+c],N=b[rm*W+c],Sd=b[rp*W+c],Wc=b[r*W+cm],E=b[r*W+cp];
      let nw,ne,sw,se;if(ev){nw=b[rm*W+cm];ne=N;sw=b[rp*W+cm];se=Sd;}else{nw=N;ne=b[rm*W+cp];sw=Sd;se=b[rp*W+cp];}
      nb[r*W+c]=lut[(s<<12)|(nw<<10)|(ne<<8)|(E<<6)|(se<<4)|(sw<<2)|Wc];}}return nb;}
function annih(A,B){for(let i=0;i<A.length;i++)if(A[i]>0&&B[i]>0){A[i]=0;B[i]=0;}}
function seed(arr,W,r,c,sz){const lo=c-(sz>>1),lr=r-(sz>>1);for(let i=lr;i<lr+sz;i++)for(let j=lo;j<lo+sz;j++)if(i>=0&&j>=0)arr[i*W+j]=1+(Math.random()*3|0);}
function mass(A){let m=0;for(let i=0;i<A.length;i++)if(A[i]>0)m++;return m;}
function massReg(A,W,r0,r1,c0,c1){let m=0;for(let r=r0;r<r1;r++)for(let c=c0;c<c1;c++)if(A[r*W+c]>0)m++;return m;}
const $=id=>document.getElementById(id);
function drawTwo(ctx,A,B,W,H,cA,cB,mask){const im=ctx.createImageData(W,H);
  for(let p=0;p<W*H;p++){let col=null;if(A[p]>0)col=cA;else if(B[p]>0)col=cB;else if(mask&&mask[p]===0)col=[18,22,30];
    if(col){im.data[p*4]=col[0];im.data[p*4+1]=col[1];im.data[p*4+2]=col[2];im.data[p*4+3]=255;}else im.data[p*4+3]=255;}
  // scale up via temp canvas
  const t=document.createElement("canvas");t.width=W;t.height=H;t.getContext("2d").putImageData(im,0,0);
  ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);
  ctx.drawImage(t,0,0,ctx.canvas.width,ctx.canvas.height);}
const AMBER=[255,210,127],BLUE=[109,179,255],GREEN=[94,209,138];

/* ---------- Panel 1: NAND gate ---------- */
const GS=60; let gO=new Uint8Array(GS*GS),gZ=new Uint8Array(GS*GS),gCombo=0,gT=0,gTT=[null,null,null,null];
function gReset(){gO=new Uint8Array(GS*GS);gZ=new Uint8Array(GS*GS);const k=gCombo;
  seed(gO,GS,GS>>1,GS>>1,18);if(k&1)seed(gZ,GS,(GS>>1)-12,GS>>1,14);if(k&2)seed(gZ,GS,(GS>>1)+12,GS>>1,14);
  gT=0;$("g_in").textContent=((k&2)>>1)+""+(k&1);}
function gTick(){gO=step(gO,LO,GS,GS);gZ=step(gZ,LZ,GS,GS);annih(gO,gZ);gT++;
  if(gT===55){const o=mass(gO)>mass(gZ)?1:0;gTT[gCombo]=o;$("g_out").textContent=o;
    $("g_tt").innerHTML="NAND: "+[0,1,2,3].map(k=>`<span class="${gTT[k]!==null?'hit':''}">${(k&2)>>1}${k&1}:${gTT[k]===null?'·':gTT[k]}</span>`).join(" ");}
  if(gT>=72){gCombo=(gCombo+1)&3;gReset();}
  drawTwo($("cg").getContext("2d"),gO,gZ,GS,GS,AMBER,BLUE);}

/* ---------- Panel 2: Latch ---------- */
const LS=60; let lA=new Uint8Array(LS*LS),lB=new Uint8Array(LS*LS),lAuto=true,lCd=0,lWant=1;
function lWrite(bit){lA=new Uint8Array(LS*LS);lB=new Uint8Array(LS*LS);seed(bit?lA:lB,LS,LS>>1,LS>>1,24);}
function lTick(){lA=step(lA,LO,LS,LS);lB=step(lB,LZ,LS,LS);annih(lA,lB);
  const bit=mass(lA)>mass(lB)?1:0;$("l_bit").textContent=bit;
  if(lAuto&&(++lCd>=110)){lCd=0;lWant^=1;lWrite(lWant);}
  drawTwo($("cl").getContext("2d"),lA,lB,LS,LS,AMBER,BLUE);}

/* ---------- Panel 3: Inverter ---------- */
const IW=96,IH=40; const Imask=new Uint8Array(IW*IH);
for(let r=4;r<36;r++)for(let c=4;c<34;c++)Imask[r*IW+c]=1;
for(let r=17;r<23;r++)for(let c=34;c<58;c++)Imask[r*IW+c]=1;
for(let r=4;r<36;r++)for(let c=58;c<92;c++)Imask[r*IW+c]=1;
let iZ=new Uint8Array(IW*IH),iO=new Uint8Array(IW*IH),iIn=0,iAuto=true,iCd=0;
function iTick(){seed(iZ,IW,20,12,7);if(iIn)seed(iO,IW,20,12,17);
  iZ=step(iZ,LW,IW,IH);iO=step(iO,LO,IW,IH);
  for(let p=0;p<IW*IH;p++)if(Imask[p]===0){iZ[p]=0;iO[p]=0;}annih(iZ,iO);
  const em=massReg(iZ,IW,4,36,74,92)>20?1:0;$("i_out").textContent=em;$("i_in").textContent=iIn;
  if(iAuto&&(++iCd>=90)){iCd=0;iIn^=1;iZ=new Uint8Array(IW*IH);iO=new Uint8Array(IW*IH);}
  drawTwo($("ci").getContext("2d"),iZ,iO,IW,IH,GREEN,AMBER,Imask);}

/* ---------- Panel 4: Autonomous wire (autowire2) ---------- */
const WW=96,WH=40; const Wmask=new Uint8Array(WW*WH);
for(let r=4;r<36;r++)for(let c=4;c<30;c++)Wmask[r*WW+c]=1;
for(let r=17;r<23;r++)for(let c=30;c<54;c++)Wmask[r*WW+c]=1;
for(let r=4;r<36;r++)for(let c=54;c<92;c++)Wmask[r*WW+c]=1;
let wZ=new Uint8Array(WW*WH),wO=new Uint8Array(WW*WH),wCombo=0,wT=0;
function wReset(){wZ=new Uint8Array(WW*WH);wO=new Uint8Array(WW*WH);const k=wCombo;
  if(k&1)seed(wZ,WW,12,10,7);if(k&2)seed(wZ,WW,28,10,7);wT=0;$("w_in").textContent=((k&2)>>1)+""+(k&1);}
function wTick(){if(wT<50){seed(wO,WW,20,16,7);seed(wO,WW,20,80,9);}
  wZ=step(wZ,LW,WW,WH);wO=step(wO,LO,WW,WH);
  for(let p=0;p<WW*WH;p++)if(Wmask[p]===0){wZ[p]=0;wO[p]=0;}annih(wZ,wO);wT++;
  if(wT===150){const o=massReg(wO,WW,4,36,78,92)>massReg(wZ,WW,4,36,78,92)?1:0;$("w_out").textContent=o;}
  if(wT>=180){wCombo=(wCombo+1)&3;wReset();}
  drawTwo($("cw").getContext("2d"),wZ,wO,WW,WH,GREEN,AMBER,Wmask);}

/* ---------- Panel 5: Circulating register ---------- */
const C=40,GAP=10,RH=40,PS=24,N=5; const RW=N*(C+GAP);
let rA=new Uint8Array(RW*RH),rB=new Uint8Array(RW*RH),rBits=[1,0,1,1,0],rClk=0,rCd=0,rSettle=0;
function rWrite(bits){rA=new Uint8Array(RW*RH);rB=new Uint8Array(RW*RH);const cy=RH>>1;
  for(let i=0;i<N;i++){const cx=i*(C+GAP)+GAP+(C>>1);seed(bits[i]?rA:rB,RW,cy,cx,PS);}rSettle=12;}
function rRead(){const out=[];for(let i=0;i<N;i++){const x0=i*(C+GAP);
  out.push(massReg(rA,RW,0,RH,x0,x0+C+GAP)>massReg(rB,RW,0,RH,x0,x0+C+GAP)?1:0);}return out;}
function rTick(){if(rSettle>0){rA=step(rA,LO,RW,RH);rB=step(rB,LZ,RW,RH);annih(rA,rB);rSettle--;}
  else if(++rCd>=40){rCd=0;const cur=rRead();const nb=[cur[N-1]].concat(cur.slice(0,N-1));rWrite(nb);rClk++;}
  $("r_bits").textContent=rRead().join("");$("r_clk").textContent=rClk;
  drawTwo($("cr").getContext("2d"),rA,rB,RW,RH,AMBER,BLUE);}

// buttons
$("l_set").onclick=()=>{lAuto=false;$("l_auto").classList.remove("on");lWrite(1);};
$("l_rst").onclick=()=>{lAuto=false;$("l_auto").classList.remove("on");lWrite(0);};
$("l_auto").onclick=function(){lAuto=!lAuto;this.classList.toggle("on",lAuto);};
$("i_tog").onclick=()=>{iAuto=false;$("i_auto").classList.remove("on");iIn^=1;iZ=new Uint8Array(IW*IH);iO=new Uint8Array(IW*IH);};
$("i_auto").onclick=function(){iAuto=!iAuto;this.classList.toggle("on",iAuto);};

gReset();lWrite(1);wReset();rWrite(rBits);
let fc=0;
function loop(){fc++;
  gTick();                       // gate every frame
  if(fc%2===0)lTick();           // latch a bit slower
  iTick(); wTick();
  rTick();
  requestAnimationFrame(loop);}
requestAnimationFrame(loop);
</script>
</body>
</html>
'''
HTML = HTML.replace("__LO__", luts["LO"]).replace("__LZ__", luts["LZ"]).replace("__LW__", luts["LW"])
open("dissemination/glider-lab10.html", "w").write(HTML)
print("wrote dissemination/glider-lab10.html", len(HTML), "bytes")
