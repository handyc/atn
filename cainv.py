#!/usr/bin/env python3
# cainv.py — the CRUX primitive for an autonomous universal place-and-route: an INVERTING
# REPEATER. The passive autowire carrier is monotone (a chamber floods = OR of inputs; only
# the readout inverts), so it can only realise a single NOR level. Universal multi-level
# autonomous logic needs a chamber that EMITS a carrier when its input is ABSENT (a NOT/NOR
# that outputs a routable carrier, not just a readout). Mechanism under test:
#   * a SELF-EMITTING SOURCE on layer Z, re-seeded every step at the chamber, spreads down
#     the output channel = "emit a carrier".
#   * an INPUT on the opposite layer O, held at the chamber, mutually annihilates the Z
#     source where they overlap -> if an input is present it SUPPRESSES emission.
#   => output carrier present iff NO input present = NOT(input); any of several inputs
#      suppresses = NOR. If this holds held-out, inverting repeaters chain (alternating
#      layers) and autonomous universality is unlocked. rulehub + numpy only.
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

LZ = newton_lut(-0.255, -0.077, 0.270)     # spreading carrier (emission)
LO = newton_lut(-0.105, -0.135, 0.152)     # stable suppressor (input)

H, W = 40, 96
OPEN = np.zeros((H, W), bool)
OPEN[4:36, 4:34] = True        # source chamber
OPEN[17:23, 34:58] = True      # output channel
OPEN[4:36, 58:92] = True       # readout chamber
WALL = ~OPEN

def run(inputs, T=200, seed=0, srcsz=7, insz=17):
    # inputs: list of bools; each present input suppresses the source (-> NOR of inputs).
    rng = np.random.default_rng(seed)
    Z = np.zeros((H, W), np.uint8); O = np.zeros((H, W), np.uint8)
    def put(arr, r, c, sz): arr[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = rng.integers(1, 4, (sz, sz))
    # input suppressors converge on the source (any present input kills emission -> NOR)
    sites = [(20, 12), (18, 12), (22, 12)]
    for t in range(T):
        put(Z, 20, 12, srcsz)                       # self-emitting Z source (always on)
        for i, on in enumerate(inputs):
            if on: put(O, *sites[i], insz)          # held input suppressor on layer O
        Z = LZ[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        O = LO[rulehub.hex_key(O.astype(np.int64))].astype(np.uint8)
        Z[WALL] = 0; O[WALL] = 0
        both = (Z > 0) & (O > 0); Z[both] = 0; O[both] = 0
    reg = (slice(4, 36), slice(74, 92))             # readout: did a carrier reach the far end?
    zmass = int((Z[reg] > 0).sum())
    return 1 if zmass > 20 else 0                   # carrier present -> 1 (= emission survived)

def truth(nin, seeds):
    combos = [tuple((k >> b) & 1 for b in range(nin)) for k in range(2**nin)]
    ok = tot = 0; tbl = {}
    for cb in combos:
        tgt = 1 if not any(cb) else 0               # NOR: 1 iff all inputs 0
        bits = [run(list(cb), seed=s + 3*sum(cb)) for s in seeds]
        tbl["".join(map(str, cb))] = int(round(np.mean(bits)))
        ok += sum(b == tgt for b in bits); tot += len(bits)
    return ok/tot, tbl

def main():
    print("cainv — inverting repeater test (self-emitting source suppressed by the input)\n")
    for nin, name in [(1, "NOT"), (2, "NOR2"), (3, "NOR3")]:
        tr, _ = truth(nin, range(6)); ho, tbl = truth(nin, range(100, 108))
        print(f"  {name:5s}: TRAIN {100*tr:4.0f}%  HELD-OUT {100*ho:4.0f}%   truth: {tbl}")
    print("\n  If NOT/NOR are clean held-out, the inverting repeater works -> emission can be")
    print("  suppressed by an input -> chains -> autonomous universal logic is reachable.")
    print("  If not, the passive carrier stays monotone and autonomous universality is blocked")
    print("  on this primitive (an honest negative; orchestrated routing remains the route).")

if __name__ == "__main__":
    main()
