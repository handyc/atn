#!/usr/bin/env python3
# build_lab25.py — glider-lab25.html: the CA Unicode Writer. A CA-2 in a 4 MB machine holds the entire
# 16x16 GNU-Unifont (full Unicode BMP, incl. CJK) in its own memory and blits every glyph itself; the
# browser captures keystrokes as Unicode codepoints (IME + paste supported) and blits the framebuffer.
import json
import caos_uni as u
from ca1sys import make_machine

m = u.make()
prog, _ = u.program()
FONT = json.load(open("unifont16.json"))   # {cps_b64, b64 (zlib glyph blob), n}
OS = dict(prog=[[op, (a if a is not None else 0)] for op, a in prog],
          SP=0x7FFF, MEM=u.MEMSIZE, W=u.W, H=u.H, FB=u.FB, UBUF=u.UBUF, WTAB=u.WTAB, FONT16=u.FONT16,
          KEY=u.KEY, ULEN=u.ULEN, DIRTY=u.DIRTY, PAL=u.PAL)
OSJSON = json.dumps(OS, separators=(",", ":"))
FONTJSON = json.dumps(FONT, separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CA Unicode Writer — every language, rendered by a cellular automaton</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:900px;margin:0 auto;padding:16px}
 h1{font-size:21px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:13px}
 p{color:var(--mut);max-width:820px}
 #screen{image-rendering:pixelated;width:768px;max-width:100%;border:3px solid #2a3340;border-radius:4px;background:#000;display:block;margin-top:8px}
 #ime{width:768px;max-width:100%;margin-top:8px;background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:8px 10px;font:15px system-ui;resize:vertical}
 .row{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
 .row button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:13px}
 .row button:hover{border-color:var(--a)}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:12px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)} #stat{color:var(--a)}
</style></head><body><div class="wrap">
 <h1>CA Unicode Writer <small>— every language, rendered by a cellular automaton</small></h1>
 <p>The same CA-2 machine, given <b>4 MB of memory</b>, holds the entire <b>16×16 GNU Unifont</b> — the full
 Unicode Basic Multilingual Plane (Latin, Greek, Cyrillic, Hiragana/Katakana, Hangul, and ~27,000 CJK
 ideographs) — in its <i>own</i> memory, and blits every glyph itself. Type below (your IME and paste work),
 or pick a sample. <span id="stat">loading font…</span></p>
 <canvas id="screen" width="512" height="384"></canvas>
 <textarea id="ime" rows="3" placeholder="type here — any language (Enter for new line; IME &amp; paste supported)" autocomplete="off" autocapitalize="off" spellcheck="false"></textarea>
 <div class="row" id="samples"></div>
 <p class="note"><b>Honest scope:</b> the glyphs are <b>GNU Unifont</b> (16×16 bitmaps), inflated in the browser
 and written into the CA's RAM at <code>0x100000</code> as a direct codepoint→glyph table (32 bytes each); the
 CA-2 program reads each typed codepoint and blits its 16×16 cell with a flat indexed store — no browser font
 is used for the canvas. Right-to-left scripts render left-to-right (no bidi/shaping). Same machine + ISA as
 the other CA-OS labs, just with more RAM and a bigger font.</p>
</div>
<script>
"use strict";
const OS=__OS__, FONT=__FONT__;
function makeVM(sz,sp){const M=new Uint8Array(sz),NM=sz-1;let A=0,X=0,SP=sp||0x7FFF,PC=0,Z=1,C=0,N=0;
 const set=(v,c)=>{const w=v>>>0;Z=w===0?1:0;N=(w>>>31)&1;if(c!==undefined)C=c&1;return w;};
 const wrd=d=>{d&=NM;return (M[d]|(M[d+1]<<8)|(M[d+2]<<16)|(M[d+3]<<24))>>>0;};
 function run(prog){let n=0;while(n<60000000){const I=prog[PC],op=I[0],arg=I[1];PC++;n++;const a=A;
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
const vm=makeVM(OS.MEM,OS.SP);
const W=OS.W,H=OS.H,FB=OS.FB;
const sc=document.getElementById("screen"),sx=sc.getContext("2d"),im=sx.createImageData(W,H);
const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
let keyq=[],ready=false;
function wr32(addr,v){vm.M[addr]=v&0xFF;vm.M[addr+1]=(v>>>8)&0xFF;vm.M[addr+2]=(v>>>16)&0xFF;vm.M[addr+3]=(v>>>24)&0xFF;}
const b2u=s=>{const b=atob(s),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;};
async function loadFont(){
 const comp=b2u(FONT.b64);
 const blob=new Uint8Array(await new Response(new Blob([comp]).stream().pipeThrough(new DecompressionStream("deflate"))).arrayBuffer());
 const cpb=b2u(FONT.cps_b64),n=FONT.n,M=vm.M,F16=OS.FONT16,WT=OS.WTAB;
 for(let i=0;i<n;i++){const cp=cpb[i*2]|(cpb[i*2+1]<<8),off=F16+cp*32,src=i*32;let wide=0;
   for(let b=0;b<32;b++){const v=blob[src+b];M[off+b]=v;if((b&1)&&v)wide=1;}
   M[WT+cp]=wide?16:8;}
 ready=true;document.getElementById("stat").textContent="font loaded ("+n.toLocaleString()+" glyphs in the CA's memory) — type away.";
}
/* keyboard: codepoint (8=backspace, 10=enter); mirror the IME box so paste & CJK input work */
const ime=document.getElementById("ime");let prev="";
function syncIME(){const cur=ime.value;let p=0;while(p<prev.length&&p<cur.length&&prev[p]===cur[p])p++;
 const remTail=[...prev.slice(p)].length;for(let i=0;i<remTail;i++)keyq.push(8);
 for(const ch of cur.slice(p))keyq.push(ch.codePointAt(0));prev=cur;}
ime.addEventListener("input",syncIME);   // textarea: Enter inserts \n -> codePointAt(0)=10 -> CA newline
const SAMPLES=[["English","Hello, world!"],["Francais","Voila, francais: e a u c"],["Ελληνικα","Ελληνικα: αβγδ"],
 ["Русский","Привет, мир!"],["日本語","こんにちは 日本語"],["中文","你好世界 中文"],["한국어","안녕하세요 한국어"]];
const sdiv=document.getElementById("samples");
for(const [lab,txt] of SAMPLES){const b=document.createElement("button");b.textContent=lab;
 b.onclick=()=>{ime.value=(ime.value?ime.value+"  ":"")+txt;ime.focus();syncIME();};sdiv.appendChild(b);}
function frame(){if(ready){if(keyq.length&&vm.M[OS.KEY]===0)wr32(OS.KEY,keyq.shift());vm.run(OS.prog);
  for(let i=0;i<W*H;i++){const v=vm.M[FB+i],p=PAL[v]||PAL[0];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}
  sx.putImageData(im,0,0);}requestAnimationFrame(frame);}
loadFont();requestAnimationFrame(frame);ime.focus();
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON).replace("__FONT__", FONTJSON)
open("dissemination/glider-lab25.html", "w").write(HTML)
print("wrote dissemination/glider-lab25.html", len(HTML), "bytes")
