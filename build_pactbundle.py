#!/usr/bin/env python3
# build_pactbundle.py — the tiny self-contained CA-OS page that the 64 KB pact ELF serves.
# Everything is REGENERATED from the embedded program: the CA-OS/2 desktop (caos_ca2), an ASCII-only
# 16x16 Unifont (95 glyphs, not the 1.2 MB full BMP — keeps the packet small), the faithful 32-bit
# CA-2 VM, and the secure pact channel (AES-256-GCM keyed by a hex-K4 CA grown from the shared seed).
# Two nodes each run the same packet, regenerate the identical OS locally, and exchange ONLY sealed
# input deltas over the ELF's relay -> "send the whole OS through the pact" with almost no bytes sent.
import json, base64, zlib, struct
import caos_ca2 as o

m = o.make(); o.load_memory(m)
prog, _ = o.program()

# ---- ASCII-only 16x16 font (printable 0x20..0x7E), packed from unifont16.json (1-bit, 32 B/glyph) ----
_f = json.load(open("unifont16.json"))
_blob = zlib.decompress(base64.b64decode(_f["b64"]))
_cps = struct.unpack("<%dH" % (_f["n"]), base64.b64decode(_f["cps_b64"]))
_idx = {cp: i for i, cp in enumerate(_cps)}
ascii_glyphs = {}
for cp in range(0x20, 0x7F):
    if cp in _idx:
        ascii_glyphs[cp] = base64.b64encode(_blob[_idx[cp]*32:_idx[cp]*32+32]).decode()
FONTASCII = ascii_glyphs            # {codepoint: b64(32 bytes)}

OS = dict(prog=[[op, (a if a is not None else 0)] for op, a in prog],
          mem={str(a): m.M[a] for a in range(0x10000) if m.M[a]},
          SP=0x7FFF, MEM=o.MEMSIZE, W=o.W, H=o.H, FB=o.FB, MX=o.MX, MY=o.MY, MB=o.MB, KEY=o.KEY, PAL=o.PAL,
          TBUF=o.TBUF, TLEN=o.TLEN, CELLS=o.CELLS, DIRTY=o.DIRTY, APP=o.APP,
          WINX=o.WINX, WINY=o.WINY, WW=o.WW, WH=o.WH, CSTRIDE=o.CSTRIDE, WTAB=o.WTAB, FONT16=o.FONT16,
          FONT=FONTASCII)
OSJSON = json.dumps(OS, separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>node</title>
<style>*{box-sizing:border-box}body{margin:0;background:#0a0c10;color:#cfd8e3;font:13px system-ui;display:flex;flex-direction:column;align-items:center;gap:6px;padding:10px}
#screen{image-rendering:pixelated;width:768px;max-width:100%;border:3px solid #2a3340;border-radius:4px;background:#000;cursor:none;display:block}
#bar{font:12px ui-monospace,monospace;color:#9aa7b4}#bar b{color:#ffd27f}</style></head><body>
<canvas id="screen" width="512" height="384" tabindex="0"></canvas>
<div id="bar">CA-OS regenerated from the pact · <span id="st">solo</span></div>
<script>
"use strict";
const OS=__OS__;
function makeVM(sz,sp){const M=new Uint8Array(sz),NM=sz-1;let A=0,X=0,SP=sp||0x7FFF,PC=0,Z=1,C=0,N=0;
 const set=(v,c)=>{const w=v>>>0;Z=w===0?1:0;N=(w>>>31)&1;if(c!==undefined)C=c&1;return w;};
 const wrd=d=>{d&=NM;return (M[d]|(M[d+1]<<8)|(M[d+2]<<16)|(M[d+3]<<24))>>>0;};
 function run(prog){let n=0;while(n<60000000){const I=prog[PC],op=I[0],arg=I[1];PC++;n++;const a=A;
   switch(op){case"LDI":A=set(arg);break;case"LDA":A=set(M[arg&NM]);break;case"STA":M[arg&NM]=a&0xFF;break;
    case"LDAX":A=set(M[(arg+X)&NM]);break;case"STAX":M[(arg+X)&NM]=a&0xFF;break;case"LDW":A=set(wrd(arg));break;
    case"STW":{const d=arg&NM;M[d]=a&0xFF;M[d+1]=(a>>>8)&0xFF;M[d+2]=(a>>>16)&0xFF;M[d+3]=(a>>>24)&0xFF;break;}
    case"ADDW":{const w=wrd(arg);A=set(a+w,(a+w)>0xFFFFFFFF?1:0);break;}case"SUBW":{const w=wrd(arg);A=set(a-w,a>=w?1:0);break;}
    case"CMPW":{const w=wrd(arg);set((a-w)>>>0,a>=w?1:0);break;}case"LDX":X=set(M[arg&NM]);break;case"LXI":X=set(arg);break;
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
const vm=makeVM(OS.MEM,OS.SP);for(const k in OS.mem)vm.M[+k]=OS.mem[k];
// regenerate the ASCII font into the CA's RAM (FONT16 table + WTAB widths)
{const b2u=s=>{const b=atob(s),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;};
 for(const cp in OS.FONT){const g=b2u(OS.FONT[cp]),off=OS.FONT16+(+cp)*32;let wide=0;for(let i=0;i<32;i++){vm.M[off+i]=g[i];if((i&1)&&g[i])wide=1;}vm.M[OS.WTAB+ +cp]=wide?16:8;}}
const W=OS.W,H=OS.H,FB=OS.FB,sc=document.getElementById("screen"),sx=sc.getContext("2d"),im=sx.createImageData(W,H);
const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
let mx=W>>1,my=H>>1,mb=0,keyq=[];
function rel(e){const r=sc.getBoundingClientRect(),cs=getComputedStyle(sc),bl=parseFloat(cs.borderLeftWidth)||0,bt=parseFloat(cs.borderTopWidth)||0;
 return[Math.max(0,Math.min(W-1,((e.clientX-r.left-bl)/sc.clientWidth*W)|0)),Math.max(0,Math.min(H-1,((e.clientY-r.top-bt)/sc.clientHeight*H)|0))];}
function wr32(a,v){vm.M[a]=v&0xFF;vm.M[a+1]=(v>>>8)&0xFF;vm.M[a+2]=(v>>>16)&0xFF;vm.M[a+3]=(v>>>24)&0xFF;}
sc.addEventListener("mousemove",e=>{[mx,my]=rel(e);});
sc.addEventListener("mousedown",e=>{[mx,my]=rel(e);mb=1;sc.focus();});window.addEventListener("mouseup",()=>mb=0);
sc.addEventListener("keydown",e=>{let cp=-1;if(e.key==="Backspace")cp=8;else if(e.key==="Enter")cp=10;else if([...e.key].length===1)cp=e.key.codePointAt(0);
 if(cp>=0){e.preventDefault();keyq.push(cp);}});
function frame(){wr32(OS.MX,mx);wr32(OS.MY,my);wr32(OS.MB,mb);
 if(keyq.length&&vm.M[OS.KEY]===0)wr32(OS.KEY,keyq.shift());
 vm.run(OS.prog);
 for(let i=0;i<W*H;i++){const v=vm.M[FB+i],p=PAL[v]||PAL[0];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}
 sx.putImageData(im,0,0);requestAnimationFrame(frame);}
requestAnimationFrame(frame);
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON)
open("pactbundle.html", "w").write(HTML)
gz = zlib.compress(HTML.encode(), 9)
open("pactbundle.html.z", "wb").write(gz)
print("pactbundle.html", len(HTML), "bytes ->  raw deflate", len(gz), "bytes;  ASCII glyphs:", len(FONTASCII))
