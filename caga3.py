#!/usr/bin/env python3
# caga3.py — GA over CA networks combining this session's two generator-side wins:
#   * rule pool from JULIA+NEWTON fractals (--pool-dir, ~2x class-4 yield, diverse)
#   * a per-node SYMMETRY gene: each node may be none / C6 / D6 symmetric (a soft,
#     GA-selectable wallpaper-style prior; the search keeps symmetry only where it
#     helps, since hard symmetry over-stabilises).
# Fitness = held-out both_acc on a VAL split (TEST untouched), same honest protocol.

import argparse, json, os, random, time, collections
import numpy as np
from multiprocessing import Pool
import caca

G = {}
def init_worker(pool, data, warmup, ctx):
    G["pool"] = pool; G["data"] = data
    s, e = warmup, len(data) - 1; G["s"], G["e"] = s, e
    y, C = caca.make_targets(data, s, e); G["y"], G["C"] = y, C
    Xctx = caca.context_features(data, s, e, ctx)
    m = len(y); i1, i2 = int(m * 0.7), int(m * 0.85); G["i1"], G["i2"] = i1, i2
    G["ytr"], G["yva"], G["yte"] = caca.split3(y, i1, i2)
    G["Xc"] = caca.standardize(*caca.split3(Xctx, i1, i2))
    uni = np.bincount(G["ytr"], minlength=C).astype(np.float64); uni /= uni.sum()
    G["ctx_acc"] = caca.accuracy(caca.ridge_logits(G["Xc"][0], G["ytr"], G["Xc"][1], C), G["yva"])

def fitness(gene):
    try:
        net = caca.HexNet(gene, G["pool"], seed=1234)
        F = net.run(G["data"], warmup=0)[G["s"]:G["e"]]; C = G["C"]
        Ftr, Fva, Fte = caca.standardize(*caca.split3(F, G["i1"], G["i2"]))
        Xc = G["Xc"]
        both = caca.accuracy(caca.ridge_logits(np.hstack([Xc[0], Ftr]), G["ytr"],
                                               np.hstack([Xc[1], Fva]), C), G["yva"])
        res = caca.accuracy(caca.ridge_logits(Ftr, G["ytr"], Fva, C), G["yva"])
        sym = collections.Counter(gene.get("sym", []))
        return {"both_acc": both, "res_acc": res, "lift": both - G["ctx_acc"],
                "sym": {0: sym.get(0, 0), 1: sym.get(1, 0), 2: sym.get(2, 0)}}
    except Exception as ex:
        return {"both_acc": -1.0, "res_acc": -1.0, "lift": -1.0, "sym": {}, "err": repr(ex)}

SIDES = [16, 20, 24]; TICKS = [1, 2, 3]; RCELLS = [48, 64, 96]
DECAY = [0.0, 0.05, 0.1, 0.2]; COUPLE = [3, 4, 6, 8]; NNODES = [2, 3, 4, 5]; SYM = [0, 1, 2]

def rand_parents(n, rng):
    return [sorted(rng.sample([j for j in range(n) if j != i],
                              min(rng.choice([0, 1, 1, 2]), n - 1))) if n > 1 else []
            for i in range(n)]

def rand_gene(npool, rng):
    n = rng.choice(NNODES)
    g = {"side": rng.choice(SIDES), "ticks": rng.choice(TICKS), "decay": rng.choice(DECAY),
         "couple": rng.choice(COUPLE), "reps": 18, "rcells": rng.choice(RCELLS), "n_nodes": n,
         "lut_ids": rng.sample(range(npool), min(n, npool)), "parents": rand_parents(n, rng),
         "sym": [rng.choice(SYM) for _ in range(n)], "mrate": rng.uniform(0.15, 0.45)}
    return normalize(g, npool, rng)

def normalize(g, npool, rng):
    n = g["n_nodes"]
    ids = list(dict.fromkeys(g["lut_ids"]))
    while len(ids) < n:
        c = rng.randrange(npool)
        if c not in ids: ids.append(c)
    g["lut_ids"] = ids[:n]
    p = g.get("parents", [])
    if len(p) != n: p = rand_parents(n, rng)
    g["parents"] = [[j for j in ps if 0 <= j < n and j != i] for i, ps in enumerate(p)]
    sym = g.get("sym", [])
    g["sym"] = (sym + [0] * n)[:n]
    g["mrate"] = float(min(0.6, max(0.05, g.get("mrate", 0.25))))
    return g

def crossover(a, b, npool, rng):
    pick = lambda k: a[k] if rng.random() < 0.5 else b[k]
    n = pick("n_nodes"); src = a if rng.random() < 0.5 else b
    ids = a["lut_ids"] + b["lut_ids"]; rng.shuffle(ids)
    g = {k: pick(k) for k in ("side", "ticks", "decay", "couple", "rcells")}
    g.update({"n_nodes": n, "lut_ids": ids, "parents": src.get("parents", []),
              "sym": src.get("sym", []), "reps": 18, "mrate": (a["mrate"] + b["mrate"]) / 2})
    return normalize(g, npool, rng)

def mutate(g, npool, rng):
    g = json.loads(json.dumps(g)); g["mrate"] = float(min(0.6, max(0.05, g["mrate"] * np.exp(rng.gauss(0, 0.3)))))
    mr = g["mrate"]
    for f, opts in (("side", SIDES), ("ticks", TICKS), ("decay", DECAY), ("couple", COUPLE), ("rcells", RCELLS)):
        if rng.random() < mr: g[f] = rng.choice(opts)
    if rng.random() < mr + 0.1:
        i = rng.randrange(len(g["lut_ids"])); g["lut_ids"][i] = rng.randrange(npool)
    n = g["n_nodes"]
    for i in range(n):
        if rng.random() < mr: g["sym"][i] = rng.choice(SYM)   # flip a node's symmetry
        if rng.random() < mr:
            others = [j for j in range(n) if j != i]
            k = min(rng.choice([0, 1, 2]), len(others))
            g["parents"][i] = sorted(rng.sample(others, k)) if k else []
    if rng.random() < mr: g["n_nodes"] = max(2, min(5, g["n_nodes"] + rng.choice([-1, 1])))
    return normalize(g, npool, rng)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--bytes", type=int, default=12000)
    ap.add_argument("--pop", type=int, default=20)
    ap.add_argument("--gens", type=int, default=20)
    ap.add_argument("--elite", type=int, default=3)
    ap.add_argument("--pool-dir", default="julnewt-pool")
    ap.add_argument("--poolk", type=int, default=160)
    ap.add_argument("--ctx", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--procs", type=int, default=0)
    ap.add_argument("--baseline", type=float, default=0.3037)
    ap.add_argument("--out", default="caga3-news")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    pool, names = caca.load_pool(a.poolk, pool_dir=a.pool_dir, seed=a.seed)
    npool = len(pool); data = open(a.file, "rb").read(a.bytes)
    procs = a.procs or max(1, (os.cpu_count() or 2) - 2)
    init_worker(pool, data, a.warmup, a.ctx); base = G["ctx_acc"]
    print(f"corpus {a.file} {len(data)}B  pool {npool} ({a.pool_dir})  pop {a.pop} gens {a.gens}")
    print(f"  ctx baseline acc={base:.3f}; mandelhunt 7->1 ceiling was {a.baseline:.4f}\n")
    pop = [rand_gene(npool, rng) for _ in range(a.pop)]; history = []; t0 = time.time(); best = (-1, None, None)
    with Pool(procs, initializer=init_worker, initargs=(pool, data, a.warmup, a.ctx)) as P:
        for gen in range(1, a.gens + 1):
            res = P.map(fitness, pop)
            scored = sorted(zip(res, pop), key=lambda x: x[0]["both_acc"], reverse=True)
            br, bg = scored[0]
            if br["both_acc"] > best[0]: best = (br["both_acc"], bg, br)
            dt = time.time() - t0
            print(f"gen {gen:2d}  both={best[0]:.4f} (vs ceiling {best[0]-a.baseline:+.4f}) "
                  f"res={best[2]['res_acc']:.3f}  sym(none/C6/D6)={best[2]['sym']}  "
                  f"n={best[1]['n_nodes']} side={best[1]['side']}  [{dt:.0f}s]")
            history.append({"gen": gen, "both": best[0], "vs_ceiling": best[0] - a.baseline, "sym": best[2]["sym"]})
            json.dump({"gen": gen, "ctx_acc": base, "baseline": a.baseline, "pool_dir": a.pool_dir,
                       "best_gene": best[1], "best_result": best[2]},
                      open(os.path.join(a.out, "state.json"), "w"), indent=2)
            elites = [g for _, g in scored[:a.elite]]; parents = [g for _, g in scored[: max(a.elite, a.pop // 2)]]
            nxt = list(elites)
            while len(nxt) < a.pop:
                pa, pb = rng.sample(parents, 2); nxt.append(mutate(crossover(pa, pb, npool, rng), npool, rng))
            pop = nxt
    print(f"\nDONE {time.time()-t0:.0f}s  best both={best[0]:.4f} (vs ceiling {best[0]-a.baseline:+.4f}) "
          f"sym={best[2]['sym']}  -> {a.out}/state.json")

if __name__ == "__main__":
    main()
