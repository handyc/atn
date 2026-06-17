#!/usr/bin/env python3
# build_lab23.py — glider-lab23.html: a WIDE-WORD CA computer in the browser, bypassing JS's 32-bit
# limit with BigInt. The VM mirrors ca1sys (registers carried as JS BigInt = arbitrary precision), so
# it computes integers no host register can hold. Two workloads, each genuine CA machine code:
#   * Factorial — N! on a 1024-bit machine (exact, up to 170! = 307 digits).
#   * RSA       — encrypt + decrypt a message via modular exponentiation (square-and-multiply with a
#                 shift-subtract modulo) on a 256-bit machine, with a 128-bit key. The core of RSA,
#                 running on the cellular-automaton CPU.
# Honest: BigInt is the bypass; the cost is speed + you can't mix BigInt with Number (memory/addresses
# stay byte Numbers, registers are BigInt). The CA datapath itself has no width limit (the adder tiles;
# verified at 256/512-bit with the real gates on ALICE). JS isn't runnable in the build env, so the VM
# is checked by a Python mirror of its exact ops + static checks, as with the other labs.
import json, random
from ca1sys import asm, make_machine

# ---------- factorial machine (1024-bit) ----------
FWB, FMEM = 1024, 0x400
F_NP, F_R, F_I, F_T0, F_T1, F_T2 = 0x00, 0x80, 0x100, 0x180, 0x200, 0x280
def fact_program():
    L = []; a = L.append
    a(("LDI", 1)); a(("STW", F_R)); a(("LDW", F_NP)); a(("STW", F_I))
    a(("fl:",)); a(("LDW", F_I)); a(("CMPI", 2)); a(("JNC", "fd"))
    a(("LDI", 0)); a(("STW", F_T0)); a(("LDW", F_R)); a(("STW", F_T1)); a(("LDW", F_I)); a(("STW", F_T2))
    a(("ml:",)); a(("LDW", F_T2)); a(("JZ", "md"))
    a(("LDW", F_T2)); a(("ANDI", 1)); a(("JZ", "mn")); a(("LDW", F_T0)); a(("ADDW", F_T1)); a(("STW", F_T0)); a(("mn:",))
    a(("LDW", F_T1)); a(("SHL",)); a(("STW", F_T1)); a(("LDW", F_T2)); a(("SHR",)); a(("STW", F_T2)); a(("JMP", "ml"))
    a(("md:",)); a(("LDW", F_T0)); a(("STW", F_R))
    a(("LDW", F_I)); a(("SUBI", 1)); a(("STW", F_I)); a(("JMP", "fl"))
    a(("fd:",)); a(("LDW", F_R)); a(("HLT",))
    return asm(L)

# ---------- RSA / modexp machine (256-bit; products of a 128-bit modulus fit) ----------
RWB, RMEM = 256, 0x8000
BASE, EXP, MOD, RES, MB, P, R, MA, MBV, BITC, MMX, MMY, MMO = (i*0x20 for i in range(13))
def modexp_program():
    L = []; a = L.append
    a(("JMP", "modexp"))
    # modmul: MMO = (MMX * MMY) mod MOD  (shift-add multiply, then shift-subtract long-division modulo)
    a(("modmul:",))
    a(("LDI", 0)); a(("STW", P)); a(("LDW", MMX)); a(("STW", MA)); a(("LDW", MMY)); a(("STW", MBV))
    a(("mm:",)); a(("LDW", MBV)); a(("JZ", "mmd"))
    a(("LDW", MBV)); a(("ANDI", 1)); a(("JZ", "mmn")); a(("LDW", P)); a(("ADDW", MA)); a(("STW", P)); a(("mmn:",))
    a(("LDW", MA)); a(("SHL",)); a(("STW", MA)); a(("LDW", MBV)); a(("SHR",)); a(("STW", MBV)); a(("JMP", "mm"))
    a(("mmd:",))
    a(("LDI", 0)); a(("STW", R)); a(("LDI", RWB)); a(("STW", BITC))
    a(("mdl:",)); a(("LDW", BITC)); a(("JZ", "mddone"))
    a(("LDW", P)); a(("SHL",)); a(("STW", P)); a(("JC", "m1"))
    a(("LDW", R)); a(("SHL",)); a(("STW", R)); a(("JMP", "mc"))
    a(("m1:",)); a(("LDW", R)); a(("SHL",)); a(("ADDI", 1)); a(("STW", R))
    a(("mc:",)); a(("LDW", R)); a(("CMPW", MOD)); a(("JNC", "mn2")); a(("LDW", R)); a(("SUBW", MOD)); a(("STW", R))
    a(("mn2:",)); a(("LDW", BITC)); a(("SUBI", 1)); a(("STW", BITC)); a(("JMP", "mdl"))
    a(("mddone:",)); a(("LDW", R)); a(("STW", MMO)); a(("RET",))
    # modexp: RES = BASE^EXP mod MOD  (square-and-multiply)
    a(("modexp:",))
    a(("LDI", 1)); a(("STW", RES)); a(("LDW", BASE)); a(("STW", MB))
    a(("el:",)); a(("LDW", EXP)); a(("JZ", "ed"))
    a(("LDW", EXP)); a(("ANDI", 1)); a(("JZ", "es"))
    a(("LDW", RES)); a(("STW", MMX)); a(("LDW", MB)); a(("STW", MMY)); a(("CALL", "modmul")); a(("LDW", MMO)); a(("STW", RES))
    a(("es:",)); a(("LDW", MB)); a(("STW", MMX)); a(("LDW", MB)); a(("STW", MMY)); a(("CALL", "modmul")); a(("LDW", MMO)); a(("STW", MB))
    a(("LDW", EXP)); a(("SHR",)); a(("STW", EXP)); a(("JMP", "el"))
    a(("ed:",)); a(("LDW", RES)); a(("HLT",))
    return asm(L)

# ---------- a small RSA key (128-bit modulus), generated at build time ----------
def _isprime(n, rng):
    if n < 2: return False
    for p in (2,3,5,7,11,13,17,19,23,29,31,37):
        if n % p == 0: return n == p
    d=n-1; s=0
    while d % 2 == 0: d//=2; s+=1
    for _ in range(20):
        a=rng.randrange(2, n-1); x=pow(a,d,n)
        if x in (1,n-1): continue
        for _ in range(s-1):
            x=x*x%n
            if x==n-1: break
        else: return False
    return True
def _genprime(bits, rng):
    while True:
        c=rng.getrandbits(bits)|(1<<(bits-1))|1
        if _isprime(c,rng): return c
_rng=random.Random(20260617)
P_,Q_=_genprime(64,_rng),_genprime(64,_rng)
N_=P_*Q_; PHI=(P_-1)*(Q_-1); E_=65537; D_=pow(E_,-1,PHI)
MSG=_rng.randrange(2, N_)

if __name__ == "__main__":
    import math
    FP, _ = fact_program(); MP, _ = modexp_program()
    # verify factorial on the 1024-bit reference
    for N in (50, 170):
        m = make_machine("CA-2", word_bits=FWB, memsize=FMEM); m.M[F_NP] = N
        m.run((FP, {}), max_i=80_000_000)
        print(f"fact ref: {N}! exact={m.A==math.factorial(N)} ({len(str(m.A))} digits)")
    # verify RSA round-trip on the 256-bit reference
    def modexp(base, exp, mod):
        m = make_machine("CA-2", word_bits=RWB, memsize=RMEM)
        for addr, v in ((BASE, base), (EXP, exp), (MOD, mod)):
            for i in range(RWB//8): m.M[addr+i] = (v >> (8*i)) & 0xFF
        m.run((MP, {}), max_i=400_000_000)
        return m.A
    ct = modexp(MSG, E_, N_); dec = modexp(ct, D_, N_)
    print(f"RSA ref: n={N_} ({N_.bit_length()} bits)")
    print(f"  encrypt msg^e mod n == pow: {ct==pow(MSG,E_,N_)} ; decrypt ct^d mod n == msg: {dec==MSG}")

    OS = dict(
        fact=dict(prog=[[op,(arg if arg is not None else 0)] for op,arg in FP], WB=FWB, MEM=FMEM, NP=F_NP, R=F_R),
        rsa=dict(prog=[[op,(arg if arg is not None else 0)] for op,arg in MP], WB=RWB, MEM=RMEM,
                 BASE=BASE, EXP=EXP, MOD=MOD, RES=RES,
                 n=str(N_), e=str(E_), d=str(D_), msg=str(MSG)))
    HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wide-word CA computer — factorials & RSA via BigInt</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#5ed18a;--no:#ff7a7a}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:880px;margin:0 auto;padding:18px}
 h1{font-size:21px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:13px}
 h2{font-size:15px;margin:18px 0 6px;color:var(--b)} p{color:var(--mut)}
 .card{background:#161b22;border:1px solid #2a3340;border-radius:10px;padding:12px;margin-top:10px}
 .bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:4px 0}
 input{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:6px 8px;font-family:ui-monospace,monospace}
 input.n{width:80px} button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:6px 12px;cursor:pointer}
 .out{font-family:ui-monospace,monospace;font-size:12.5px;background:#0b0e13;border:1px solid #2a3340;border-radius:8px;padding:10px;word-break:break-all;color:var(--a);margin-top:8px}
 .meta{font-size:12px;color:var(--mut);margin-top:4px}.meta b{color:var(--b)} .ok{color:var(--ok)}.no{color:var(--no)}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:14px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}
</style></head><body><div class="wrap">
 <h1>Wide-word CA computer <small>— factorials &amp; RSA, via BigInt</small></h1>
 <p>JavaScript bitwise ops are 32-bit and Numbers lose precision past 2&#8309;&#179;. The bypass is <b>BigInt</b>:
 this VM carries every register as an arbitrary-precision BigInt, so the cellular-automaton CPU computes
 integers no host register can hold. <span id="selftest"></span></p>

 <div class="card"><h2>Factorial — on a 1024-bit machine</h2>
  <div class="bar"><label>N! for N =</label><input class="n" type="number" id="n" value="50" min="1" max="170">
   <button id="gofact">compute</button></div>
  <div class="out" id="fout">press compute</div><div class="meta" id="fmeta"></div></div>

 <div class="card"><h2>RSA — encrypt &amp; decrypt on the CA (256-bit machine, 128-bit key)</h2>
  <div class="meta">modulus n = <span id="rn"></span></div>
  <div class="bar" style="margin-top:6px"><label>message m =</label><input type="text" id="msg" style="width:280px">
   <button id="gorsa">encrypt &amp; decrypt</button></div>
  <div class="out" id="rout">press encrypt &amp; decrypt</div><div class="meta" id="rmeta"></div></div>

 <p class="note"><b>How:</b> RSA is just <code>m<sup>e</sup> mod n</code> then <code>c<sup>d</sup> mod n</code>.
 The CA runs square-and-multiply with a shift-subtract modulo — multiply, modulo, and the underlying add are
 all CA machine code (the genuine CA adder, here carried in BigInt so the browser can keep up). The CA datapath
 has no width limit: a wider adder is just more tiled gliders — verified at <b>256-bit and 512-bit with the real
 gates on the ALICE cluster</b> (≈145 s and ≈287 s per add). BigInt's cost is speed, and you can't mix it with
 Number — so memory/addresses stay byte Numbers and only registers are BigInt. (JS isn't runnable in the build
 env; the VM is checked by a Python mirror of its exact ops + static checks, as with the other labs.)</p>
</div>
<script>
"use strict";
const OS=__OS__;
/* BigInt CA VM: arbitrary-precision registers; mirrors ca1sys. cfg = {prog,WB,MEM} */
function makeVM(cfg){const M=new Uint8Array(cfg.MEM),WB=BigInt(cfg.WB),MASK=(1n<<WB)-1n,BPW=cfg.WB>>3,NM=cfg.MEM-1;
 let A=0n,SP=cfg.MEM-1,PC=0,Z=1,C=0,N=0;
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
    case"CALL":M[SP]=PC&255;M[SP-1]=(PC>>8)&255;SP-=2;PC=arg;break;case"RET":SP+=2;PC=(M[SP-1]<<8)|M[SP];break;
    case"NOP":break;case"FRAME":return n;case"HLT":return n;default:throw"op "+op;}}return n;}
 return {run,setW:(d,v)=>stw(d,v),getW:d=>wrd(d)};}
const $=id=>document.getElementById(id);
/* factorial */
function fact(){const C=OS.fact,N=Math.max(1,Math.min(170,parseInt($("n").value)||1));
 const vm=makeVM(C);vm.setW(C.NP,BigInt(N));const t0=performance.now();const k=vm.run(C.prog,80000000);const ms=performance.now()-t0;
 const r=vm.getW(C.R),s=r.toString();
 $("fout").textContent=N+"! = "+s;
 $("fmeta").innerHTML="<b>"+s.length+"</b> digits · <b>"+r.toString(2).length+"</b> bits · "+k.toLocaleString()+" instr · "+ms.toFixed(0)+" ms";}
/* RSA */
const RN=BigInt(OS.rsa.n),RE=BigInt(OS.rsa.e),RD=BigInt(OS.rsa.d);
function modexp(base,exp){const C=OS.rsa,vm=makeVM(C);vm.setW(C.BASE,base);vm.setW(C.EXP,exp);vm.setW(C.MOD,RN);
 vm.run(C.prog,400000000);return vm.getW(C.RES);}
function rsa(){let m;try{m=BigInt($("msg").value)%RN;}catch(e){$("rout").textContent="enter an integer message";return;}
 const t0=performance.now();const ct=modexp(m,RE);const dec=modexp(ct,RD);const ms=performance.now()-t0;
 const okd=(dec===m);
 $("rout").innerHTML="m  = "+m.toString()+"<br>c  = m^e mod n = "+ct.toString()+"<br>m' = c^d mod n = "+dec.toString();
 $("rmeta").innerHTML="round-trip "+(okd?"<span class='ok'>m' = m ✓</span>":"<span class='no'>FAILED</span>")+" · "+ms.toFixed(0)+" ms · all on the CA machine";}
$("gofact").onclick=fact;$("gorsa").onclick=rsa;
$("rn").textContent=RN.toString();$("msg").value=OS.rsa.msg;
/* self-test: 20! known + RSA round-trip */
(function(){const C=OS.fact,vm=makeVM(C);vm.setW(C.NP,20n);vm.run(C.prog,80000000);
 const f=vm.getW(C.R)===2432902008176640000n;
 const m=BigInt(OS.rsa.msg)%RN;const ok=modexp(modexp(m,RE),RD)===m;
 $("selftest").textContent=(f&&ok)?"":"  [self-test FAILED]";})();
fact();rsa();
</script></body></html>'''
    HTML = HTML.replace("__OS__", json.dumps(OS, separators=(",", ":")))
    open("dissemination/glider-lab23.html", "w").write(HTML)
    print("wrote dissemination/glider-lab23.html", len(HTML), "bytes")
