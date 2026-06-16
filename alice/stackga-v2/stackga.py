#!/usr/bin/env python3
# stackga.py (v2, DEEPER) — evolve ways to stack glider environments, going deeper:
#   * each layer carries its OWN evolvable rule (fractal coords cx,cy,span), not just
#     a steered direction — the GA searches real rule diversity.
#   * VERTICAL coupling: each layer also takes the adjacent layer's same-cell value as
#     an excitation (a true stacked/3rd axis), on top of the L×L same-cell coupling W.
#   * SHARPER objective: hunt EMERGENT STRUCTURES AT THE INTERSECTIONS — the field of
#     cells where >=2 layers are active must be persistent + bounded, LOCALIZED
#     (sparse), and TRANSLATING coherently (shifted-copy of itself in a consistent
#     direction = a glider-like emergent object the overlap creates). Persistence +
#     coherent drift implicitly demands emergence (transient crossings can't satisfy it).
# Self-contained: rulehub + numpy. Reads {"seed0","gens","pop","T"}.
import argparse, json, os
import numpy as np
import rulehub
OPS = ["kill", "birth", "flip", "setmax", "decay"]

def newton_lut(cx, cy, span, it=140, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    lut = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if lut[0] != 0: lut = lut.copy(); lut[0] = 0
    return lut

def rand_layer(rng):
    return [float(rng.normal(-0.10, 0.09)), float(rng.normal(-0.02, 0.09)), float(rng.uniform(0.30, 0.70))]

def rand_genome(rng):
    L = int(rng.integers(2, 5))
    return dict(L=L, layers=[rand_layer(rng) for _ in range(L)],
                W=(rng.uniform(-1, 1, (L, L)) * (1 - np.eye(L))).tolist(),
                tau=rng.uniform(0.2, 1.2, L).tolist(), op=OPS[int(rng.integers(0, len(OPS)))],
                p=float(rng.uniform(0.2, 1.0)), period=int(rng.integers(1, 4)),
                vc=float(rng.uniform(0.0, 0.5)))

def luts_of(g):
    return [newton_lut(*ly) for ly in g["layers"]]

def shift_overlap(a, b):
    sa = int(a.sum()); sb = int(b.sum())
    if sa < 4 or sb < 4: return 0.0, 0.0
    best, bang = 0.0, 0.0
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            if dy == 0 and dx == 0: continue
            ov = int(np.logical_and(a, np.roll(np.roll(b, dy, 0), dx, 1)).sum())
            c = ov / np.sqrt(sa * sb)
            if c > best: best, bang = c, float(np.arctan2(dy, dx))
    return best, bang

def simulate(g, luts, side=64, T=130, seed=0):
    L = g["L"]; W = np.array(g["W"]); tau = np.array(g["tau"]); op = g["op"]
    p = g["p"]; per = g["period"]; vc = g.get("vc", 0.0)
    rng = np.random.default_rng(seed)
    B = [np.zeros((side, side), np.uint8) for _ in range(L)]
    for k in range(L):
        r0, c0 = rng.integers(16, side - 16, 2); B[k][r0-2:r0+3, c0-2:c0+3] = rng.integers(1, 4, (5, 5))
    motion = []; angs = []; occ = []; imass = []; prev_inter = None
    for t in range(T):
        for k in range(L):
            B[k] = luts[k][rulehub.hex_key(B[k].astype(np.int64))].astype(np.uint8)
        if vc > 0:                                   # vertical excitation from the layer "above"
            up = [(B[(k + 1) % L] > 0) for k in range(L)]
            vm = rng.random((side, side)) < vc
            for k in range(L):
                m = up[k] & vm & (B[k] == 0); B[k][m] = 1
        if t % per == 0:                             # same-cell coupling W
            A = [(b > 0).astype(np.float32) for b in B]; cmask = rng.random((side, side)) < p
            for k in range(L):
                sig = sum(W[k, j] * A[j] for j in range(L) if j != k); trig = (sig > tau[k]) & cmask
                if op == "kill": B[k][trig] = 0
                elif op == "birth": B[k][trig & (B[k] == 0)] = 1
                elif op == "flip": B[k][trig] = (3 - B[k][trig].astype(np.int16)).astype(np.uint8)
                elif op == "setmax": mx = np.maximum.reduce(B); B[k][trig] = mx[trig]
                elif op == "decay": B[k][trig & (B[k] > 0)] -= 1
        tot = sum(int((b > 0).sum()) for b in B)
        if tot > 0.45 * L * side * side: return None, "explode"
        if tot == 0: return None, "dead"
        inter = sum((b > 0).astype(np.int16) for b in B) >= 2
        imass.append(int(inter.sum())); occ.append(float(inter.mean()))
        if prev_inter is not None:
            mo, an = shift_overlap(inter, prev_inter); motion.append(mo); angs.append(an)
        prev_inter = inter
    return dict(motion=motion, angs=angs, occ=occ, imass=imass), "alive"

def fitness(g):
    luts = luts_of(g); sc = []
    for s in range(3):
        d, st = simulate(g, luts, seed=s)
        if st != "alive" or len(d["motion"]) < 50: sc.append(0.0); continue
        h = len(d["motion"]) // 3; im = np.array(d["imass"][h:])
        if im.mean() < 8 or im.mean() > 0.18 * 64 * 64: sc.append(0.0); continue   # persistent + bounded
        mo = float(np.array(d["motion"][h:]).mean())
        an = np.array(d["angs"][h:]); Rd = float(np.hypot(np.cos(an).mean(), np.sin(an).mean()))
        loc = 1.0 - min(1.0, float(np.array(d["occ"][h:]).mean()) / 0.10)
        sc.append(mo * (0.25 + Rd) * (0.25 + loc))
    return float(np.mean(sc))

def mutate(g, rng):
    h = json.loads(json.dumps(g)); L = h["L"]; r = rng.random()
    if r < 0.30:                                            # perturb a layer's rule (fractal coords)
        k = int(rng.integers(0, L)); ly = h["layers"][k]
        ly[0] += float(rng.normal(0, 0.04)); ly[1] += float(rng.normal(0, 0.04))
        ly[2] = float(np.clip(ly[2] + rng.normal(0, 0.08), 0.18, 0.9))
    elif r < 0.55:
        Wm = np.array(h["W"]); Wm += rng.normal(0, 0.3, Wm.shape) * (1 - np.eye(L)); h["W"] = np.clip(Wm, -1.5, 1.5).tolist()
    elif r < 0.68: h["tau"] = np.clip(np.array(h["tau"]) + rng.normal(0, 0.2, L), 0.05, 1.6).tolist()
    elif r < 0.80: h["vc"] = float(np.clip(h.get("vc", 0.0) + rng.normal(0, 0.12), 0.0, 0.7))
    elif r < 0.88: h["op"] = OPS[int(rng.integers(0, len(OPS)))]
    elif r < 0.95: h["p"] = float(np.clip(h["p"] + rng.normal(0, 0.2), 0.1, 1.0)); h["period"] = int(rng.integers(1, 4))
    else:                                                   # add or drop a layer
        if L < 4 and rng.random() < 0.5:
            h["layers"].append(rand_layer(rng)); L += 1
            Wm = np.zeros((L, L)); Wm[:L-1, :L-1] = np.array(h["W"]); Wm[L-1, :] = rng.uniform(-1, 1, L); Wm[:, L-1] = rng.uniform(-1, 1, L); np.fill_diagonal(Wm, 0)
            h["W"] = Wm.tolist(); h["tau"] = h["tau"] + [float(rng.uniform(0.2, 1.2))]
        elif L > 2:
            h["layers"].pop(); L -= 1; h["W"] = (np.array(h["W"])[:L, :L]).tolist(); h["tau"] = h["tau"][:L]
        h["L"] = L
    return h

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); spec = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    rng = np.random.default_rng(spec["seed0"]); gens = spec.get("gens", 36); pop = spec.get("pop", 28)
    P = [rand_genome(rng) for _ in range(pop)]; F = [fitness(g) for g in P]
    best = max(range(pop), key=lambda i: F[i]); hist = [max(F)]
    for gen in range(gens):
        newP, newF = [P[best]], [F[best]]
        while len(newP) < pop:
            i, j = rng.integers(0, pop, 2); par = P[i] if F[i] >= F[j] else P[j]
            ch = mutate(par, rng); newP.append(ch); newF.append(fitness(ch))
        P, F = newP, newF; best = max(range(pop), key=lambda i: F[i]); hist.append(F[best])
    bg = P[best]; d, st = simulate(bg, luts_of(bg), seed=0)
    ok = st == "alive" and len(d["motion"]) > 6; h = len(d["motion"]) // 3 if ok else 0
    desc = dict(fitness=float(F[best]), genome=bg,
                inter_motion=float(np.mean(d["motion"][h:])) if ok else 0.0,
                drift_R=float(np.hypot(np.cos(np.array(d["angs"][h:])).mean(), np.sin(np.array(d["angs"][h:])).mean())) if ok and len(d["angs"]) > 6 else 0.0,
                inter_occ=float(np.mean(d["occ"][h:])) if ok else 0.0,
                inter_mass=float(np.mean(d["imass"][h:])) if ok else 0.0,
                hist=[float(x) for x in hist])
    json.dump(desc, open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: fit {F[best]:.3f} op={bg['op']} L={bg['L']} vc={bg.get('vc',0):.2f} "
          f"motion={desc['inter_motion']:.2f} driftR={desc['drift_R']:.2f} occ={desc['inter_occ']:.3f}")

if __name__ == "__main__":
    main()
