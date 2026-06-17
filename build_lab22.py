#!/usr/bin/env python3
# build_lab22.py — glider-lab22.html: CA-OS/2 running in the browser on a faithful 32-bit CA-2 VM.
# The JS VM implements the EXACT CA-2 semantics from ca1sys (32-bit registers/ALU, flat 1 MB
# addressing, LDW/STW/ADDW/SUBW/CMPW word ops) — the same machine code that rendered the verified
# reference frame in caos_ca2.py. The browser is a dumb terminal: blit the 512x384 framebuffer +
# forward the mouse. Honest: CA-2's ALU is the genuine 8-bit CA NAND-gate adder tiled to 32 bits
# (cacpu.verify_adder_ca); this VM just runs it ~1e8x faster, exactly as the CA-1 labs do for CA-1.
import json
import caos_ca2 as o
from ca1sys import make_machine

m = make_machine("CA-2", fb_addr=o.FB, fb_w=o.W, fb_h=o.H); o.load_memory(m)
prog, _ = o.program()
OS = dict(
    prog=[[op, (arg if arg is not None else 0)] for op, arg in prog],
    mem={str(a): m.M[a] for a in range(0x10000) if m.M[a]},   # initial memory (font); FB is drawn at runtime
    SP=0x7FFF, W=o.W, H=o.H, FB=o.FB, MX=o.MX, MY=o.MY, MB=o.MB, KEY=o.KEY, PAL=o.PAL, GIDX=o.c1.GIDX)
OSJSON = json.dumps(OS, separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CA-OS/2 — a 32-bit operating system running on a cellular-automaton computer</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:900px;margin:0 auto;padding:16px}
 h1{font-size:21px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:13px}
 p{color:var(--mut);max-width:820px}
 #screen{image-rendering:pixelated;width:768px;max-width:100%;border:3px solid #2a3340;border-radius:4px;background:#000;cursor:none;display:block}
 .hud{font-size:12px;color:var(--mut);margin-top:8px;font-variant-numeric:tabular-nums}.hud b{color:var(--a)}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:12px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)} b.b{color:var(--b)}
</style></head><body><div class="wrap">
 <h1>CA-OS/2 <small>— a 32-bit OS running on the CA-2 cellular-automaton computer</small></h1>
 <p>This is the <b>32-bit</b> member of the family. The same parameterized core that builds the 8-bit CA-1
 builds <b class="b">CA-2</b>: 32-bit registers and ALU, <b>1 MB of flat memory</b>, a 512×384 screen. Everything
 you see — the window, the text, the cursor, the clock — is CA-2 machine code writing colour bytes into a
 framebuffer; the browser only blits it and forwards your mouse. <span id="selftest"></span></p>
 <canvas id="screen" width="512" height="384" tabindex="0"></canvas>
 <div class="hud">move the mouse over the screen · CA-2 instr/frame <b id="ipf">·</b> · fps <b id="fps">·</b></div>
 <p class="note"><b>Honest scope:</b> CA-2's 32-bit ALU is the <i>genuine</i> 8-bit CA NAND-gate ripple-adder
 <b>tiled to 32 bits</b> — verified bit-for-bit against the reference (<code>cacpu.verify_adder_ca</code>), no new
 gate. This JS VM runs the identical CA-2 instruction set ~10⁸× faster so it's interactive, exactly as the CA-1
 labs do for CA-1. The framebuffer lives flat at <code>0x10000</code>; pixels are written with a 32-bit indexed
 store (<code>STAX</code>), no banking. One registry, many machines — add a row to grow the family.</p>
</div>
<script>
"use strict";
const OS=__OS__;
/* faithful 32-bit CA-2 VM (mirrors ca1sys make_machine("CA-2"): 32-bit regs/ALU, flat 1 MB) */
function makeVM(sp){const M=new Uint8Array(0x100000);let A=0,X=0,SP=sp||0x7FFF,PC=0,Z=1,C=0,N=0;
 const NM=0xFFFFF;                                  // flat near/addr mask (1 MB)
 const set=(v,c)=>{const w=v>>>0;Z=w===0?1:0;N=(w>>>31)&1;if(c!==undefined)C=c&1;return w;};
 const wrd=d=>{d&=NM;return (M[d]|(M[d+1]<<8)|(M[d+2]<<16)|(M[d+3]<<24))>>>0;};
 function run(prog){let n=0;while(n<30000000){const I=prog[PC],op=I[0],arg=I[1];PC++;n++;const a=A;
   switch(op){
    case"LDI":A=set(arg);break;case"LDA":A=set(M[arg&NM]);break;case"STA":M[arg&NM]=a&0xFF;break;
    case"LDAX":A=set(M[(arg+X)&NM]);break;case"STAX":M[(arg+X)&NM]=a&0xFF;break;
    case"LDW":A=set(wrd(arg));break;
    case"STW":{const d=arg&NM;M[d]=a&0xFF;M[d+1]=(a>>>8)&0xFF;M[d+2]=(a>>>16)&0xFF;M[d+3]=(a>>>24)&0xFF;break;}
    case"ADDW":{const w=wrd(arg);A=set(a+w,(a+w)>0xFFFFFFFF?1:0);break;}
    case"SUBW":{const w=wrd(arg);A=set(a-w,a>=w?1:0);break;}
    case"CMPW":{const w=wrd(arg);set((a-w)>>>0,a>=w?1:0);break;}
    case"LDX":X=set(M[arg&NM]);break;case"LXI":X=set(arg);break;
    case"TAX":X=set(a);break;case"TXA":A=set(X);break;case"INX":X=set(X+1);break;case"DEX":X=set(X-1);break;
    case"ADD":{const w=M[arg&NM];A=set(a+w,(a+w)>0xFFFFFFFF?1:0);break;}case"ADDI":A=set(a+arg,(a+arg)>0xFFFFFFFF?1:0);break;
    case"SUB":{const w=M[arg&NM];A=set(a-w,a>=w?1:0);break;}case"SUBI":A=set(a-arg,a>=arg?1:0);break;
    case"AND":A=set(a&M[arg&NM]);break;case"ANDI":A=set((a&arg)>>>0);break;case"OR":A=set(a|M[arg&NM]);break;case"XOR":A=set(a^M[arg&NM]);break;
    case"INC":A=set(a+1);break;case"DEC":A=set(a-1);break;case"SHL":A=set((a*2)>>>0,(a>>>31)&1);break;case"SHR":A=set(a>>>1,a&1);break;
    case"CMP":{const w=M[arg&NM];set((a-w)>>>0,a>=w?1:0);break;}case"CMPI":set((a-arg)>>>0,a>=arg?1:0);break;
    case"JMP":PC=arg;break;case"JZ":if(Z)PC=arg;break;case"JNZ":if(!Z)PC=arg;break;case"JC":if(C)PC=arg;break;case"JNC":if(!C)PC=arg;break;case"JN":if(N)PC=arg;break;
    case"CALL":M[SP]=PC&255;M[SP-1]=(PC>>8)&255;SP-=2;PC=arg;break;case"RET":SP+=2;PC=(M[SP-1]<<8)|M[SP];break;
    case"FRAME":return n;case"NOP":break;case"HLT":return n;default:throw"op "+op;}}return n;}
 return {M,run};}
const vm=makeVM(OS.SP);for(const k in OS.mem)vm.M[+k]=OS.mem[k];
const W=OS.W,H=OS.H,FB=OS.FB;
const sc=document.getElementById("screen"),sx=sc.getContext("2d"),im=sx.createImageData(W,H);
const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
let mx=W>>1,my=H>>1,mb=0;
function rel(e){const r=sc.getBoundingClientRect(),cs=getComputedStyle(sc),
  bl=parseFloat(cs.borderLeftWidth)||0,bt=parseFloat(cs.borderTopWidth)||0;   // border-exact: clientX/Y minus border, over the content box
  const x=(e.clientX-r.left-bl)/sc.clientWidth*W,y=(e.clientY-r.top-bt)/sc.clientHeight*H;
  return[Math.max(0,Math.min(W-1,x|0)),Math.max(0,Math.min(H-1,y|0))];}
function wr32(addr,v){vm.M[addr]=v&0xFF;vm.M[addr+1]=(v>>>8)&0xFF;vm.M[addr+2]=(v>>>16)&0xFF;vm.M[addr+3]=(v>>>24)&0xFF;}
sc.addEventListener("mousemove",e=>{[mx,my]=rel(e);});
sc.addEventListener("mousedown",e=>{[mx,my]=rel(e);mb=1;sc.focus();});window.addEventListener("mouseup",()=>mb=0);
/* keyboard -> KEY register as (glyph index + 1); 0 = none, so digit '0' (glyph 0) isn't lost */
sc.addEventListener("keydown",e=>{let g=-1;
 if(e.key==="Backspace")g=0xFE; else if(e.key===" ")g=(OS.GIDX[" "]||0);
 else if(e.key.length===1&&OS.GIDX[e.key]!==undefined)g=OS.GIDX[e.key];   // preserve case (font has a-z and A-Z)
 if(g>=0){e.preventDefault();wr32(OS.KEY,g+1);}});
let last=performance.now(),fc=0,ipf=0;
function frame(t){wr32(OS.MX,mx);wr32(OS.MY,my);wr32(OS.MB,mb);ipf=vm.run(OS.prog);
 for(let i=0;i<W*H;i++){const v=vm.M[FB+i],p=PAL[v]||PAL[0];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}
 sx.putImageData(im,0,0);fc++;if(t-last>=500){document.getElementById("ipf").textContent=ipf.toLocaleString();
  document.getElementById("fps").textContent=(fc*1000/(t-last)).toFixed(0);fc=0;last=t;}
 requestAnimationFrame(frame);}
requestAnimationFrame(frame);
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON)
open("dissemination/glider-lab22.html", "w").write(HTML)
print("wrote dissemination/glider-lab22.html", len(HTML), "bytes")
