#!/usr/bin/env python3
# build_lab26.py — glider-lab26.html: the REAL spoeqi envelope, in the browser.
# This is the secure pact design (mirrors velour spoeqi/envelope.py): the cellular automaton is the
# shared KEY SCHEDULE, not the cipher. Both sides evolve the same hex-K4 CA from a shared seed; the
# key at generation g is SHA-256(domain ‖ g ‖ full CA state at g); the message is sealed with a
# vetted AEAD -- AES-256-GCM via the browser's WebCrypto (velour uses ChaCha20-Poly1305; same class,
# but WebCrypto exposes AES-GCM natively). The receiver discovers g by brute-forcing a small window
# around its own clock; the AEAD tag tells it which generation matched. No homemade XOR cipher.
print_to = "dissemination/glider-lab26.html"

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The spoeqi envelope — a vetted cipher keyed by a cellular automaton</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#7ee787;--no:#ff7b72}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:900px;margin:0 auto;padding:18px}
 h1{font-size:21px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:13px}
 p{color:var(--mut);max-width:840px}
 .row{display:flex;gap:14px;flex-wrap:wrap}
 .card{flex:1;min-width:300px;background:#161b22;border:1px solid #2a3340;border-radius:10px;padding:12px}
 .card.alice{border-color:#3a3050}.card.bob{border-color:#26424f}
 h2{font-size:15px;margin:0 0 8px}
 label{font-size:12px;color:var(--mut)}
 input[type=text],textarea{width:100%;background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:7px 9px;font:14px ui-monospace,monospace;margin-top:3px}
 textarea{resize:vertical;font:14px system-ui}
 button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:7px 12px;cursor:pointer;font-size:13px;margin-top:8px}
 button:hover{border-color:var(--a)} button.go{background:#2a3344;border-color:#3a4a5a}
 .seedbar{background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin:10px 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
 .env{font:11.5px ui-monospace,monospace;color:var(--a);word-break:break-all;background:#0b0e13;border:1px solid #2a3340;border-radius:6px;padding:8px;margin-top:8px;max-height:120px;overflow:auto}
 .res{margin-top:8px;font-size:13px} .ok{color:var(--ok)} .no{color:var(--no)}
 canvas{image-rendering:pixelated;border:1px solid #2a3340;border-radius:5px;background:#000;vertical-align:middle}
 .pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:10px;border:1px solid #2a3340;color:var(--mut)}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:11px;margin-top:14px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)} b.b{color:var(--b)}
 .chk{font-size:12px;color:var(--mut)} .grid{display:flex;gap:8px;align-items:center;margin-top:6px}
</style></head><body><div class="wrap">
 <h1>The spoeqi envelope <small>— a vetted cipher (AES-256-GCM) keyed by a cellular automaton</small></h1>
 <p>The secure pact design: the cellular automaton is the <b>shared key schedule</b>, not the cipher. Alice and
 Bob both evolve the <b>same hex K=4 CA</b> from a shared seed; the key at generation <i>g</i> is
 <code>SHA-256(domain ‖ g ‖ CA-state)</code>, and the message is sealed with <b class="b">AES-256-GCM</b> (the
 browser's audited WebCrypto AEAD). Bob never receives the generation — he <b>discovers</b> it by trying a small
 window around his own clock; the AEAD tag tells him which one matched. (This mirrors velour <code>spoeqi/envelope.py</code>,
 which uses ChaCha20-Poly1305.)</p>

 <div class="seedbar">
   <label>shared pact seed (the only secret): <input type="text" id="seed" value="alice&lt;-&gt;bob pact 2026" style="min-width:240px"></label>
   <span class="grp"><label>gen <span class="pill" id="gen">0</span></label></span>
   <span class="grp"><canvas id="ca" width="48" height="48" style="width:48px;height:48px" title="the shared CA state both sides evolve"></canvas> <span class="chk">shared CA state</span></span>
 </div>

 <div class="row">
   <div class="card alice"><h2>👩 Alice — seal</h2>
     <label>message</label><textarea id="msg" rows="3">Meet at the old pier, midnight. 🌙 中文 ok</textarea>
     <button class="go" id="seal">🔒 Seal at the current generation</button>
     <div class="env" id="envhex">— envelope appears here —</div>
   </div>
   <div class="card bob"><h2>🧑 Bob — unseal</h2>
     <div class="chk"><label><input type="checkbox" id="wrongseed"> Bob uses the <i>wrong</i> seed (tweaked)</label></div>
     <div class="chk"><label><input type="checkbox" id="tamper"> flip one ciphertext byte (tamper)</label></div>
     <div class="grid"><label>Bob clock drift: <span class="pill" id="driftv">0</span> gen</label>
       <input type="range" id="drift" min="-25" max="25" value="0" style="flex:1"></div>
     <button class="go" id="unseal">🔓 Unseal (discover the generation)</button>
     <div class="res" id="res">— receive an envelope, then unseal —</div>
   </div>
 </div>

 <p class="note"><b>What's real and what isn't.</b> Confidentiality + integrity rest on <b>AES-256-GCM</b>
 (WebCrypto), not on the CA — so this is <i>not</i> the broken "XOR-with-a-CA-keystream" pattern. The CA only
 derives a shared, time-evolving key (its job is a KDF, and SHA-256 + AES-GCM wrap it, so its lack of a security
 proof doesn't weaken the envelope). Security reduces to <b>seed secrecy</b>. Honest limits (same as velour's
 documented threat model): <b>no forward secrecy</b> — whoever learns the seed can derive every past and future
 key — and "expiry" (the ±window) is a convenience, not a guarantee. Try it: a <span class="no">wrong seed</span>
 or a <span class="no">tampered byte</span> makes the AEAD tag fail; a clock drift inside the window still opens,
 outside it doesn't.</p>
</div>
<script>
"use strict";
const $=id=>document.getElementById(id);
const enc=s=>new TextEncoder().encode(s), dec=b=>new TextDecoder().decode(b);
const hex=b=>Array.from(b).map(x=>x.toString(16).padStart(2,"0")).join("");
/* SHA-256 (sync) — for the CA PRNG and the key derivation */
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
/* hex K=4 cellular automaton — the shared key schedule (same family as the other labs) */
const NCOMP=4,SIDE=48,DOM=enc("spoeqi/envelope/v1");
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
/* derive_key(pact,g) = SHA-256(DOM ‖ g(8 LE) ‖ full CA state at g)  -> 32-byte AES key */
function deriveKeyBytes(pact,g){const grids=gridsAt(pact,g);const st=new Uint8Array(8+NCOMP*SIDE*SIDE);
 new DataView(st.buffer).setUint32(0,g>>>0,true);let o=8;for(const gr of grids){st.set(gr,o);o+=gr.length;}
 const full=new Uint8Array(DOM.length+st.length);full.set(DOM,0);full.set(st,DOM.length);return sha256(full);}
const aesKey=kb=>crypto.subtle.importKey("raw",kb,{name:"AES-GCM"},false,["encrypt","decrypt"]);

const MAGIC=enc("SPENV"), VER=1, TICK_MS=1000, WINDOW=20;
let launch=performance.now();
const curGen=()=>Math.max(0,Math.floor((performance.now()-launch)/TICK_MS));
function pactFor(seed){return buildPact(seed);}
let alice=pactFor($("seed").value), envelope=null;
$("seed").addEventListener("change",()=>{alice=pactFor($("seed").value);launch=performance.now();});

async function seal(){
 const g=curGen(), kb=deriveKeyBytes(alice,g), key=await aesKey(kb);
 const nonce=crypto.getRandomValues(new Uint8Array(12));
 const ct=new Uint8Array(await crypto.subtle.encrypt({name:"AES-GCM",iv:nonce},key,enc($("msg").value)));
 const env=new Uint8Array(MAGIC.length+1+12+ct.length);let o=0;env.set(MAGIC,o);o+=MAGIC.length;env[o++]=VER;env.set(nonce,o);o+=12;env.set(ct,o);
 envelope=env;
 $("envhex").innerHTML="<b>sealed at gen "+g+"</b> ("+env.length+" B): "+hex(env);
 $("res").innerHTML="— envelope ready; click Unseal —";
}
async function unseal(){
 if(!envelope){$("res").innerHTML="<span class='no'>no envelope yet — Alice must seal first</span>";return;}
 let env=envelope.slice();
 if($("tamper").checked) env[env.length-3]^=0x01;                       // flip a ciphertext byte
 const nonce=env.slice(MAGIC.length+1,MAGIC.length+13), ct=env.slice(MAGIC.length+13);
 let seed=$("seed").value; if($("wrongseed").checked) seed=seed+"!";    // Bob's (wrong) seed
 const bob=pactFor(seed);
 const gNow=curGen()+(+$("drift").value);                               // Bob's drifted clock
 let order=[];for(let d=0;d<=WINDOW;d++){order.push(gNow+d);if(d)order.push(gNow-d);}
 for(const g of order){ if(g<0) continue;
   try{ const key=await aesKey(deriveKeyBytes(bob,g));
     const pt=await crypto.subtle.decrypt({name:"AES-GCM",iv:nonce},key,ct);
     $("res").innerHTML="<span class='ok'>✓ opened</span> — discovered generation <b>"+g+"</b> (Bob's clock said "+gNow+
        ", drift "+(g-gNow)+"):<br><code style='color:var(--ink)'>"+dec(pt).replace(/[&<]/g,m=>m=='&'?'&amp;':'&lt;')+"</code>"; return; }
   catch(e){}
 }
 $("res").innerHTML="<span class='no'>✗ could not open</span> within ±"+WINDOW+" of gen "+gNow+
   " — wrong seed, tampered ciphertext, or clock drift outside the window.";
}
$("seal").onclick=()=>seal().catch(e=>$("envhex").textContent="error: "+e);
$("unseal").onclick=()=>unseal().catch(e=>$("res").textContent="error: "+e);
$("drift").oninput=()=>$("driftv").textContent=$("drift").value;
/* live: show the shared CA state evolving + the generation counter */
const cv=$("ca"),cx=cv.getContext("2d"),cim=cx.createImageData(SIDE,SIDE);
const COL=[[10,12,20],[110,80,200],[80,150,220],[230,210,130]];
function paint(){const g=curGen();$("gen").textContent=g;const grid=gridsAt(alice,g)[0];
 for(let i=0;i<SIDE*SIDE;i++){const c=COL[grid[i]];cim.data[i*4]=c[0];cim.data[i*4+1]=c[1];cim.data[i*4+2]=c[2];cim.data[i*4+3]=255;}
 cx.putImageData(cim,0,0);requestAnimationFrame(paint);}
requestAnimationFrame(paint);
</script></body></html>'''
open(print_to, "w").write(HTML)
print("wrote", print_to, len(HTML), "bytes")
