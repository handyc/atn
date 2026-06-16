#!/usr/bin/env python3
# build_lab11.py — glider-lab11.html: a playable raycaster (Doom's core) running on a faithful
# CA-1 virtual machine in the browser. The JS VM implements the EXACT CA-1 ISA (same 8-bit
# semantics as ca1sys.py / the genuine CA datapath); it runs the same 195-instruction program
# that rendered the verified reference frame. Arrow/WASD keys drive it. Honest banner: every
# ALU op is one the CA gate computes (verified bit-identical); this VM just runs it ~1e8x faster
# than the 2.5 instr/s genuine CA so it's interactive.
import json
E = json.load(open("/tmp/raycast_export.json"))
EJSON = json.dumps(E, separators=(",", ":"))

HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Glider Lab 11 — Doom-reduced on the CA-1 computer</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:900px;margin:0 auto;padding:18px}
 h1{font-size:22px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:14px}
 p{color:var(--mut);max-width:820px}
 canvas{background:#000;border:1px solid #2a3340;border-radius:8px;display:block;image-rendering:pixelated;width:600px;height:350px;max-width:100%}
 .hud{display:flex;gap:18px;flex-wrap:wrap;margin-top:8px;font-size:13px;color:var(--mut);font-variant-numeric:tabular-nums}
 .hud b{color:var(--a)}
 kbd{background:#222b36;border:1px solid #2a3340;border-radius:4px;padding:1px 6px;font-size:12px}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:12px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}
</style></head>
<body><div class="wrap">
 <h1>Glider Lab 11 <small>— "Doom", reduced to its core, running on the CA-1 computer</small></h1>
 <p>This is a first-person raycaster — the rendering idea at the heart of Doom — running as a
 <b>195-instruction program on a faithful CA-1 virtual machine</b>. Move with <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd>
 or the arrow keys. Every arithmetic op the program executes (ADD/SUB/AND/OR/shift/compare) is one the
 cellular-automaton datapath computes — verified bit-identical to the CA gates. This VM just runs it
 ~10⁸× faster than the real CA's 2.5 instructions/second, so it's actually playable.</p>
 <canvas id="s" width="48" height="28" tabindex="0"></canvas>
 <div class="hud">
   <span>fps <b id="fps">·</b></span><span>instr / frame <b id="ipf">·</b></span>
   <span>CA-1 instr executed <b id="tot">0</b></span><span>player ∠ <b id="pa">·</b></span>
   <span style="color:var(--a)">click the view, then use WASD / arrows</span>
 </div>
 <div class="note"><b>What you're looking at.</b> A 48×28 view, ~40,000 CA-1 instructions per frame. On the
 genuine cellular automaton (one NAND = a 60×60 board run 60 steps; ~2.5 instr/s) one frame would take
 ~4½ hours — so the real CA renders this, just not in real time. Full Doom needs ~15 million 32-bit
 instr/s and megabytes of RAM; on this 8-bit machine that's ~2 billion× too slow and ~260,000× too little
 memory. So this is Doom's <i>algorithm</i> on a real CA computer — a universality demo, not the shipping game.
 (The VM here is exact CA-1 machine code; <code>ca1sys.py</code> verifies its ALU equals the CA gates.)</div>
</div>
<script>
"use strict";
const E=__EJSON__, PROG=E.prog, SW=E.SW, SH=E.SH, FB=E.FB, INP=E.INP, MASK=0xFF;
const M=new Uint8Array(0x10000);
for(const k in E.mem) M[+k]=E.mem[k];
let A=0,X=0,P=0,PC=0,Z=1,C=0,N=0, total=0, keys=0;
function set(v,carry){const v8=v&MASK; Z=(v8===0)?1:0; N=(v8>>7)&1; if(carry!==undefined)C=carry&1; return v8;}
function runFrame(maxi){ // run until a FRAME op; return instrs used
  M[INP]=keys; let n=0;
  while(n<maxi){ const ins=PROG[PC]; const op=ins[0], arg=ins[1]; PC++; n++; const a=A;
    switch(op){
      case "LDI": A=set(arg); break;
      case "LDA": A=set(M[arg]); break;
      case "STA": M[arg&0xFFFF]=a; break;
      case "LDAX": A=set(M[(arg+X)&0xFFFF]); break;
      case "STAX": M[(arg+X)&0xFFFF]=a; break;
      case "LDX": X=set(M[arg]); break;
      case "LXI": X=set(arg); break;
      case "TAX": X=set(a); break;
      case "TXA": A=set(X); break;
      case "INX": X=set(X+1); break;
      case "DEX": X=set(X-1); break;
      case "ADD": A=set(a+M[arg],(a+M[arg])>MASK?1:0); break;
      case "ADDI": A=set(a+arg,(a+arg)>MASK?1:0); break;
      case "SUB": A=set(a-M[arg], a>=M[arg]?1:0); break;
      case "SUBI": A=set(a-arg, a>=arg?1:0); break;
      case "AND": A=set(a&M[arg]); break;
      case "ANDI": A=set(a&arg); break;
      case "OR": A=set(a|M[arg]); break;
      case "XOR": A=set(a^M[arg]); break;
      case "INC": A=set(a+1); break;
      case "DEC": A=set(a-1); break;
      case "SHL": A=set(a<<1,(a>>7)&1); break;
      case "SHR": A=set(a>>1,a&1); break;
      case "CMP": {const d=a-M[arg]; set(d, a>=M[arg]?1:0); break;}
      case "CMPI": {const d=a-arg; set(d, a>=arg?1:0); break;}
      case "JMP": PC=arg; break;
      case "JZ": if(Z)PC=arg; break;
      case "JNZ": if(!Z)PC=arg; break;
      case "JC": if(C)PC=arg; break;
      case "JNC": if(!C)PC=arg; break;
      case "JN": if(N)PC=arg; break;
      case "LDP": P=arg&0xFFFF; break;
      case "ADDP": P=(P+arg)&0xFFFF; break;
      case "STPX": M[(P+X)&0xFFFF]=a; break;
      case "LDPX": A=set(M[(P+X)&0xFFFF]); break;
      case "IN": A=set(M[INP]); break;
      case "FRAME": total+=n; return n;
      case "NOP": break;
      case "HLT": return n;
      default: throw "bad op "+op;
    }
  }
  total+=n; return n;
}
// palette (Doom-ish): 0 black,1 ceiling,2 wall near,3 mid,4 far,5 floor
const PAL=[[0,0,0],[26,32,42],[210,124,44],[150,86,32],[86,52,22],[58,58,66]];
const cv=document.getElementById("s"), cx=cv.getContext("2d"), img=cx.createImageData(SW,SH);
function draw(){ for(let c=0;c<SW;c++)for(let y=0;y<SH;y++){const v=M[FB+c*SH+y],p=PAL[v]||PAL[0],i=(y*SW+c)*4;
    img.data[i]=p[0];img.data[i+1]=p[1];img.data[i+2]=p[2];img.data[i+3]=255;}
  cx.putImageData(img,0,0); }
// keyboard -> input bits (0 left,1 right,2 fwd,3 back)
const KB={37:0,65:0, 39:1,68:1, 38:2,87:2, 40:3,83:3};
function keymask(e,down){const b=KB[e.keyCode]; if(b===undefined)return; e.preventDefault(); if(down)keys|=(1<<b); else keys&=~(1<<b);}
cv.addEventListener("keydown",e=>keymask(e,true)); cv.addEventListener("keyup",e=>keymask(e,false));
cv.addEventListener("blur",()=>keys=0); cv.focus();
let last=performance.now(), fa=0, fc=0, ipf=0;
function loop(t){ ipf=runFrame(2_000_000); draw();
  fc++; if(t-last>=500){document.getElementById("fps").textContent=(fc*1000/(t-last)).toFixed(0);
    document.getElementById("ipf").textContent=ipf.toLocaleString();
    document.getElementById("tot").textContent=total.toLocaleString();
    document.getElementById("pa").textContent=M[0x12]; fc=0; last=t;}
  requestAnimationFrame(loop);}
requestAnimationFrame(loop);
</script></body></html>'''
HTML = HTML.replace("__EJSON__", EJSON)
open("dissemination/glider-lab11.html", "w").write(HTML)
print("wrote dissemination/glider-lab11.html", len(HTML), "bytes")
