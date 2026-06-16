#!/usr/bin/env python3
# calayout.py — a PLACE-AND-ROUTE COMPILER for the CA gate fabric. Give it ANY boolean
# function (as a truth table); it (1) SYNTHESISES a netlist (sum-of-products over the
# universal CA NAND gate), (2) PLACES the gates automatically into layers with a floorplan,
# (3) RUNS every gate as a REAL CA computation (the verified latch-threshold NAND), and
# (4) VERIFIES the result against the reference over ALL input combinations + HELD-OUT seeds.
# This removes the hand-laying of circuits for the compute fabric: arbitrary logic in, a
# verified CA circuit out, automatically. HONEST scope: signal transport between placed gates
# is controller-orchestrated (as in CA-1 / any CPU control unit; the autonomous wiring
# primitives — combine/route/fan-out — are verified in autowire2-4, and the autonomy limit is
# pinned in cainv). rulehub + numpy only.
import glob, json, itertools
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

# ---- the one real CA gate everything is built from: latch-threshold NAND ----
S, BIAS, INSZ, GHOLD = 60, 18, 14, 60
def ca_nand(a, b, seed):
    rng = np.random.default_rng(seed)
    O = np.zeros((S, S), np.uint8); Z = np.zeros((S, S), np.uint8)
    def patch(arr, r, c, sz): arr[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = rng.integers(1, 4, (sz, sz))
    patch(O, S//2, S//2, BIAS)
    if a: patch(Z, S//2 - 12, S//2, INSZ)
    if b: patch(Z, S//2 + 12, S//2, INSZ)
    for _ in range(GHOLD):
        O = LO[rulehub.hex_key(O.astype(np.int64))].astype(np.uint8)
        Z = LZ[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        both = (O > 0) & (Z > 0); O[both] = 0; Z[both] = 0
    return 1 if int((O > 0).sum()) > int((Z > 0).sum()) else 0

# ================= synthesis: arbitrary truth table -> a NAND netlist =====================
# A netlist node is (op, (arg_ids...)); op in {IN, NAND}. Everything reduces to NAND:
#   NOT a   = NAND(a,a)        AND a b = NOT(NAND(a,b))      OR a b = NAND(NOT a, NOT b)
class Netlist:
    def __init__(self, n): self.n = n; self.nodes = [("IN", (i,)) for i in range(n)]
    def add(self, args): self.nodes.append(("NAND", tuple(args))); return len(self.nodes) - 1
    def NOT(self, a): return self.add((a, a))
    def AND(self, a, b): return self.NOT(self.add((a, b)))
    def OR(self, a, b): return self.add((self.NOT(a), self.NOT(b)))

def synth_sop(func, n):
    """Sum-of-products of the true minterms, compiled to a NAND netlist."""
    net = Netlist(n)
    minterms = [c for c in itertools.product((0, 1), repeat=n) if func(c)]
    if not minterms:                                   # constant 0
        z = net.NOT(0); return net, net.add((z, 0)), minterms      # a AND NOT a = 0
    term_ids = []
    for mt in minterms:
        lits = [i if mt[i] else net.NOT(i) for i in range(n)]      # literal node ids
        acc = lits[0]
        for L in lits[1:]: acc = net.AND(acc, L)
        term_ids.append(acc)
    out = term_ids[0]
    for t in term_ids[1:]: out = net.OR(out, t)
    return net, out, minterms

# ================= place: layer each gate by longest path from inputs =====================
def place(net):
    depth = [0] * len(net.nodes)
    for i, (op, args) in enumerate(net.nodes):
        if op == "NAND": depth[i] = 1 + max(depth[a] for a in args)
    layers = {}
    for i, d in enumerate(depth):
        if net.nodes[i][0] == "NAND": layers.setdefault(d, []).append(i)
    fanout = [0] * len(net.nodes)
    for op, args in net.nodes:
        if op == "NAND":
            for a in set(args): fanout[a] += 1
    return depth, layers, max(fanout) if fanout else 0

# ================= run the placed netlist as real CA gates ================================
def run_ca(net, out_id, inbits, seed):
    val = [None] * len(net.nodes)
    for i, (op, args) in enumerate(net.nodes):
        if op == "IN": val[i] = inbits[args[0]]
        else: val[i] = ca_nand(val[args[0]], val[args[1]], seed + 17 * i)
    return val[out_id]

def verify(func, n, net, out_id, seeds):
    ok = tot = 0
    for c in itertools.product((0, 1), repeat=n):
        ref = func(c)
        for s in seeds:
            ok += (run_ca(net, out_id, c, seed=s + 1000 * sum(c)) == ref); tot += 1
    return ok, tot

FUNCS = {
    "XOR(a,b)":        (2, lambda c: c[0] ^ c[1]),
    "MUX(s,a,b)":      (3, lambda c: c[1] if c[0] == 0 else c[2]),         # s ? b : a
    "ADD.sum(a,b,cin)":(3, lambda c: c[0] ^ c[1] ^ c[2]),
    "ADD.carry(a,b,c)":(3, lambda c: 1 if (c[0] + c[1] + c[2]) >= 2 else 0),
}

def main():
    print(f"calayout — place-and-route compiler for the CA gate fabric (gate = verified CA NAND)\n")
    all_ok = True
    for name, (n, func) in FUNCS.items():
        net, out_id, minterms = synth_sop(func, n)
        depth, layers, maxfo = place(net)
        ngates = sum(1 for op, _ in net.nodes if op == "NAND")
        print(f"  {name}")
        print(f"    synth : {len(minterms)} product terms -> {ngates} CA-NAND gates")
        print(f"    place : {len(layers)} layers, depth {max(depth)}, max fan-out {maxfo}")
        floor = "  ".join(f"L{d}:{len(layers[d])}" for d in sorted(layers))
        print(f"    floorplan: {floor}")
        ok, tot = verify(func, n, net, out_id, seeds=[0, 1, 100, 250])      # 100,250 held-out
        print(f"    verify: {ok}/{tot} correct over all {2**n} inputs x 4 seeds (2 held-out): "
              f"{'PASS' if ok == tot else 'FAIL'}\n")
        all_ok &= (ok == tot)
    print("  ==> arbitrary boolean functions compiled to verified CA-gate circuits AUTOMATICALLY"
          if all_ok else "  ==> a function failed verification")
    print("      (synthesise -> place -> run real CA NANDs -> verify). The hand-laying of the")
    print("      compute fabric is gone. Honest scope: inter-gate transport is orchestrated")
    print("      (autowire2-4 prove the autonomous wiring primitives; cainv pins the one")
    print("      remaining primitive for fully-autonomous universality: a 2nd spreading layer).")

if __name__ == "__main__":
    main()
