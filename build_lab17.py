#!/usr/bin/env python3
# build_lab17.py — glider-lab17.html: Alice & Bob INTERACT with one shared desktop by sending only
# tiny ENCRYPTED INPUT DELTAS over a classical line. Both run the identical CA-OS locally (sent once
# via the pact); thereafter the wire carries only Alice's mouse deltas (x,y,button), sealed against
# the pact's CA keystream at a fresh per-delta coordinate. Because CA-1 is deterministic, identical
# machine + identical inputs => pixel-identical desktops. The full screen (49,152 B/frame) never
# crosses; ~9 encrypted bytes per input change do. Self-contained (pure-JS SHA-256 + hex CA + VM).
import json
OS = json.load(open("/tmp/caos_export.json"))
OSJSON = json.dumps(OS, separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alice &amp; Bob — steering one desktop over an encrypted classical line</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#5ed18a;--no:#ff7a7a;--pa:#c77dff}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1060px;margin:0 auto;padding:16px}
 h1{font-size:21px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:13px}
 p{color:var(--mut);max-width:920px}
 .seedbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0;background:#161b22;border:1px solid #2a3340;border-radius:8px;padding:8px 10px}
 input[type=text]{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:6px 8px;font-family:ui-monospace,monospace;min-width:200px}
 .cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:8px}
 .card{background:#161b22;border:1px solid #2a3340;border-radius:10px;padding:10px}
 .card.alice{border-color:#5a4a2a}.card.bob{border-color:#2a4a5a}
 .card h2{margin:0 0 6px;font-size:15px}.alice h2{color:var(--a)}.bob h2{color:var(--b)}
 canvas.screen{image-rendering:pixelated;width:100%;border:2px solid #2a3340;border-radius:4px;background:#000;display:block}
 .alice canvas.screen{cursor:none}.bob canvas.screen{cursor:default}
 .line{background:#13101c;border:1px solid #3a2a55;border-radius:8px;padding:10px;margin-top:12px}
 .line h3{margin:0 0 4px;color:var(--pa);font-size:13px}
 .wire{font-family:ui-monospace,monospace;font-size:11px;color:var(--mut);word-break:break-all;min-height:18px}
 .stat{font-size:12px;color:var(--mut);margin-top:4px}.stat b{color:var(--a)} .ok{color:var(--ok)}.no{color:var(--no)}
 .grids{display:flex;gap:6px;align-items:center;margin-top:6px}
 canvas.ca{image-rendering:pixelated;width:54px;height:54px;border:1px solid #2a3340;border-radius:3px}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:12px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)} button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:6px 10px;cursor:pointer}
</style></head><body><div class="wrap">
 <h1>Alice &amp; Bob <small>— steering one shared desktop over an encrypted classical line</small></h1>
 <p>Both machines run the <b>identical</b> CA-OS (sent once through the pact). Now drive
 <b>Alice's</b> desktop with your mouse — and only her tiny <b>encrypted input deltas</b> (x, y, button)
 cross the wire. Bob applies them to his own copy; because the computer is deterministic, his desktop
 stays <b>pixel-identical</b>. The 49,152-byte screen never travels — only ~9 encrypted bytes per move do.
 <span id="selftest"></span></p>
 <div class="seedbar"><label>shared pact seed:</label><input type="text" id="seed" value="alice&lt;-&gt;bob pact 2026">
  <button id="rekey">re-derive &amp; reboot both</button><label><input type="checkbox" id="drop"> drop the line (stop sending)</label></div>
 <div class="cols">
   <div class="card alice"><h2>👩 Alice — you drive</h2><canvas class="screen" id="sa" width="256" height="192" tabindex="0"></canvas>
     <div class="stat" id="ahud">move the mouse over this desktop</div></div>
   <div class="card bob"><h2>🧑 Bob — mirror (no mouse)</h2><canvas class="screen" id="sb" width="256" height="192"></canvas>
     <div class="stat" id="bhud">applies Alice's encrypted deltas</div></div>
 </div>
 <div class="line"><h3>🔐 the classical line — only encrypted relative changes cross it</h3>
   <div class="wire" id="wire">idle — nothing to send</div>
   <div class="stat">this session: <b id="sent">0</b> bytes sent · <b id="ndelta">0</b> deltas · vs <b>49,152 B/frame</b> for a full screen
     · desktops <b id="sync">—</b></div>
   <div class="grids" id="grids"></div>
   <div class="stat">pact CA (the shared key tape) advances one generation per delta — shown above; gen <b id="gen">0</b></div>
 </div>
 <p class="note"><b>How it works:</b> each input change is sealed as <code>delta XOR tap(pact, channel, seq)</code> with a
 fresh keystream per delta (no reuse) + a SHA-256 tag. Bob unseals with the same pact and applies it. Tick "drop the
 line" and Bob freezes (no deltas) while Alice keeps moving — proof the wire really carries the steering. The key
 (the CA state) is never sent; mirrors <code>atn_spoeqi.py</code>. (Pure-JS SHA-256 + the hex CA + two CA-1 VMs.)</p>
</div>
<script>
"use strict";
const OS=__OS__;
/* ── SHA-256 (verified == hashlib) ── */
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
/* ── pact ── */
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
/* ── CA-1 VM ── */
function makeVM(sp){const M=new Uint8Array(0x10000);let A=0,X=0,P=0,SP=sp||0x7FFF,PC=0,Z=1,C=0,N=0;
 const set=(v,c)=>{const v8=v&255;Z=v8===0?1:0;N=(v8>>7)&1;if(c!==undefined)C=c&1;return v8;};
 function run(prog){let n=0;while(n<20000000){const I=prog[PC],op=I[0],arg=I[1];PC++;n++;const a=A;
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
/* ── state (declare BEFORE any load-time call) ── */
const $=id=>document.getElementById(id);
let pact=null, aliceVM=null, bobVM=null, mx=80,my=70,mb=0, bobIn=[80,70,0], seq=0, sent=0, ndelta=0, lastIn=null, raf=0;
const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
const ctxA=$("sa").getContext("2d"), ctxB=$("sb").getContext("2d");
const imA=ctxA.createImageData(OS.W,OS.H), imB=ctxB.createImageData(OS.W,OS.H);
function blit(ctx,im,vm){for(let i=0;i<OS.W*OS.H;i++){const v=vm.M[OS.FB+i],p=PAL[v]||PAL[0];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}ctx.putImageData(im,0,0);}
function bootVM(){const vm=makeVM(OS.SP);for(const k in OS.mem)vm.M[+k]=OS.mem[k];return vm;}
// shared CA viz
const gc=[];for(let c=0;c<NCOMP;c++){const cv=document.createElement("canvas");cv.className="ca";cv.width=SIDE;cv.height=SIDE;$("grids").appendChild(cv);gc.push(cv.getContext("2d"));}
const CPAL=[[10,12,20],[60,110,165],[255,210,127],[200,90,70]];
function drawGrids(){const gs=gridsAt(pact,seq);for(let c=0;c<NCOMP;c++){const im=gc[c].createImageData(SIDE,SIDE),g=gs[c];for(let i=0;i<SIDE*SIDE;i++){const p=CPAL[g[i]];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}gc[c].putImageData(im,0,0);}$("gen").textContent=seq;}
function reset(){if(raf)cancelAnimationFrame(raf);const s=$("seed").value;pact=buildPact(s);aliceVM=bootVM();bobVM=bootVM();
 mx=80;my=70;mb=0;bobIn=[80,70,0];seq=0;sent=0;ndelta=0;lastIn=null;$("sent").textContent=0;$("ndelta").textContent=0;$("wire").textContent="idle — nothing to send";drawGrids();raf=requestAnimationFrame(tick);}
// mouse on Alice's canvas
const sa=$("sa");
function rel(e){const r=sa.getBoundingClientRect();return[Math.max(0,Math.min(OS.W-1,((e.clientX-r.left)/r.width*OS.W)|0)),Math.max(0,Math.min(OS.H-1,((e.clientY-r.top)/r.height*OS.H)|0))];}
sa.onmousemove=e=>{[mx,my]=rel(e);};sa.onmousedown=e=>{[mx,my]=rel(e);mb=1;};window.addEventListener("mouseup",()=>mb=0);
function syncCheck(){let same=true;for(let i=0;i<OS.W*OS.H;i++){if(aliceVM.M[OS.FB+i]!==bobVM.M[OS.FB+i]){same=false;break;}}
 $("sync").innerHTML=same?"<span class='ok'>in sync ✓</span>":"<span class='no'>diverged ✗</span>";}
let fc=0;
function tick(){
 aliceVM.M[OS.MX]=mx;aliceVM.M[OS.MY]=my;aliceVM.M[OS.MB]=mb;aliceVM.run(OS.prog);blit(ctxA,imA,aliceVM);
 const cur=[mx,my,mb], changed=!lastIn||cur[0]!==lastIn[0]||cur[1]!==lastIn[1]||cur[2]!==lastIn[2];
 if(changed && !$("drop").checked){
   const plain=new Uint8Array(cur), ks=tap(pact,CH,seq,3), ct=new Uint8Array(3);for(let i=0;i<3;i++)ct[i]=plain[i]^ks[i];
   const tagsrc=new Uint8Array(7);tagsrc.set(plain,0);new DataView(tagsrc.buffer).setUint32(3,seq,true);const tag=sha256(tagsrc).slice(0,4);
   // ── Bob receives & decrypts ──
   const ks2=tap(pact,CH,seq,3),pl=new Uint8Array(3);for(let i=0;i<3;i++)pl[i]=ct[i]^ks2[i];
   const chk=new Uint8Array(7);chk.set(pl,0);new DataView(chk.buffer).setUint32(3,seq,true);
   if(hex(sha256(chk).slice(0,4))===hex(tag))bobIn=[pl[0],pl[1],pl[2]];
   sent+=ct.length+tag.length+2;ndelta++;lastIn=cur;
   $("wire").innerHTML=`delta @ seq ${seq}: <span style="color:var(--pa)">${hex(ct)} ${hex(tag)}</span> (${ct.length+tag.length+2} bytes)`;
   $("sent").textContent=sent;$("ndelta").textContent=ndelta;seq++;drawGrids();
 }
 bobVM.M[OS.MX]=bobIn[0];bobVM.M[OS.MY]=bobIn[1];bobVM.M[OS.MB]=bobIn[2];bobVM.run(OS.prog);blit(ctxB,imB,bobVM);
 if((++fc%20)===0)syncCheck();
 raf=requestAnimationFrame(tick);
}
$("selftest").textContent=hex(sha256(enc("abc")))==="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"?"":"  [SHA-256 self-test FAILED]";
$("rekey").onclick=reset;$("seed").onchange=reset;
reset();
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON)
open("dissemination/glider-lab17.html", "w").write(HTML)
print("wrote dissemination/glider-lab17.html", len(HTML), "bytes")
