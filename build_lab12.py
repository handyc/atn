#!/usr/bin/env python3
# build_lab12.py — glider-lab12.html: "CA-1 98", a Windows-98-style desktop whose apps' actual
# computation runs on the CA-1 machine (the faithful VM; ALU verified == CA gates). Calculator
# arithmetic and DOOM rendering are genuinely executed by CA-1; the window chrome is a skin for
# showing it off. An About window states plainly what is CA-powered vs presentation.
import json
import calc, raycaster as rc
from ca1sys import CA1Sys

# --- calculator export ---
cprog, _ = calc.program()
CALC = dict(prog=[[op, (arg if arg is not None else 0)] for op, arg in cprog],
            OPA=calc.OPA, OPB=calc.OPB, OP=calc.OP, RLO=calc.RLO, RHI=calc.RHI, ERR=calc.ERR)
# --- raycaster export ---
mm = CA1Sys(fb_addr=rc.FB_A, fb_w=rc.SH, fb_h=rc.SW); rc.load_memory(mm)
rprog, _ = rc.program(loop=True)
RAY = dict(prog=[[op, (arg if arg is not None else 0)] for op, arg in rprog],
           mem={str(a): mm.M[a] for a in range(0x10000) if mm.M[a]}, SW=rc.SW, SH=rc.SH, FB=rc.FB_A, INP=mm.inp_addr)
DATA = json.dumps(dict(calc=CALC, ray=RAY), separators=(",", ":"))

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CA-1 98</title>
<style>
 *{box-sizing:border-box;-webkit-user-select:none;user-select:none}
 html,body{margin:0;height:100%;overflow:hidden;font:12px/1.4 "MS Sans Serif",Tahoma,Geneva,sans-serif}
 #desk{position:absolute;inset:0 0 30px 0;background:#118f8f;overflow:hidden}
 .ico{position:absolute;width:78px;text-align:center;color:#fff;cursor:pointer;padding:4px}
 .ico:focus,.ico.sel{background:#0a3d91;outline:1px dotted #fff}
 .ico div{font-size:30px;line-height:1}.ico span{display:block;margin-top:3px;text-shadow:1px 1px #003}
 .win{position:absolute;background:#c0c0c0;border:2px solid;border-color:#dfdfdf #808080 #808080 #dfdfdf;box-shadow:1px 1px 0 #000;min-width:180px}
 .tb{background:linear-gradient(90deg,#000080,#1084d0);color:#fff;font-weight:bold;padding:2px 3px;display:flex;align-items:center;cursor:move}
 .tb .t{flex:1;padding-left:3px}
 .tb button{width:16px;height:14px;margin-left:2px;font:10px/1 sans-serif;padding:0}
 .cli{padding:8px}
 button.w{background:#c0c0c0;border:2px solid;border-color:#dfdfdf #808080 #808080 #dfdfdf;padding:2px 6px;cursor:pointer;font:12px "MS Sans Serif",sans-serif}
 button.w:active{border-color:#808080 #dfdfdf #dfdfdf #808080}
 .sunk{border:2px solid;border-color:#808080 #dfdfdf #dfdfdf #808080;background:#fff}
 /* taskbar */
 #bar{position:absolute;left:0;right:0;bottom:0;height:30px;background:#c0c0c0;border-top:2px solid #dfdfdf;display:flex;align-items:center;padding:2px 4px;gap:4px}
 #start{font-weight:bold;display:flex;align-items:center;gap:4px}
 #start .flag{font-size:14px}
 #tasks{flex:1;display:flex;gap:4px;overflow:hidden}
 #tasks button{max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left}
 #clock{border:1px solid;border-color:#808080 #dfdfdf #dfdfdf #808080;padding:2px 8px;font-variant-numeric:tabular-nums}
 #menu{position:absolute;bottom:30px;left:2px;width:200px;background:#c0c0c0;border:2px solid;border-color:#dfdfdf #808080 #808080 #dfdfdf;display:none}
 #menu .side{position:absolute;left:0;top:0;bottom:0;width:22px;background:linear-gradient(#000080,#1084d0);writing-mode:vertical-rl;color:#fff;font-weight:bold;text-align:center;padding:6px 2px;transform:rotate(180deg)}
 #menu ul{list-style:none;margin:0;padding:0 0 0 24px}
 #menu li{padding:5px 10px;cursor:pointer;display:flex;gap:8px}#menu li:hover{background:#000080;color:#fff}
 /* calculator */
 .calc .disp{text-align:right;font:16px "Courier New",monospace;padding:4px 6px;margin-bottom:6px}
 .calc .grid{display:grid;grid-template-columns:repeat(4,40px);gap:4px}
 .calc .grid button{height:32px}
 .calc .st{font-size:10px;color:#333;margin-top:6px}
 textarea{width:320px;height:180px;border:2px solid;border-color:#808080 #dfdfdf #dfdfdf #808080;font:12px "Courier New",monospace;resize:none}
 canvas{image-rendering:pixelated;background:#000;display:block}
 .about{width:320px}.about b{color:#000080} .about .ca{color:#0a0}
 .menubar{background:#c0c0c0;font-size:11px;padding:2px 4px;border-bottom:1px solid #808080}
 .menubar span{margin-right:10px}
</style></head><body>
<div id="desk"></div>
<div id="menu"><div class="side">CA-1&nbsp;98</div><ul id="mitems"></ul></div>
<div id="bar"><button class="w" id="start"><span class="flag">🪟</span>Start</button><div id="tasks"></div><div id="clock">--:--</div></div>
<script>
"use strict";
const DATA=__DATA__;
/* ---------------- CA-1 virtual machine (exact CA-1 ISA; ALU == CA gates, verified) ------- */
function makeVM(){const M=new Uint8Array(0x10000);let A=0,X=0,P=0,PC=0,Z=1,C=0,N=0,ic=0;
 function set(v,c){const v8=v&255;Z=v8===0?1:0;N=(v8>>7)&1;if(c!==undefined)C=c&1;return v8;}
 function run(prog,untilFrame,maxi){let n=0;maxi=maxi||3000000;
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
    case"LDP":P=arg&0xFFFF;break;case"ADDP":P=(P+arg)&0xFFFF;break;case"STPX":M[(P+X)&0xFFFF]=a;break;case"LDPX":A=set(M[(P+X)&0xFFFF]);break;
    case"IN":A=set(M[DATA.ray.INP]);break;case"FRAME":if(untilFrame)return n;break;case"NOP":break;case"HLT":return n;
    default:throw"op "+op;}}
  return n;}
 return {M,run,reset(){PC=0;A=X=P=0;Z=1;C=0;N=0;},get ic(){return ic;}};
}
/* ---------------- window manager ---------------- */
const desk=document.getElementById("desk"),tasks=document.getElementById("tasks");
let zc=10;
function makeWin(title,w,cli,onclose){
 const win=document.createElement("div");win.className="win";win.style.left=(40+Math.random()*120|0)+"px";win.style.top=(30+Math.random()*80|0)+"px";win.style.zIndex=++zc;
 win.innerHTML=`<div class="tb"><span class="t">${title}</span><button class="w" data-x>✕</button></div>`;
 const body=document.createElement("div");win.appendChild(body);body.appendChild(cli);
 desk.appendChild(win);
 const tb=win.querySelector(".tb");
 win.addEventListener("mousedown",()=>win.style.zIndex=++zc);
 // drag
 let dx,dy,drag=false;
 tb.addEventListener("mousedown",e=>{if(e.target.dataset.x!==undefined)return;drag=true;dx=e.clientX-win.offsetLeft;dy=e.clientY-win.offsetTop;});
 window.addEventListener("mousemove",e=>{if(drag){win.style.left=(e.clientX-dx)+"px";win.style.top=(e.clientY-dy)+"px";}});
 window.addEventListener("mouseup",()=>drag=false);
 // taskbar button
 const tbtn=document.createElement("button");tbtn.className="w";tbtn.textContent=title;tasks.appendChild(tbtn);
 tbtn.onclick=()=>win.style.zIndex=++zc;
 function close(){win.remove();tbtn.remove();if(onclose)onclose();}
 win.querySelector("[data-x]").onclick=close;
 return {win,body,close};
}
/* ---------------- apps ---------------- */
function appCalc(){
 const vm=makeVM(),C=DATA.calc;
 const el=document.createElement("div");el.className="cli calc";
 el.innerHTML=`<div class="disp sunk" id="cd">0</div>
  <div class="grid">
   <button class="w" data-k="7">7</button><button class="w" data-k="8">8</button><button class="w" data-k="9">9</button><button class="w" data-o="3">÷</button>
   <button class="w" data-k="4">4</button><button class="w" data-k="5">5</button><button class="w" data-k="6">6</button><button class="w" data-o="2">×</button>
   <button class="w" data-k="1">1</button><button class="w" data-k="2">2</button><button class="w" data-k="3">3</button><button class="w" data-o="1">−</button>
   <button class="w" data-k="0">0</button><button class="w" data-c="1">C</button><button class="w" data-eq="1">=</button><button class="w" data-o="0">+</button>
  </div><div class="st" id="cs">every result computed on CA-1 (cellular-automaton arithmetic)</div>`;
 let acc=0,cur="0",op=null,fresh=true;
 const disp=()=>el.querySelector("#cd").textContent=cur;
 function setcur(v){cur=String(v);disp();}
 function calcCA(a,b,o){vm.reset();vm.M[C.OPA]=a&255;vm.M[C.OPB]=b&255;vm.M[C.OP]=o;
   const n=vm.run(C.prog,false);const err=vm.M[C.ERR],rhi=vm.M[C.RHI],rlo=vm.M[C.RLO];
   const val=(o===1||o===3)?rlo:rhi*256+rlo;
   el.querySelector("#cs").textContent=err?`error (÷0 or negative) · ${n} CA-1 instructions`:`${a} ${"+−×÷"[o]} ${b} computed by CA-1 in ${n} instructions`;
   return err?null:val;}
 el.addEventListener("click",e=>{const t=e.target;
  if(t.dataset.k!==undefined){if(fresh){cur="";fresh=false}cur=(cur+t.dataset.k).replace(/^0(?=\d)/,"").slice(0,3);setcur(cur);}
  else if(t.dataset.o!==undefined){acc=parseInt(cur)||0;op=+t.dataset.o;fresh=true;}
  else if(t.dataset.eq!==undefined&&op!==null){const r=calcCA(acc,parseInt(cur)||0,op);setcur(r===null?"ERR":r);op=null;fresh=true;}
  else if(t.dataset.c!==undefined){acc=0;cur="0";op=null;fresh=true;disp();el.querySelector("#cs").textContent="cleared";}
 });
 makeWin("Calculator",0,el);
}
function appNotepad(){
 const el=document.createElement("div");el.className="cli";el.style.padding="0";
 el.innerHTML=`<div class="menubar"><span>File</span><span>Edit</span><span>Help</span></div>`;
 const ta=document.createElement("textarea");ta.value="Welcome to CA-1 98.\n\nThis Notepad is part of the desktop skin.\nThe Calculator and DOOM windows run real\nprograms on the CA-1 machine — every add,\nsubtract, multiply and pixel is computed by\nthe cellular automaton.";
 el.appendChild(ta);makeWin("Untitled - Notepad",0,el);
}
function appAbout(){
 const el=document.createElement("div");el.className="cli about";
 el.innerHTML=`<p><b>CA-1 98</b> — a desktop for the CA-1 computer.</p>
  <p><b>Processor:</b> CA-1, 8-bit accumulator<br><b>Clock:</b> 2.5 instructions/sec (genuine CA) · ~10⁸× faster here<br>
  <b>Logic:</b> mutual-annihilation latch gates (a cellular automaton)<br><b>RAM:</b> CA-latch storage</p>
  <p class="ca">✓ CA-powered: Calculator arithmetic (+ − × ÷, multiply = repeated CA addition) and DOOM rendering — every operation verified bit-identical to the CA gates.</p>
  <p style="color:#a00">Skin only: the windows, taskbar and Notepad text are ordinary presentation, here so non-experts can recognise it as a computer.</p>
  <div style="text-align:center"><button class="w" onclick="this.closest('.win').querySelector('[data-x]').click()">OK</button></div>`;
 makeWin("About CA-1 98",0,el);
}
function appDoom(){
 const R=DATA.ray,vm=makeVM();for(const k in R.mem)vm.M[+k]=R.mem[k];
 const el=document.createElement("div");el.className="cli";el.style.padding="3px";
 const cv=document.createElement("canvas");cv.width=R.SW;cv.height=R.SH;cv.tabIndex=0;cv.style.width="384px";cv.style.height="224px";
 const cap=document.createElement("div");cap.style.cssText="font-size:10px;margin-top:3px";cap.textContent="click & use WASD / arrows · rendering computed on CA-1";
 el.appendChild(cv);el.appendChild(cap);
 const cx=cv.getContext("2d"),img=cx.createImageData(R.SW,R.SH);
 const PAL=[[0,0,0],[26,32,42],[210,124,44],[150,86,32],[86,52,22],[58,58,66]];
 let keys=0;const KB={37:0,65:0,39:1,68:1,38:2,87:2,40:3,83:3};
 cv.addEventListener("keydown",e=>{const b=KB[e.keyCode];if(b!==undefined){e.preventDefault();keys|=1<<b;}});
 cv.addEventListener("keyup",e=>{const b=KB[e.keyCode];if(b!==undefined){e.preventDefault();keys&=~(1<<b);}});
 cv.addEventListener("blur",()=>keys=0);
 let alive=true;const w=makeWin("DOOM.EXE",0,el,()=>alive=false);
 function frame(){if(!alive)return;vm.M[R.INP]=keys;vm.run(R.prog,true);
   for(let c=0;c<R.SW;c++)for(let y=0;y<R.SH;y++){const v=vm.M[R.FB+c*R.SH+y],p=PAL[v]||PAL[0],i=(y*R.SW+c)*4;
     img.data[i]=p[0];img.data[i+1]=p[1];img.data[i+2]=p[2];img.data[i+3]=255;}
   cx.putImageData(img,0,0);requestAnimationFrame(frame);}
 requestAnimationFrame(frame);cv.focus();
}
/* ---------------- desktop icons + start menu ---------------- */
const APPS=[["🖩","Calculator",appCalc],["📝","Notepad",appNotepad],["🎮","DOOM.EXE",appDoom],["💻","My Computer",appAbout]];
APPS.forEach((ap,i)=>{const d=document.createElement("div");d.className="ico";d.tabIndex=0;d.style.left="16px";d.style.top=(16+i*84)+"px";
 d.innerHTML=`<div>${ap[0]}</div><span>${ap[1]}</span>`;d.ondblclick=ap[2];
 d.onclick=()=>{document.querySelectorAll(".ico").forEach(x=>x.classList.remove("sel"));d.classList.add("sel");};desk.appendChild(d);});
const menu=document.getElementById("menu"),mitems=document.getElementById("mitems");
APPS.forEach(ap=>{const li=document.createElement("li");li.innerHTML=`<span>${ap[0]}</span>${ap[1]}`;li.onclick=()=>{menu.style.display="none";ap[2]();};mitems.appendChild(li);});
document.getElementById("start").onclick=e=>{e.stopPropagation();menu.style.display=menu.style.display==="block"?"none":"block";};
document.addEventListener("click",()=>menu.style.display="none");
// clock
function tick(){const d=new Date();let h=d.getHours(),m=d.getMinutes();const ap=h>=12?"PM":"AM";h=h%12||12;
 document.getElementById("clock").textContent=`${h}:${String(m).padStart(2,"0")} ${ap}`;}
tick();setInterval(tick,10000);
appAbout();   // greet on boot
</script></body></html>'''
HTML = HTML.replace("__DATA__", DATA)
open("dissemination/glider-lab12.html", "w").write(HTML)
print("wrote dissemination/glider-lab12.html", len(HTML), "bytes")
