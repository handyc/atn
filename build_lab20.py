#!/usr/bin/env python3
# build_lab20.py — glider-lab20.html: Alice & Bob over an encrypted line that can be CUT and RESTORED,
# with an optional zero-trust "mother server" they each sync to when able.
#
# Builds on lab19 (dual CA-OFFICE, encrypted input deltas). New in lab20:
#   PART A — cut/restore resilience (client-only):
#     * Each delta is sealed (ct + SHA-256 tag) and seq-numbered. When the line is DROPPED, Alice keeps
#       working locally and her sealed deltas QUEUE instead of vanishing. On RESTORE they replay to Bob
#       in seq order -> Bob catches up and reconverges (lossless). Bob applies the *next expected* seq
#       only, so keystrokes replay one-per-frame and a gap stalls Bob until it's filled (lossy demo).
#   PART B — zero-trust mother server (static-hosting friendly):
#     * The "server" only ever holds CIPHERTEXT (sealed deltas). Alice can PUSH her queue to it; Bob can
#       PULL (replays seq>bob). EXPORT downloads the sealed bundle (to upload to a static domain); FETCH
#       pulls a sealed bundle from a domain URL. The host never sees a key or any plaintext.
import json
OS = json.load(open("/tmp/caos3_export.json"))
OSJSON = json.dumps(OS, separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alice &amp; Bob — an encrypted line you can cut, restore, and sync through a mother server</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#5ed18a;--no:#ff7a7a;--pa:#c77dff;--sv:#7de0c7}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1060px;margin:0 auto;padding:14px}
 h1{font-size:20px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:13px}
 p{color:var(--mut);max-width:920px}
 .seedbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:6px 0;background:#161b22;border:1px solid #2a3340;border-radius:8px;padding:8px 10px}
 input[type=text]{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:6px 8px;font-family:ui-monospace,monospace;min-width:190px}
 .cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:6px}
 .card{background:#161b22;border:1px solid #2a3340;border-radius:10px;padding:10px}
 .card.alice{border-color:#5a4a2a}.card.bob{border-color:#2a4a5a}
 .card h2{margin:0 0 6px;font-size:15px}.alice h2{color:var(--a)}.bob h2{color:var(--b)}
 canvas.screen{image-rendering:pixelated;width:100%;border:2px solid #2a3340;border-radius:4px;background:#000;display:block}
 .alice canvas.screen{cursor:none}
 .line{background:#13101c;border:1px solid #3a2a55;border-radius:8px;padding:10px;margin-top:10px}
 .line h3{margin:0 0 4px;color:var(--pa);font-size:13px}
 .wire{font-family:ui-monospace,monospace;font-size:11px;color:var(--mut);word-break:break-all;min-height:16px}
 .stat{font-size:12px;color:var(--mut);margin-top:4px}.stat b{color:var(--a)} .ok{color:var(--ok)}.no{color:var(--no)}
 .grids{display:flex;gap:6px;align-items:center;margin-top:6px}
 canvas.ca{image-rendering:pixelated;width:48px;height:48px;border:1px solid #2a3340;border-radius:3px}
 .srv{background:#0c1a17;border:1px solid #265048;border-radius:8px;padding:10px;margin-top:10px}
 .srv h3{margin:0 0 4px;color:var(--sv);font-size:13px}
 .srv .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0}
 .store{font-family:ui-monospace,monospace;font-size:10.5px;color:var(--mut);max-height:64px;overflow:auto;background:#08110f;border:1px solid #1c3b35;border-radius:5px;padding:6px;word-break:break-all}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:10px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:6px 10px;cursor:pointer}
 button:disabled{opacity:.45;cursor:default}
 .pill{display:inline-block;font-size:11px;padding:1px 7px;border-radius:10px;border:1px solid #2a3340}
 .pill.up{color:var(--ok);border-color:#2c5a3e}.pill.down{color:var(--no);border-color:#5a2c2c}
</style></head><body><div class="wrap">
 <h1>Alice &amp; Bob <small>— an encrypted line you can <b>cut</b>, <b>restore</b>, and sync through a zero-trust <b>mother server</b></small></h1>
 <p>Both machines run the <b>identical CA-Office</b> locally. Drive <b>Alice</b>; only her <b>encrypted input deltas</b>
 (x, y, button, key = 4 bytes, sealed + seq-numbered) cross the wire. <b>Cut the line</b> and Alice keeps working — her
 deltas <b>queue</b> instead of vanishing; <b>restore</b> and they replay in order so Bob reconverges, pixel-for-pixel
 (lossless). Or offload the queue to a <b>mother server</b> that only ever stores ciphertext, and let Bob sync from it
 when able. <span id="selftest"></span></p>
 <div class="seedbar"><label>shared pact seed:</label><input type="text" id="seed" value="alice&lt;-&gt;bob pact 2026">
  <button id="rekey">re-derive &amp; reboot</button>
  <label><input type="checkbox" id="drop"> cut the line</label>
  <span class="pill up" id="linep">line up</span>
  <span class="stat">click Alice's desktop to focus (for typing)</span></div>
 <div class="cols">
   <div class="card alice"><h2>👩 Alice — you drive (mouse + keyboard)</h2><canvas class="screen" id="sa" width="256" height="192" tabindex="0"></canvas></div>
   <div class="card bob"><h2>🧑 Bob — mirror (replays deltas in seq order)</h2><canvas class="screen" id="sb" width="256" height="192"></canvas></div>
 </div>
 <div class="line"><h3>🔐 the classical line — only encrypted input deltas cross it</h3>
   <div class="wire" id="wire">idle</div>
   <div class="stat"><b id="sent">0</b> bytes sent · <b id="ndelta">0</b> deltas · vs <b>49,152 B/frame</b> for a full screen · desktops <b id="sync">—</b></div>
   <div class="stat">Alice holding (unsent): <b id="queue">0</b> deltas · Bob applied seq <b id="bobseq">—</b> of <b id="topseq">—</b> · pact gen <b id="gen">0</b></div>
   <div class="grids" id="grids"></div>
 </div>
 <div class="srv"><h3>🗄️ mother server — zero-trust store-and-forward (ciphertext only)</h3>
   <div class="row">
     <button id="push">👩 Alice → push queue to server</button>
     <button id="pull">🧑 Bob ← sync from server</button>
     <button id="export">⤓ export sealed bundle</button>
     <input type="text" id="srv" placeholder="https://your-domain/sync.json (static)">
     <button id="fetch">⤒ Bob fetch from domain</button>
   </div>
   <div class="stat"><b id="srvcount">0</b> sealed deltas stored · <b id="srvbytes">0</b> B (all ciphertext — the host holds no key)</div>
   <div class="store" id="store">empty</div>
 </div>
 <p class="note"><b>How it stays correct across a cut:</b> each delta is <code>[x,y,button,key] XOR tap(pact,ch,seq)</code> + a
 SHA-256 tag, keyed by its <b>seq</b>. Because the keystream is seq-derived, a delta can be replayed at any later time and
 still unseals — so a queued/stored delta is as good as a live one. Bob only applies <b>seq = lastApplied+1</b>, so order is
 preserved and a missing delta stalls him until it arrives (the lossy case → fetch it from the server). The mother server
 never sees plaintext or a key; on a static host it's just a sealed JSON bundle you upload and the other side fetches.
 Everything drawn is CA-1 machine code; mirrors <code>atn_spoeqi.py</code>.</p>
</div>
<script>
"use strict";
const OS=__OS__;
/* SHA-256 */
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
 const out=new Uint8Array(32),o=new DataView(out.buffer);[h0,h1,h2,h3,h4,h5,h6,h7].forEach((v,i)=>o.setUint32(i*4,v>>>0,false));return out;}
const enc=s=>new TextEncoder().encode(s);
const hex=(b,n)=>Array.from(b.slice(0,n||b.length)).map(x=>x.toString(16).padStart(2,'0')).join('');
const unhex=s=>{const a=new Uint8Array(s.length/2);for(let i=0;i<a.length;i++)a[i]=parseInt(s.substr(i*2,2),16);return a;};
/* pact */
const NCOMP=4,SIDE=48,DOMAIN=enc("spoeqi/tap/v1"),CH=1;
function prng(seed,label,n){let out=new Uint8Array(n),pos=0,ctr=0;const s=enc(seed),l=enc(label);
 while(pos<n){const b=new Uint8Array(s.length+l.length+4);b.set(s,0);b.set(l,s.length);new DataView(b.buffer).setUint32(s.length+l.length,ctr,true);
  const h=sha256(b);for(let i=0;i<32&&pos<n;i++)out[pos++]=h[i];ctr++;}return out;}
function buildPact(seed){const luts=[],init=[];for(let c=0;c<NCOMP;c++){const lb=prng(seed,"rule"+c,16384),lut=new Uint8Array(16384);for(let i=0;i<16384;i++)lut[i]=lb[i]&3;luts.push(lut);
  const gb=prng(seed,"grid"+c,SIDE*SIDE),g=new Uint8Array(SIDE*SIDE);for(let i=0;i<SIDE*SIDE;i++)g[i]=gb[i]&3;init.push(g);}return{luts,init,cache:{0:init.map(g=>g.slice())}};}
function castep(b,lut,W,H){const nb=new Uint8Array(W*H);for(let r=0;r<H;r++){const rm=(r-1+H)%H,rp=(r+1)%H,ev=(r%2===0);
  for(let c=0;c<W;c++){const cm=(c-1+W)%W,cp=(c+1)%W,s=b[r*W+c],N=b[rm*W+c],Sd=b[rp*W+c],Wc=b[r*W+cm],E=b[r*W+cp];
   let nw,ne,sw,se;if(ev){nw=b[rm*W+cm];ne=N;sw=b[rp*W+cm];se=Sd;}else{nw=N;ne=b[rm*W+cp];sw=Sd;se=b[rp*W+cp];}
   nb[r*W+c]=lut[(s<<12)|(nw<<10)|(ne<<8)|(E<<6)|(se<<4)|(sw<<2)|Wc];}}return nb;}
function gridsAt(p,gen){if(p.cache[gen])return p.cache[gen];let base=0;for(const k in p.cache)if(+k<=gen&&+k>base)base=+k;
 let g=p.cache[base].map(x=>x.slice());for(let t=0;t<gen-base;t++)g=g.map((gg,c)=>castep(gg,p.luts[c],SIDE,SIDE));p.cache[gen]=g.map(x=>x.slice());return p.cache[gen];}
function tap(p,comp,gen,n){const grid=gridsAt(p,gen)[comp];let out=new Uint8Array(n),pos=0,ctr=0;
 while(pos<n){const hdr=new Uint8Array(12),dv=new DataView(hdr.buffer);dv.setUint32(0,comp,true);dv.setUint32(4,gen,true);dv.setUint32(8,ctr,true);
  const buf=new Uint8Array(DOMAIN.length+12+grid.length);buf.set(DOMAIN,0);buf.set(hdr,DOMAIN.length);buf.set(grid,DOMAIN.length+12);
  const h=sha256(buf);for(let i=0;i<32&&pos<n;i++)out[pos++]=h[i];ctr++;}return out;}
/* CA-1 VM */
function makeVM(sp){const M=new Uint8Array(0x10000);let A=0,X=0,P=0,SP=sp||0x7FFF,PC=0,Z=1,C=0,N=0;
 const set=(v,c)=>{const v8=v&255;Z=v8===0?1:0;N=(v8>>7)&1;if(c!==undefined)C=c&1;return v8;};
 function run(prog){let n=0;while(n<8000000){const I=prog[PC],op=I[0],arg=I[1];PC++;n++;const a=A;
   switch(op){case"LDI":A=set(arg);break;case"LDA":A=set(M[arg]);break;case"STA":M[arg&0xFFFF]=a;break;
    case"LDAX":A=set(M[(arg+X)&0xFFFF]);break;case"STAX":M[(arg+X)&0xFFFF]=a;break;case"LDX":X=set(M[arg]);break;case"LXI":X=set(arg);break;
    case"TAX":X=set(a);break;case"TXA":A=set(X);break;case"INX":X=set(X+1);break;case"DEX":X=set(X-1);break;
    case"ADD":A=set(a+M[arg],(a+M[arg])>255?1:0);break;case"ADDI":A=set(a+arg,(a+arg)>255?1:0);break;
    case"SUB":A=set(a-M[arg],a>=M[arg]?1:0);break;case"SUBI":A=set(a-arg,a>=arg?1:0);break;
    case"AND":A=set(a&M[arg]);break;case"ANDI":A=set(a&arg);break;case"OR":A=set(a|M[arg]);break;case"XOR":A=set(a^M[arg]);break;
    case"INC":A=set(a+1);break;case"DEC":A=set(a-1);break;case"SHL":A=set(a<<1,(a>>7)&1);break;case"SHR":A=set(a>>1,a&1);break;
    case"CMP":{const d=a-M[arg];set(d,a>=M[arg]?1:0);break;}case"CMPI":{const d=a-arg;set(d,a>=arg?1:0);break;}
    case"JMP":PC=arg;break;case"JZ":if(Z)PC=arg;break;case"JNZ":if(!Z)PC=arg;break;case"JC":if(C)PC=arg;break;case"JNC":if(!C)PC=arg;break;case"JN":if(N)PC=arg;break;
    case"CALL":M[SP]=PC&255;M[SP-1]=(PC>>8)&255;SP-=2;PC=arg;break;case"RET":SP+=2;PC=(M[SP-1]<<8)|M[SP];break;
    case"PUSH":M[SP]=a;SP-=1;break;case"POP":SP+=1;A=set(M[SP]);break;
    case"LDP":P=arg&0xFFFF;break;case"ADDP":P=(P+arg)&0xFFFF;break;case"PLO":P=(P&0xFF00)|a;break;case"PHI":P=(P&0x00FF)|(a<<8);break;
    case"STPX":M[(P+X)&0xFFFF]=a;break;case"LDPX":A=set(M[(P+X)&0xFFFF]);break;
    case"FRAME":return n;case"NOP":break;case"HLT":return n;default:throw"op "+op;}}return n;}
 return {M,run};}
/* state — declared BEFORE any load-time call */
const $=id=>document.getElementById(id);
let pact=null,aliceVM=null,bobVM=null,mx=80,my=70,mb=0,pendKey=0,bobIn=[80,70,0],seq=0,sent=0,ndelta=0,lastMouse=null,raf=0;
let bobInbox=[],aliceQueue=[],server=[],srvBytes=0,bobSeq=-1;
const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
const ctxA=$("sa").getContext("2d"),ctxB=$("sb").getContext("2d");
const imA=ctxA.createImageData(OS.W,OS.H),imB=ctxB.createImageData(OS.W,OS.H);
function blit(ctx,im,vm){for(let i=0;i<OS.W*OS.H;i++){const v=vm.M[OS.FB+i],p=PAL[v]||PAL[0];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}ctx.putImageData(im,0,0);}
function bootVM(){const vm=makeVM(OS.SP);for(const k in OS.mem)vm.M[+k]=OS.mem[k];return vm;}
const gc=[];for(let c=0;c<NCOMP;c++){const cv=document.createElement("canvas");cv.className="ca";cv.width=SIDE;cv.height=SIDE;$("grids").appendChild(cv);gc.push(cv.getContext("2d"));}
const CPAL=[[10,12,20],[60,110,165],[255,210,127],[200,90,70]];
function drawGrids(){const gs=gridsAt(pact,seq);for(let c=0;c<NCOMP;c++){const im=gc[c].createImageData(SIDE,SIDE),g=gs[c];for(let i=0;i<SIDE*SIDE;i++){const p=CPAL[g[i]];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}gc[c].putImageData(im,0,0);}$("gen").textContent=seq;}
/* seal a delta from the current input, keyed by seq; unseal+apply to Bob, keyed by the delta's own seq */
function sealDelta(){const plain=new Uint8Array([mx,my,mb,pendKey]),ks=tap(pact,CH,seq,4),ct=new Uint8Array(4);for(let i=0;i<4;i++)ct[i]=plain[i]^ks[i];
 const tagsrc=new Uint8Array(8);tagsrc.set(plain,0);new DataView(tagsrc.buffer).setUint32(4,seq,true);const tag=sha256(tagsrc).slice(0,4);
 return {seq:seq,ct:ct,tag:tag};}
function applyToBob(d){const ks=tap(pact,CH,d.seq,4),pl=new Uint8Array(4);for(let i=0;i<4;i++)pl[i]=d.ct[i]^ks[i];
 const chk=new Uint8Array(8);chk.set(pl,0);new DataView(chk.buffer).setUint32(4,d.seq,true);
 if(hex(sha256(chk).slice(0,4))!==hex(d.tag))return 0;   // tampered/foreign -> reject
 bobIn=[pl[0],pl[1],pl[2]];bobSeq=d.seq;return pl[3];}
function renderServer(){$("srvcount").textContent=server.length;$("srvbytes").textContent=srvBytes;
 $("store").innerHTML=server.length?server.slice(-12).map(d=>`seq ${d.seq}: <span style="color:var(--sv)">${hex(d.ct)} ${hex(d.tag)}</span>`).join("<br>"):"empty";}
function stats(){$("queue").textContent=aliceQueue.length;$("bobseq").textContent=bobSeq<0?"—":bobSeq;$("topseq").textContent=seq>0?seq-1:"—";
 const up=!$("drop").checked;$("linep").textContent=up?"line up":"line CUT";$("linep").className="pill "+(up?"up":"down");}
const sa=$("sa");
function rel(e){return[Math.max(0,Math.min(OS.W-1,(e.offsetX/sa.clientWidth*OS.W)|0)),Math.max(0,Math.min(OS.H-1,(e.offsetY/sa.clientHeight*OS.H)|0))];}  // content-box -> exact
sa.onmousemove=e=>{[mx,my]=rel(e);};sa.onmousedown=e=>{[mx,my]=rel(e);mb=1;sa.focus();};window.addEventListener("mouseup",()=>mb=0);
sa.addEventListener("keydown",e=>{let code=0;if(e.key==="Backspace")code=0xFE;else if(e.key==="Enter")code=0xFD;else if(e.key===" ")code=(OS.GIDX[" "]||0);
 else if(e.key.length===1&&OS.GIDX[e.key]!==undefined)code=OS.GIDX[e.key];   // preserve case
 if(code){e.preventDefault();pendKey=code;}});
function syncCheck(){let same=true;for(let i=0;i<OS.W*OS.H;i++){if(aliceVM.M[OS.FB+i]!==bobVM.M[OS.FB+i]){same=false;break;}}
 $("sync").innerHTML=same?"<span class='ok'>in sync ✓</span>":"<span class='no'>diverged ✗ (Bob behind / line cut)</span>";}
function reset(){if(raf)cancelAnimationFrame(raf);pact=buildPact($("seed").value);aliceVM=bootVM();bobVM=bootVM();
 mx=80;my=70;mb=0;pendKey=0;bobIn=[80,70,0];seq=0;sent=0;ndelta=0;lastMouse=null;bobInbox=[];aliceQueue=[];server=[];srvBytes=0;bobSeq=-1;
 $("sent").textContent=0;$("ndelta").textContent=0;$("wire").textContent="idle";drawGrids();renderServer();stats();raf=requestAnimationFrame(tick);}
let fc=0;
function tick(){
 // ALICE: drive locally (always — a cut line never stops her own machine)
 aliceVM.M[OS.MX]=mx;aliceVM.M[OS.MY]=my;aliceVM.M[OS.MB]=mb;aliceVM.M[OS.KEY]=pendKey;aliceVM.run(OS.prog);blit(ctxA,imA,aliceVM);
 const mouseChanged=!lastMouse||mx!==lastMouse[0]||my!==lastMouse[1]||mb!==lastMouse[2];
 if(mouseChanged||pendKey!==0){
   const d=sealDelta();
   if($("drop").checked){aliceQueue.push(d);                                   // line cut -> hold locally
     $("wire").innerHTML=`✗ line cut — queued delta seq ${seq} locally (Alice keeps working)`;}
   else{bobInbox.push(d);                                                      // line up -> straight to Bob
     $("wire").innerHTML=`delta @ seq ${seq}: <span style="color:var(--pa)">${hex(d.ct)} ${hex(d.tag)}</span>${pendKey?" (incl. keystroke)":""} (${d.ct.length+d.tag.length+2} B)`;}
   sent+=d.ct.length+d.tag.length+2;ndelta++;lastMouse=[mx,my,mb];$("sent").textContent=sent;$("ndelta").textContent=ndelta;seq++;drawGrids();
 }
 // BOB: apply ONLY the next expected seq (ordered, lossless replay); drop already-applied stragglers
 let bobKey=0;
 bobInbox=bobInbox.filter(d=>d.seq>bobSeq);
 let ni=-1;for(let i=0;i<bobInbox.length;i++)if(bobInbox[i].seq===bobSeq+1){ni=i;break;}
 if(ni>=0){bobKey=applyToBob(bobInbox.splice(ni,1)[0]);}
 bobVM.M[OS.MX]=bobIn[0];bobVM.M[OS.MY]=bobIn[1];bobVM.M[OS.MB]=bobIn[2];bobVM.M[OS.KEY]=bobKey;bobVM.run(OS.prog);blit(ctxB,imB,bobVM);
 pendKey=0;
 if((++fc%12)===0){syncCheck();stats();}
 raf=requestAnimationFrame(tick);
}
/* line restore: replay Alice's locally-queued deltas straight to Bob, in order */
$("drop").onchange=function(){if(!this.checked&&aliceQueue.length){for(const d of aliceQueue)bobInbox.push(d);
   $("wire").innerHTML=`✓ line restored — replaying ${aliceQueue.length} queued deltas to Bob in seq order`;aliceQueue=[];}stats();};
/* mother server (zero-trust, ciphertext only) */
$("push").onclick=function(){for(const d of aliceQueue){server.push(d);srvBytes+=d.ct.length+d.tag.length+2;}aliceQueue=[];renderServer();stats();
 $("wire").innerHTML=`👩→🗄️ Alice pushed her queue to the mother server (sealed)`;};
$("pull").onclick=function(){let added=0;for(const d of server)if(d.seq>bobSeq&&!bobInbox.some(x=>x.seq===d.seq)){bobInbox.push(d);added++;}stats();
 $("wire").innerHTML=`🗄️→🧑 Bob syncing ${added} sealed deltas from the server (replays in order)`;};
$("export").onclick=function(){const bundle=JSON.stringify(server.map(d=>({seq:d.seq,ct:hex(d.ct),tag:hex(d.tag)})));
 const a=document.createElement("a");a.href="data:application/json,"+encodeURIComponent(bundle);a.download="sync.json";a.click();};
$("fetch").onclick=function(){const url=$("srv").value.trim();if(!url){$("wire").textContent="enter your static domain URL first";return;}
 fetch(url).then(r=>r.json()).then(arr=>{let added=0;for(const o of arr){const d={seq:o.seq,ct:unhex(o.ct),tag:unhex(o.tag)};
   if(!server.some(x=>x.seq===d.seq)){server.push(d);srvBytes+=d.ct.length+d.tag.length+2;}
   if(d.seq>bobSeq&&!bobInbox.some(x=>x.seq===d.seq)){bobInbox.push(d);added++;}}renderServer();stats();
   $("wire").innerHTML=`⤒ fetched a sealed bundle from your domain — Bob replaying ${added} deltas`;})
  .catch(err=>{$("wire").textContent="fetch failed: "+err+" (CORS or no file yet)";});};
$("selftest").textContent=hex(sha256(enc("abc")))==="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"?"":"  [SHA-256 self-test FAILED]";
$("rekey").onclick=reset;$("seed").onchange=reset;
reset();
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON)
open("dissemination/glider-lab20.html", "w").write(HTML)
print("wrote dissemination/glider-lab20.html", len(HTML), "bytes")
