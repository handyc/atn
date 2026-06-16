#!/usr/bin/env python3
# flipflopga.py — EVOLVE a flippable CA flip-flop. flipflop.py showed two mutually-
# annihilating layers give a WRITE-ONCE latch (SET holds, but RESET can't overwrite).
# Here the GA searches for a clean FLIPPABLE flip-flop: a genome = the two layers'
# rules (fractal coords) + the SET/RESET pulse size & duration. Fitness rewards the
# full cycle SET->A, RESET->B, SET->A-again, with each state DOMINANT and PERSISTENT
# (held through a no-input window) and bounded. A high score = 1 bit of designed,
# rewritable memory in a CA network. Self-contained: rulehub + numpy.
import argparse, json, os
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

def rand_genome(rng):
    def coord(): return [float(rng.normal(-0.12, 0.1)), float(rng.normal(-0.05, 0.1)), float(rng.uniform(0.2, 0.6))]
    return dict(A=coord(), B=coord(), psize=int(rng.integers(8, 18)), pticks=int(rng.integers(4, 12)))

def run_cycle(lutA, lutB, g, side=60, hold=45, seed=0):
    rng = np.random.default_rng(seed); A = np.zeros((side, side), np.uint8); B = np.zeros((side, side), np.uint8)
    ps = g["psize"]; pt = g["pticks"]; c = side // 2
    lo = c - ps // 2
    def pair(A, B, ticks, inj):     # inj in {'A','B',None}
        for t in range(ticks):
            if inj == "A" and t < pt: A[lo:lo+ps, lo:lo+ps] = rng.integers(1, 4, (ps, ps))
            if inj == "B" and t < pt: B[lo:lo+ps, lo:lo+ps] = rng.integers(1, 4, (ps, ps))
            A = lutA[rulehub.hex_key(A.astype(np.int64))].astype(np.uint8)
            B = lutB[rulehub.hex_key(B.astype(np.int64))].astype(np.uint8)
            both = (A > 0) & (B > 0); A[both] = 0; B[both] = 0
            if (A > 0).sum() + (B > 0).sum() > 0.6*side*side: return None, None
        return A, B
    states = []
    for inj in ("A", "B", "A"):                       # set, reset, set-again
        A, B = pair(A, B, 14, inj)
        if A is None: return None
        A, B = pair(A, B, hold, None)                 # hold (no input)
        if A is None: return None
        states.append((int((A > 0).sum()), int((B > 0).sum())))
    return states                                     # [(mA,mB) after set, after reset, after set2]

def fitness(g):
    lutA = newton_lut(*g["A"]); lutB = newton_lut(*g["B"]); sc = []
    for s in range(3):
        st = run_cycle(lutA, lutB, g, seed=s)
        if st is None: sc.append(0.0); continue
        (a1, b1), (a2, b2), (a3, b3) = st
        s1 = (a1 - b1) / (a1 + b1 + 1)                # want A>B
        sr = (b2 - a2) / (a2 + b2 + 1)                # want B>A
        s2 = (a3 - b3) / (a3 + b3 + 1)                # want A>B again (flip back)
        alive = min(a1+b1, a2+b2, a3+b3) > 20         # states must be non-trivial
        sc.append(max(0, s1) * max(0, sr) * max(0, s2) * (1 if alive else 0))
    return float(np.mean(sc))

def mutate(g, rng):
    h = json.loads(json.dumps(g)); r = rng.random()
    if r < 0.4:
        k = "A" if rng.random() < 0.5 else "B"; h[k][0] += float(rng.normal(0, 0.04)); h[k][1] += float(rng.normal(0, 0.04)); h[k][2] = float(np.clip(h[k][2] + rng.normal(0, 0.07), 0.15, 0.8))
    elif r < 0.7: h["psize"] = int(np.clip(h["psize"] + rng.integers(-3, 4), 6, 24))
    else: h["pticks"] = int(np.clip(h["pticks"] + rng.integers(-2, 3), 3, 16))
    return h

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); spec = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    rng = np.random.default_rng(spec["seed0"]); gens = spec.get("gens", 30); pop = spec.get("pop", 24)
    P = [rand_genome(rng) for _ in range(pop)]; F = [fitness(g) for g in P]
    best = max(range(pop), key=lambda i: F[i]); hist = [max(F)]
    for gen in range(gens):
        nP, nF = [P[best]], [F[best]]
        while len(nP) < pop:
            i, j = rng.integers(0, pop, 2); par = P[i] if F[i] >= F[j] else P[j]
            c = mutate(par, rng); nP.append(c); nF.append(fitness(c))
        P, F = nP, nF; best = max(range(pop), key=lambda i: F[i]); hist.append(F[best])
    bg = P[best]; st = run_cycle(newton_lut(*bg["A"]), newton_lut(*bg["B"]), bg, seed=7)  # held-out seed
    json.dump(dict(fitness=float(F[best]), genome=bg, heldout_states=st, hist=[float(x) for x in hist]),
              open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: fit {F[best]:.3f} psize={bg['psize']} pt={bg['pticks']} heldout={st}")

if __name__ == "__main__":
    main()
