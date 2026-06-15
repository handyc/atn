#!/usr/bin/env python3
# One GA-sweep task = explicit confirmation datapoint. Runs a CA-reservoir GA on
# one (corpus, seed, mode), then evaluates the winner on a FRESH held-out region.
#   mode=class4 -> bundled class-4 rule pool (pool.npy)
#   mode=random -> random K=4 rules, same count (the adversarial control)
# Writes result_<id>.json. Self-contained: imports the bundled caca.py + caga.py.
import json, os, sys, random
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caca, caga

def run_ga(pool, data, s, e, rng, pop, gens, ctx=4):
    npool = len(pool)
    population = [caga.rand_gene(npool, rng) for _ in range(pop)]
    best = (-1.0, None)
    for _ in range(gens):
        scored = []
        for g in population:
            try:
                F = caca.HexNet(g, pool, seed=1234).run(data)[s:e]
                acc = caca.evaluate(F, data, s, e, ctx=ctx, full=False)["both_acc"]
            except Exception:
                acc = -1.0
            scored.append((acc, g))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored[0][0] > best[0]:
            best = scored[0]
        elites = [g for _, g in scored[:3]]
        parents = [g for _, g in scored[:max(3, pop // 2)]]
        nxt = list(elites)
        while len(nxt) < pop:
            pa, pb = rng.sample(parents, 2)
            nxt.append(caga.mutate(caga.crossover(pa, pb, npool, rng), npool, rng))
        population = nxt
    return best[1]

def main():
    tid = int(sys.argv[1]); here = os.path.dirname(os.path.abspath(__file__))
    spec = json.load(open(os.path.join(here, "inputs", f"task_{tid:04d}.json")))
    corpus, seed, mode = spec["corpus"], spec["seed"], spec["mode"]
    data_all = open(os.path.join(here, "inputs", "corpora", corpus + ".txt"), "rb").read()
    rng = random.Random(seed)
    if mode == "class4":
        pool = np.load(os.path.join(here, "pool.npy"))
    else:
        pool = np.random.default_rng(seed).integers(0, 4, (256, 16384), dtype=np.uint8)
    warm = 150; tb = spec.get("train_bytes", 9000)
    train = data_all[:tb]; s, e = warm, len(train) - 1
    best = run_ga(pool, train, s, e, rng, spec.get("pop", 14), spec.get("gens", 8))
    foff = spec.get("fresh_offset", 40000); fb = spec.get("fresh_bytes", 12000)
    fresh = data_all[foff:foff + fb]
    if len(fresh) < 3000:
        fresh = data_all[-min(len(data_all), fb):]   # small corpora: use the tail
    F = caca.HexNet(best, pool, seed=1234).run(fresh)
    fs, fe = warm, len(fresh) - 1
    r = caca.evaluate(F[fs:fe], fresh, fs, fe, ctx=4, full=True)
    out = {"corpus": corpus, "mode": mode, "seed": seed,
           "fresh_res_acc": r["res_acc"], "fresh_both_acc": r["both_acc"],
           "fresh_ctx_acc": r["ctx_acc"], "fresh_uni_acc": r["uni_acc"],
           "fresh_res_bpb": r["res_bpb"], "fresh_ctx_bpb": r["ctx_bpb"],
           "n_nodes": best["n_nodes"], "side": best["side"]}
    os.makedirs(os.path.join(here, "outputs"), exist_ok=True)
    json.dump(out, open(os.path.join(here, "outputs", f"result_{tid:04d}.json"), "w"))
    print(f"task {tid}: {corpus}/{mode} seed{seed} -> res {r['res_acc']:.3f} "
          f"both {r['both_acc']:.3f} ctx {r['ctx_acc']:.3f}")

if __name__ == "__main__":
    main()
