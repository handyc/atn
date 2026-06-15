#!/usr/bin/env python3
# caga.py — a genetic algorithm that EVOLVES networks of class-4 hexagonal CAs
# (caca.HexNet) as reservoirs, scoring them against each other on real ingested
# data (e.g. demo-run news). This is the user's hunch made testable: can evolution
# find an ARRANGEMENT / SIZE / COMPLEXITY of CAs that adds predictive signal a
# plain linear context model lacks?
#
# Gene = {side, ticks, decay, couple, reps, rcells, n_nodes, lut_ids, parents}.
# Fitness = held-out accuracy of (context + reservoir) — i.e. does the network
# help the SAME readout do better than context alone? The context-only baseline
# is constant across genes, so maximising both_acc == maximising the lift.
# Honest by construction: a reservoir that only adds noise scores <= the baseline.
#
# Deterministic; checkpoints each generation to <out>/state.json.

import argparse, json, os, random, time
import numpy as np
from multiprocessing import Pool
import caca

# worker globals (inherited via fork) -----------------------------------------
G = {}

def init_worker(pool, data, warmup, ctx):
    G["pool"] = pool
    G["data"] = data
    s, e = warmup, len(data) - 1
    G["s"], G["e"] = s, e
    y, C = caca.make_targets(data, s, e)
    G["y"], G["C"] = y, C
    Xctx = caca.context_features(data, s, e, ctx)
    m = len(y); i1, i2 = int(m * 0.7), int(m * 0.85)
    G["i1"], G["i2"] = i1, i2
    G["ytr"], G["yva"], G["yte"] = caca.split3(y, i1, i2)
    Xc = caca.standardize(*caca.split3(Xctx, i1, i2))
    G["Xctx_std"] = Xc            # standardized ctx splits (train/val/test)
    uni = np.bincount(G["ytr"], minlength=C).astype(np.float64); uni /= uni.sum()
    G["uni"] = uni
    # constant context baseline on the VAL split (fitness is scored on val so the
    # TEST split stays untouched for an honest final check — no scorekeeper leak).
    lg = caca.ridge_logits(Xc[0], G["ytr"], Xc[1], C)
    G["ctx_acc"] = caca.accuracy(lg, G["yva"])
    G["uni_acc"] = float((G["yva"] == uni.argmax()).mean())


def fitness(gene):
    """Build the network, run it, return held-out both_acc (and diagnostics)."""
    try:
        net = caca.HexNet(gene, G["pool"], seed=1234)
        F = net.run(G["data"], warmup=0)[G["s"]:G["e"]]
        C = G["C"]
        Ftr, Fva, Fte = caca.split3(F, G["i1"], G["i2"])
        Ftr, Fva, Fte = caca.standardize(Ftr, Fva, Fte)
        Xc = G["Xctx_std"]
        # combined model scored on VAL (the objective; test stays untouched).
        Xboth_tr = np.hstack([Xc[0], Ftr]); Xboth_va = np.hstack([Xc[1], Fva])
        lg_both = caca.ridge_logits(Xboth_tr, G["ytr"], Xboth_va, C)
        both_acc = caca.accuracy(lg_both, G["yva"])
        # reservoir-alone (diagnostic)
        lg_res = caca.ridge_logits(Ftr, G["ytr"], Fva, C)
        res_acc = caca.accuracy(lg_res, G["yva"])
        return {"both_acc": both_acc, "res_acc": res_acc, "dim": net.dim,
                "lift": both_acc - G["ctx_acc"]}
    except Exception as ex:
        return {"both_acc": -1.0, "res_acc": -1.0, "dim": 0, "lift": -1.0,
                "err": repr(ex)}


# gene operators --------------------------------------------------------------
SIDES = [16, 20, 24, 28, 32]
TICKS = [1, 2, 3, 4]
DECAY = [0.0, 0.0, 0.05, 0.1, 0.2]
COUPLE = [3, 4, 6, 8, 12]
REPS = [6, 12, 18, 24]
RCELLS = [32, 48, 64]
NNODES = [2, 3, 4, 5, 6]

def rand_parents(n, rng):
    p = []
    for i in range(n):
        others = [j for j in range(n) if j != i]
        k = rng.choice([0, 1, 1, 2]) if others else 0
        k = min(k, len(others))
        p.append(sorted(rng.sample(others, k)))
    return p

def rand_gene(npool, rng):
    n = rng.choice(NNODES)
    return normalize({
        "side": rng.choice(SIDES), "ticks": rng.choice(TICKS),
        "decay": rng.choice(DECAY), "couple": rng.choice(COUPLE),
        "reps": rng.choice(REPS), "rcells": rng.choice(RCELLS),
        "n_nodes": n,
        "lut_ids": rng.sample(range(npool), min(n, npool)),
        "parents": rand_parents(n, rng),
    }, npool, rng)

def normalize(g, npool, rng):
    n = g["n_nodes"]
    ids = list(dict.fromkeys(g["lut_ids"]))            # dedup, keep order
    while len(ids) < n:
        c = rng.randrange(npool)
        if c not in ids: ids.append(c)
    g["lut_ids"] = ids[:n]
    p = g.get("parents", [])
    if len(p) != n:
        p = rand_parents(n, rng)
    p = [[j for j in ps if 0 <= j < n and j != i] for i, ps in enumerate(p)]
    g["parents"] = p
    return g

def crossover(a, b, npool, rng):
    pick = lambda k: a[k] if rng.random() < 0.5 else b[k]
    n = pick("n_nodes")
    src = a if rng.random() < 0.5 else b
    ids = (a["lut_ids"] + b["lut_ids"])
    rng.shuffle(ids)
    g = {"side": pick("side"), "ticks": pick("ticks"), "decay": pick("decay"),
         "couple": pick("couple"), "reps": pick("reps"), "rcells": pick("rcells"),
         "n_nodes": n, "lut_ids": ids, "parents": src.get("parents", [])}
    return normalize(g, npool, rng)

def mutate(g, npool, rng):
    g = json.loads(json.dumps(g))
    if rng.random() < 0.3: g["side"] = rng.choice(SIDES)
    if rng.random() < 0.3: g["ticks"] = rng.choice(TICKS)
    if rng.random() < 0.3: g["decay"] = rng.choice(DECAY)
    if rng.random() < 0.3: g["couple"] = rng.choice(COUPLE)
    if rng.random() < 0.3: g["reps"] = rng.choice(REPS)
    if rng.random() < 0.3: g["rcells"] = rng.choice(RCELLS)
    if rng.random() < 0.4:                              # swap one rule
        i = rng.randrange(len(g["lut_ids"])); g["lut_ids"][i] = rng.randrange(npool)
    if rng.random() < 0.4:                              # rewire one node
        n = g["n_nodes"]; i = rng.randrange(n)
        others = [j for j in range(n) if j != i]
        k = min(rng.choice([0, 1, 2]), len(others))
        g["parents"][i] = sorted(rng.sample(others, k)) if k else []
    if rng.random() < 0.25:                             # grow / shrink network
        g["n_nodes"] = max(2, min(6, g["n_nodes"] + rng.choice([-1, 1])))
    return normalize(g, npool, rng)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--bytes", type=int, default=10000)
    ap.add_argument("--pop", type=int, default=24)
    ap.add_argument("--gens", type=int, default=20)
    ap.add_argument("--elite", type=int, default=4)
    ap.add_argument("--poolk", type=int, default=128)
    ap.add_argument("--ctx", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--procs", type=int, default=0)
    ap.add_argument("--out", default="caga-run")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    pool, names = caca.load_pool(a.poolk, seed=a.seed)
    npool = len(pool)
    data = open(a.file, "rb").read(a.bytes)
    procs = a.procs or max(1, (os.cpu_count() or 2) - 2)

    print(f"corpus: {a.file}  {len(data)} bytes   pool: {npool} class-4 hex rules")
    print(f"GA: pop={a.pop} gens={a.gens} elite={a.elite} procs={procs} ctx={a.ctx}")

    init_worker(pool, data, a.warmup, a.ctx)  # also sets baselines in parent
    base_ctx, base_uni = G["ctx_acc"], G["uni_acc"]
    print(f"baselines (held-out acc): unigram={base_uni:.3f}  context-{a.ctx}={base_ctx:.3f}")
    print(f"  (a network is USEFUL only if both_acc > {base_ctx:.3f})\n")

    population = [rand_gene(npool, rng) for _ in range(a.pop)]
    history = []
    t0 = time.time()

    with Pool(procs, initializer=init_worker,
              initargs=(pool, data, a.warmup, a.ctx)) as P:
        for gen in range(1, a.gens + 1):
            results = P.map(fitness, population)
            scored = sorted(zip(results, population),
                            key=lambda x: x[0]["both_acc"], reverse=True)
            best_r, best_g = scored[0]
            mean_both = float(np.mean([r["both_acc"] for r, _ in scored if r["both_acc"] >= 0]))
            best_res = max(r["res_acc"] for r, _ in scored)
            dt = time.time() - t0
            print(f"gen {gen:2d}  best both_acc={best_r['both_acc']:.4f} "
                  f"(lift {best_r['lift']:+.4f})  best res_acc={best_res:.4f}  "
                  f"mean both={mean_both:.4f}  nodes={best_g['n_nodes']} "
                  f"side={best_g['side']} ticks={best_g['ticks']} "
                  f"decay={best_g['decay']}  [{dt:.0f}s]")
            history.append({"gen": gen, "best_both": best_r["both_acc"],
                            "best_lift": best_r["lift"], "best_res": best_res,
                            "mean_both": mean_both, "ctx_acc": base_ctx,
                            "uni_acc": base_uni})
            # checkpoint
            json.dump({"gen": gen, "ctx_acc": base_ctx, "uni_acc": base_uni,
                       "best_gene": best_g, "best_result": best_r,
                       "rule_names": [names[i] for i in best_g["lut_ids"]],
                       "history": history},
                      open(os.path.join(a.out, "state.json"), "w"), indent=2)

            # next generation: elitism + crossover/mutation
            elites = [g for _, g in scored[:a.elite]]
            parents = [g for _, g in scored[: max(a.elite, a.pop // 2)]]
            nxt = list(elites)
            while len(nxt) < a.pop:
                pa, pb = rng.sample(parents, 2)
                child = crossover(pa, pb, npool, rng)
                child = mutate(child, npool, rng)
                nxt.append(child)
            population = nxt

    print(f"\nDONE in {time.time()-t0:.0f}s. best both_acc={scored[0][0]['both_acc']:.4f} "
          f"vs context {base_ctx:.4f}  (lift {scored[0][0]['lift']:+.4f})")
    print(f"checkpoint: {a.out}/state.json")


if __name__ == "__main__":
    main()
