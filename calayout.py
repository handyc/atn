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
S, BIAS, INSZ, GHOLD = 48, 18, 14, 20    # was 60/60; 100% held-out at 40/10 (caregen_opt.py), 48/20 = margin
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
# Netlist.add does COMMON-SUBEXPRESSION ELIMINATION (memo on sorted args, since NAND is commutative): a
# repeated gate — e.g. NOT(input0) used by many product terms — is built ONCE and shared.  Each gate is a
# real CA run, so a shared gate is a CA run saved.
class Netlist:
    def __init__(self, n):
        self.n = n; self.nodes = [("IN", (i,)) for i in range(n)]; self.memo = {}
    def add(self, args):
        key = tuple(sorted(args))
        hit = self.memo.get(key)
        if hit is not None: return hit
        self.nodes.append(("NAND", tuple(args))); nid = len(self.nodes) - 1
        self.memo[key] = nid; return nid
    def NOT(self, a): return self.add((a, a))
    def AND(self, a, b): return self.NOT(self.add((a, b)))
    def OR(self, a, b): return self.add((self.NOT(a), self.NOT(b)))
    def XOR(self, a, b):                               # classic 4-NAND XOR (CSE shares the inner NAND)
        nb = self.add((a, b)); return self.add((self.add((a, nb)), self.add((b, nb))))
    def ANDr(self, lits):                              # balanced AND-reduce (shallower depth, more sharing)
        if not lits: return None
        while len(lits) > 1:
            lits = [self.AND(lits[i], lits[i+1]) for i in range(0, len(lits)-1, 2)] + ([lits[-1]] if len(lits) % 2 else [])
        return lits[0]
    def ORr(self, terms):
        while len(terms) > 1:
            terms = [self.OR(terms[i], terms[i+1]) for i in range(0, len(terms)-1, 2)] + ([terms[-1]] if len(terms) % 2 else [])
        return terms[0]
    def XORr(self, terms):
        while len(terms) > 1:
            terms = [self.XOR(terms[i], terms[i+1]) for i in range(0, len(terms)-1, 2)] + ([terms[-1]] if len(terms) % 2 else [])
        return terms[0]

# ---- Quine-McCluskey: minterms -> minimal prime-implicant cover (fewer, wider product terms) ----
def _primes(minterms, n):
    groups = {tuple((m >> i) & 1 for i in range(n)) for m in minterms}   # each var-bit, position i = var i
    groups = {tuple(str(b) for b in g) for g in groups}
    primes = set()
    while groups:
        used = set(); nxt = set()
        terms = list(groups)
        for i in range(len(terms)):
            for j in range(i+1, len(terms)):
                a, b = terms[i], terms[j]
                diff = [k for k in range(n) if a[k] != b[k]]
                if len(diff) == 1 and a[diff[0]] != '-' and b[diff[0]] != '-':
                    c = list(a); c[diff[0]] = '-'; nxt.add(tuple(c)); used.add(a); used.add(b)
        primes |= (set(terms) - used)
        groups = nxt
    return primes

def _covers(pi, m, n): return all(pi[i] == '-' or int(pi[i]) == ((m >> i) & 1) for i in range(n))

def _cover(primes, minterms, n):
    primes = list(primes); pc = {p: {m for m in minterms if _covers(p, m, n)} for p in primes}
    selected = set(); covered = set()
    for m in minterms:                                  # essential prime implicants first
        cov = [p for p in primes if m in pc[p]]
        if len(cov) == 1: selected.add(cov[0])
    for p in selected: covered |= pc[p]
    remaining = set(minterms) - covered
    while remaining:                                    # greedy cover of the rest
        best = max(primes, key=lambda p: len(remaining & pc[p]))
        selected.add(best); remaining -= pc[best]
    return selected

def _parity_sense(func, n):
    """If func is the parity (XOR) of ALL inputs, return func(0,..,0) (0=XOR-tree, 1=XNOR); else None.
    Parity is SOP-INCOMPRESSIBLE (QM can't shrink it), but it's a balanced XOR-tree of 4-NAND gates."""
    p0 = func((0,) * n)
    for m in range(1 << n):
        if func(tuple((m >> i) & 1 for i in range(n))) != (p0 ^ (bin(m).count("1") & 1)):
            return None
    return p0

def synth_min(func, n):
    """Quine-McCluskey minimal SOP + XOR-extraction, compiled to a NAND netlist with CSE (replaces the
    naive per-minterm SOP)."""
    net = Netlist(n)
    minterms = [m for m in range(1 << n) if func(tuple((m >> i) & 1 for i in range(n)))]
    if not minterms:                                            # constant 0 = a AND NOT a
        return net, net.NOT(net.add((0, net.NOT(0)))), []
    if len(minterms) == (1 << n):                               # constant 1 = NAND(a, NOT a)
        return net, net.add((0, net.NOT(0))), minterms
    sense = _parity_sense(func, n)                              # XOR-tree wins for parity (arithmetic sum, XOR)
    if sense is not None:
        tree = net.XORr(list(range(n)))
        return net, (net.NOT(tree) if sense else tree), minterms
    cover = _cover(_primes(minterms, n), minterms, n)
    terms = []
    for pi in cover:
        lits = [i if pi[i] == '1' else net.NOT(i) for i in range(n) if pi[i] != '-']
        terms.append(net.ANDr(lits))
    return net, net.ORr(terms), minterms

# kept for comparison: the original naive per-minterm sum-of-products (no minimization, no sharing)
def synth_sop(func, n):
    net = Netlist.__new__(Netlist); net.n = n; net.nodes = [("IN", (i,)) for i in range(n)]; net.memo = None
    def add(args): net.nodes.append(("NAND", tuple(args))); return len(net.nodes) - 1
    NOT = lambda a: add((a, a)); AND = lambda a, b: NOT(add((a, b))); OR = lambda a, b: add((NOT(a), NOT(b)))
    minterms = [c for c in itertools.product((0, 1), repeat=n) if func(c)]
    if not minterms: z = NOT(0); return net, add((z, 0)), minterms
    term_ids = []
    for mt in minterms:
        lits = [i if mt[i] else NOT(i) for i in range(n)]; acc = lits[0]
        for L in lits[1:]: acc = AND(acc, L)
        term_ids.append(acc)
    out = term_ids[0]
    for t in term_ids[1:]: out = OR(out, t)
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
    all_ok = True; tot_old = tot_new = 0
    for name, (n, func) in FUNCS.items():
        old_net, _, _ = synth_sop(func, n)
        old_gates = sum(1 for op, _ in old_net.nodes if op == "NAND")
        net, out_id, minterms = synth_min(func, n)                  # QM-minimized + CSE
        depth, layers, maxfo = place(net)
        ngates = sum(1 for op, _ in net.nodes if op == "NAND")
        tot_old += old_gates; tot_new += ngates
        print(f"  {name}")
        print(f"    synth : {len(minterms)} minterms -> {ngates} CA-NAND gates  (naive SOP was {old_gates}, "
              f"{old_gates/ngates:.1f}x fewer)")
        print(f"    place : {len(layers)} layers, depth {max(depth)}, max fan-out {maxfo}")
        floor = "  ".join(f"L{d}:{len(layers[d])}" for d in sorted(layers))
        print(f"    floorplan: {floor}")
        ok, tot = verify(func, n, net, out_id, seeds=[0, 1, 100, 250])      # 100,250 held-out
        print(f"    verify: {ok}/{tot} correct over all {2**n} inputs x 4 seeds (2 held-out): "
              f"{'PASS' if ok == tot else 'FAIL'}\n")
        all_ok &= (ok == tot)
    print(f"  total gates: {tot_old} (naive SOP) -> {tot_new} (QM-min + CSE) = {tot_old/tot_new:.1f}x fewer CA runs\n")
    print("  ==> arbitrary boolean functions compiled to verified CA-gate circuits AUTOMATICALLY"
          if all_ok else "  ==> a function failed verification")
    print("      (synthesise -> place -> run real CA NANDs -> verify). The hand-laying of the")
    print("      compute fabric is gone. Honest scope: inter-gate transport is orchestrated")
    print("      (autowire2-4 prove the autonomous wiring primitives; cainv pins the one")
    print("      remaining primitive for fully-autonomous universality: a 2nd spreading layer).")

if __name__ == "__main__":
    main()
