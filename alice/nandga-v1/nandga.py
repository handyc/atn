#!/usr/bin/env python3
# nandga.py — UNIVERSALITY by construction: search for a NAND gate built entirely from
# our CA primitives. NAND alone is functionally complete -> if the substrate realises
# it, the substrate is computation-universal. Layout: three input ports on the left —
# A, B (emit a glider iff their bit is 1) and a CONSTANT-TRUE source C (always emits) —
# feeding a routing FABRIC of region tiles, each a glider rule steered a chosen way
# (wires + waveguides). Gliders annihilate where they collide. An output detector
# reads 1 iff activity reaches it in a readout window. A genome = the fabric's per-tile
# directions + detector position + readout time. Fitness = match to the NAND truth
# table [A,B -> out]: 00->1, 01->1, 10->1, 11->0, across seeds. Self-contained: rulehub+numpy.
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
BASE = newton_lut(-0.10, -0.02, 0.52)
NDIR = 8
def rule_for(theta_deg):
    phi = np.radians(theta_deg) - np.pi; out = BASE.copy()
    for k, s in DSH.items():
        n = int(round(3 * max(0, np.cos(DANG[k] - phi))))
        for i, v in enumerate((1, 2, 3)): out[v << s] = v if i < n else 0
    return out
BANK = [rule_for(d * 360.0 / NDIR) for d in range(NDIR)]   # 8 steered "wire" rules
STACK = np.stack(BANK)
H, Wd, RG = 56, 72, 4                                       # board, region grid RGxRG
def region_map(genome):
    reg = np.zeros((H, Wd), np.int64)
    bh, bw = H // RG, Wd // RG
    for i in range(RG):
        for j in range(RG):
            reg[i*bh:(i+1)*bh if i < RG-1 else H, j*bw:(j+1)*bw if j < RG-1 else Wd] = genome["fab"][i*RG+j]
    return reg
def seed(b, r, c, rng):
    b[r-2:r+3, c-2:c+3] = rng.integers(1, 4, (5, 5))
def run(genome, A, B, seedv):
    reg = region_map(genome); rng = np.random.default_rng(seedv)
    b = np.zeros((H, Wd), np.uint8)
    if A: seed(b, 12, 6, rng)
    if B: seed(b, 28, 6, rng)
    seed(b, 44, 6, rng)                                     # constant-TRUE source C
    dr, dc, T = genome["det"]; mass = 0
    for t in range(T + 8):
        b = STACK[reg, rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
        if (b > 0).sum() > 0.30 * H * Wd: return None
        if t >= T:                                          # readout window
            win = b[max(0, dr-4):dr+5, max(0, dc-4):dc+5]
            mass = max(mass, int((win > 0).sum()))
    return mass
NAND = {(0, 0): 1, (0, 1): 1, (1, 0): 1, (1, 1): 0}
def fitness(genome):
    # calibrate an output threshold per genome from the observed masses, then score NAND
    res = {};
    for (A, B) in NAND:
        ms = [run(genome, A, B, s) for s in (1, 2, 3)]
        if any(m is None for m in ms): return 0.0, None
        res[(A, B)] = np.mean(ms)
    vals = list(res.values()); thr = (max(vals) + min(vals)) / 2 + 1e-6
    if max(vals) - min(vals) < 4: return 0.0, None          # no separation -> not a gate
    out = {k: int(v > thr) for k, v in res.items()}
    correct = sum(out[k] == NAND[k] for k in NAND) / 4.0
    return correct, out
def rand_genome(rng):
    return dict(fab=[int(rng.integers(0, NDIR)) for _ in range(RG*RG)],
                det=[int(rng.integers(8, H-8)), int(rng.integers(Wd-20, Wd-4)), int(rng.integers(30, 70))])
def mutate(g, rng):
    h = json.loads(json.dumps(g))
    if rng.random() < 0.7:
        i = int(rng.integers(0, RG*RG)); h["fab"][i] = int(rng.integers(0, NDIR))
    else:
        h["det"][0] = int(np.clip(h["det"][0] + rng.integers(-6, 7), 8, H-8))
        h["det"][1] = int(np.clip(h["det"][1] + rng.integers(-6, 7), Wd-24, Wd-4))
        h["det"][2] = int(np.clip(h["det"][2] + rng.integers(-8, 9), 24, 80))
    return h
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); spec = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    rng = np.random.default_rng(spec["seed0"]); gens = spec.get("gens", 40); pop = spec.get("pop", 30)
    P = [rand_genome(rng) for _ in range(pop)]; F = [fitness(g)[0] for g in P]
    best = max(range(pop), key=lambda i: F[i]); hist = [max(F)]
    for gen in range(gens):
        nP, nF = [P[best]], [F[best]]
        while len(nP) < pop:
            i, j = rng.integers(0, pop, 2); par = P[i] if F[i] >= F[j] else P[j]
            c = mutate(par, rng); nP.append(c); nF.append(fitness(c)[0])
        P, F = nP, nF; best = max(range(pop), key=lambda i: F[i]); hist.append(F[best])
        if F[best] >= 0.999: break
    acc, table = fitness(P[best])
    json.dump(dict(accuracy=float(acc), truth_table={f"{k[0]}{k[1]}": v for k, v in (table or {}).items()},
                   genome=P[best], hist=[float(x) for x in hist]),
              open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: NAND match {acc*100:.0f}%  table={table}")
if __name__ == "__main__":
    main()
