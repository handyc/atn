#!/usr/bin/env python3
# caga2.py — a SCALED island-model GA over CA networks, to hunt the sweet spot.
# Extends caga.py with everything the search needs to go bigger:
#   * bigger nets: more nodes, larger boards, more connections (fan-in)
#   * more CA ruleset diversity: a large pool spread across the c4 range
#   * larger populations split into ISLANDS with periodic ring MIGRATION
#     (the legit "multiple / meta populations")
#   * self-adaptive MUTATION RATE carried per-gene (evolves its own search step)
#   * DEEP / hierarchical reservoirs via gene["depth"] (the "meta-node /
#     meta-network": each deeper layer is driven by the previous layer's state)
#
# Honest design unchanged: fitness = held-out both_acc on a VAL split (TEST kept
# clean); a reservoir that only adds noise scores <= the linear context baseline.
# Calibration: more capacity/meta-layers add organization & scale; the LINEAR
# readout caps what any reservoir can contribute, so expect a sweet spot, not
# monotone gains. Checkpoints each round to <out>/state.json.

import argparse, json, os, random, time
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
    lg = caca.ridge_logits(G["Xc"][0], G["ytr"], G["Xc"][1], C)
    G["ctx_acc"] = caca.accuracy(lg, G["yva"])

DIM_CAP = 4000   # readout dim cap: bigger -> ridge solve too slow for the inner loop

def fitness(gene):
    try:
        net = caca.build_net(gene, G["pool"], seed=1234)
        if net.dim > DIM_CAP:           # cull pathologically huge nets (compute guard)
            return {"both_acc": -1.0, "res_acc": -1.0, "dim": net.dim, "lift": -1.0,
                    "skip": "dim"}
        F = net.run(G["data"], warmup=0)[G["s"]:G["e"]]
        C = G["C"]
        Ftr, Fva, Fte = caca.standardize(*caca.split3(F, G["i1"], G["i2"]))
        Xc = G["Xc"]
        lg = caca.ridge_logits(np.hstack([Xc[0], Ftr]), G["ytr"],
                               np.hstack([Xc[1], Fva]), C)
        both = caca.accuracy(lg, G["yva"])
        res = caca.accuracy(caca.ridge_logits(Ftr, G["ytr"], Fva, C), G["yva"])
        return {"both_acc": both, "res_acc": res, "dim": net.dim,
                "lift": both - G["ctx_acc"]}
    except Exception as ex:
        return {"both_acc": -1.0, "res_acc": -1.0, "dim": 0, "lift": -1.0, "err": repr(ex)}

# ---- bigger gene space ----
SIDES = [16, 20, 24, 28, 32, 40]
TICKS = [1, 2, 3, 4, 5]
DECAY = [0.0, 0.0, 0.05, 0.1, 0.2, 0.3]
COUPLE = [3, 4, 6, 8, 12, 16]
REPS = [6, 12, 18, 24, 32]
RCELLS = [32, 48, 64, 96, 128]
NNODES = [2, 3, 4, 5, 6, 8, 10]
DEPTH = [1, 1, 1, 2, 2, 3]          # biased shallow; deep is expensive
FANIN = [0, 1, 1, 2, 2, 3, 4]

def rand_parents(n, rng):
    p = []
    for i in range(n):
        others = [j for j in range(n) if j != i]
        k = min(rng.choice(FANIN), len(others))
        p.append(sorted(rng.sample(others, k)) if k else [])
    return p

def rand_gene(npool, rng):
    n = rng.choice(NNODES)
    g = {"side": rng.choice(SIDES), "ticks": rng.choice(TICKS), "decay": rng.choice(DECAY),
         "couple": rng.choice(COUPLE), "reps": rng.choice(REPS), "rcells": rng.choice(RCELLS),
         "n_nodes": n, "depth": rng.choice(DEPTH),
         "lut_ids": rng.sample(range(npool), min(n, npool)), "parents": rand_parents(n, rng),
         "mrate": rng.uniform(0.15, 0.45)}
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
    g["mrate"] = float(min(0.6, max(0.05, g.get("mrate", 0.25))))
    g["depth"] = int(g.get("depth", 1))
    return g

def crossover(a, b, npool, rng):
    pick = lambda k: a[k] if rng.random() < 0.5 else b[k]
    n = pick("n_nodes"); src = a if rng.random() < 0.5 else b
    ids = a["lut_ids"] + b["lut_ids"]; rng.shuffle(ids)
    g = {k: pick(k) for k in ("side", "ticks", "decay", "couple", "reps", "rcells", "depth")}
    g.update({"n_nodes": n, "lut_ids": ids, "parents": src.get("parents", []),
              "mrate": (a["mrate"] + b["mrate"]) / 2})
    return normalize(g, npool, rng)

def mutate(g, npool, rng):
    g = json.loads(json.dumps(g))
    # self-adaptive: the mutation rate mutates first, then drives the rest.
    g["mrate"] = float(min(0.6, max(0.05, g["mrate"] * np.exp(rng.gauss(0, 0.3)))))
    mr = g["mrate"]
    if rng.random() < mr: g["side"] = rng.choice(SIDES)
    if rng.random() < mr: g["ticks"] = rng.choice(TICKS)
    if rng.random() < mr: g["decay"] = rng.choice(DECAY)
    if rng.random() < mr: g["couple"] = rng.choice(COUPLE)
    if rng.random() < mr: g["reps"] = rng.choice(REPS)
    if rng.random() < mr: g["rcells"] = rng.choice(RCELLS)
    if rng.random() < mr: g["depth"] = rng.choice(DEPTH)
    if rng.random() < mr + 0.1:
        i = rng.randrange(len(g["lut_ids"])); g["lut_ids"][i] = rng.randrange(npool)
    if rng.random() < mr + 0.1:
        n = g["n_nodes"]; i = rng.randrange(n); others = [j for j in range(n) if j != i]
        k = min(rng.choice(FANIN), len(others))
        g["parents"][i] = sorted(rng.sample(others, k)) if k else []
    if rng.random() < mr:
        g["n_nodes"] = max(2, min(10, g["n_nodes"] + rng.choice([-2, -1, 1, 2])))
    return normalize(g, npool, rng)

def evolve_island(pop, results, npool, rng, elite, pop_size):
    scored = sorted(zip(results, pop), key=lambda x: x[0]["both_acc"], reverse=True)
    elites = [g for _, g in scored[:elite]]
    parents = [g for _, g in scored[: max(elite, pop_size // 2)]]
    nxt = list(elites)
    while len(nxt) < pop_size:
        pa, pb = rng.sample(parents, 2)
        nxt.append(mutate(crossover(pa, pb, npool, rng), npool, rng))
    return nxt, scored

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--bytes", type=int, default=12000)
    ap.add_argument("--islands", type=int, default=4)
    ap.add_argument("--pop", type=int, default=16)
    ap.add_argument("--gens", type=int, default=24)
    ap.add_argument("--elite", type=int, default=3)
    ap.add_argument("--migrate-every", type=int, default=4)
    ap.add_argument("--migrants", type=int, default=2)
    ap.add_argument("--poolk", type=int, default=384)
    ap.add_argument("--ctx", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--procs", type=int, default=0)
    ap.add_argument("--out", default="caga2-news")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    pool, names = caca.load_pool(a.poolk, seed=a.seed)
    npool = len(pool)
    data = open(a.file, "rb").read(a.bytes)
    procs = a.procs or max(1, (os.cpu_count() or 2) - 2)
    init_worker(pool, data, a.warmup, a.ctx)
    base = G["ctx_acc"]
    print(f"corpus {a.file} {len(data)}B  pool {npool}  islands {a.islands}x{a.pop} "
          f"gens {a.gens}  ctx-{a.ctx} baseline acc={base:.3f}")
    print(f"  (useful only if both_acc > {base:.3f}; bigger nets cost more — watch the sweet spot)\n")

    islands = [[rand_gene(npool, rng) for _ in range(a.pop)] for _ in range(a.islands)]
    history = []; t0 = time.time(); overall_best = (-1, None, None)

    with Pool(procs, initializer=init_worker, initargs=(pool, data, a.warmup, a.ctx)) as P:
        for gen in range(1, a.gens + 1):
            flat = [g for isl in islands for g in isl]
            res = P.map(fitness, flat)
            # split results back per island
            new_islands, per_isl_scored = [], []
            off = 0
            for ii, isl in enumerate(islands):
                r = res[off:off + len(isl)]; off += len(isl)
                nxt, scored = evolve_island(isl, r, npool, rng, a.elite, a.pop)
                new_islands.append(nxt)
                per_isl_scored.append(scored)
                if scored[0][0]["both_acc"] > overall_best[0]:
                    overall_best = (scored[0][0]["both_acc"], scored[0][1], scored[0][0])
            # ring migration: top `migrants` of island i overwrite the tail
            # (the freshly-made children slots) of island i+1.
            if gen % a.migrate_every == 0 and a.islands > 1:
                for i in range(a.islands):
                    j = (i + 1) % a.islands
                    top = [g for _, g in per_isl_scored[i][:a.migrants]]
                    new_islands[j][-len(top):] = [json.loads(json.dumps(g)) for g in top]
            islands = new_islands

            bb = overall_best[0]; bg = overall_best[1]; brr = overall_best[2]
            isl_bests = " ".join(f"{sc[0][0]['both_acc']:.3f}" for sc in per_isl_scored)
            mean_mr = np.mean([g["mrate"] for isl in islands for g in isl])
            dt = time.time() - t0
            print(f"gen {gen:2d}  overall both={bb:.4f} (lift {bb-base:+.4f}) "
                  f"res={brr['res_acc']:.3f} dim={brr['dim']}  islands[{isl_bests}]  "
                  f"n={bg['n_nodes']} side={bg['side']} depth={bg['depth']} "
                  f"mr~{mean_mr:.2f}  [{dt:.0f}s]")
            history.append({"gen": gen, "best_both": bb, "lift": bb - base,
                            "island_bests": [sc[0][0]["both_acc"] for sc in per_isl_scored],
                            "mean_mrate": float(mean_mr)})
            json.dump({"gen": gen, "ctx_acc": base, "best_gene": bg, "best_result": brr,
                       "rule_names": [names[i] for i in bg["lut_ids"]], "history": history},
                      open(os.path.join(a.out, "state.json"), "w"), indent=2)

    print(f"\nDONE {time.time()-t0:.0f}s  best both_acc={overall_best[0]:.4f} "
          f"vs ctx {base:.4f}  (lift {overall_best[0]-base:+.4f})  -> {a.out}/state.json")

if __name__ == "__main__":
    main()
