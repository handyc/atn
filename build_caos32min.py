#!/usr/bin/env python3
# build_caos32min.py — caos-32-min.html: the BARE CA-OS/2. Just the operating system and its apps
# (Writer/Sheet/Calc/Paint + save/load), nothing else — no prose, no HUD, no metrics, no demo tab.
# Same faithful 32-bit CA-2 VM and same OS machine code as lab22/lab24; this strips the page down so
# you can see how small "just the OS" is. The bytes are dominated by the embedded OS program itself.
import json
import caos_ca2 as o
from ca1sys import make_machine

m = o.make(); o.load_memory(m)
prog, _ = o.program()
OS = dict(
    prog=[[op, (arg if arg is not None else 0)] for op, arg in prog],
    mem={str(a): m.M[a] for a in range(0x10000) if m.M[a]},
    SP=0x7FFF, MEM=o.MEMSIZE, W=o.W, H=o.H, FB=o.FB, MX=o.MX, MY=o.MY, MB=o.MB, KEY=o.KEY, PAL=o.PAL,
    TBUF=o.TBUF, TLEN=o.TLEN, CELLS=o.CELLS, DIRTY=o.DIRTY, APP=o.APP,
    WINX=o.WINX, WINY=o.WINY, WW=o.WW, WH=o.WH, CSTRIDE=o.CSTRIDE, WTAB=o.WTAB, FONT16=o.FONT16)
FONT = json.load(open("unifont16.json"))
OSJSON = json.dumps(OS, separators=(",", ":")); FONTJSON = json.dumps(FONT, separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CA-OS/2</title>
<style>
 *{box-sizing:border-box}body{margin:0;background:#0a0c10;color:#cfd8e3;font:13px system-ui,Segoe UI,Roboto,sans-serif;
  display:flex;flex-direction:column;align-items:center;gap:8px;padding:12px}
 #screen{image-rendering:pixelated;width:768px;max-width:100%;border:3px solid #2a3340;border-radius:4px;background:#000;cursor:none;display:block}
 .tools{display:flex;gap:6px;flex-wrap:wrap;align-items:center;justify-content:center}
 .tools button{background:#222b36;color:#cfd8e3;border:1px solid #2a3340;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:12px}
 .tools button:hover{border-color:#ffd27f} .tools .grp{color:#9aa7b4;font-size:11px;margin-left:6px}
 #ime{width:768px;max-width:100%;background:#0b0e13;color:#cfd8e3;border:1px solid #2a3340;border-radius:6px;padding:6px 8px;font:14px system-ui;resize:vertical}
</style></head><body>
<canvas id="screen" width="512" height="384" tabindex="0"></canvas>
<div class="tools">
 <span class="grp">Writer</span><button id="wsave">Save .txt</button><button id="wload">Open .txt</button>
 <span class="grp">Sheet</span><button id="csave">Export CSV</button><button id="cload">Import CSV</button>
 <span class="grp">Paint</span><button id="psave">Save PNG</button><button id="pload">Open image</button>
 <input id="file" type="file" style="display:none">
</div>
<textarea id="ime" rows="2" placeholder="type here — any language (CJK via your IME, paste OK) — sent to the active app" autocomplete="off" autocapitalize="off" spellcheck="false"></textarea>
<div id="stat" style="color:#9aa7b4;font-size:12px">loading font…</div>
<script>
"use strict";
const OS=__OS__, FONT=__FONT__;
/* faithful 32-bit CA-2 VM (mirrors ca1sys make_machine("CA-2"): 32-bit regs/ALU, flat 1 MB) */
function makeVM(sz,sp){const M=new Uint8Array(sz),NM=sz-1;let A=0,X=0,SP=sp||0x7FFF,PC=0,Z=1,C=0,N=0;
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
const vm=makeVM(OS.MEM,OS.SP);for(const k in OS.mem)vm.M[+k]=OS.mem[k];
const W=OS.W,H=OS.H,FB=OS.FB;
const sc=document.getElementById("screen"),sx=sc.getContext("2d"),im=sx.createImageData(W,H);
const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
let mx=W>>1,my=H>>1,mb=0,keyq=[],ready=false;
function rel(e){const r=sc.getBoundingClientRect(),cs=getComputedStyle(sc),
  bl=parseFloat(cs.borderLeftWidth)||0,bt=parseFloat(cs.borderTopWidth)||0;
  const x=(e.clientX-r.left-bl)/sc.clientWidth*W,y=(e.clientY-r.top-bt)/sc.clientHeight*H;
  return[Math.max(0,Math.min(W-1,x|0)),Math.max(0,Math.min(H-1,y|0))];}
function wr32(addr,v){vm.M[addr]=v&0xFF;vm.M[addr+1]=(v>>>8)&0xFF;vm.M[addr+2]=(v>>>16)&0xFF;vm.M[addr+3]=(v>>>24)&0xFF;}
sc.addEventListener("mousemove",e=>{[mx,my]=rel(e);});
sc.addEventListener("mousedown",e=>{[mx,my]=rel(e);mb=1;sc.focus();});window.addEventListener("mouseup",()=>mb=0);
function kdcp(e){let cp=-1;if(e.key==="Backspace")cp=8;else if(e.key==="Enter")cp=10;else if([...e.key].length===1)cp=e.key.codePointAt(0);
 if(cp>=0){e.preventDefault();keyq.push(cp);}}                       // KEY = Unicode codepoint (8=BS,10=NL)
sc.addEventListener("keydown",kdcp);
const ime=document.getElementById("ime");let composing=false;       // IME/paste box -> forward codepoints to the active app
function flush(){for(const ch of ime.value)keyq.push(ch.codePointAt(0));ime.value="";}
ime.addEventListener("compositionstart",()=>composing=true);
ime.addEventListener("compositionend",()=>{composing=false;flush();});
ime.addEventListener("input",()=>{if(!composing)flush();});
ime.addEventListener("keydown",e=>{if(e.key==="Backspace"){e.preventDefault();keyq.push(8);}else if(e.key==="Enter"){e.preventDefault();keyq.push(10);}});
/* inflate the 16x16 GNU-Unifont into the CA's RAM (FONT16 direct table + WTAB widths) */
const b2u=x=>{const b=atob(x),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;};
async function loadFont(){const blob=new Uint8Array(await new Response(new Blob([b2u(FONT.b64)]).stream().pipeThrough(new DecompressionStream("deflate"))).arrayBuffer());
 const cpb=b2u(FONT.cps_b64),wv=b2u(FONT.w_b64),M=vm.M,F=OS.FONT16,WT=OS.WTAB;for(let i=0;i<FONT.n;i++){const cp=cpb[i*2]|(cpb[i*2+1]<<8),off=F+cp*64;
  for(let b=0;b<64;b++)M[off+b]=blob[i*64+b];M[WT+cp]=wv[i];}
 ready=true;document.getElementById("stat").textContent="font loaded ("+FONT.n.toLocaleString()+" Unicode glyphs in the CA) — Writer is multilingual.";}
/* ---- save / load: poke the CA-2 memory directly; the OS just redraws ---- */
function rd32(a){return (vm.M[a]|(vm.M[a+1]<<8)|(vm.M[a+2]<<16)|(vm.M[a+3]<<24))>>>0;}
function dl(name,blob){const u=URL.createObjectURL(blob),a=document.createElement("a");a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),800);}
function pick(accept,cb){const f=document.getElementById("file");f.value="";f.accept=accept;f.onchange=()=>{if(f.files[0])cb(f.files[0]);};f.click();}
function nearest(r,g,b){let bi=0,bd=1e9;for(let i=0;i<PAL.length;i++){const p=PAL[i],dr=p[0]-r,dg=p[1]-g,db=p[2]-b,dd=dr*dr+dg*dg+db*db;if(dd<bd){bd=dd;bi=i;}}return bi;}
document.getElementById("wsave").onclick=()=>{const n=rd32(OS.TLEN);let s="";
 for(let i=0;i<n;i++){const cp=vm.M[OS.TBUF+i*2]|(vm.M[OS.TBUF+i*2+1]<<8);s+=String.fromCodePoint(cp);}
 dl("document.txt",new Blob([s],{type:"text/plain"}));};
document.getElementById("wload").onclick=()=>pick(".txt,text/plain",f=>{const r=new FileReader();
 r.onload=()=>{let i=0;for(const ch of r.result){if(i>=1800)break;if(ch==="\r")continue;
   const cp=ch.codePointAt(0);vm.M[OS.TBUF+i*2]=cp&0xFF;vm.M[OS.TBUF+i*2+1]=(cp>>8)&0xFF;i++;}
  wr32(OS.TLEN,i);wr32(OS.APP,3);wr32(OS.DIRTY,1);};r.readAsText(f);});
document.getElementById("csave").onclick=()=>{const rows=[];for(let r=0;r<4;r++){const c=[];for(let col=0;col<3;col++)c.push(rd32(OS.CELLS+(r*3+col)*OS.CSTRIDE));rows.push(c.join(","));}
 dl("sheet.csv",new Blob([rows.join("\n")+"\n"],{type:"text/csv"}));};
document.getElementById("cload").onclick=()=>pick(".csv,text/csv",f=>{const r=new FileReader();
 r.onload=()=>{const cells=[];r.result.split(/\r?\n/).forEach(L=>{if(!L.trim())return;L.split(",").forEach(v=>cells.push((parseInt(v.trim(),10)||0)>>>0));});
  for(let i=0;i<12;i++)wr32(OS.CELLS+i*OS.CSTRIDE,cells[i]||0);wr32(OS.APP,4);wr32(OS.DIRTY,1);};r.readAsText(f);});
const CXo=OS.WINX+10,CYo=OS.WINY+42,CWp=OS.WW-20,CHp=OS.WH-54;
document.getElementById("psave").onclick=()=>{const cv=document.createElement("canvas");cv.width=CWp;cv.height=CHp;
 const g2=cv.getContext("2d"),id=g2.createImageData(CWp,CHp);
 for(let y=0;y<CHp;y++)for(let x=0;x<CWp;x++){const v=vm.M[FB+(CYo+y)*W+(CXo+x)],p=PAL[v]||PAL[0],o=(y*CWp+x)*4;id.data[o]=p[0];id.data[o+1]=p[1];id.data[o+2]=p[2];id.data[o+3]=255;}
 g2.putImageData(id,0,0);cv.toBlob(b=>dl("paint.png",b));};
document.getElementById("pload").onclick=()=>pick("image/*",f=>{const img=new Image();img.onload=()=>{
  const cv=document.createElement("canvas");cv.width=CWp;cv.height=CHp;const g2=cv.getContext("2d");
  g2.fillStyle="#fff";g2.fillRect(0,0,CWp,CHp);g2.drawImage(img,0,0,CWp,CHp);
  const d=g2.getImageData(0,0,CWp,CHp).data;
  wr32(OS.APP,1);wr32(OS.DIRTY,1);
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    for(let y=0;y<CHp;y++)for(let x=0;x<CWp;x++){const o=(y*CWp+x)*4;vm.M[FB+(CYo+y)*W+(CXo+x)]=nearest(d[o],d[o+1],d[o+2]);}}));
  URL.revokeObjectURL(img.src);};img.src=URL.createObjectURL(f);});
function frame(){if(!ready){requestAnimationFrame(frame);return;}
 wr32(OS.MX,mx);wr32(OS.MY,my);wr32(OS.MB,mb);
 if(keyq.length&&vm.M[OS.KEY]===0)wr32(OS.KEY,keyq.shift());
 vm.run(OS.prog);
 for(let i=0;i<W*H;i++){const v=vm.M[FB+i],p=PAL[v]||PAL[0];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}
 sx.putImageData(im,0,0);requestAnimationFrame(frame);}
loadFont();requestAnimationFrame(frame);
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON).replace("__FONT__", FONTJSON)
open("dissemination/caos-32-min.html", "w").write(HTML)
print("wrote dissemination/caos-32-min.html", len(HTML), "bytes")
