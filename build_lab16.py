#!/usr/bin/env python3
# build_lab16.py — glider-lab16.html: send the WHOLE CA-OS DESKTOP through an Alice<->Bob pact.
# Same pact mechanism as lab15 (pure-JS SHA-256 + the hex CA + tap/seal/recover), but the payload
# is the entire CA-OS computer (program + memory). Bob recovers it from the seed alone and BOOTS
# the full interactive Windows-style desktop on his machine — draggable calculator window, mouse,
# the works — all running on the CA-1 VM. Self-contained.
import json
OS = json.load(open("/tmp/caos_export.json"))
OSJSON = json.dumps(OS, separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alice &amp; Bob — sending a whole desktop through a cellular-automaton pact</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#5ed18a;--no:#ff7a7a;--pa:#c77dff}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1060px;margin:0 auto;padding:16px}
 h1{font-size:21px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:13px}
 p{color:var(--mut);max-width:920px}
 .seedbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0;background:#161b22;border:1px solid #2a3340;border-radius:8px;padding:10px}
 input[type=text]{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:6px 8px;font-family:ui-monospace,monospace;min-width:220px}
 .shared{background:#13101c;border:1px solid #3a2a55;border-radius:8px;padding:8px 10px;margin:8px 0}
 .shared h3{margin:0 0 4px;color:var(--pa);font-size:13px}
 .grids{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
 canvas.ca{image-rendering:pixelated;border:1px solid #2a3340;border-radius:4px;width:72px;height:72px}
 .cols{display:grid;grid-template-columns:290px 1fr;gap:14px;margin-top:10px}
 .card{background:#161b22;border:1px solid #2a3340;border-radius:10px;padding:12px}
 .card.alice{border-color:#5a4a2a}.card.bob{border-color:#2a4a5a}
 .card h2{margin:0 0 6px;font-size:15px}.alice h2{color:var(--a)}.bob h2{color:var(--b)}
 button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:7px 11px;cursor:pointer;font-size:13px}
 button.go{background:var(--a);color:#1a1205;font-weight:700;border:none}button.go.bob{background:var(--b);color:#04121f}
 button:disabled{opacity:.4;cursor:default}
 .env{font-family:ui-monospace,monospace;font-size:10px;color:var(--mut);background:#0b0e13;border:1px solid #2a3340;border-radius:6px;padding:7px;word-break:break-all;min-height:48px;margin-top:6px}
 .stat{font-size:12px;color:var(--mut);margin-top:6px}.stat b{color:var(--a)} .ok{color:var(--ok)}.no{color:var(--no)}
 label{font-size:12px;color:var(--mut)} select{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:4px}
 #screen{image-rendering:pixelated;width:100%;max-width:680px;border:3px solid #2a3340;border-radius:4px;background:#000;cursor:none;display:none}
 .pill{display:inline-block;background:#0b0e13;border:1px solid #2a3340;border-radius:10px;padding:1px 8px;font-size:11px}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:14px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}
</style></head><body><div class="wrap">
 <h1>Alice &amp; Bob <small>— sending an entire desktop OS through a cellular-automaton pact</small></h1>
 <p>The machines aren't connected; they share only a <b>pact</b> (a seed). Both run the same
 cellular automaton, holding an identical secret tape. Alice seals the entire <b>CA-OS desktop</b>
 (a 2,222-instruction CA-1 computer) against it and sends only ciphertext. Bob, from the seed
 alone, recovers and <b>boots the live, interactive desktop</b>. <span class="pill" id="selftest">SHA-256…</span></p>
 <div class="seedbar"><label>shared pact seed:</label><input type="text" id="seed" value="alice&lt;-&gt;bob pact 2026">
  <button id="rekey">re-derive</button><label><input type="checkbox" id="wrongseed"> Bob uses the wrong seed</label></div>
 <div class="shared"><h3>▣ the pact's cellular automaton — identical on both machines, shared generation <b id="gen">0</b></h3>
  <div class="grids" id="grids"></div></div>
 <div class="cols">
   <div class="card alice"><h2>👩 Alice</h2>
     <div class="stat">computer to send: <b>CA-OS desktop</b> (<span id="proglen">?</span> instr · <span id="imgkb">?</span> KB image)</div>
     <div class="stat">pact coordinate — component <select id="comp"></select> · gen = clock</div>
     <button class="go" id="seal" style="margin-top:8px">🔒 seal &amp; send the desktop ▶</button>
     <button id="tamper" disabled>⚡ tamper</button>
     <div class="env" id="env">— nothing sent yet —</div>
     <div class="stat" id="alicestat"></div>
   </div>
   <div class="card bob"><h2>🧑 Bob</h2>
     <div class="stat" id="bobinfo">waiting for a sealed computer…</div>
     <button class="go bob" id="recv" disabled style="margin:8px 0">📥 receive &amp; boot the desktop</button>
     <div class="stat" id="bobstat"></div>
     <canvas id="screen" width="256" height="192" tabindex="0"></canvas>
     <div class="stat" id="bobhud"></div>
   </div>
 </div>
 <p class="note"><b>What crossed:</b> only the <b id="sentkb">0</b> KB of ciphertext + the coordinate. The key
 (the CA state) was never sent — Bob regenerated it from the seed. Tamper or wrong-seed → recovery fails: the
 desktop is bound to the shared cellular automaton. Once booted, the desktop runs on the CA-1 VM (~520k CA-1
 instructions on a full repaint, ~5k idle thanks to dirty-rect); move the mouse, drag the window, use the
 calculator. Mirrors <code>atn_spoeqi.py</code> (Python uses ChaCha20-Poly1305).</p>
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
document.getElementById("selftest").textContent=hex(sha256(enc("abc")))==="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"?"SHA-256 ✓":"SHA-256 ✗";
/* ── pact ── */
const NCOMP=4,SIDE=48,DOMAIN=enc("spoeqi/tap/v1");
function prng(seed,label,n){let out=new Uint8Array(n),pos=0,ctr=0;const s=enc(seed),l=enc(label);
 while(pos<n){const b=new Uint8Array(s.length+l.length+4);b.set(s,0);b.set(l,s.length);new DataView(b.buffer).setUint32(s.length+l.length,ctr,true);
  const h=sha256(b);for(let i=0;i<32&&pos<n;i++)out[pos++]=h[i];ctr++;}return out;}
function buildPact(seed){const luts=[],init=[];for(let c=0;c<NCOMP;c++){const lb=prng(seed,"rule"+c,16384),lut=new Uint8Array(16384);for(let i=0;i<16384;i++)lut[i]=lb[i]&3;luts.push(lut);
  const gb=prng(seed,"grid"+c,SIDE*SIDE),g=new Uint8Array(SIDE*SIDE);for(let i=0;i<SIDE*SIDE;i++)g[i]=gb[i]&3;init.push(g);}return{luts,init,cache:{0:init.map(g=>g.slice())}};}
function step(b,lut,W,H){const nb=new Uint8Array(W*H);for(let r=0;r<H;r++){const rm=(r-1+H)%H,rp=(r+1)%H,ev=(r%2===0);
  for(let c=0;c<W;c++){const cm=(c-1+W)%W,cp=(c+1)%W,s=b[r*W+c],N=b[rm*W+c],Sd=b[rp*W+c],Wc=b[r*W+cm],E=b[r*W+cp];
   let nw,ne,sw,se;if(ev){nw=b[rm*W+cm];ne=N;sw=b[rp*W+cm];se=Sd;}else{nw=N;ne=b[rm*W+cp];sw=Sd;se=b[rp*W+cp];}
   nb[r*W+c]=lut[(s<<12)|(nw<<10)|(ne<<8)|(E<<6)|(se<<4)|(sw<<2)|Wc];}}return nb;}
function gridsAt(p,gen){if(p.cache[gen])return p.cache[gen];let base=0;for(const k in p.cache)if(+k<=gen&&+k>base)base=+k;
 let g=p.cache[base].map(x=>x.slice());for(let t=0;t<gen-base;t++)g=g.map((gg,c)=>step(gg,p.luts[c],SIDE,SIDE));p.cache[gen]=g.map(x=>x.slice());return p.cache[gen];}
function tap(p,comp,gen,n){const grid=gridsAt(p,gen)[comp];let out=new Uint8Array(n),pos=0,ctr=0;
 while(pos<n){const hdr=new Uint8Array(12),dv=new DataView(hdr.buffer);dv.setUint32(0,comp,true);dv.setUint32(4,gen,true);dv.setUint32(8,ctr,true);
  const buf=new Uint8Array(DOMAIN.length+12+grid.length);buf.set(DOMAIN,0);buf.set(hdr,DOMAIN.length);buf.set(grid,DOMAIN.length+12);
  const h=sha256(buf);for(let i=0;i<32&&pos<n;i++)out[pos++]=h[i];ctr++;}return out;}
/* ── CA-1 VM (full ISA) ── */
function makeVM(sp){const M=new Uint8Array(0x10000);let A=0,X=0,P=0,SP=sp||0x7FFF,PC=0,Z=1,C=0,N=0;
 const set=(v,c)=>{const v8=v&255;Z=v8===0?1:0;N=(v8>>7)&1;if(c!==undefined)C=c&1;return v8;};
 function run(prog,maxi){let n=0;maxi=maxi||20000000;
  while(n<maxi){const I=prog[PC],op=I[0],arg=I[1];PC++;n++;const a=A;
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
/* ── UI ── */
const $=id=>document.getElementById(id);
let aliceP,bobP,gen=0,sent=null,osVM=null,osRAF=0,mx=80,my=70,mb=0;
function stopOS(){if(osRAF){cancelAnimationFrame(osRAF);osRAF=0;}osVM=null;}
function rederive(){const s=$("seed").value;aliceP=buildPact(s);bobP=buildPact($("wrongseed").checked?s+" (wrong)":s);
 gen=0;sent=null;$("env").textContent="— nothing sent yet —";$("alicestat").textContent="";$("recv").disabled=true;$("tamper").disabled=true;
 $("bobstat").textContent="";$("bobinfo").textContent="waiting for a sealed computer…";$("screen").style.display="none";$("sentkb").textContent="0";stopOS();}
const imageBytes=enc(JSON.stringify({prog:OS.prog,mem:OS.mem,SP:OS.SP}));
$("proglen").textContent=OS.prog.length;$("imgkb").textContent=(imageBytes.length/1024|0);
const cs=$("comp");for(let c=0;c<NCOMP;c++){const o=document.createElement("option");o.value=c;o.textContent=c;cs.appendChild(o);}
$("rekey").onclick=rederive;$("seed").onchange=rederive;$("wrongseed").onchange=rederive;rederive();
// shared CA viz
const gc=[];for(let c=0;c<NCOMP;c++){const cv=document.createElement("canvas");cv.className="ca";cv.width=SIDE;cv.height=SIDE;$("grids").appendChild(cv);gc.push(cv.getContext("2d"));}
const CPAL=[[10,12,20],[60,110,165],[255,210,127],[200,90,70]];
function drawGrids(){const gs=gridsAt(aliceP,gen);for(let c=0;c<NCOMP;c++){const im=gc[c].createImageData(SIDE,SIDE),g=gs[c];for(let i=0;i<SIDE*SIDE;i++){const p=CPAL[g[i]];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}gc[c].putImageData(im,0,0);}$("gen").textContent=gen;}
drawGrids();setInterval(()=>{gen++;drawGrids();},800);
// seal & send the desktop
$("seal").onclick=()=>{const comp=+cs.value,g=gen,img=imageBytes,ks=tap(aliceP,comp,g,img.length),ct=new Uint8Array(img.length);
 for(let i=0;i<img.length;i++)ct[i]=img[i]^ks[i];const tag=sha256(img).slice(0,8);
 sent={comp,gen:g,ct,tag,len:img.length};
 $("env").innerHTML=`<span style="color:var(--pa)">desktop sealed @ (component ${comp}, generation ${g}), ${(ct.length/1024|0)} KB</span><br>`+hex(ct,56)+" …";
 $("alicestat").innerHTML="sent the whole desktop, encrypted by the shared CA.";$("sentkb").textContent=(ct.length/1024|0);
 $("recv").disabled=false;$("tamper").disabled=false;
 $("bobinfo").innerHTML=`a sealed desktop arrived: <b>${(ct.length/1024|0)} KB</b> at (component ${comp}, gen ${g}). Key not included.`;};
$("tamper").onclick=()=>{if(!sent)return;sent.ct[10]^=0x55;$("env").innerHTML+="<br><span class='no'>⚡ tampered (byte 10)</span>";};
// receive & boot the desktop
$("recv").onclick=()=>{if(!sent)return;const ks=tap(bobP,sent.comp,sent.gen,sent.len),pt=new Uint8Array(sent.len);
 for(let i=0;i<sent.len;i++)pt[i]=sent.ct[i]^ks[i];
 if(hex(sha256(pt).slice(0,8))!==hex(sent.tag)){$("bobstat").innerHTML="<span class='no'>✗ recovery failed — wrong pact or tampered ciphertext.</span>";$("screen").style.display="none";stopOS();return;}
 let obj;try{obj=JSON.parse(new TextDecoder().decode(pt));}catch(e){$("bobstat").innerHTML="<span class='no'>✗ recovered garbage (wrong key)</span>";return;}
 $("bobstat").innerHTML="<span class='ok'>✓ recovered &amp; booting a byte-identical CA-OS desktop — use the mouse:</span>";
 bootOS(obj);};
function bootOS(obj){stopOS();const vm=makeVM(obj.SP);for(const k in obj.mem)vm.M[+k]=obj.mem[k];osVM=vm;
 const sc=$("screen");sc.style.display="";sc.width=OS.W;sc.height=OS.H;const sx=sc.getContext("2d"),im=sx.createImageData(OS.W,OS.H);
 const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
 function rel(e){const r=sc.getBoundingClientRect();return[Math.max(0,Math.min(OS.W-1,((e.clientX-r.left)/r.width*OS.W)|0)),Math.max(0,Math.min(OS.H-1,((e.clientY-r.top)/r.height*OS.H)|0))];}
 sc.onmousemove=e=>{[mx,my]=rel(e);};sc.onmousedown=e=>{[mx,my]=rel(e);mb=1;};window.addEventListener("mouseup",()=>mb=0);
 let last=performance.now(),fc=0;
 function frame(t){if(!osVM)return;vm.M[OS.MX]=mx;vm.M[OS.MY]=my;vm.M[OS.MB]=mb;const n=vm.run(OS.prog);
  for(let y=0;y<OS.H;y++)for(let x=0;x<OS.W;x++){const v=vm.M[OS.FB+y*OS.W+x],p=PAL[v]||PAL[0],i=(y*OS.W+x)*4;im.data[i]=p[0];im.data[i+1]=p[1];im.data[i+2]=p[2];im.data[i+3]=255;}
  sx.putImageData(im,0,0);fc++;if(t-last>=600){$("bobhud").textContent=`desktop live · ${(fc*1000/(t-last)).toFixed(0)} fps · ${n.toLocaleString()} CA-1 instr/frame`;fc=0;last=t;}
  osRAF=requestAnimationFrame(frame);}
 osRAF=requestAnimationFrame(frame);sc.focus();}
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON)
open("dissemination/glider-lab16.html", "w").write(HTML)
print("wrote dissemination/glider-lab16.html", len(HTML), "bytes")
