#!/usr/bin/env python3
# autowire2.py — CONFINED autonomous wire between two gates (no controller, no flooding).
# WALLS (forced-0 cells) isolate chamber1 (gate1) and chamber2 (gate2), connected only by
# a narrow CHANNEL. Gate1 computes NOR(A,B): inputs seed the spreading layer Z in chamber1,
# bias O1 competes; if NOR=0, Z fills chamber1 and flows THROUGH THE CHANNEL into chamber2
# (the wire); if NOR=1, Z dies in chamber1 and nothing flows. Chamber2 has its own bias O2;
# the arriving Z (or its absence) decides gate2's reading. So gate2 reproduces gate1's
# output, transported across a confined channel, in one continuous run. Reading gate2 ==
# NOR(A,B) (held-out) => an autonomous, confined gate-to-gate wire. rulehub + numpy.
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

LZ = newton_lut(-0.255, -0.077, 0.270)     # spreading carrier (wire)
LO = newton_lut(-0.105, -0.135, 0.152)     # stable bias
H, W = 40, 96
# WALLS: everything is wall except chamber1 (cols 4..30), channel (cols 30..52 at rows 17..23),
# chamber2 (cols 54..92). Cells in walls are forced to 0 each step (confine the flow).
OPEN = np.zeros((H, W), bool)
OPEN[4:36, 4:30] = True                      # chamber1
OPEN[17:23, 30:54] = True                    # channel
OPEN[4:36, 54:92] = True                     # chamber2
WALL = ~OPEN

def run(A, B, C, T=200, seed=0):
    rng = np.random.default_rng(seed)
    Z = np.zeros((H, W), np.uint8); O = np.zeros((H, W), np.uint8)
    def s(arr, r, c, sz=7): arr[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = rng.integers(1, 4, (sz, sz))
    if A: s(Z, 12, 10)                       # inputs into chamber1's Z (gate1)
    if B: s(Z, 28, 10)
    if C: s(Z, 12, 62)   # fresh input C injected at GATE2 (chamber2)
    for t in range(T):
        if t < 50:
            s(O, 20, 16, 7)                  # gate1 bias O1 (chamber1)
            s(O, 20, 80, 9)                  # gate2 bias O2 (chamber2)
        Z = LZ[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        O = LO[rulehub.hex_key(O.astype(np.int64))].astype(np.uint8)
        Z[WALL] = 0; O[WALL] = 0             # confine to chambers + channel
        both = (Z > 0) & (O > 0); Z[both] = 0; O[both] = 0
    reg = (slice(4, 36), slice(78, 92))      # read GATE2's far side
    return 1 if int((O[reg] > 0).sum()) > int((Z[reg] > 0).sum()) else 0

NOR3 = {(a,b,c):(1 if a==0 and b==0 and c==0 else 0) for a in (0,1) for b in (0,1) for c in (0,1)}
def truth(seeds):
    ok = tot = 0; tbl = {}
    for k in NOR3:
        bits = [run(k[0], k[1], k[2], seed=s+5*(k[0]+2*k[1]+4*k[2])) for s in seeds]
        tbl["".join(map(str,k))] = int(round(np.mean(bits))); ok += sum(b == NOR3[k] for b in bits); tot += len(bits)
    return ok/tot, tbl

def main():
    print("AUTONOMOUS 2-GATE CIRCUIT: gate1 NOR(A,B) -> wire -> gate2 combines with C = NOR(A,B,C)\n")
    tr, tbl = truth(range(8)); ho, tblh = truth(range(100, 110))
    print(f"  TRAIN    acc {100*tr:.0f}%")
    print(f"  HELD-OUT acc {100*ho:.0f}%  truth(ABC->out): {tblh}")
    if ho >= 0.95:
        print("\n  -> CONFINED AUTONOMOUS WIRE WORKS: gate1's output travels through a walled")
        print("     channel to gate2 (no flooding, no controller). Gate2 reproduces NOR(A,B).")
        print("     This is the gate-to-gate wire a controller-free CA circuit needs.")
    else:
        print("\n  -> the confined wire doesn't cleanly carry the output across the channel")
        print("     (timing/margin/leakage). The honest remaining wall for autonomous cascades.")

if __name__ == "__main__":
    main()
