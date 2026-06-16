#!/usr/bin/env python3
# gatecell.py — build a universal gate from the WORKING LATCH (not the failed collision-
# routing). A NOR/NAND gate is threshold logic, and the mutual-annihilation latch is a
# winner-take-all threshold element. Decision cell: a constant BIAS seeds the output=1
# layer (O); each present input A/B seeds the output=0 layer (Z); winner-take-all decides.
# Territory ~ (patch size)^2, and the layer with more territory wins. So:
#   output=1 iff  bias^2 > (#inputs)*input^2
#   NOR  : 1 input beats bias  -> input > bias            (out=1 only if 0 inputs)
#   NAND : only 2 inputs beat bias -> bias < input*sqrt2  with input < bias (out=0 only at 1,1)
# Test both, on TRAIN and HELD-OUT seeds. A clean held-out NOR or NAND = functional
# completeness = the substrate is computation-universal. Self-contained: rulehub + numpy.
import glob, json
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

def best_genome():
    R = [json.load(open(f)) for f in glob.glob("alice/flipflopga-v1/outputs/result_*.json")]
    R.sort(key=lambda r: -r["fitness"]); return R[0]["genome"]

G = best_genome(); LO = newton_lut(*G["A"]); LZ = newton_lut(*G["B"])
S = 60  # cell board

def decide(A, B, bias, insz, hold=60, seed=0):
    rng = np.random.default_rng(seed)
    O = np.zeros((S, S), np.uint8); Z = np.zeros((S, S), np.uint8)
    def patch(arr, r, c, sz): arr[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = rng.integers(1, 4, (sz, sz))
    patch(O, S//2, S//2, bias)                      # constant-1 bias (center)
    if A: patch(Z, S//2 - 12, S//2, insz)           # input A -> output-0 layer (upper)
    if B: patch(Z, S//2 + 12, S//2, insz)           # input B -> output-0 layer (lower)
    for _ in range(hold):
        O = LO[rulehub.hex_key(O.astype(np.int64))].astype(np.uint8)
        Z = LZ[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        both = (O > 0) & (Z > 0); O[both] = 0; Z[both] = 0
    return 1 if int((O > 0).sum()) > int((Z > 0).sum()) else 0

NOR = {(0,0):1,(0,1):0,(1,0):0,(1,1):0}; NAND = {(0,0):1,(0,1):1,(1,0):1,(1,1):0}
def truth(bias, insz, seeds):
    out = {}; ok = 0; tot = 0; tgtN = NOR; tgtA = NAND; okN = okA = 0
    for k in [(0,0),(0,1),(1,0),(1,1)]:
        bits = [decide(k[0], k[1], bias, insz, seed=s+7*(k[0]+2*k[1])) for s in seeds]
        out[k] = bits
        okN += sum(b == tgtN[k] for b in bits); okA += sum(b == tgtA[k] for b in bits)
    n = 4*len(seeds)
    return okN/n, okA/n, out

def main():
    print(f"gate-from-latch (genome A={[round(x,3) for x in G['A']]} B={[round(x,3) for x in G['B']]})\n")
    configs = [("NOR-tuned", 14, 22), ("NAND-tuned", 18, 14), ("NOR-alt", 12, 20), ("NAND-alt", 20, 15)]
    for name, bias, insz in configs:
        nor_tr, nand_tr, _ = truth(bias, insz, range(8))
        nor_ho, nand_ho, out = truth(bias, insz, range(100, 108))
        gate = "NOR" if nor_ho >= nand_ho else "NAND"
        best_tr = max(nor_tr, nand_tr); best_ho = max(nor_ho, nand_ho)
        print(f"  [{name}] bias={bias} in={insz} -> best gate {gate}: train {100*best_tr:.0f}%  HELD-OUT {100*best_ho:.0f}%")
        if best_ho >= 0.95:
            tbl = {f"{k[0]}{k[1]}": int(np.round(np.mean(out[k]))) for k in out}
            print(f"      held-out truth table: {tbl}  (NOR={NOR if gate=='NOR' else ''} target)")
    print("\n  -> a >=95% HELD-OUT NOR or NAND from the latch = a universal gate that GENERALISES")
    print("     (unlike the collision-routing approach). That would make the substrate")
    print("     computation-universal via the SAME robust mechanism as the memory.")

if __name__ == "__main__":
    main()
