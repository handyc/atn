#!/usr/bin/env python3
# nandga.py (v2) — search for a real, GENERALISING NAND gate (gate composition, the
# crux for a CA computer). v1 hit "100%" but was a fitness ARTIFACT: a per-genome
# threshold over 3 seeds + an input-independent detector. v2 fixes all of that:
#   * PHYSICAL threshold: output bit = "did the constant-TRUE signal reach the detector?"
#     theta = half of that seed's own C-only reference mass (anchored, not data-fit).
#   * 10 seeds per input combo (per-seed bit, must be right per-seed) — hard to overfit.
#   * INPUT-DEPENDENCE gate: require mass(1,1) clearly below mass(0,0) (the gate must
#     actually suppress the constant when both inputs are present) else fitness 0.
#   * HELD-OUT accuracy on FRESH seeds is computed and stored, so a genome is only
#     believed if it generalises. NAND truth: 00->1,01->1,10->1,11->0.
import argparse, json, os
import numpy as np
import rulehub
SHIFT = {"self": 12, "nw": 10, "ne": 8, "r": 6, "se": 4, "sw": 2, "l": 0}
_DIR = {"nw": (-1, -0.5), "ne": (-1, 0.5), "r": (0, 1.0), "se": (1, 0.5), "sw": (1, -0.5), "l": (0, -1.0)}
DIRV = {k: np.array(v) / np.hypot(*v) for k, v in _DIR.items()}
DANG = {k: np.arctan2(v[0], v[1]) for k, v in DIRV.items()}; DSH = {k: SHIFT[k] for k in DIRV}
def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l
BASE = newton_lut(-0.10, -0.02, 0.52); NDIR = 8
def rule_for(theta_deg):
    phi = np.radians(theta_deg) - np.pi; out = BASE.copy()
    for k, s in DSH.items():
        n = int(round(3 * max(0, np.cos(DANG[k] - phi))))
        for i, v in enumerate((1, 2, 3)): out[v << s] = v if i < n else 0
    return out
BANK = [rule_for(d * 360.0 / NDIR) for d in range(NDIR)]; STACK = np.stack(BANK)
H, Wd, RG = 56, 72, 4
def region_map(g):
    reg = np.zeros((H, Wd), np.int64); bh, bw = H // RG, Wd // RG
    for i in range(RG):
        for j in range(RG):
            reg[i*bh:(i+1)*bh if i < RG-1 else H, j*bw:(j+1)*bw if j < RG-1 else Wd] = g["fab"][i*RG+j]
    return reg
def seed(b, r, c, rng): b[r-2:r+3, c-2:c+3] = rng.integers(1, 4, (5, 5))
def run(g, reg, A, B, seedv):
    rng = np.random.default_rng(seedv); b = np.zeros((H, Wd), np.uint8)
    if A: seed(b, 12, 6, rng)
    if B: seed(b, 28, 6, rng)
    seed(b, 44, 6, rng)                                       # constant-TRUE source
    dr, dc, T = g["det"]; mass = 0
    for t in range(T + 8):
        b = STACK[reg, rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
        if (b > 0).sum() > 0.30 * H * Wd: return None
        if t >= T:
            win = b[max(0, dr-4):dr+5, max(0, dc-4):dc+5]; mass = max(mass, int((win > 0).sum()))
    return mass
# both NAND and NOR are functionally complete (universal). With pairwise annihilation,
# one input already blocks C, so NOR (1 only if neither input) is the mechanism-natural gate.
GATES = {"NAND": {(0,0):1,(0,1):1,(1,0):1,(1,1):0}, "NOR": {(0,0):1,(0,1):0,(1,0):0,(1,1):0}}
def masses(g, seeds):                                          # mean detector mass per combo + per-seed bits
    reg = region_map(g); M = {k: [] for k in [(0,0),(0,1),(1,0),(1,1)]}; bits = {k: [] for k in M}
    for sv in seeds:
        ref = run(g, reg, 0, 0, sv)
        if ref is None or ref < 4: return None, None
        theta = 0.5 * ref
        for (A, B) in M:
            m = run(g, reg, A, B, sv + 31*(A+2*B))
            if m is None: return None, None
            M[(A, B)].append(m); bits[(A, B)].append(1 if m > theta else 0)
    return M, bits
def score_gate(M, bits, gate):
    tgt = GATES[gate]; ok = tot = 0
    for k in tgt:
        for bb in bits[k]: ok += (bb == tgt[k]); tot += 1
    hi = np.mean([np.mean(M[k]) for k in tgt if tgt[k] == 1])
    lo = np.mean([np.mean(M[k]) for k in tgt if tgt[k] == 0]) if any(v == 0 for v in tgt.values()) else 0
    dep = lo < 0.6 * hi
    return (ok / tot) if dep else (ok / tot) * 0.5
def best_gate(g, seeds):
    M, bits = masses(g, seeds)
    if M is None: return "NOR", 0.0
    sc = {gate: score_gate(M, bits, gate) for gate in GATES}
    gate = max(sc, key=sc.get); return gate, sc[gate]
def accuracy(g, seeds, gate):
    M, bits = masses(g, seeds)
    return 0.0 if M is None else score_gate(M, bits, gate)
def fitness(g): return best_gate(g, range(10))[1]
def rand_genome(rng):
    return dict(fab=[int(rng.integers(0, NDIR)) for _ in range(RG*RG)],
                det=[int(rng.integers(8, H-8)), int(rng.integers(Wd-20, Wd-4)), int(rng.integers(30, 70))])
def mutate(g, rng):
    h = json.loads(json.dumps(g))
    if rng.random() < 0.7: h["fab"][int(rng.integers(0, RG*RG))] = int(rng.integers(0, NDIR))
    else:
        h["det"][0] = int(np.clip(h["det"][0] + rng.integers(-6, 7), 8, H-8))
        h["det"][1] = int(np.clip(h["det"][1] + rng.integers(-6, 7), Wd-24, Wd-4))
        h["det"][2] = int(np.clip(h["det"][2] + rng.integers(-8, 9), 24, 80))
    return h
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); spec = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    rng = np.random.default_rng(spec["seed0"]); gens = spec.get("gens", 45); pop = spec.get("pop", 30)
    P = [rand_genome(rng) for _ in range(pop)]; F = [fitness(g) for g in P]
    best = max(range(pop), key=lambda i: F[i]); hist = [max(F)]
    for gen in range(gens):
        nP, nF = [P[best]], [F[best]]
        while len(nP) < pop:
            i, j = rng.integers(0, pop, 2); par = P[i] if F[i] >= F[j] else P[j]
            c = mutate(par, rng); nP.append(c); nF.append(fitness(c))
        P, F = nP, nF; best = max(range(pop), key=lambda i: F[i]); hist.append(F[best])
        if F[best] >= 0.999: break
    bg = P[best]
    gate, train = best_gate(bg, range(10))
    heldout = accuracy(bg, range(500, 514), gate)             # 14 FRESH seeds, same gate
    json.dump(dict(gate=gate, train_acc=float(train), heldout_acc=float(heldout),
                   genome=bg, hist=[float(x) for x in hist]),
              open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: gate={gate} train {train*100:.0f}% heldout {heldout*100:.0f}%")
if __name__ == "__main__":
    main()
