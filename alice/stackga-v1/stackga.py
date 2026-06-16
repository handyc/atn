#!/usr/bin/env python3
# stackga.py — EVOLVE ways of stacking glider environments. A genome describes a
# coupled multi-layer hex-CA: number of layers L, each layer's steered glider
# direction, an L×L coupling matrix W (how each layer's activity drives another), a
# per-layer trigger threshold, a coupling operator, a coupling probability, and a
# period. We search this space with a GA for EMERGENT, INTERESTING dynamics — bounded
# and self-sustaining, with stack-level "edge of chaos": moderate, fluctuating change
# and spatially structured (localized) activity — i.e. behaviour that no single
# uncoupled layer has. Self-contained: rulehub + numpy. Reads {"seed0","gens","pop"}.
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
    return rulehub._posterise(rulehub._newton(gx, gy, it), it)
BASE = newton_lut(-0.10, -0.02, 0.52)
OPS = ["kill", "birth", "flip", "setmax", "decay"]

def surgery(theta_deg):
    phi = np.radians(theta_deg) - np.pi; out = BASE.copy()
    for k, s in DSH.items():
        n = int(round(3 * max(0, np.cos(DANG[k] - phi))))
        for i, v in enumerate((1, 2, 3)): out[v << s] = v if i < n else 0
    return out

def rand_genome(rng):
    L = int(rng.integers(2, 5))
    return dict(L=L, thetas=(rng.random(L) * 360).tolist(),
                W=(rng.uniform(-1, 1, (L, L)) * (1 - np.eye(L))).tolist(),
                tau=rng.uniform(0.2, 1.2, L).tolist(),
                op=OPS[int(rng.integers(0, len(OPS)))],
                p=float(rng.uniform(0.2, 1.0)), period=int(rng.integers(1, 4)))

def simulate(g, side=64, T=90, seed=0):
    L = g["L"]; luts = [surgery(t) for t in g["thetas"]]
    W = np.array(g["W"]); tau = np.array(g["tau"]); op = g["op"]; p = g["p"]; per = g["period"]
    rng = np.random.default_rng(seed)
    B = [np.zeros((side, side), np.uint8) for _ in range(L)]
    for k in range(L):
        r0, c0 = rng.integers(16, side - 16, 2); B[k][r0-2:r0+3, c0-2:c0+3] = rng.integers(1, 4, (5, 5))
    cr = []; prev = [b.copy() for b in B]
    for t in range(T):
        for k in range(L):
            B[k] = luts[k][rulehub.hex_key(B[k].astype(np.int64))].astype(np.uint8)
        if t % per == 0:
            A = [(b > 0).astype(np.float32) for b in B]
            cmask = rng.random((side, side)) < p
            for k in range(L):
                sig = sum(W[k, j] * A[j] for j in range(L) if j != k)
                trig = (sig > tau[k]) & cmask
                if op == "kill": B[k][trig] = 0
                elif op == "birth": B[k][trig & (B[k] == 0)] = 1
                elif op == "flip": B[k][trig] = (3 - B[k][trig].astype(np.int16)).astype(np.uint8)
                elif op == "setmax":
                    mx = np.maximum.reduce(B); B[k][trig] = mx[trig]
                elif op == "decay": B[k][trig & (B[k] > 0)] -= 1
        tot = sum(int((b > 0).sum()) for b in B)
        if tot > 0.45 * L * side * side: return None, "explode"
        ch = sum(int((B[k] != prev[k]).sum()) for k in range(L)) / (L * side * side)
        cr.append(ch); prev = [b.copy() for b in B]
        if tot == 0: return cr, "dead"
    return cr, B

def structure(B, side=64, blk=8):
    comb = np.maximum.reduce([(b > 0) for b in B]).astype(np.float32)
    if comb.sum() < 6: return 0.0
    nb = side // blk
    dens = comb.reshape(nb, blk, nb, blk).mean(axis=(1, 3))
    return float(min(1.0, dens.std() / (dens.mean() + 1e-6) / 2.0))

def fitness(g):
    scores = []
    for s in range(3):
        cr, out = simulate(g, seed=s)
        if cr is None or out == "dead" or len(cr) < 30:
            scores.append(0.0); continue
        cr = np.array(cr); late = cr[len(cr)//3:]
        m = late.mean()
        band = np.exp(-((m - 0.12) / 0.12) ** 2)        # peak at ~12% change/step (edge of chaos)
        fluct = late.std()                               # gliders/structures appearing & moving
        struct = structure(out)
        scores.append(band * (0.3 + 6 * fluct) * (0.3 + struct))
    return float(np.mean(scores))

def mutate(g, rng):
    h = json.loads(json.dumps(g)); L = h["L"]
    r = rng.random()
    if r < 0.5:
        W = np.array(h["W"]); W += rng.normal(0, 0.3, W.shape) * (1 - np.eye(L)); h["W"] = np.clip(W, -1.5, 1.5).tolist()
    elif r < 0.7:
        h["tau"] = np.clip(np.array(h["tau"]) + rng.normal(0, 0.2, L), 0.05, 1.6).tolist()
    elif r < 0.85:
        h["thetas"] = ((np.array(h["thetas"]) + rng.normal(0, 30, L)) % 360).tolist()
    elif r < 0.93:
        h["op"] = OPS[int(rng.integers(0, len(OPS)))]
    else:
        h["p"] = float(np.clip(h["p"] + rng.normal(0, 0.2), 0.1, 1.0)); h["period"] = int(rng.integers(1, 4))
    return h

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); spec = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    seed0 = spec["seed0"]; gens = spec.get("gens", 24); pop = spec.get("pop", 24)
    rng = np.random.default_rng(seed0)
    P = [rand_genome(rng) for _ in range(pop)]
    F = [fitness(g) for g in P]
    best = max(range(pop), key=lambda i: F[i]); hist = [max(F)]
    for gen in range(gens):
        newP, newF = [P[best]], [F[best]]                # elitism
        while len(newP) < pop:
            i, j = rng.integers(0, pop, 2); par = P[i] if F[i] >= F[j] else P[j]
            child = mutate(par, rng); newP.append(child); newF.append(fitness(child))
        P, F = newP, newF; best = max(range(pop), key=lambda i: F[i]); hist.append(F[best])
    bg = P[best]
    # characterise the winner
    cr, out = simulate(bg, seed=0)
    desc = dict(fitness=float(F[best]), genome=bg,
                mean_change=float(np.mean(cr[len(cr)//3:])) if cr else 0.0,
                change_var=float(np.var(cr[len(cr)//3:])) if cr else 0.0,
                structure=structure(out) if isinstance(out, list) else 0.0,
                hist=[float(x) for x in hist])
    json.dump(desc, open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: best fitness {F[best]:.3f}  op={bg['op']} L={bg['L']} "
          f"mean_change={desc['mean_change']:.3f} struct={desc['structure']:.2f}")

if __name__ == "__main__":
    main()
