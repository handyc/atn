#!/usr/bin/env python3
# autowire4.py — does the confined-channel autonomous wire (autowire2) COMPOSE? CA-1's
# datapath can only self-wire if two things hold beyond a single gate->gate hop:
#   TEST A  ROUTING DEPTH  — a signal crossing the chip through TWO channel hops and an
#           intermediate RELAY chamber (does it survive re-flooding + distance?).
#   TEST B  FAN-OUT        — one gate's output forking through a junction to drive TWO
#           downstream readouts (the hard one: a wire that branches).
# Mechanism (from autowire2): only the spreading carrier Z travels; the stable bias O is the
# local "1" reference; walls (forced-0) confine flow to chambers+channels. A readout is O-
# dominant=1 (no carrier arrived) vs Z-dominant=0 (carrier flooded in). Gate1 = NOR(A,B).
# Both outputs should reproduce NOR(A,B). Train + HELD-OUT seeds. rulehub + numpy only.
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

LZ = newton_lut(-0.255, -0.077, 0.270)     # spreading carrier (wire)
LO = newton_lut(-0.105, -0.135, 0.152)     # stable bias ("1" reference)

def simulate(H, W, OPEN, z_seeds, o_seeds, T=260, seed=0):
    WALL = ~OPEN; rng = np.random.default_rng(seed)
    Z = np.zeros((H, W), np.uint8); O = np.zeros((H, W), np.uint8)
    def put(arr, r, c, sz): arr[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = rng.integers(1, 4, (sz, sz))
    for (r, c, sz) in z_seeds: put(Z, r, c, sz)            # active inputs (t=0)
    for t in range(T):
        if t < 50:
            for (r, c, sz) in o_seeds: put(O, r, c, sz)    # constant biases
        Z = LZ[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        O = LO[rulehub.hex_key(O.astype(np.int64))].astype(np.uint8)
        Z[WALL] = 0; O[WALL] = 0
        both = (Z > 0) & (O > 0); Z[both] = 0; O[both] = 0
    return Z, O
def rd(Z, O, reg): return 1 if int((O[reg] > 0).sum()) > int((Z[reg] > 0).sum()) else 0

# ============================= TEST A: routing depth (2 hops + relay) ====================
HA, WA = 40, 160
OA = np.zeros((HA, WA), bool)
OA[4:36, 4:28] = True       # chamber1 (gate1 NOR(A,B))
OA[17:23, 28:52] = True     # channel A
OA[4:36, 52:76] = True      # RELAY chamber (no bias — pure conduction)
OA[17:23, 76:100] = True    # channel B
OA[4:36, 100:156] = True    # readout chamber (bias here)
def runA(A, B, seed=0):
    z = [];
    if A: z.append((12, 10, 7))
    if B: z.append((28, 10, 7))
    o = [(20, 15, 7), (20, 148, 9)]              # gate1 bias + readout bias (inside readout region)
    Z, O = simulate(HA, WA, OA, z, o, seed=seed)
    return rd(Z, O, (slice(4, 36), slice(140, 156)))

# ============================= TEST B: fan-out (one output -> two readouts) ===============
HB, WB = 64, 108
OB = np.zeros((HB, WB), bool)
OB[24:40, 4:28] = True      # chamber1 (gate1 NOR(A,B))
OB[30:34, 28:48] = True     # trunk channel
OB[12:52, 46:52] = True     # vertical bus (the fork)
OB[14:18, 52:68] = True     # branch up
OB[6:26, 68:104] = True     # readout chamber 2a (top)
OB[46:50, 52:68] = True     # branch down
OB[38:58, 68:104] = True    # readout chamber 2b (bottom)
def runB(A, B, seed=0):
    z = []
    if A: z.append((30, 10, 7))
    if B: z.append((36, 10, 7))
    o = [(32, 14, 7), (16, 90, 9), (48, 90, 9)]  # gate1 bias + two readout biases
    Z, O = simulate(HB, WB, OB, z, o, seed=seed)
    a = rd(Z, O, (slice(6, 26), slice(88, 104)))     # top output
    b = rd(Z, O, (slice(38, 58), slice(88, 104)))    # bottom output
    return a, b

NOR = {(0,0):1,(0,1):0,(1,0):0,(1,1):0}
def truthA(seeds):
    ok = tot = 0; tbl = {}
    for k in NOR:
        bits = [runA(k[0], k[1], seed=s+5*(k[0]+2*k[1])) for s in seeds]
        tbl[f"{k[0]}{k[1]}"] = int(round(np.mean(bits))); ok += sum(b == NOR[k] for b in bits); tot += len(bits)
    return ok/tot, tbl
def truthB(seeds):
    oka = okb = tot = 0; tbl = {}
    for k in NOR:
        res = [runB(k[0], k[1], seed=s+5*(k[0]+2*k[1])) for s in seeds]
        a = [r[0] for r in res]; b = [r[1] for r in res]
        tbl[f"{k[0]}{k[1]}"] = (int(round(np.mean(a))), int(round(np.mean(b))))
        oka += sum(x == NOR[k] for x in a); okb += sum(x == NOR[k] for x in b); tot += len(a)
    return oka/tot, okb/tot, tbl

def main():
    print("autowire4 — does the autonomous confined wire COMPOSE? (no controller)\n")
    print("TEST A — ROUTING DEPTH: NOR(A,B) across 2 channel hops + a relay chamber")
    trA, _ = truthA(range(8)); hoA, tblA = truthA(range(100, 110))
    print(f"  TRAIN {100*trA:.0f}%   HELD-OUT {100*hoA:.0f}%   truth(AB->out): {tblA}")
    okA = hoA >= 0.95
    print(f"  => deep routing {'WORKS — signals cross the chip through relays' if okA else 'fails (margin/timing over distance)'}\n")

    print("TEST B — FAN-OUT: gate1 NOR(A,B) forks to TWO readouts (both must reproduce it)")
    a, b, tblB = truthB(range(100, 110)); ta, tb, _ = truthB(range(8))
    print(f"  TRAIN  out1 {100*ta:.0f}%  out2 {100*tb:.0f}%")
    print(f"  HELD-OUT out1 {100*a:.0f}%  out2 {100*b:.0f}%   truth(AB->(o1,o2)): {tblB}")
    okB = a >= 0.95 and b >= 0.95
    print(f"  => fan-out {'WORKS — one output drives two gates (a branching wire)' if okB else 'fails (the fork splits/starves the carrier)'}\n")

    print("  VERDICT for self-wiring the CA-1 datapath:")
    if okA and okB:
        print("    BOTH compose -> long-distance routing AND fan-out work autonomously. With")
        print("    gate-combining (autowire3) that is the full wiring kit; the open part is a")
        print("    place-and-route layout algorithm, not a missing primitive.")
    else:
        print("    " + ("depth ok but fan-out is the wall" if okA and not okB else
                         "fan-out ok but long routing is the wall" if okB and not okA else
                         "both need tuning") + " — the honest remaining obstacle to self-wiring.")

if __name__ == "__main__":
    main()
