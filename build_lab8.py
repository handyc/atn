#!/usr/bin/env python3
# build_lab8.py — generate dissemination/glider-lab8.html with the REAL latch/gate LUTs
# embedded (from /tmp/luts.txt), so the lab runs the genuine CA sequential circuit.
lo = lz = None
for line in open("/tmp/luts.txt"):
    if line.startswith("LO_B64="): lo = line[len("LO_B64="):].strip()
    if line.startswith("LZ_B64="): lz = line[len("LZ_B64="):].strip()
assert lo and lz, "missing LUTs"

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glider Lab 8 — the sequential circuit (closed feedback loop)</title>
<style>
  :root{--bg:#0e1116;--panel:#161b22;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#5ed18a;--no:#ff7a7a}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
  .wrap{max-width:1040px;margin:0 auto;padding:18px}
  h1{font-size:22px;margin:0 0 2px} h1 small{color:var(--mut);font-weight:400;font-size:14px}
  p{color:var(--mut);max-width:880px;margin:6px 0}
  .row{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-start;margin-top:10px}
  canvas{background:#05070a;border:1px solid #2a3340;border-radius:6px;display:block}
  .col{display:flex;flex-direction:column;gap:8px}
  button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:6px 11px;cursor:pointer;font-size:13px}
  button.on{background:var(--a);color:#1a1205;font-weight:600;border-color:var(--a)}
  button.act{background:var(--b);color:#04121f;border:none;font-weight:600}
  label{font-size:12px;color:var(--mut)} input[type=text]{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:4px 7px;width:120px;font-family:ui-monospace,monospace}
  .stat{font-size:12px;color:var(--mut);font-variant-numeric:tabular-nums} .stat b{color:var(--a)}
  .seq{font-family:ui-monospace,Menlo,monospace;font-size:15px;letter-spacing:2px;word-break:break-all;max-width:520px}
  .ok{color:var(--ok)} .no{color:var(--no)}
  .bits{font-family:ui-monospace,monospace;font-size:13px;color:var(--mut)}
  .hint{font-size:12px;color:var(--mut);max-width:520px} code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}
  .legend{font-size:12px;color:var(--mut)} .sw{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle;margin:0 3px}
</style>
</head>
<body>
<div class="wrap">
  <h1>Glider Lab 8 <small>— a sequential circuit: the loop is closed</small></h1>
  <p>Every other lab showed <i>combinational</i> CA logic — output depends only on the current input. This one closes
  the <b>feedback loop</b>: each clock tick, the circuit's output is routed back to its own input, so the state evolves
  <b>over time</b>. The boxes below are real <b>CA latches</b> (the verified mutual-annihilation flip-flop, the same
  genome as the memory work) — each holds one bit. This is the live substrate, not a schematic.</p>
  <p><b>RING</b>: a bit pattern circulates around a loop of latches (a delay-line memory). <b>LFSR</b>: add an XOR
  feedback tap — computed by the <b>CA NAND gate</b> — and the loop generates the exact maximal-length pseudo-random
  sequence of its tap polynomial. The reference sequence is mathematics; the CA reproduces it.</p>

  <div class="row">
    <button data-m="ring" class="on">RING (circulate)</button>
    <button data-m="lfsr">LFSR (XOR tap)</button>
    <label>init bits <input type="text" id="init" value="10110"></label>
    <button class="act" id="step">▶ step clock</button>
    <button class="act" id="run">⏩ run</button>
    <button id="reset">reset</button>
  </div>

  <div class="row">
    <canvas id="ca" width="760" height="180"></canvas>
    <div class="col">
      <div class="stat">mode <b id="mode">ring</b> · clock <b id="clk">0</b> · cells <b id="N">5</b></div>
      <div class="bits">state bits: <b id="bits" style="color:var(--a)">—</b></div>
      <div class="legend"><span class="sw" style="background:#ffd27f"></span>layer A (bit=1)
        <span class="sw" style="background:#6db3ff"></span>layer B (bit=0) — each cell's winner is its stored bit</div>
      <div class="stat">output stream (newest right):</div>
      <div class="seq" id="seq">—</div>
      <div id="refrow" style="display:none">
        <div class="stat">reference LFSR (math):</div>
        <div class="seq" id="ref">—</div>
        <div class="stat">CA vs reference: <b id="match">—</b></div>
      </div>
      <div class="hint" id="hint">The pattern rotates one cell per clock and wraps around — a circulating memory.
        After N clocks it returns to the start (period = N).</div>
    </div>
  </div>
  <p class="hint">Honest scope: the per-tick re-write and the clock are orchestrated by the page (a real CPU has an
  external clock too). What is genuinely in the substrate and verified here: the <b>state</b> (CA latches), the
  <b>logic</b> (CA NAND→XOR), and the <b>closed loop</b> computing a correct stateful sequence. Autonomous
  in-substrate transport (channels carrying bits between cells) is the remaining step — see <code>autowire2.py</code>.</p>
</div>
<script>
"use strict";
function unpack(b64,n){const raw=atob(b64);const out=new Uint8Array(n);let p=0;
  for(let i=0;i<raw.length&&p<n;i++){const by=raw.charCodeAt(i);for(let k=0;k<4&&p<n;k++)out[p++]=(by>>(k*2))&3;}return out;}
const LO=unpack("__LO__",16384), LZ=unpack("__LZ__",16384);
function step(b,lut,W,H){const nb=new Uint8Array(W*H);
  for(let r=0;r<H;r++){const rm=(r-1+H)%H,rp=(r+1)%H,ev=(r%2===0);
    for(let c=0;c<W;c++){const cm=(c-1+W)%W,cp=(c+1)%W,s=b[r*W+c],N=b[rm*W+c],Sd=b[rp*W+c],Wc=b[r*W+cm],E=b[r*W+cp];
      let nw,ne,sw,se;if(ev){nw=b[rm*W+cm];ne=N;sw=b[rp*W+cm];se=Sd;}else{nw=N;ne=b[rm*W+cp];sw=Sd;se=b[rp*W+cp];}
      nb[r*W+c]=lut[(s<<12)|(nw<<10)|(ne<<8)|(E<<6)|(se<<4)|(sw<<2)|Wc];}}return nb;}
function annih(A,B){for(let i=0;i<A.length;i++)if(A[i]>0&&B[i]>0){A[i]=0;B[i]=0;}}
// ---- CA latch register (verified genome) ----
const C=40,GAP=10,H=40,PS=24,HOLD=12;
function settle(A,B,W){for(let h=0;h<HOLD;h++){A=step(A,LO,W,H);B=step(B,LZ,W,H);annih(A,B);}return[A,B];}
function seed(arr,W,cx,cy,sz){const lo=cx-(sz>>1),lr=cy-(sz>>1);for(let r=lr;r<lr+sz;r++)for(let c=lo;c<lo+sz;c++)arr[r*W+c]=1+(Math.random()*3|0);}
function writeState(bits){const N=bits.length,W=N*(C+GAP);let A=new Uint8Array(W*H),B=new Uint8Array(W*H);const cy=H>>1;
  for(let i=0;i<N;i++){const cx=i*(C+GAP)+GAP+(C>>1);seed(bits[i]?A:B,W,cx,cy,PS);}return settle(A,B,W);}
function readState(A,B,N){const W=N*(C+GAP),out=[];
  for(let i=0;i<N;i++){let ma=0,mb=0;const x0=i*(C+GAP),x1=x0+C+GAP;
    for(let r=0;r<H;r++)for(let c=x0;c<x1;c++){if(A[r*W+c]>0)ma++;if(B[r*W+c]>0)mb++;}out.push(ma>mb?1:0);}return out;}
// ---- CA universal gate: latch-threshold NAND, XOR composed from it ----
const GS=60,BIAS=18,INSZ=14,GHOLD=60;
function decide(a,b){let O=new Uint8Array(GS*GS),Z=new Uint8Array(GS*GS);
  seed(O,GS,GS>>1,GS>>1,BIAS);if(a)seed(Z,GS,GS>>1,(GS>>1)-12,INSZ);if(b)seed(Z,GS,GS>>1,(GS>>1)+12,INSZ);
  for(let h=0;h<GHOLD;h++){O=step(O,LO,GS,GS);Z=step(Z,LZ,GS,GS);annih(O,Z);}
  let mo=0,mz=0;for(let i=0;i<O.length;i++){if(O[i]>0)mo++;if(Z[i]>0)mz++;}return mo>mz?1:0;}
function nand(a,b){return decide(a,b);}
function xor(a,b){const n1=nand(a,b);return nand(nand(a,n1),nand(b,n1));}
// ---- reference LFSR (exact math) ----
function refLFSR(init,steps){let st=init.slice(),seq=[];for(let t=0;t<steps;t++){const o=st[st.length-1];const fb=st[st.length-1]^st[st.length-2];st=[fb].concat(st.slice(0,-1));seq.push(o);}return seq;}
// ---- state ----
let mode="ring",bits=[1,0,1,1,0],A,B,clk=0,outSeq=[],running=false,refSeq=[];
const cc=document.getElementById("ca").getContext("2d");
const $=id=>document.getElementById(id);
function init(){const txt=$("init").value.replace(/[^01]/g,"")||"10110";bits=txt.split("").map(Number);
  if(mode==="lfsr"&&bits.length<2)bits=[1,0,0,0];
  [A,B]=writeState(bits);clk=0;outSeq=[];refSeq=mode==="lfsr"?refLFSR(bits,40):[];
  $("N").textContent=bits.length;render();}
function clock(){const N=bits.length,cur=readState(A,B,N);let newbits,out;
  if(mode==="ring"){out=cur[N-1];newbits=[cur[N-1]].concat(cur.slice(0,N-1));}   // rotate, wrap last->first
  else{out=cur[N-1];const fb=xor(cur[N-1],cur[N-2]);newbits=[fb].concat(cur.slice(0,N-1));} // XOR tap -> bit0
  outSeq.push(out);bits=newbits;[A,B]=writeState(bits);clk++;render();}
function render(){const N=bits.length,W=N*(C+GAP),sc=Math.min(760/W,180/H);
  cc.fillStyle="#05070a";cc.fillRect(0,0,760,180);
  for(let r=0;r<H;r++)for(let c=0;c<W;c++){const ia=A[r*W+c],ib=B[r*W+c];if(!ia&&!ib)continue;
    cc.fillStyle=ia>0?"#ffd27f":"#6db3ff";cc.fillRect(c*sc,r*sc,sc+0.6,sc+0.6);}
  const rb=readState(A,B,N);cc.font="bold 13px ui-monospace,monospace";cc.textBaseline="top";
  for(let i=0;i<N;i++){const cx=(i*(C+GAP)+GAP+(C>>1))*sc;cc.fillStyle=rb[i]?"#ffd27f":"#6db3ff";cc.textAlign="center";cc.fillText(rb[i],cx,2);}
  $("mode").textContent=mode;$("clk").textContent=clk;$("bits").textContent=rb.join("");
  const tail=outSeq.slice(-40).join("");$("seq").textContent=tail||"—";
  if(mode==="lfsr"){$("refrow").style.display="";const rt=refSeq.slice(0,outSeq.length).join("");
    $("ref").textContent=refSeq.slice(0,Math.max(outSeq.length,1)).join("")||"—";
    const m=outSeq.length>0&&outSeq.join("")===refSeq.slice(0,outSeq.length).join("");
    const el=$("match");el.textContent=outSeq.length?(m?"MATCH ✓":"diverged"):"—";el.className=m?"ok":(outSeq.length?"no":"");}
  else $("refrow").style.display="none";}
document.querySelectorAll("button[data-m]").forEach(btn=>btn.onclick=()=>{
  document.querySelectorAll("button[data-m]").forEach(b=>b.classList.remove("on"));btn.classList.add("on");
  mode=btn.dataset.m;$("init").value=mode==="lfsr"?"1000":"10110";
  $("hint").textContent=mode==="lfsr"
    ?"Each clock: the top two bits are XOR'd (by the CA NAND gate) and fed into bit 0; the rest shift right. The stream below must match the mathematical reference exactly — a 4-bit maximal LFSR has period 15."
    :"The pattern rotates one cell per clock and wraps around — a circulating memory. After N clocks it returns to the start (period = N).";
  init();});
$("step").onclick=()=>{if(!running)clock();};
$("run").onclick=function(){running=!running;this.textContent=running?"⏸ pause":"⏩ run";
  const tick=()=>{if(!running)return;clock();setTimeout(tick,650);};if(running)tick();};
$("reset").onclick=init;$("init").onchange=init;
init();
</script>
</body>
</html>
'''
HTML = HTML.replace("__LO__", lo).replace("__LZ__", lz)
open("dissemination/glider-lab8.html", "w").write(HTML)
print("wrote dissemination/glider-lab8.html", len(HTML), "bytes")
