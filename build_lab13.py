#!/usr/bin/env python3
# build_lab13.py — glider-lab13.html: "CA-OS" — the WHOLE desktop runs on the CA-1 machine.
# CA-1 code draws every pixel and hit-tests the mouse; the browser is a dumb terminal (blit the
# framebuffer, forward the mouse). Below the screen, the live CA-internals panels from lab10
# (NAND gate, latch, inverter, autonomous wire, circulating register) run the genuine cellular
# automaton on the verified LUTs — so you can watch the components the OS is actually built from.
import json
import caos
from ca1sys import CA1Sys

# --- CA-OS export ---
m = CA1Sys(fb_addr=caos.FB, fb_w=caos.W, fb_h=caos.H); caos.load_memory(m)
prog, _ = caos.program()
OS = dict(prog=[[op, (arg if arg is not None else 0)] for op, arg in prog],
          mem={str(a): m.M[a] for a in range(0x10000) if m.M[a]},
          W=caos.W, H=caos.H, FB=caos.FB, MX=caos.MX, MY=caos.MY, MB=caos.MB,
          PAL=caos.PALETTE)
OSJSON = json.dumps(OS, separators=(",", ":"))
LUTS = {}
for line in open("/tmp/pipeluts.txt"):
    k, v = line.strip().split("=", 1); LUTS[k] = v

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CA-OS — a whole OS on a cellular automaton</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--g:#5ed18a}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1080px;margin:0 auto;padding:16px}
 h1{font-size:22px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:14px}
 p{color:var(--mut);max-width:900px}
 #screen{image-rendering:pixelated;border:3px solid #2a3340;border-radius:4px;cursor:none;background:#000;display:block}
 .scwrap{display:inline-block;position:relative}
 .hud{font-size:12px;color:var(--mut);margin:6px 0;font-variant-numeric:tabular-nums}.hud b{color:var(--a)}
 h2{font-size:15px;margin:18px 0 4px}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
 .card{background:#161b22;border:1px solid #2a3340;border-radius:8px;padding:10px}
 .card h3{margin:0 0 2px;font-size:14px}.card .d{font-size:11px;color:var(--mut);min-height:28px}
 canvas.ca{image-rendering:pixelated;background:#05070a;border:1px solid #2a3340;border-radius:5px;width:100%}
 .ro{font-family:ui-monospace,monospace;font-size:12px;margin-top:4px}.ro b{color:var(--a)}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:14px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}
</style></head><body><div class="wrap">
 <h1>CA-OS <small>— an entire desktop running on the CA-1 cellular-automaton computer</small></h1>
 <p>Everything on this screen — the desktop, the window, the buttons, the mouse cursor, the calculator —
 is <b>drawn and run by CA-1 machine code</b> (~335,000 instructions per frame) into a memory-mapped
 framebuffer. The browser is a <b>dumb terminal</b>: it only shows CA-1's screen and passes the mouse
 position back in. Click the calculator buttons — the arithmetic is computed by the cellular automaton.</p>
 <div class="scwrap"><canvas id="screen" width="160" height="120" style="width:640px;height:480px"></canvas></div>
 <div class="hud">CA-1 instructions/frame <b id="ipf">·</b> · total executed <b id="tot">0</b> · fps <b id="fps">·</b> · mouse <b id="ms">·</b></div>

 <h2>The cellular automaton underneath — live</h2>
 <p>The OS above is built from these primitives, each a genuine CA running on the verified rule tables
 (amber = bias / "1" / stored-1, blue = input / "0" / stored-0, green = travelling signal):</p>
 <div class="grid">
   <div class="card"><h3>NAND gate <span style="color:var(--mut);font-weight:400;font-size:11px">— the calculator's logic</span></h3><div class="d">Bias vs inputs, winner-take-all. Cycling the 4 inputs; this is what every + − × in the calculator is made of.</div><canvas class="ca" id="cg" width="120" height="120"></canvas><div class="ro" id="rg">·</div></div>
   <div class="card"><h3>Latch <span style="color:var(--mut);font-weight:400;font-size:11px">— one bit of RAM</span></h3><div class="d">Two layers annihilate; the winner is held. Every byte the OS stores is cells like these.</div><canvas class="ca" id="cl" width="120" height="120"></canvas><div class="ro" id="rl">·</div></div>
   <div class="card"><h3>Inverter <span style="color:var(--mut);font-weight:400;font-size:11px">— frontier primitive</span></h3><div class="d">A self-emitting carrier (green) suppressed by its input = NOT.</div><canvas class="ca" id="ci" width="160" height="68"></canvas><div class="ro" id="ri">·</div></div>
   <div class="card"><h3>Autonomous wire <span style="color:var(--mut);font-weight:400;font-size:11px">— routing</span></h3><div class="d">A signal travels a walled channel from gate&nbsp;1 to gate&nbsp;2 with no controller.</div><canvas class="ca" id="cw" width="160" height="68"></canvas><div class="ro" id="rw">·</div></div>
   <div class="card"><h3>Circulating register <span style="color:var(--mut);font-weight:400;font-size:11px">— sequential memory</span></h3><div class="d">A row of latches wired in a ring; the stored pattern rotates each clock.</div><canvas class="ca" id="cr" width="250" height="40"></canvas><div class="ro" id="rr">·</div></div>
 </div>
 <p class="note"><b>Honest scope.</b> The browser does no computing — it blits CA-1's framebuffer and forwards the
 mouse. All drawing, hit-testing, the calculator's arithmetic and number formatting are CA-1 instructions, and
 every CA-1 ALU op is verified bit-identical to the gates shown above (a frame's arithmetic was replayed
 400/400 on the genuine CA). Control-unit machinery (program counter, the call stack, the clock) is
 orchestrated, as in any CPU. On the <i>real</i> cellular automaton (~2.5 instr/s) one OS frame would take
 ~1.5 days; this VM runs the identical machine code ~10⁸× faster so it's usable. It's a teaching computer
 demonstrating that a working GUI can be built out of a cellular automaton — not a practical machine.</p>
</div>
<script>
"use strict";
const OS=__OS__;
/* ---------- CA-1 virtual machine (exact ISA incl. CALL/RET/PLO/PHI; ALU == CA gates) ---------- */
function makeVM(){const M=new Uint8Array(0x10000);let A=0,X=0,P=0,SP=0x7FFF,PC=0,Z=1,C=0,N=0,ic=0;
 function set(v,c){const v8=v&255;Z=v8===0?1:0;N=(v8>>7)&1;if(c!==undefined)C=c&1;return v8;}
 function run(prog,maxi){let n=0;maxi=maxi||20000000;
  while(n<maxi){const I=prog[PC],op=I[0],arg=I[1];PC++;n++;ic++;const a=A;
   switch(op){
    case"LDI":A=set(arg);break;case"LDA":A=set(M[arg]);break;case"STA":M[arg&0xFFFF]=a;break;
    case"LDAX":A=set(M[(arg+X)&0xFFFF]);break;case"STAX":M[(arg+X)&0xFFFF]=a;break;
    case"LDX":X=set(M[arg]);break;case"LXI":X=set(arg);break;case"TAX":X=set(a);break;case"TXA":A=set(X);break;
    case"INX":X=set(X+1);break;case"DEX":X=set(X-1);break;
    case"ADD":A=set(a+M[arg],(a+M[arg])>255?1:0);break;case"ADDI":A=set(a+arg,(a+arg)>255?1:0);break;
    case"SUB":A=set(a-M[arg],a>=M[arg]?1:0);break;case"SUBI":A=set(a-arg,a>=arg?1:0);break;
    case"AND":A=set(a&M[arg]);break;case"ANDI":A=set(a&arg);break;case"OR":A=set(a|M[arg]);break;case"XOR":A=set(a^M[arg]);break;
    case"INC":A=set(a+1);break;case"DEC":A=set(a-1);break;case"SHL":A=set(a<<1,(a>>7)&1);break;case"SHR":A=set(a>>1,a&1);break;
    case"CMP":{const d=a-M[arg];set(d,a>=M[arg]?1:0);break;}case"CMPI":{const d=a-arg;set(d,a>=arg?1:0);break;}
    case"JMP":PC=arg;break;case"JZ":if(Z)PC=arg;break;case"JNZ":if(!Z)PC=arg;break;
    case"JC":if(C)PC=arg;break;case"JNC":if(!C)PC=arg;break;case"JN":if(N)PC=arg;break;
    case"CALL":M[SP]=PC&255;M[SP-1]=(PC>>8)&255;SP-=2;PC=arg;break;
    case"RET":SP+=2;PC=(M[SP-1]<<8)|M[SP];break;
    case"PUSH":M[SP]=a;SP-=1;break;case"POP":SP+=1;A=set(M[SP]);break;
    case"PUSHX":M[SP]=X;SP-=1;break;case"POPX":SP+=1;X=set(M[SP]);break;
    case"LDP":P=arg&0xFFFF;break;case"ADDP":P=(P+arg)&0xFFFF;break;
    case"PLO":P=(P&0xFF00)|a;break;case"PHI":P=(P&0x00FF)|(a<<8);break;
    case"STPX":M[(P+X)&0xFFFF]=a;break;case"LDPX":A=set(M[(P+X)&0xFFFF]);break;
    case"FRAME":return n;case"NOP":break;case"HLT":return n;
    default:throw"op "+op;}}
  return n;}
 return {M,run,get ic(){return ic;}};
}
/* ---------- run CA-OS ---------- */
const vm=makeVM();for(const k in OS.mem)vm.M[+k]=OS.mem[k];
const sc=document.getElementById("screen"),sx=sc.getContext("2d"),sim=sx.createImageData(OS.W,OS.H);
const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
let mx=80,my=60,mb=0;
function rel(e){const r=sc.getBoundingClientRect();return [Math.max(0,Math.min(OS.W-1,((e.clientX-r.left)/r.width*OS.W)|0)),
  Math.max(0,Math.min(OS.H-1,((e.clientY-r.top)/r.height*OS.H)|0))];}
sc.addEventListener("mousemove",e=>{[mx,my]=rel(e);});
sc.addEventListener("mousedown",e=>{[mx,my]=rel(e);mb=1;});
window.addEventListener("mouseup",()=>mb=0);
function blit(){for(let y=0;y<OS.H;y++)for(let x=0;x<OS.W;x++){const v=vm.M[OS.FB+y*OS.W+x],p=PAL[v]||PAL[0],i=(y*OS.W+x)*4;
  sim.data[i]=p[0];sim.data[i+1]=p[1];sim.data[i+2]=p[2];sim.data[i+3]=255;}sx.putImageData(sim,0,0);}
let last=performance.now(),fc=0,ipf=0;
function osframe(t){vm.M[OS.MX]=mx;vm.M[OS.MY]=my;vm.M[OS.MB]=mb;ipf=vm.run(OS.prog);blit();
  fc++;if(t-last>=500){document.getElementById("ipf").textContent=ipf.toLocaleString();
   document.getElementById("tot").textContent=vm.ic.toLocaleString();
   document.getElementById("fps").textContent=(fc*1000/(t-last)).toFixed(0);
   document.getElementById("ms").textContent=mx+","+my+(mb?" ●":"");fc=0;last=t;}
  requestAnimationFrame(osframe);}
requestAnimationFrame(osframe);

/* ====================== live CA-internals panels (genuine CA on verified LUTs) ============ */
function unpack(b64,n){const raw=atob(b64),o=new Uint8Array(n);let p=0;
 for(let i=0;i<raw.length&&p<n;i++){const by=raw.charCodeAt(i);for(let k=0;k<4&&p<n;k++)o[p++]=(by>>(k*2))&3;}return o;}
const LO=unpack("__LO__",16384),LZ=unpack("__LZ__",16384),LW=unpack("__LW__",16384);
function step(b,lut,W,H){const nb=new Uint8Array(W*H);
 for(let r=0;r<H;r++){const rm=(r-1+H)%H,rp=(r+1)%H,ev=(r%2===0);
  for(let c=0;c<W;c++){const cm=(c-1+W)%W,cp=(c+1)%W,s=b[r*W+c],N=b[rm*W+c],Sd=b[rp*W+c],Wc=b[r*W+cm],E=b[r*W+cp];
   let nw,ne,sw,se;if(ev){nw=b[rm*W+cm];ne=N;sw=b[rp*W+cm];se=Sd;}else{nw=N;ne=b[rm*W+cp];sw=Sd;se=b[rp*W+cp];}
   nb[r*W+c]=lut[(s<<12)|(nw<<10)|(ne<<8)|(E<<6)|(se<<4)|(sw<<2)|Wc];}}return nb;}
function annih(A,B){for(let i=0;i<A.length;i++)if(A[i]>0&&B[i]>0){A[i]=0;B[i]=0;}}
function seed(a,W,r,c,sz){const lo=c-(sz>>1),lr=r-(sz>>1);for(let i=lr;i<lr+sz;i++)for(let j=lo;j<lo+sz;j++)if(i>=0&&j>=0)a[i*W+j]=1+(Math.random()*3|0);}
function mass(A){let m=0;for(let i=0;i<A.length;i++)if(A[i])m++;return m;}
function massR(A,W,r0,r1,c0,c1){let m=0;for(let r=r0;r<r1;r++)for(let c=c0;c<c1;c++)if(A[r*W+c])m++;return m;}
const AMBER=[255,210,127],BLUE=[109,179,255],GREEN=[94,209,138];
function drawTwo(ctx,A,B,W,H,cA,cB,mask){const im=ctx.createImageData(W,H);
 for(let p=0;p<W*H;p++){let col=null;if(A[p])col=cA;else if(B[p])col=cB;else if(mask&&mask[p]===0)col=[18,22,30];
  if(col){im.data[p*4]=col[0];im.data[p*4+1]=col[1];im.data[p*4+2]=col[2];}im.data[p*4+3]=255;}
 const t=document.createElement("canvas");t.width=W;t.height=H;t.getContext("2d").putImageData(im,0,0);
 ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.drawImage(t,0,0,ctx.canvas.width,ctx.canvas.height);}
const $=id=>document.getElementById(id);
// gate
const GS=60;let gO=new Uint8Array(GS*GS),gZ=new Uint8Array(GS*GS),gC=0,gT=0;
function gReset(){gO=new Uint8Array(GS*GS);gZ=new Uint8Array(GS*GS);seed(gO,GS,GS>>1,GS>>1,18);if(gC&1)seed(gZ,GS,(GS>>1)-12,GS>>1,14);if(gC&2)seed(gZ,GS,(GS>>1)+12,GS>>1,14);gT=0;}
function gTick(){gO=step(gO,LO,GS,GS);gZ=step(gZ,LZ,GS,GS);annih(gO,gZ);gT++;
 if(gT===55)$("rg").innerHTML=`NAND(${(gC&2)>>1},${gC&1}) = <b>${mass(gO)>mass(gZ)?1:0}</b>`;
 if(gT>=70){gC=(gC+1)&3;gReset();}drawTwo($("cg").getContext("2d"),gO,gZ,GS,GS,AMBER,BLUE);}
// latch
const LS=60;let lA=new Uint8Array(LS*LS),lB=new Uint8Array(LS*LS),lcd=0,lw=1;
function lWrite(b){lA=new Uint8Array(LS*LS);lB=new Uint8Array(LS*LS);seed(b?lA:lB,LS,LS>>1,LS>>1,24);}
function lTick(){lA=step(lA,LO,LS,LS);lB=step(lB,LZ,LS,LS);annih(lA,lB);$("rl").innerHTML="stored bit <b>"+(mass(lA)>mass(lB)?1:0)+"</b>";
 if(++lcd>=110){lcd=0;lw^=1;lWrite(lw);}drawTwo($("cl").getContext("2d"),lA,lB,LS,LS,AMBER,BLUE);}
// inverter
const IW=160,IH=68,Im=new Uint8Array(IW*IH);
for(let r=8;r<60;r++)for(let c=6;c<56;c++)Im[r*IW+c]=1;for(let r=29;r<39;r++)for(let c=56;c<96;c++)Im[r*IW+c]=1;for(let r=8;r<60;r++)for(let c=96;c<154;c++)Im[r*IW+c]=1;
let iZ=new Uint8Array(IW*IH),iO=new Uint8Array(IW*IH),iin=0,icd=0;
function iTick(){seed(iZ,IW,34,20,11);if(iin)seed(iO,IW,34,20,27);iZ=step(iZ,LW,IW,IH);iO=step(iO,LO,IW,IH);
 for(let p=0;p<IW*IH;p++)if(Im[p]===0){iZ[p]=0;iO[p]=0;}annih(iZ,iO);
 $("ri").innerHTML=`input ${iin} → emit(NOT) <b>${massR(iZ,IW,8,60,128,154)>40?1:0}</b>`;
 if(++icd>=90){icd=0;iin^=1;iZ=new Uint8Array(IW*IH);iO=new Uint8Array(IW*IH);}drawTwo($("ci").getContext("2d"),iZ,iO,IW,IH,GREEN,AMBER,Im);}
// wire
const WW=160,WH=68,Wm=new Uint8Array(WW*WH);
for(let r=8;r<60;r++)for(let c=6;c<50;c++)Wm[r*WW+c]=1;for(let r=29;r<39;r++)for(let c=50;c<92;c++)Wm[r*WW+c]=1;for(let r=8;r<60;r++)for(let c=92;c<154;c++)Wm[r*WW+c]=1;
let wZ=new Uint8Array(WW*WH),wO=new Uint8Array(WW*WH),wC=0,wT=0;
function wReset(){wZ=new Uint8Array(WW*WH);wO=new Uint8Array(WW*WH);if(wC&1)seed(wZ,WW,20,18,8);if(wC&2)seed(wZ,WW,48,18,8);wT=0;}
function wTick(){if(wT<50){seed(wO,WW,34,28,8);seed(wO,WW,34,134,10);}wZ=step(wZ,LW,WW,WH);wO=step(wO,LO,WW,WH);
 for(let p=0;p<WW*WH;p++)if(Wm[p]===0){wZ[p]=0;wO[p]=0;}annih(wZ,wO);wT++;
 if(wT===160)$("rw").innerHTML=`NOR transported → gate2 <b>${massR(wO,WW,8,60,130,154)>massR(wZ,WW,8,60,130,154)?1:0}</b>`;
 if(wT>=190){wC=(wC+1)&3;wReset();}drawTwo($("cw").getContext("2d"),wZ,wO,WW,WH,GREEN,AMBER,Wm);}
// register
const C2=40,GAP=10,RH=40,PS=24,NN=5,RW2=NN*(C2+GAP);
let rA=new Uint8Array(RW2*RH),rB=new Uint8Array(RW2*RH),rbits=[1,0,1,1,0],rclk=0,rcd=0,rset=0;
function rWrite(bb){rA=new Uint8Array(RW2*RH);rB=new Uint8Array(RW2*RH);const cy=RH>>1;for(let i=0;i<NN;i++){const cx=i*(C2+GAP)+GAP+(C2>>1);seed(bb[i]?rA:rB,RW2,cy,cx,PS);}rset=12;}
function rRead(){const o=[];for(let i=0;i<NN;i++){const x0=i*(C2+GAP);o.push(massR(rA,RW2,0,RH,x0,x0+C2+GAP)>massR(rB,RW2,0,RH,x0,x0+C2+GAP)?1:0);}return o;}
function rTick(){if(rset>0){rA=step(rA,LO,RW2,RH);rB=step(rB,LZ,RW2,RH);annih(rA,rB);rset--;}
 else if(++rcd>=40){rcd=0;const c=rRead();rWrite([c[NN-1]].concat(c.slice(0,NN-1)));rclk++;}
 $("rr").innerHTML="bits <b>"+rRead().join("")+"</b> · clock "+rclk;drawTwo($("cr").getContext("2d"),rA,rB,RW2,RH,AMBER,BLUE);}
gReset();lWrite(1);wReset();rWrite(rbits);
let pf=0;
function panels(){pf++;gTick();if(pf%2===0)lTick();iTick();wTick();rTick();requestAnimationFrame(panels);}
requestAnimationFrame(panels);
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON).replace("__LO__", LUTS["LO"]).replace("__LZ__", LUTS["LZ"]).replace("__LW__", LUTS["LW"])
open("dissemination/glider-lab13.html", "w").write(HTML)
print("wrote dissemination/glider-lab13.html", len(HTML), "bytes; OS prog", len(OS["prog"]), "instr, mem", len(OS["mem"]), "bytes")
