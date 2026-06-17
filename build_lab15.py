#!/usr/bin/env python3
# build_lab15.py — glider-lab15.html: the "Alice <-> Bob" spoeqi pact lab. Two machines share
# ONLY a seed (no connection). The pact's cellular automaton runs identically on both. Alice
# seals the CA-1 calculator computer against the shared CA keystream and "sends" the ciphertext;
# Bob, from the seed alone, recovers and BOOTS the identical computer (interactive). The shared
# CA is shown evolving in lockstep. Self-contained: pure-JS SHA-256 + the hex CA + the CA-1 VM.
import json
E = json.load(open("/tmp/calc_export.json"))
EJSON = json.dumps(E, separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alice &amp; Bob — sending a computer through a cellular-automaton pact</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#5ed18a;--no:#ff7a7a;--pa:#c77dff}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1040px;margin:0 auto;padding:18px}
 h1{font-size:22px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:14px}
 p{color:var(--mut);max-width:900px}
 .seedbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:10px 0;background:#161b22;border:1px solid #2a3340;border-radius:8px;padding:10px}
 input[type=text]{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:6px 8px;font-family:ui-monospace,monospace;min-width:240px}
 .shared{background:#13101c;border:1px solid #3a2a55;border-radius:8px;padding:10px;margin:10px 0}
 .shared h3{margin:0 0 4px;color:var(--pa);font-size:14px}
 .grids{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
 canvas.ca{image-rendering:pixelated;border:1px solid #2a3340;border-radius:4px;width:96px;height:96px}
 .cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:10px}
 .card{background:#161b22;border:1px solid #2a3340;border-radius:10px;padding:12px}
 .card.alice{border-color:#5a4a2a}.card.bob{border-color:#2a4a5a}
 .card h2{margin:0 0 4px;font-size:16px}.alice h2{color:var(--a)}.bob h2{color:var(--b)}
 button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:7px 12px;cursor:pointer;font-size:13px}
 button.go{background:var(--a);color:#1a1205;font-weight:700;border:none}button.go.bob{background:var(--b);color:#04121f}
 button:disabled{opacity:.4;cursor:default}
 .env{font-family:ui-monospace,monospace;font-size:11px;color:var(--mut);background:#0b0e13;border:1px solid #2a3340;border-radius:6px;padding:8px;word-break:break-all;min-height:54px;margin-top:6px}
 .stat{font-size:12px;color:var(--mut);margin-top:6px}.stat b{color:var(--a)} .ok{color:var(--ok)}.no{color:var(--no)}
 .calc{margin-top:8px} .calc .disp{text-align:right;font:18px ui-monospace,monospace;background:#fff;color:#000;border-radius:4px;padding:4px 8px;margin-bottom:6px}
 .calc .grid{display:grid;grid-template-columns:repeat(4,46px);gap:5px}.calc .grid button{height:34px}
 label{font-size:12px;color:var(--mut)} select{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:4px}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:14px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)} .pill{display:inline-block;background:#0b0e13;border:1px solid #2a3340;border-radius:10px;padding:1px 8px;font-size:11px}
</style></head><body><div class="wrap">
 <h1>Alice &amp; Bob <small>— sending an entire computer through a cellular-automaton pact</small></h1>
 <p>Alice and Bob's machines are <b>not connected</b>. They share only a <b>pact</b> — a seed.
 From it, both run the <b>same cellular automaton</b>, so they hold an identical, secret, evolving
 byte-tape. Alice seals the CA-1 <b>calculator computer</b> against that tape and sends only the
 ciphertext; Bob, from the seed alone, <b>recovers and boots the identical computer</b>. The key
 (the CA state) is never transmitted. <span class="pill" id="selftest">SHA-256 self-test…</span></p>

 <div class="seedbar">
   <label>shared pact seed:</label><input type="text" id="seed" value="alice&lt;-&gt;bob pact 2026">
   <button id="rekey">re-derive pact</button>
   <label><input type="checkbox" id="wrongseed"> Bob uses the wrong seed</label>
 </div>

 <div class="shared"><h3>▣ the pact's cellular automaton — identical on both machines, nothing connecting them</h3>
   <div class="grids" id="grids"></div>
   <div class="stat">shared generation (clock): <b id="gen">0</b> · these grids are byte-identical on Alice's and Bob's machines</div>
 </div>

 <div class="cols">
   <div class="card alice"><h2>👩 Alice</h2>
     <div class="stat">computer to send: <b>CALCULATOR</b> (<span id="proglen">?</span>-instruction CA-1 program)</div>
     <div class="stat">place at pact coordinate — component <select id="comp"></select> · generation = current clock</div>
     <button class="go" id="seal" style="margin-top:8px">🔒 seal &amp; send ▶</button>
     <button id="tamper" disabled>⚡ tamper a byte</button>
     <div class="env" id="env">— nothing sent yet —</div>
     <div class="stat" id="alicestat"></div>
   </div>
   <div class="card bob"><h2>🧑 Bob</h2>
     <div class="stat" id="bobinfo">waiting for a sealed computer…</div>
     <button class="go bob" id="recv" disabled style="margin-top:8px">📥 receive &amp; boot</button>
     <div class="stat" id="bobstat"></div>
     <div class="calc" id="bobcalc" style="display:none">
       <div class="disp" id="bd">0</div>
       <div class="grid">
        <button data-k="7">7</button><button data-k="8">8</button><button data-k="9">9</button><button data-o="3">÷</button>
        <button data-k="4">4</button><button data-k="5">5</button><button data-k="6">6</button><button data-o="2">×</button>
        <button data-k="1">1</button><button data-k="2">2</button><button data-k="3">3</button><button data-o="1">−</button>
        <button data-k="0">0</button><button data-c="1">C</button><button data-eq="1">=</button><button data-o="0">+</button>
       </div>
       <div class="stat" id="bcs">the recovered computer runs on Bob's machine — arithmetic by the CA</div>
     </div>
   </div>
 </div>
 <p class="note"><b>What crossed the wire:</b> only the <b id="sentbytes">0</b> ciphertext bytes + the coordinate
 (component, generation). The pact's CA state — the key — was <b>never sent</b>; Bob regenerated it from the seed.
 Flip a byte (tamper) or give Bob the wrong seed and recovery fails: the computer is genuinely bound to the shared
 cellular automaton. (Pure-JS SHA-256 + the atn hex CA + the CA-1 VM; the Python side <code>atn_spoeqi.py</code>
 does the same with ChaCha20-Poly1305.)</p>
</div>
<script>
"use strict";
const CALC=__E__;
/* ───────── SHA-256 (pure JS) ───────── */
const K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
function rotr(x,n){return ((x>>>n)|(x<<(32-n)))>>>0;}
function sha256(msg){
 let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
 const ml=msg.length, total=(((ml+8)>>6)+1)<<6, m=new Uint8Array(total);
 m.set(msg); m[ml]=0x80; const dv=new DataView(m.buffer), bit=ml*8;
 dv.setUint32(total-4,bit>>>0,false); dv.setUint32(total-8,Math.floor(bit/0x100000000)>>>0,false);
 const w=new Uint32Array(64);
 for(let off=0;off<total;off+=64){
  for(let i=0;i<16;i++)w[i]=dv.getUint32(off+i*4,false);
  for(let i=16;i<64;i++){const s0=(rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>>3))>>>0,s1=(rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>>10))>>>0;w[i]=(w[i-16]+s0+w[i-7]+s1)>>>0;}
  let a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,hh=h7;
  for(let i=0;i<64;i++){const S1=(rotr(e,6)^rotr(e,11)^rotr(e,25))>>>0,ch=((e&f)^((~e)&g))>>>0,t1=(hh+S1+ch+K[i]+w[i])>>>0,S0=(rotr(a,2)^rotr(a,13)^rotr(a,22))>>>0,maj=((a&b)^(a&c)^(b&c))>>>0,t2=(S0+maj)>>>0;hh=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}
  h0=(h0+a)>>>0;h1=(h1+b)>>>0;h2=(h2+c)>>>0;h3=(h3+d)>>>0;h4=(h4+e)>>>0;h5=(h5+f)>>>0;h6=(h6+g)>>>0;h7=(h7+hh)>>>0;
 }
 const out=new Uint8Array(32),o=new DataView(out.buffer);[h0,h1,h2,h3,h4,h5,h6,h7].forEach((v,i)=>o.setUint32(i*4,v>>>0,false));return out;
}
const enc=s=>new TextEncoder().encode(s);
function hex(bytes,n){return Array.from(bytes.slice(0,n||bytes.length)).map(b=>b.toString(16).padStart(2,'0')).join('');}
// self test
document.getElementById("selftest").textContent =
  hex(sha256(enc("abc")))==="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" ? "SHA-256 self-test ✓" : "SHA-256 self-test ✗";

/* ───────── pact (seed -> hex-CA rules + grids; same construction both sides) ───────── */
const NCOMP=4, SIDE=48, DOMAIN=enc("spoeqi/tap/v1");
function prng(seed,label,n){let out=new Uint8Array(n),pos=0,ctr=0;const s=enc(seed),l=enc(label);
 while(pos<n){const b=new Uint8Array(s.length+l.length+4);b.set(s,0);b.set(l,s.length);new DataView(b.buffer).setUint32(s.length+l.length,ctr,true);
  const h=sha256(b);for(let i=0;i<32&&pos<n;i++)out[pos++]=h[i];ctr++;}return out;}
function buildPact(seed){const luts=[],init=[];
 for(let c=0;c<NCOMP;c++){const lb=prng(seed,"rule"+c,16384),lut=new Uint8Array(16384);for(let i=0;i<16384;i++)lut[i]=lb[i]&3;luts.push(lut);
  const gb=prng(seed,"grid"+c,SIDE*SIDE),g=new Uint8Array(SIDE*SIDE);for(let i=0;i<SIDE*SIDE;i++)g[i]=gb[i]&3;init.push(g);}
 return {seed,luts,init,cache:{0:init.map(g=>g.slice())}};}
function step(b,lut,W,H){const nb=new Uint8Array(W*H);
 for(let r=0;r<H;r++){const rm=(r-1+H)%H,rp=(r+1)%H,ev=(r%2===0);
  for(let c=0;c<W;c++){const cm=(c-1+W)%W,cp=(c+1)%W,s=b[r*W+c],N=b[rm*W+c],Sd=b[rp*W+c],Wc=b[r*W+cm],E=b[r*W+cp];
   let nw,ne,sw,se;if(ev){nw=b[rm*W+cm];ne=N;sw=b[rp*W+cm];se=Sd;}else{nw=N;ne=b[rm*W+cp];sw=Sd;se=b[rp*W+cp];}
   nb[r*W+c]=lut[(s<<12)|(nw<<10)|(ne<<8)|(E<<6)|(se<<4)|(sw<<2)|Wc];}}return nb;}
function gridsAt(p,gen){if(p.cache[gen])return p.cache[gen];let base=0;for(const k in p.cache)if(+k<=gen&&+k>base)base=+k;
 let g=p.cache[base].map(x=>x.slice());for(let t=0;t<gen-base;t++)g=g.map((gg,c)=>step(gg,p.luts[c],SIDE,SIDE));p.cache[gen]=g.map(x=>x.slice());return p.cache[gen];}
function tap(p,comp,gen,n){const grid=gridsAt(p,gen)[comp];let out=new Uint8Array(n),pos=0,ctr=0;
 while(pos<n){const hdr=new Uint8Array(12),dv=new DataView(hdr.buffer);dv.setUint32(0,comp,true);dv.setUint32(4,gen,true);dv.setUint32(8,ctr,true);
  const buf=new Uint8Array(DOMAIN.length+12+grid.length);buf.set(DOMAIN,0);buf.set(hdr,DOMAIN.length);buf.set(grid,DOMAIN.length+12);
  const h=sha256(buf);for(let i=0;i<32&&pos<n;i++)out[pos++]=h[i];ctr++;}return out;}

/* ───────── CA-1 VM (runs the recovered calculator) ───────── */
function runCalc(prog,a,b,op){const M=new Uint8Array(0x10000);M[CALC.OPA]=a;M[CALC.OPB]=b;M[CALC.OP]=op;
 let A=0,X=0,P=0,SP=0x7FFF,PC=0,Z=1,C=0,N=0,n=0;
 const set=(v,c)=>{const v8=v&255;Z=v8===0?1:0;N=(v8>>7)&1;if(c!==undefined)C=c&1;return v8;};
 while(n<2000000){const I=prog[PC],op2=I[0],arg=I[1];PC++;n++;const aa=A;
  switch(op2){case"LDI":A=set(arg);break;case"LDA":A=set(M[arg]);break;case"STA":M[arg&0xFFFF]=aa;break;
   case"ADD":A=set(aa+M[arg],(aa+M[arg])>255?1:0);break;case"ADDI":A=set(aa+arg,(aa+arg)>255?1:0);break;
   case"SUB":A=set(aa-M[arg],aa>=M[arg]?1:0);break;case"SUBI":A=set(aa-arg,aa>=arg?1:0);break;
   case"AND":A=set(aa&M[arg]);break;case"ANDI":A=set(aa&arg);break;case"OR":A=set(aa|M[arg]);break;
   case"SHL":A=set(aa<<1,(aa>>7)&1);break;case"SHR":A=set(aa>>1,aa&1);break;
   case"CMP":{const d=aa-M[arg];set(d,aa>=M[arg]?1:0);break;}case"CMPI":{const d=aa-arg;set(d,aa>=arg?1:0);break;}
   case"JMP":PC=arg;break;case"JZ":if(Z)PC=arg;break;case"JNZ":if(!Z)PC=arg;break;case"JC":if(C)PC=arg;break;case"JNC":if(!C)PC=arg;break;
   case"HLT":return M[CALC.ERR]?null:M[CALC.RHI]*256+M[CALC.RLO];default:break;}}
 return null;}

/* ───────── image = the computer (program) as bytes ───────── */
function computerImage(){return enc(JSON.stringify({prog:CALC.prog}));}

/* ───────── UI ───────── */
const $=id=>document.getElementById(id);
let aliceP, bobP, gen=0, sent=null;   // sent = {comp,gen,ct,tag}
function rederive(){const seed=$("seed").value;aliceP=buildPact(seed);
 bobP=buildPact($("wrongseed").checked?seed+" (wrong)":seed);
 // reset cache so gens recompute; restart clock
 gen=0; sent=null; $("env").textContent="— nothing sent yet —"; $("alicestat").textContent="";
 $("recv").disabled=true; $("tamper").disabled=true; $("bobcalc").style.display="none";
 $("bobstat").textContent=""; $("bobinfo").textContent="waiting for a sealed computer…"; $("sentbytes").textContent="0";}
$("proglen").textContent=CALC.prog.length;
const compSel=$("comp");for(let c=0;c<NCOMP;c++){const o=document.createElement("option");o.value=c;o.textContent=c;compSel.appendChild(o);}
$("rekey").onclick=rederive; $("seed").onchange=rederive; $("wrongseed").onchange=rederive;
rederive();
// shared CA viz
const gcanv=[];for(let c=0;c<NCOMP;c++){const cv=document.createElement("canvas");cv.className="ca";cv.width=SIDE;cv.height=SIDE;$("grids").appendChild(cv);gcanv.push(cv.getContext("2d"));}
const PAL=[[10,12,20],[60,110,165],[255,210,127],[200,90,70]];
function drawGrids(){const gs=gridsAt(aliceP,gen);for(let c=0;c<NCOMP;c++){const im=gcanv[c].createImageData(SIDE,SIDE),g=gs[c];
  for(let i=0;i<SIDE*SIDE;i++){const p=PAL[g[i]];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}gcanv[c].putImageData(im,0,0);}$("gen").textContent=gen;}
drawGrids();
setInterval(()=>{gen++;drawGrids();},700);
// seal & send
$("seal").onclick=()=>{const img=computerImage(),comp=+compSel.value,g=gen;
 const ks=tap(aliceP,comp,g,img.length),ct=new Uint8Array(img.length);for(let i=0;i<img.length;i++)ct[i]=img[i]^ks[i];
 const tag=sha256(img).slice(0,8);
 sent={comp,gen:g,ct,tag,len:img.length};
 $("env").innerHTML=`<span style="color:var(--pa)">envelope @ (component ${comp}, generation ${g})</span><br>`+hex(ct,40)+" … <span class='stat'>("+ct.length+" bytes)</span>";
 $("alicestat").innerHTML=`sealed the ${img.length}-byte computer against the shared CA tape and sent it.`;
 $("sentbytes").textContent=ct.length;
 $("recv").disabled=false; $("tamper").disabled=false;
 $("bobinfo").innerHTML=`a sealed computer arrived: <b>${ct.length}</b> bytes at coordinate (component ${comp}, generation ${g}). The key was not sent.`;};
$("tamper").onclick=()=>{if(!sent)return;sent.ct[3]^=0x40;$("env").innerHTML+="<br><span class='no'>⚡ tampered: byte 3 flipped</span>";};
// receive & boot
$("recv").onclick=()=>{if(!sent)return;const ks=tap(bobP,sent.comp,sent.gen,sent.len),pt=new Uint8Array(sent.len);
 for(let i=0;i<sent.len;i++)pt[i]=sent.ct[i]^ks[i];
 const ok=hex(sha256(pt).slice(0,8))===hex(sent.tag);
 if(!ok){$("bobstat").innerHTML="<span class='no'>✗ recovery failed — wrong pact or tampered ciphertext. The computer is bound to the shared CA.</span>";$("bobcalc").style.display="none";return;}
 let obj;try{obj=JSON.parse(new TextDecoder().decode(pt));}catch(e){$("bobstat").innerHTML="<span class='no'>✗ recovered garbage (wrong key)</span>";return;}
 bobProg=obj.prog;$("bobstat").innerHTML="<span class='ok'>✓ recovered &amp; booted a byte-identical CA-1 computer — try it:</span>";
 $("bobcalc").style.display="";};
// Bob's interactive calculator (runs the recovered program on the CA-1 VM)
let bobProg=null, acc=0, cur="0", curop=null, fresh=true;
function bdisp(v){cur=String(v);$("bd").textContent=cur;}
$("bobcalc").addEventListener("click",e=>{const t=e.target;if(!bobProg)return;
 if(t.dataset.k!==undefined){if(fresh){cur="";fresh=false;}cur=(cur+t.dataset.k).replace(/^0(?=\d)/,"").slice(0,3);$("bd").textContent=cur;}
 else if(t.dataset.o!==undefined){acc=parseInt(cur)||0;curop=+t.dataset.o;fresh=true;}
 else if(t.dataset.eq!==undefined&&curop!==null){const r=runCalc(bobProg,acc&255,(parseInt(cur)||0)&255,curop);
   bdisp(r===null?"ERR":r);$("bcs").innerHTML=`${acc} ${"+−×÷"[curop]} ${parseInt(cur)||0} = <b>${r}</b> — computed by the CA-1 program Bob recovered from the pact`;curop=null;fresh=true;}
 else if(t.dataset.c!==undefined){acc=0;curop=null;fresh=true;bdisp(0);}});
</script></body></html>'''
HTML = HTML.replace("__E__", EJSON)
open("dissemination/glider-lab15.html", "w").write(HTML)
print("wrote dissemination/glider-lab15.html", len(HTML), "bytes")
