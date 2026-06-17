#!/usr/bin/env python3
# build_lab23.py — glider-lab23.html: a WIDE-WORD CA computer in the browser, bypassing JS's 32-bit
# limit with BigInt. The VM mirrors ca1sys make_machine("CA-4") (1024-bit registers, the verified CA
# adder tiled 1024 deep) but carries each register as a JS BigInt, so it computes integers no host
# register can hold. Workload: N! for a runtime N (read from memory), shown as an exact decimal.
# Honest: BigInt is the bypass (arbitrary precision + big-value bitwise ops); the cost is speed and
# that you can't mix BigInt with Number (addresses/memory stay byte Numbers; registers are BigInt).
import json
from ca1sys import asm, make_machine

WBITS = 1024
MEM   = 0x400                      # 1 KB is plenty (six 1024-bit words)
NP, R, I, T0, T1, T2 = 0x00, 0x80, 0x100, 0x180, 0x200, 0x280   # 128-byte (1024-bit) words

def fact_program():
    # result=1; i=N; while i>=2: result*=i (shift-add); i-=1.  N read from NP.
    L = []; a = L.append
    a(("LDI", 1)); a(("STW", R)); a(("LDW", NP)); a(("STW", I))
    a(("fl:",)); a(("LDW", I)); a(("CMPI", 2)); a(("JNC", "fd"))
    a(("LDI", 0)); a(("STW", T0)); a(("LDW", R)); a(("STW", T1)); a(("LDW", I)); a(("STW", T2))   # T0=0,a=R,b=i
    a(("ml:",)); a(("LDW", T2)); a(("JZ", "md"))
    a(("LDW", T2)); a(("ANDI", 1)); a(("JZ", "mn")); a(("LDW", T0)); a(("ADDW", T1)); a(("STW", T0)); a(("mn:",))
    a(("LDW", T1)); a(("SHL",)); a(("STW", T1)); a(("LDW", T2)); a(("SHR",)); a(("STW", T2)); a(("JMP", "ml"))
    a(("md:",)); a(("LDW", T0)); a(("STW", R))
    a(("LDW", I)); a(("SUBI", 1)); a(("STW", I)); a(("JMP", "fl"))
    a(("fd:",)); a(("LDW", R)); a(("HLT",))
    return asm(L)

PROG, _ = fact_program()

if __name__ == "__main__":
    import math
    # reference: the 1024-bit CA-4 machine computes N! exactly
    for N in (50, 100, 170):
        m = make_machine("CA-4", memsize=MEM); m.M[NP] = N    # N<256 -> one byte
        m.run((PROG, {}), max_i=50_000_000)
        ok = (m.A == math.factorial(N))
        print(f"CA-4 (1024-bit) {N}! exact: {ok}  ({m.A.bit_length()} bits, {len(str(m.A))} digits)")

    OS = dict(prog=[[op, (arg if arg is not None else 0)] for op, arg in PROG],
              WB=WBITS, MEM=MEM, NP=NP, R=R)
    HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wide-word CA computer — bypassing JS's 32-bit limit with BigInt</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:860px;margin:0 auto;padding:18px}
 h1{font-size:21px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:13px}
 p{color:var(--mut)} .bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:12px 0;background:#161b22;border:1px solid #2a3340;border-radius:8px;padding:10px}
 input{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:6px 8px;width:80px;font-family:ui-monospace,monospace}
 button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:6px 12px;cursor:pointer}
 .out{font-family:ui-monospace,monospace;font-size:13px;background:#0b0e13;border:1px solid #2a3340;border-radius:8px;padding:12px;word-break:break-all;color:var(--a);min-height:40px}
 .meta{font-size:12px;color:var(--mut);margin-top:6px}.meta b{color:var(--b)}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:14px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}
</style></head><body><div class="wrap">
 <h1>Wide-word CA computer <small>— a 1024-bit machine in the browser, via BigInt</small></h1>
 <p>JavaScript's bitwise operators are 32-bit and its Numbers lose precision past 2&#8309;&#179;. The bypass is
 <b>BigInt</b>: this VM keeps every register as an arbitrary-precision BigInt, mirroring the 1024-bit
 <code>CA-4</code> machine (the genuine CA adder tiled 1024 deep). It computes <b>N!</b> — exact integers far
 wider than any host register. <span id="selftest"></span></p>
 <div class="bar"><label>compute&nbsp; N! &nbsp;for N =</label><input type="number" id="n" value="50" min="1" max="170">
  <button id="go">run on CA-4</button><span class="meta" id="time"></span></div>
 <div class="out" id="out">press run</div>
 <div class="meta" id="meta"></div>
 <p class="note"><b>Honest scope:</b> BigInt is the real bypass (arbitrary precision; bitwise ops work on big
 values). The cost: BigInt is slower than Number, and you can't mix BigInt with Number — so the machine's
 memory stays a byte array (Numbers) and only the registers are BigInt. The CA <i>datapath</i> has no width
 limit at all — a wider adder is just more tiled gliders (the 1-bit CA full-adder rippled), verified
 width-parametric in <code>cacpu.verify_adder_ca</code>. As always: capability scales, the physical CA's speed
 never — this VM is fast only because it carries the value in a BigInt instead of grinding 1024 gliders.</p>
</div>
<script>
"use strict";
const OS=__OS__;
/* BigInt CA VM: mirrors ca1sys CA-4 (1024-bit) with arbitrary-precision registers */
function makeVM(){const M=new Uint8Array(OS.MEM),WB=BigInt(OS.WB),MASK=(1n<<WB)-1n,BPW=OS.WB>>3,NM=OS.MEM-1;
 let A=0n,PC=0,Z=1,C=0,N=0;
 const set=(v,c)=>{const w=v&MASK;Z=(w===0n)?1:0;N=Number((w>>(WB-1n))&1n);if(c!==undefined)C=c;return w;};
 const wrd=d=>{let r=0n;for(let i=0;i<BPW;i++)r|=BigInt(M[(d+i)&NM])<<BigInt(8*i);return r;};
 const stw=(d,a)=>{for(let i=0;i<BPW;i++)M[(d+i)&NM]=Number((a>>BigInt(8*i))&255n);};
 function run(prog,cap){let n=0;while(n<cap){const Ii=prog[PC],op=Ii[0],arg=Ii[1];PC++;n++;const a=A;
   switch(op){
    case"LDI":A=set(BigInt(arg));break;case"LDW":A=set(wrd(arg));break;case"STW":stw(arg,a);break;
    case"ADDW":{const w=wrd(arg);A=set(a+w,(a+w)>MASK?1:0);break;}case"SUBW":{const w=wrd(arg);A=set(a-w,a>=w?1:0);break;}
    case"ADDI":{const w=BigInt(arg);A=set(a+w,(a+w)>MASK?1:0);break;}case"SUBI":{const w=BigInt(arg);A=set(a-w,a>=w?1:0);break;}
    case"ANDI":A=set(a&BigInt(arg));break;
    case"CMPI":{const w=BigInt(arg);set(a-w,a>=w?1:0);break;}case"CMPW":{const w=wrd(arg);set(a-w,a>=w?1:0);break;}
    case"SHL":A=set(a<<1n,Number((a>>(WB-1n))&1n));break;case"SHR":A=set(a>>1n,Number(a&1n));break;
    case"JMP":PC=arg;break;case"JZ":if(Z)PC=arg;break;case"JNZ":if(!Z)PC=arg;break;case"JC":if(C)PC=arg;break;case"JNC":if(!C)PC=arg;break;
    case"NOP":break;case"FRAME":return n;case"HLT":return n;default:throw"op "+op;}}return n;}
 return {run,setN:v=>stw(OS.NP,BigInt(v)),getR:()=>wrd(OS.R)};}
function compute(){const N=Math.max(1,Math.min(170,parseInt(document.getElementById("n").value)||1));
 const vm=makeVM();vm.setN(N);const t0=performance.now();const instr=vm.run(OS.prog,50000000);const t1=performance.now();
 const R=vm.getR(),s=R.toString();
 document.getElementById("out").textContent=N+"! = "+s;
 document.getElementById("meta").innerHTML="<b>"+s.length+"</b> digits · <b>"+R.toString(2).length+"</b> bits · "+
   instr.toLocaleString()+" CA-4 instructions · "+(t1-t0).toFixed(1)+" ms  (a 64-bit register holds at most 20 digits)";
 document.getElementById("time").textContent="";}
document.getElementById("go").onclick=compute;
/* self-test: 20! is known */
(function(){const vm=makeVM();vm.setN(20);vm.run(OS.prog,50000000);
 document.getElementById("selftest").textContent=vm.getR()===2432902008176640000n?"":"  [self-test FAILED]";})();
compute();
</script></body></html>'''
    HTML = HTML.replace("__OS__", json.dumps(OS, separators=(",", ":")))
    open("dissemination/glider-lab23.html", "w").write(HTML)
    print("wrote dissemination/glider-lab23.html", len(HTML), "bytes")
