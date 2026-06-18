#!/usr/bin/env python3
# build_pactbundle_duo.py — the Alice & Bob DUAL-SCREEN pact, in one self-contained pactbundle-sized
# page.  Both panes are full CA-OS/2 desktops on the faithful 32-bit CA-2 VM, regenerated from the same
# embedded program + ASCII-subset antialiased font.  You drive ALICE; every input delta (x,y,button,key)
# is sealed with AES-256-GCM keyed by a hex-K4 cellular automaton grown from the shared seed, and the
# sealed bytes are handed to BOB in-page — he opens them in seq order and reconverges, pixel-for-pixel.
# CUT THE LINE and Alice keeps working; her deltas queue; RESTORE and they replay so Bob catches up.
# Same crypto/VM as build_pactbundle.py, just both ends shown at once (no socket — it's the visualisation).
import json, base64, zlib, struct
import caos_ca2 as o

m = o.make()
prog, _ = o.program()

# ---- compact "extended ASCII" font: printable ASCII + the Latin-1 Supplement (accented Latin — é ñ ü ç
#      …), plus the two typographic glyphs the chrome uses (— …).  No CJK, so the page stays small. ----
_f = json.load(open("unifont16.json"))
_blob = zlib.decompress(base64.b64decode(_f["b64"]))
_cps = struct.unpack("<%dH" % (_f["n"]), base64.b64decode(_f["cps_b64"]))
_w = base64.b64decode(_f["w_b64"])
_idx = {cp: i for i, cp in enumerate(_cps)}
SUBSET = list(range(0x20, 0x7F)) + list(range(0xA0, 0x100)) + [0x2014, 0x2026]   # ASCII + Latin-1 + — …
latin_glyphs = {}
for cp in SUBSET:
    if cp in _idx:
        i = _idx[cp]
        latin_glyphs[cp] = [base64.b64encode(_blob[i*128:i*128+128]).decode(), _w[i]]
FONTSUB = latin_glyphs

OS = dict(prog=[[op, (a if a is not None else 0)] for op, a in prog],
          mem={str(a): m.M[a] for a in range(0x10000) if m.M[a]},
          SP=0x7FFF, MEM=o.MEMSIZE, W=o.W, H=o.H, FB=o.FB, MX=o.MX, MY=o.MY, MB=o.MB, KEY=o.KEY, PAL=o.PAL,
          TBUF=o.TBUF, TLEN=o.TLEN, CELLS=o.CELLS, DIRTY=o.DIRTY, APP=o.APP,
          WINX=o.WINX, WINY=o.WINY, WW=o.WW, WH=o.WH, CSTRIDE=o.CSTRIDE, WTAB=o.WTAB, FONT16=o.FONT16,
          FONT=FONTSUB)
OSJSON = json.dumps(OS, separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alice &amp; Bob — the pact, both ends</title>
<style>
 *{box-sizing:border-box}
 body{margin:0;background:#0a0c10;color:#cfd8e3;font:14px system-ui,Segoe UI,Roboto,sans-serif;padding:14px;display:flex;flex-direction:column;align-items:center;gap:10px}
 h1{font-size:18px;font-weight:600;margin:2px 0;text-align:center}h1 small{color:#7c8896;font-weight:400;font-size:13px}
 .bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:center}
 .bar input[type=text]{background:#0b0e13;color:#cfd8e3;border:1px solid #2a3340;border-radius:6px;padding:5px 8px;font:13px ui-monospace,monospace;min-width:200px}
 .bar button{background:#222b36;color:#cfd8e3;border:1px solid #2a3340;border-radius:6px;padding:5px 10px;cursor:pointer}
 .bar button:hover{border-color:#ffd27f}
 .pill{font:12px ui-monospace,monospace;padding:3px 9px;border-radius:999px}
 .up{background:#10331c;color:#7ee0a0;border:1px solid #1c5c33}.down{background:#3a1414;color:#ff9a9a;border:1px solid #6a2222}
 .cols{display:flex;gap:14px;flex-wrap:wrap;justify-content:center}
 .pane{display:flex;flex-direction:column;gap:5px}
 .pane h2{font-size:13px;font-weight:600;margin:0;color:#bcc8d4}
 canvas.scr{width:480px;max-width:46vw;border:3px solid #2a3340;border-radius:5px;background:#000;cursor:none;display:block}
 .alice canvas.scr{border-color:#3a4a66}.bob canvas.scr{border-color:#3a5a4a}
 .line{width:100%;max-width:960px;background:#0c1016;border:1px solid #1c2430;border-radius:8px;padding:10px 12px}
 .line h3{margin:0 0 6px;font-size:13px;font-weight:600;color:#bcc8d4}
 .wire{font:11px ui-monospace,monospace;color:#7c8896;word-break:break-all;min-height:15px;border-left:2px solid #2a3340;padding-left:8px;margin-bottom:6px}
 .nums{display:flex;gap:18px;flex-wrap:wrap;font:12px ui-monospace,monospace;color:#9aa7b4}
 .nums b{color:#ffd27f}
 .note{color:#7c8896;font-size:12px;max-width:960px;text-align:center}
</style></head><body>
<h1>👩 Alice &amp; Bob 🧑 <small>— two CA-OS/2 desktops, one encrypted line you can cut</small></h1>
<div class="bar">
 <label style="font-size:13px;color:#9aa7b4">shared pact seed:</label>
 <input type="text" id="seed" value="alice&lt;-&gt;bob pact 2026">
 <button id="rekey">re-derive &amp; reboot</button>
 <label style="font-size:13px"><input type="checkbox" id="cut"> cut the line</label>
 <span class="pill up" id="linep">line up</span>
</div>
<div class="cols">
 <div class="pane alice"><h2>👩 Alice — you drive (click to focus, then mouse + type)</h2><canvas class="scr" id="sa" width="1024" height="768" tabindex="0"></canvas></div>
 <div class="pane bob"><h2>🧑 Bob — mirror (opens sealed deltas in seq order)</h2><canvas class="scr" id="sb" width="1024" height="768"></canvas></div>
</div>
<div class="line">
 <h3>🔐 the classical line — only AES-256-GCM-sealed input deltas cross it</h3>
 <div class="wire" id="wire">idle — drive Alice</div>
 <div class="nums">
  <span><b id="sent">0</b> bytes sent</span><span><b id="ndelta">0</b> deltas</span>
  <span>vs <b>196,608</b> B/frame for a full screen</span>
  <span>Alice queued: <b id="queue">0</b></span><span>Bob applied seq <b id="bobseq">—</b>/<b id="topseq">—</b></span>
  <span>desktops <b id="sync">—</b></span>
 </div>
</div>
<div class="note">No data crosses but ciphertext: both machines regenerate the identical CA-OS locally; the key at each step is <code>SHA-256(domain ‖ the hex-K4 CA state at gen = seq)</code>. Cut the line and Alice's deltas queue; restore and Bob reconverges pixel-for-pixel.</div>
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
const b2u=s=>{const b=atob(s),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;};
// stamp the compact font (cp -> 128 B antialiased glyph) into each CA's RAM
function bootVM(){const vm=makeVM(OS.MEM,OS.SP);for(const k in OS.mem)vm.M[+k]=OS.mem[k];
 for(const cp in OS.FONT){const e=OS.FONT[cp],g=b2u(e[0]),off=OS.FONT16+(+cp)*128;for(let i=0;i<128;i++)vm.M[off+i]=g[i];vm.M[OS.WTAB+ +cp]=e[1];}return vm;}
let vmA=bootVM(),vmB=bootVM();
const W=OS.W,H=OS.H,FB=OS.FB;
const sa=document.getElementById("sa"),sxA=sa.getContext("2d");
const sb=document.getElementById("sb"),sxB=sb.getContext("2d");
const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
// supersample each pane: 1x offscreen -> 2x canvas (nearest) -> CSS downscales smoothly = crisp at any size
function mkoff(){const c=document.createElement("canvas");c.width=W;c.height=H;return c;}
const ocA=mkoff(),octA=ocA.getContext("2d"),imA=octA.createImageData(W,H);
const ocB=mkoff(),octB=ocB.getContext("2d"),imB=octB.createImageData(W,H);
sxA.imageSmoothingEnabled=false;sxB.imageSmoothingEnabled=false;
function draw(vm,im,oct,oc,sx){const M=vm.M;for(let i=0;i<W*H;i++){const p=PAL[M[FB+i]]||PAL[0],o=i*4;im.data[o]=p[0];im.data[o+1]=p[1];im.data[o+2]=p[2];im.data[o+3]=255;}oct.putImageData(im,0,0);sx.drawImage(oc,0,0,W,H,0,0,W*2,H*2);}
function wr32(vm,a,v){vm.M[a]=v&0xFF;vm.M[a+1]=(v>>>8)&0xFF;vm.M[a+2]=(v>>>16)&0xFF;vm.M[a+3]=(v>>>24)&0xFF;}
/* ---- Alice's input ---- */
let mx=W>>1,my=H>>1,mb=0,keyq=[],lastM=null;
function rel(e){const r=sa.getBoundingClientRect(),cs=getComputedStyle(sa),bl=parseFloat(cs.borderLeftWidth)||0,bt=parseFloat(cs.borderTopWidth)||0;
 return[Math.max(0,Math.min(W-1,((e.clientX-r.left-bl)/sa.clientWidth*W)|0)),Math.max(0,Math.min(H-1,((e.clientY-r.top-bt)/sa.clientHeight*H)|0))];}
sa.addEventListener("mousemove",e=>{[mx,my]=rel(e);});
sa.addEventListener("mousedown",e=>{[mx,my]=rel(e);mb=1;sa.focus();});window.addEventListener("mouseup",()=>mb=0);
sa.addEventListener("keydown",e=>{let cp=-1;if(e.key==="Backspace")cp=8;else if(e.key==="Enter")cp=10;else if([...e.key].length===1)cp=e.key.codePointAt(0);
 if(cp>=0){e.preventDefault();keyq.push(cp);}});
/* ===== the pact: a hex-K4 CA grown from the shared seed is the AES-256-GCM key schedule ===== */
const enc=s=>new TextEncoder().encode(s);
const K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
const rotr=(x,n)=>((x>>>n)|(x<<(32-n)))>>>0;
function sha256(msg){let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
 const ml=msg.length,total=(((ml+8)>>6)+1)<<6,m=new Uint8Array(total);m.set(msg);m[ml]=0x80;const dv=new DataView(m.buffer),bit=ml*8;
 dv.setUint32(total-4,bit>>>0,false);dv.setUint32(total-8,Math.floor(bit/0x100000000)>>>0,false);const w=new Uint32Array(64);
 for(let off=0;off<total;off+=64){for(let i=0;i<16;i++)w[i]=dv.getUint32(off+i*4,false);
  for(let i=16;i<64;i++){const s0=(rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>>3))>>>0,s1=(rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>>10))>>>0;w[i]=(w[i-16]+s0+w[i-7]+s1)>>>0;}
  let a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,hh=h7;
  for(let i=0;i<64;i++){const S1=(rotr(e,6)^rotr(e,11)^rotr(e,25))>>>0,ch=((e&f)^((~e)&g))>>>0,t1=(hh+S1+ch+K[i]+w[i])>>>0,S0=(rotr(a,2)^rotr(a,13)^rotr(a,22))>>>0,maj=((a&b)^(a&c)^(b&c))>>>0,t2=(S0+maj)>>>0;hh=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}
  h0=(h0+a)>>>0;h1=(h1+b)>>>0;h2=(h2+c)>>>0;h3=(h3+d)>>>0;h4=(h4+e)>>>0;h5=(h5+f)>>>0;h6=(h6+g)>>>0;h7=(h7+hh)>>>0;}
 const o=new Uint8Array(32),ov=new DataView(o.buffer);[h0,h1,h2,h3,h4,h5,h6,h7].forEach((v,i)=>ov.setUint32(i*4,v>>>0,false));return o;}
const NCOMP=4,SIDE=48,DOMENV=enc("spoeqi/envelope/v1");
function prng(seed,label,n){let out=new Uint8Array(n),pos=0,ctr=0;const s=enc(seed),l=enc(label);
 while(pos<n){const b=new Uint8Array(s.length+l.length+4);b.set(s,0);b.set(l,s.length);new DataView(b.buffer).setUint32(s.length+l.length,ctr,true);
  const h=sha256(b);for(let i=0;i<32&&pos<n;i++)out[pos++]=h[i];ctr++;}return out;}
function buildPact(seed){const luts=[],init=[];for(let c=0;c<NCOMP;c++){const lb=prng(seed,"rule"+c,16384),lut=new Uint8Array(16384);for(let i=0;i<16384;i++)lut[i]=lb[i]&3;luts.push(lut);
  const gb=prng(seed,"grid"+c,SIDE*SIDE),g=new Uint8Array(SIDE*SIDE);for(let i=0;i<SIDE*SIDE;i++)g[i]=gb[i]&3;init.push(g);}return{luts,init,cache:{0:init.map(g=>g.slice())}};}
function castep(b,lut,Wd,Hd){const nb=new Uint8Array(Wd*Hd);for(let r=0;r<Hd;r++){const rm=(r-1+Hd)%Hd,rp=(r+1)%Hd,ev=(r%2===0);
  for(let c=0;c<Wd;c++){const cm=(c-1+Wd)%Wd,cp=(c+1)%Wd,s=b[r*Wd+c],Nn=b[rm*Wd+c],Sd=b[rp*Wd+c],Wc=b[r*Wd+cm],E=b[r*Wd+cp];
   let nw,ne,sw,se;if(ev){nw=b[rm*Wd+cm];ne=Nn;sw=b[rp*Wd+cm];se=Sd;}else{nw=Nn;ne=b[rm*Wd+cp];sw=Sd;se=b[rp*Wd+cp];}
   nb[r*Wd+c]=lut[(s<<12)|(nw<<10)|(ne<<8)|(E<<6)|(se<<4)|(sw<<2)|Wc];}}return nb;}
function gridsAt(p,gen){if(p.cache[gen])return p.cache[gen];let base=0;for(const k in p.cache)if(+k<=gen&&+k>base)base=+k;
 let g=p.cache[base].map(x=>x.slice());for(let t=0;t<gen-base;t++)g=g.map((gg,c)=>castep(gg,p.luts[c],SIDE,SIDE));p.cache[gen]=g.map(x=>x.slice());return p.cache[gen];}
function dkb(g){const grids=gridsAt(pact,g),st=new Uint8Array(8+NCOMP*SIDE*SIDE);new DataView(st.buffer).setUint32(0,g>>>0,true);let o=8;for(const gr of grids){st.set(gr,o);o+=gr.length;}const full=new Uint8Array(DOMENV.length+st.length);full.set(DOMENV,0);full.set(st,DOMENV.length);return sha256(full);}
const kc=new Map();
function gk(g){if(!kc.has(g))kc.set(g,crypto.subtle.importKey("raw",dkb(g),{name:"AES-GCM"},false,["encrypt","decrypt"]));return kc.get(g);}
const b64e=u=>btoa(String.fromCharCode.apply(0,u)),b64d=s=>{const b=atob(s),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;};
async function sealDelta(s,plain){const key=await gk(s),nonce=crypto.getRandomValues(new Uint8Array(12)),ct=new Uint8Array(await crypto.subtle.encrypt({name:"AES-GCM",iv:nonce},key,plain));
 const fr=new Uint8Array(4+12+ct.length);new DataView(fr.buffer).setUint32(0,s,true);fr.set(nonce,4);fr.set(ct,16);return b64e(fr);}
async function openDelta(b64){const fr=b64d(b64),s=new DataView(fr.buffer).getUint32(0,true),nonce=fr.slice(4,16),ct=fr.slice(16);
 try{const key=await gk(s),pl=new Uint8Array(await crypto.subtle.decrypt({name:"AES-GCM",iv:nonce},key,ct));return {s,pl};}catch(e){return null;}}
/* ===== the in-page wire: sealed frames flow Alice -> (line) -> Bob ===== */
let pact=buildPact(document.getElementById("seed").value);
let seq=0,bobSeq=-1,bobIn=[W>>1,H>>1,0],pendKeyB=0,lineUp=true;
let inbox=[],outbox=[],sentBytes=0,lastWire=null;
async function bobLoop(){
 if(pendKeyB===0){ inbox.sort((a,b)=>a.s-b.s); const i=inbox.findIndex(d=>d.s===bobSeq+1);
  if(i>=0){const o=await openDelta(inbox[i].b64);
   if(o){const pl=o.pl;bobIn=[pl[0]|pl[1]<<8,pl[2]|pl[3]<<8,pl[4]];const kb=pl[5]|pl[6]<<8;if(kb)pendKeyB=kb;bobSeq=o.s;}
   inbox.splice(i,1);} }
 setTimeout(bobLoop,25);}
bobLoop();
const cut=document.getElementById("cut"),linep=document.getElementById("linep");
cut.onchange=()=>{lineUp=!cut.checked;
 if(lineUp){outbox.sort((a,b)=>a.s-b.s);for(const fr of outbox)inbox.push(fr);outbox.length=0;}
 linep.textContent=lineUp?"line up":"line CUT";linep.className="pill "+(lineUp?"up":"down");};
document.getElementById("rekey").onclick=()=>{pact=buildPact(document.getElementById("seed").value);kc.clear();
 vmA=bootVM();vmB=bootVM();seq=0;bobSeq=-1;bobIn=[W>>1,H>>1,0];pendKeyB=0;inbox=[];outbox=[];sentBytes=0;lastWire=null;lastM=null;keyq=[];};
const $=id=>document.getElementById(id);
function hud(){
 $("sent").textContent=sentBytes.toLocaleString();$("ndelta").textContent=seq;
 $("queue").textContent=outbox.length;$("bobseq").textContent=bobSeq<0?"—":bobSeq;$("topseq").textContent=seq?seq-1:"—";
 const synced=lineUp&&bobSeq===seq-1&&!inbox.length&&!outbox.length&&pendKeyB===0;
 $("sync").textContent=seq===0?"—":(synced?"in sync ✓":"catching up…");
 if(lastWire)$("wire").textContent="🔐 "+lastWire.b64.slice(0,72)+"…  (seq "+lastWire.s+", "+lastWire.len+" B)";}
function frame(){
 // ALICE drives + seals each changed delta
 let k=(keyq.length&&vmA.M[OS.KEY]===0)?keyq[0]:0;
 const ch=!lastM||mx!==lastM[0]||my!==lastM[1]||mb!==lastM[2];
 if((ch||k)&&pact){const s=seq++;lastM=[mx,my,mb];
   const plain=new Uint8Array([mx&255,(mx>>8)&255,my&255,(my>>8)&255,mb,k&255,(k>>8)&255]);
   sealDelta(s,plain).then(b64=>{const fr={s,b64,len:b64d(b64).length};sentBytes+=fr.len;lastWire=fr;(lineUp?inbox:outbox).push(fr);});}
 wr32(vmA,OS.MX,mx);wr32(vmA,OS.MY,my);wr32(vmA,OS.MB,mb);if(k)wr32(vmA,OS.KEY,keyq.shift());
 vmA.run(OS.prog);
 // BOB mirrors from the opened deltas
 wr32(vmB,OS.MX,bobIn[0]);wr32(vmB,OS.MY,bobIn[1]);wr32(vmB,OS.MB,bobIn[2]);
 if(pendKeyB&&vmB.M[OS.KEY]===0){wr32(vmB,OS.KEY,pendKeyB);pendKeyB=0;}
 vmB.run(OS.prog);
 draw(vmA,imA,octA,ocA,sxA);draw(vmB,imB,octB,ocB,sxB);hud();
 requestAnimationFrame(frame);}
requestAnimationFrame(frame);
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON)
open("pactbundle_duo.html", "w").write(HTML)
gz = zlib.compress(HTML.encode(), 9)
open("pactbundle_duo.html.z", "wb").write(gz)
print("pactbundle_duo.html", len(HTML), "bytes ->  raw deflate", len(gz), "bytes;  glyphs:", len(FONTSUB))
