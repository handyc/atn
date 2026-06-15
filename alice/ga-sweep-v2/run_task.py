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

def linear_pool(n, seed):
    """A pool of LINEAR (additive mod 4) hex rules — the K=4 analog of the
    information-preserving class-3 rules (90/150) that win in the ReCA literature.
    out(neighbourhood) = (sum_i c_i * cell_i) mod 4, random nonzero coeffs per rule.
    Hex key bit layout: self<<12 | nw<<10 | ne<<8 | r<<6 | se<<4 | sw<<2 | l."""
    keys = np.arange(16384, dtype=np.int64)
    fields = [(keys >> sh) & 3 for sh in (12, 10, 8, 6, 4, 2, 0)]
    rng = np.random.default_rng(seed)
    pool = np.zeros((n, 16384), dtype=np.uint8)
    for i in range(n):
        c = rng.integers(0, 4, 7)
        while not c.any():
            c = rng.integers(0, 4, 7)
        out = np.zeros(16384, dtype=np.int64)
        for ci, f in zip(c, fields):
            out += int(ci) * f
        pool[i] = (out % 4).astype(np.uint8)
    return pool

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
    elif mode == "linear":
        pool = linear_pool(256, seed)          # structured class-3: K=4 analog of rule 90/150
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
