#!/usr/bin/env python3
# stackga.py (v3) — evolve stacks that COMPUTE WITH RECURRENCE. The stack is closed
# into a loop (bottom layer's output -> top layer's input, strength vf, now EVOLVABLE),
# and the fitness is FEEDBACK-AWARE: it rewards the closed-loop dynamics for having a
# long fading-MEMORY time and sustained PERIODICITY, while staying bounded and active
# (neither frozen nor chaotic) — the reservoir/RNN-like regime. Memory is measured the
# way a readout would see it: fixed random spatial projections of the combined state
# give scalar time-series; their autocorrelation gives a memory time + periodicity.
# Self-contained: rulehub + numpy. Reads {"seed0","gens","pop","T"}.
import argparse, json, os
import numpy as np
import rulehub
OPS = ["kill", "birth", "flip", "setmax", "decay"]
SIDE = 56
RNGM = np.random.default_rng(20260616)                       # fixed readout masks (shared, deterministic)
MASKS = [(RNGM.random((SIDE, SIDE)) < 0.5) for _ in range(4)]

def newton_lut(cx, cy, span, it=140, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

def rand_layer(rng):
    return [float(rng.normal(-0.10, 0.09)), float(rng.normal(-0.02, 0.09)), float(rng.uniform(0.30, 0.70))]

def rand_genome(rng):
    L = int(rng.integers(2, 5))
    return dict(L=L, layers=[rand_layer(rng) for _ in range(L)],
                W=(rng.uniform(-1, 1, (L, L)) * (1 - np.eye(L))).tolist(),
                tau=rng.uniform(0.2, 1.2, L).tolist(), op=OPS[int(rng.integers(0, len(OPS)))],
                p=float(rng.uniform(0.2, 1.0)), period=int(rng.integers(1, 4)),
                vf=float(rng.uniform(0.05, 0.6)))           # feedback strength (evolvable)

def luts_of(g):
    return [newton_lut(*ly) for ly in g["layers"]]

def simulate(g, luts, T=160, seed=0):
    L = g["L"]; W = np.array(g["W"]); tau = np.array(g["tau"]); op = g["op"]
    p = g["p"]; per = g["period"]; vf = g["vf"]; side = SIDE
    rng = np.random.default_rng(seed)
    B = [np.zeros((side, side), np.uint8) for _ in range(L)]
    for k in range(L):
        r0, c0 = rng.integers(14, side-14, 2); B[k][r0-2:r0+3, c0-2:c0+3] = rng.integers(1, 4, (5, 5))
    proj = []; chrate = []; prev = [b.copy() for b in B]
    for t in range(T):
        for k in range(L):
            B[k] = luts[k][rulehub.hex_key(B[k].astype(np.int64))].astype(np.uint8)
        if t % per == 0:
            A = [(b > 0).astype(np.float32) for b in B]; cm = rng.random((side, side)) < p
            for k in range(L):
                sig = sum(W[k, j]*A[j] for j in range(L) if j != k); trig = (sig > tau[k]) & cm
                if op == "kill": B[k][trig] = 0
                elif op == "birth": B[k][trig & (B[k] == 0)] = 1
                elif op == "flip": B[k][trig] = (3 - B[k][trig].astype(np.int16)).astype(np.uint8)
                elif op == "setmax": mx = np.maximum.reduce(B); B[k][trig] = mx[trig]
                elif op == "decay": B[k][trig & (B[k] > 0)] -= 1
        if vf > 0:                                            # FEEDBACK: bottom output -> top input
            src = B[L-1] > 0; inj = src & (rng.random((side, side)) < vf) & (B[0] == 0); B[0][inj] = 1
        tot = sum(int((b > 0).sum()) for b in B)
        if tot > 0.5*L*side*side: return None, "explode"
        if tot == 0: return None, "dead"
        comb = np.maximum.reduce([(b > 0) for b in B]).astype(np.float32)
        proj.append([float((comb*m).sum()) for m in MASKS])
        chrate.append(sum(int((B[k] != prev[k]).sum()) for k in range(L)) / (L*side*side)); prev = [b.copy() for b in B]
    return dict(proj=np.array(proj), chrate=np.array(chrate)), "alive"

def mem_period(proj):                                        # over the late window
    P = proj[len(proj)//3:]; mems = []; pers = []
    for j in range(P.shape[1]):
        x = P[:, j] - P[:, j].mean()
        if x.std() < 1e-6: mems.append(0.0); pers.append(0.0); continue
        ac = np.correlate(x, x, "full")[len(x)-1:]; ac = ac / ac[0]
        mt = 0
        for lag in range(1, min(len(ac), 70)):
            if ac[lag] > 0.2: mt = lag
            else: break
        mems.append(mt); pers.append(float(np.max(ac[4:max(5, len(x)//2)])))
    return float(np.mean(mems)), float(np.mean(pers))

def fitness(g):
    luts = luts_of(g); sc = []
    for s in range(3):
        d, st = simulate(g, luts, seed=s)
        if st != "alive": sc.append(0.0); continue
        act = float(d["chrate"][len(d["chrate"])//3:].mean())
        band = np.exp(-((act - 0.10) / 0.12) ** 2)            # active, not frozen, not chaotic
        mem, per = mem_period(d["proj"])
        sc.append(band * (mem / 15.0) * (0.5 + per))          # long memory + periodicity, in the band
    return float(np.mean(sc))

def mutate(g, rng):
    h = json.loads(json.dumps(g)); L = h["L"]; r = rng.random()
    if r < 0.26:
        k = int(rng.integers(0, L)); ly = h["layers"][k]; ly[0] += float(rng.normal(0, 0.04)); ly[1] += float(rng.normal(0, 0.04)); ly[2] = float(np.clip(ly[2] + rng.normal(0, 0.08), 0.18, 0.9))
    elif r < 0.48: Wm = np.array(h["W"]); Wm += rng.normal(0, 0.3, Wm.shape) * (1 - np.eye(L)); h["W"] = np.clip(Wm, -1.5, 1.5).tolist()
    elif r < 0.60: h["tau"] = np.clip(np.array(h["tau"]) + rng.normal(0, 0.2, L), 0.05, 1.6).tolist()
    elif r < 0.78: h["vf"] = float(np.clip(h["vf"] + rng.normal(0, 0.12), 0.0, 0.8))
    elif r < 0.86: h["op"] = OPS[int(rng.integers(0, len(OPS)))]
    elif r < 0.93: h["p"] = float(np.clip(h["p"] + rng.normal(0, 0.2), 0.1, 1.0)); h["period"] = int(rng.integers(1, 4))
    else:
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
    rng = np.random.default_rng(spec["seed0"]); gens = spec.get("gens", 32); pop = spec.get("pop", 26)
    P = [rand_genome(rng) for _ in range(pop)]; F = [fitness(g) for g in P]
    best = max(range(pop), key=lambda i: F[i]); hist = [max(F)]
    for gen in range(gens):
        nP, nF = [P[best]], [F[best]]
        while len(nP) < pop:
            i, j = rng.integers(0, pop, 2); par = P[i] if F[i] >= F[j] else P[j]
            c = mutate(par, rng); nP.append(c); nF.append(fitness(c))
        P, F = nP, nF; best = max(range(pop), key=lambda i: F[i]); hist.append(F[best])
    bg = P[best]; d, st = simulate(bg, luts_of(bg), seed=0)
    mem, per = mem_period(d["proj"]) if st == "alive" else (0.0, 0.0)
    desc = dict(fitness=float(F[best]), genome=bg, memory=mem, periodicity=per,
                activity=float(d["chrate"][len(d["chrate"])//3:].mean()) if st == "alive" else 0.0,
                hist=[float(x) for x in hist])
    json.dump(desc, open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: fit {F[best]:.3f} op={bg['op']} L={bg['L']} vf={bg['vf']:.2f} "
          f"memory={mem:.1f} period={per:.2f} act={desc['activity']:.3f}")

if __name__ == "__main__":
    main()
