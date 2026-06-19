#!/usr/bin/env python3
# caregen.py — ACTIVE SIGNAL REGENERATION on the CA: the element that breaks the single-level barrier of
# pure carrier-flow logic (caplace composes only routed multi-input NOR because a gate whose output is "1"
# emits no carrier).  The fix is an active, value-holding element: the mutual-annihilation LATCH used as a
# REGENERATING INVERTER.
#
# Mechanism (write-once timing).  The newton latch territory is first-writer-wins (flipflop.py: SET holds,
# RESET can't overpower).  Turn that into NOT: on input=1 the RESET species writes FIRST and LOCKS the latch
# to "0"; on input=0 the pull-up species writes LATE and sets "1".  The latch then HOLDS and owns its
# territory — a fresh, restored output (regeneration), not an attenuated carrier.
#
# With NOT in hand the substrate is unrestricted: NAND (verified, gatecell.py) + NOT = AND, and any boolean.
# Here: verify NOT (100% held-out), then a CLOCKED two-level circuit AND = NOT(NAND(a,b)) — a function NO
# single carrier-flow chamber can produce.  Honest scope: the per-gate computation is the CA (NAND latch +
# the regenerating inverter latch); the clock that latches values between stages is orchestrated, exactly
# like CA-1's control unit (compose.py).  This closes "regeneration" — multi-LEVEL logic now composes.
import numpy as np, rulehub
import gatecell as GC

def newton_lut(cx, cy, span, it=160, side=128):
    st = span/side; ox = cx-st*side*.5; oy = cy-st*side*.5
    gx, gy = np.meshgrid(ox+np.arange(side)*st, oy+np.arange(side)*st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l
L = newton_lut(-0.255, -0.077, 0.270)                # the write-once latch territory rule
SIDE = 48                                             # was 64; NOT is 100% held-out at 48 (caregen_opt.py)
NB, NI = 18, 14                                       # NAND-tuned bias/input (gatecell.py / compose.py)

def inverter(inval, pullA=False, seed=1, hold=10):    # hold was 40; 100% held-out at 10 (caregen_opt.py)
    """Regenerating NOT.  input=1 -> RESET writes first -> latch locks "0"; input=0 -> pull-up writes late
    -> "1".  Returns the held latch value (= pull-up species dominant)."""
    rng = np.random.default_rng(seed)
    A = np.zeros((SIDE, SIDE), np.uint8); B = np.zeros((SIDE, SIDE), np.uint8)
    c = SIDE // 2
    PU, RST = (A, B) if pullA else (B, A)
    def step(ticks, inj=None):
        nonlocal A, B
        for t in range(ticks):
            if inj is not None and t < 6: inj[c-5:c+5, c-5:c+5] = rng.integers(1, 4, (10, 10))
            A = L[rulehub.hex_key(A.astype(np.int64))].astype(np.uint8)
            B = L[rulehub.hex_key(B.astype(np.int64))].astype(np.uint8)
            both = (A > 0) & (B > 0); A[both] = 0; B[both] = 0
    if inval: step(16, inj=RST)                       # input=1 writes FIRST -> locks "0"
    else:     step(16)
    step(hold)
    step(16, inj=PU)                                  # pull-up writes LATE -> "1" unless already locked
    step(hold)
    a = int((A > 0).sum()); b = int((B > 0).sum())
    return 1 if ((a > b) == pullA) else 0

def NOT(x, seed):  return inverter(x, seed=seed)
def NAND(a, b, seed): return GC.decide(int(a), int(b), NB, NI, seed=seed)
def AND(a, b, seed):  return NOT(NAND(a, b, seed), seed + 1)      # clocked two-level: NAND then NOT
def OR(a, b, seed):   return NAND(NOT(a, seed), NOT(b, seed + 1), seed + 2)   # OR = NAND(NOT a, NOT b)

def acc(fn, ref, seeds):
    ok = tot = 0; tbl = {}
    for a in (0, 1):
        for b in (0, 1):
            bits = [fn(a, b, s) for s in seeds]; tbl[(a, b)] = int(round(np.mean(bits)))
            ok += sum(x == ref(a, b) for x in bits); tot += len(bits)
    return ok/tot, tbl

if __name__ == "__main__":
    print("caregen — active regeneration on the CA: the latch-inverter (NOT) + multi-level composition\n")
    h0 = [inverter(0, seed=s) for s in range(100, 110)]; h1 = [inverter(1, seed=s) for s in range(100, 110)]
    notacc = (sum(x == 1 for x in h0) + sum(x == 0 for x in h1)) / 20
    print(f"  regenerating inverter  NOT:  held-out acc {100*notacc:.0f}%   (0->{int(round(np.mean(h0)))}, 1->{int(round(np.mean(h1)))})")
    aa, at = acc(AND, lambda a, b: a & b, range(100, 106))
    print(f"  CLOCKED 2-level  AND = NOT(NAND):  held-out acc {100*aa:.0f}%   truth {at}")
    oa, ot = acc(OR, lambda a, b: a | b, range(100, 106))
    print(f"  CLOCKED 2-level  OR  = NAND(NOT,NOT): held-out acc {100*oa:.0f}%   truth {ot}")
    if notacc >= 0.95 and aa >= 0.95 and oa >= 0.95:
        print("\n  -> REGENERATION CLOSED: the latch-inverter restores+inverts a signal, so multi-LEVEL logic")
        print("     composes (AND, OR — impossible from a single carrier-flow chamber). Per-gate = CA (NAND")
        print("     latch + inverter latch); the inter-stage clock is orchestrated, like CA-1's control unit.")
