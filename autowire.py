#!/usr/bin/env python3
# autowire.py — AUTONOMOUS WIRING (no controller). The gate's inputs are not injected at
# the gate; they are placed at the far LEFT and must PROPAGATE across a channel to the
# gate on the right, entirely within one continuous CA run. Mechanism: the input/signal
# layer Z uses a SPREADING rule (a territory front travels east = a wire); the gate's
# bias layer O is a stable latch layer at the right; mutual annihilation decides. If any
# input was placed (left), Z spreads east, reaches the gate, and beats the bias -> output
# 0; if no input, Z never starts, bias holds -> output 1. That is NOR(A,B) with the inputs
# AUTONOMOUSLY WIRED in. Verified across seeds + held-out. Self-contained: rulehub+numpy.
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

LZ = newton_lut(-0.255, -0.077, 0.270)    # spreading "wire" rule (fills from a seed)
LO = newton_lut(-0.105, -0.135, 0.152)     # stable latch layer (the gate's bias)
H, W = 36, 96

def gate(A, B, T=170, seed=0):
    rng = np.random.default_rng(seed)
    Z = np.zeros((H, W), np.uint8); O = np.zeros((H, W), np.uint8)
    def s(arr, r, c, sz=8): arr[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = rng.integers(1, 4, (sz, sz))
    if A: s(Z, 11, 8)                       # input A at far LEFT (must travel ~76 cols east)
    if B: s(Z, 25, 8)                       # input B at far LEFT
    for t in range(T):
        if t < 40: s(O, 18, 86, 10)         # the gate's constant bias on the RIGHT
        Z = LZ[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        O = LO[rulehub.hex_key(O.astype(np.int64))].astype(np.uint8)
        both = (Z > 0) & (O > 0); Z[both] = 0; O[both] = 0
        if (Z > 0).sum() + (O > 0).sum() > 0.92 * H * W: return None
    reg = slice(78, 96)                     # read the GATE region (right)
    mo = int((O[:, reg] > 0).sum()); mz = int((Z[:, reg] > 0).sum())
    return 1 if mo > mz else 0

NOR = {(0,0):1,(0,1):0,(1,0):0,(1,1):0}
def truth(seeds):
    ok = tot = 0; tbl = {}
    for k in NOR:
        bits = [gate(k[0], k[1], seed=s+5*(k[0]+2*k[1])) for s in seeds]
        bits = [b for b in bits if b is not None]
        if not bits: return 0.0, {}
        tbl[k] = int(round(np.mean(bits))); ok += sum(b == NOR[k] for b in bits); tot += len(bits)
    return ok/tot, tbl

def main():
    print("autonomous-input NOR gate: inputs at LEFT propagate ~76 cells to the gate at RIGHT\n")
    tr, tbl = truth(range(8)); ho, tblh = truth(range(100, 110))
    print(f"  TRAIN  acc {100*tr:.0f}%  truth { {f'{k[0]}{k[1]}':v for k,v in tbl.items()} }")
    print(f"  HELD-OUT acc {100*ho:.0f}%  truth { {f'{k[0]}{k[1]}':v for k,v in tblh.items()} }")
    if ho >= 0.95:
        print("\n  -> AUTONOMOUS WIRING WORKS: the gate's inputs arrive entirely via in-substrate")
        print("     propagation (no controller), and the gate computes NOR. A universal gate with")
        print("     self-wired inputs -> the foundation for a controller-free CA circuit.")
    else:
        print("\n  -> not clean yet: the wire (spreading front) doesn't reliably deliver the input")
        print("     to the gate in time / with the right margin. Autonomous wiring needs tuning.")

if __name__ == "__main__":
    main()
