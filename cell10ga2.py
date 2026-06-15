#!/usr/bin/env python3
# cell10ga2.py — evolve RICH cell10 port wiring with ports FORCED ON. Tests the
# user's hypothesis: the 3 extra inputs help IF connected to the right things.
# Sources: node/self/input/pbyte/pboard/clock/func (cell10net2). port_w in {1,2,3}
# (never 0) and no "off" port, so the GA cannot discard the inputs — it must find
# a USE. Fitness stays honest (held-out both_acc); the verdict is whether the best
# forced wiring beats the ports-OFF 7->1 ceiling (0.3037 on news).

import argparse, json, os, random, time, collections
import numpy as np
from multiprocessing import Pool
import caca, cell10net2

G = {}
def init_worker(pool7, data, warmup, ctx):
    G["pool"] = pool7; G["data"] = data
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
        net = cell10net2.HexNet10R(gene, G["pool"], seed=1234)
        F = net.run(G["data"])[G["s"]:G["e"]]; C = G["C"]
        Ftr, Fva, Fte = caca.standardize(*caca.split3(F, G["i1"], G["i2"]))
        Xc = G["Xc"]
        both = caca.accuracy(caca.ridge_logits(np.hstack([Xc[0], Ftr]), G["ytr"],
                                               np.hstack([Xc[1], Fva]), C), G["yva"])
        res = caca.accuracy(caca.ridge_logits(Ftr, G["ytr"], Fva, C), G["yva"])
        kinds = collections.Counter(k for r in gene["routes"] for (k, _) in r)
        return {"both_acc": both, "res_acc": res, "lift": both - G["ctx_acc"],
                "kinds": dict(kinds), "port_w": gene["port_w"]}
    except Exception as ex:
        return {"both_acc": -1.0, "res_acc": -1.0, "lift": -1.0, "kinds": {}, "err": repr(ex)}

SIDES = [16, 20, 24]; TICKS = [1, 2, 3]; RCELLS = [48, 64, 96]
DECAY = [0.0, 0.05, 0.1, 0.2]; PORTW = [1, 2, 3]; NNODES = [2, 3, 4, 5]
SOURCES = cell10net2.SOURCES

def rand_port(i, N, rng):
    k = rng.choice(SOURCES)
    if k == "self": return ["self", i]
    if k == "node" or k == "pboard" or k == "func": return [k, rng.randrange(N)]
    if k == "pbyte": return [k, rng.randrange(3)]
    if k == "clock": return [k, rng.randrange(4)]
    return [k, 0]                      # input

def rand_routes(N, rng):
    return [[rand_port(i, N, rng) for _ in range(3)] for i in range(N)]

def rand_gene(npool, rng):
    n = rng.choice(NNODES)
    g = {"side": rng.choice(SIDES), "ticks": rng.choice(TICKS), "rcells": rng.choice(RCELLS),
         "decay": rng.choice(DECAY), "port_w": rng.choice(PORTW), "reps": 18, "n_nodes": n,
         "lut_ids": rng.sample(range(npool), min(n, npool)), "routes": rand_routes(n, rng),
         "mrate": rng.uniform(0.15, 0.45)}
    return normalize(g, npool, rng)

def normalize(g, npool, rng):
    n = g["n_nodes"]
    ids = list(dict.fromkeys(g["lut_ids"]))
    while len(ids) < n:
        c = rng.randrange(npool)
        if c not in ids: ids.append(c)
    g["lut_ids"] = ids[:n]
    rt = g.get("routes", [])
    if len(rt) != n: rt = rand_routes(n, rng)
    fixed = []
    for i in range(n):
        ports = (rt[i] if i < len(rt) else [rand_port(i, n, rng) for _ in range(3)])
        ports = (ports + [rand_port(i, n, rng)] * 3)[:3]
        for p in ports:
            if p[0] == "self": p[1] = i
            if p[0] in ("node", "pboard", "func") and not (0 <= p[1] < n): p[1] = rng.randrange(n)
        fixed.append(ports)
    g["routes"] = fixed
    g["mrate"] = float(min(0.6, max(0.05, g.get("mrate", 0.25))))
    if g["port_w"] not in PORTW: g["port_w"] = 1
    return g

def crossover(a, b, npool, rng):
    pick = lambda k: a[k] if rng.random() < 0.5 else b[k]
    n = pick("n_nodes"); src = a if rng.random() < 0.5 else b
    ids = a["lut_ids"] + b["lut_ids"]; rng.shuffle(ids)
    g = {k: pick(k) for k in ("side", "ticks", "rcells", "decay", "port_w")}
    g.update({"n_nodes": n, "lut_ids": ids, "routes": src.get("routes", []),
              "reps": 18, "mrate": (a["mrate"] + b["mrate"]) / 2})
    return normalize(g, npool, rng)

def mutate(g, npool, rng):
    g = json.loads(json.dumps(g))
    g["mrate"] = float(min(0.6, max(0.05, g["mrate"] * np.exp(rng.gauss(0, 0.3)))))
    mr = g["mrate"]
    if rng.random() < mr: g["side"] = rng.choice(SIDES)
    if rng.random() < mr: g["ticks"] = rng.choice(TICKS)
    if rng.random() < mr: g["rcells"] = rng.choice(RCELLS)
    if rng.random() < mr: g["decay"] = rng.choice(DECAY)
    if rng.random() < mr: g["port_w"] = rng.choice(PORTW)
    if rng.random() < mr + 0.1:
        i = rng.randrange(len(g["lut_ids"])); g["lut_ids"][i] = rng.randrange(npool)
    n = g["n_nodes"]
    for i in range(n):
        for p in range(3):
            if rng.random() < mr: g["routes"][i][p] = rand_port(i, n, rng)
    if rng.random() < mr:
        g["n_nodes"] = max(2, min(5, g["n_nodes"] + rng.choice([-1, 1])))
    return normalize(g, npool, rng)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--bytes", type=int, default=9000)
    ap.add_argument("--pop", type=int, default=20)
    ap.add_argument("--gens", type=int, default=20)
    ap.add_argument("--elite", type=int, default=3)
    ap.add_argument("--poolk", type=int, default=160)
    ap.add_argument("--ctx", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--procs", type=int, default=0)
    ap.add_argument("--baseline", type=float, default=0.3037, help="ports-off 7->1 ceiling")
    ap.add_argument("--out", default="cell10ga2-news")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    pool7, names = caca.load_pool(a.poolk, seed=a.seed)
    npool = len(pool7); data = open(a.file, "rb").read(a.bytes)
    procs = a.procs or max(1, (os.cpu_count() or 2) - 2)
    init_worker(pool7, data, a.warmup, a.ctx); base = G["ctx_acc"]
    print(f"corpus {a.file} {len(data)}B  pool {npool}  pop {a.pop} gens {a.gens}  "
          f"ctx baseline acc={base:.3f}  ports-OFF 7->1 ceiling={a.baseline:.3f}")
    print(f"  ports FORCED ON; sources={SOURCES}; goal: beat {a.baseline:.4f}\n")

    pop = [rand_gene(npool, rng) for _ in range(a.pop)]; history = []; t0 = time.time()
    best = (-1, None, None)
    with Pool(procs, initializer=init_worker, initargs=(pool7, data, a.warmup, a.ctx)) as P:
        for gen in range(1, a.gens + 1):
            res = P.map(fitness, pop)
            scored = sorted(zip(res, pop), key=lambda x: x[0]["both_acc"], reverse=True)
            br, bg = scored[0]
            if br["both_acc"] > best[0]: best = (br["both_acc"], bg, br)
            dt = time.time() - t0
            kinds = best[2]["kinds"]
            print(f"gen {gen:2d}  both={best[0]:.4f} (vs ceiling {best[0]-a.baseline:+.4f}) "
                  f"res={best[2]['res_acc']:.3f} port_w={best[2]['port_w']} "
                  f"sources={kinds}  [{dt:.0f}s]")
            history.append({"gen": gen, "both": best[0], "vs_ceiling": best[0] - a.baseline,
                            "kinds": kinds})
            json.dump({"gen": gen, "ctx_acc": base, "baseline_off": a.baseline,
                       "best_gene": best[1], "best_result": best[2],
                       "rule_names": [names[i] for i in best[1]["lut_ids"]], "history": history},
                      open(os.path.join(a.out, "state.json"), "w"), indent=2)
            elites = [g for _, g in scored[:a.elite]]
            parents = [g for _, g in scored[: max(a.elite, a.pop // 2)]]
            nxt = list(elites)
            while len(nxt) < a.pop:
                pa, pb = rng.sample(parents, 2)
                nxt.append(mutate(crossover(pa, pb, npool, rng), npool, rng))
            pop = nxt
    verdict = ("BEATS" if best[0] > a.baseline + 0.003 else
               "TIES" if best[0] > a.baseline - 0.003 else "LOSES TO")
    print(f"\nDONE {time.time()-t0:.0f}s  best both={best[0]:.4f}  {verdict} ports-off "
          f"ceiling {a.baseline:.4f}  sources={best[2]['kinds']}  -> {a.out}/state.json")

if __name__ == "__main__":
    main()
