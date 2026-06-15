#!/usr/bin/env python3
# controls.py — the decisive honest controls for a POSITIVE GA result, all on a
# FRESH corpus region with the full logistic readout. Answers two questions a
# naive "reservoir beats ctx-4" result cannot:
#   1. Is the lift just "longer memory"?  -> compare to deeper linear context
#      (ctx-8, ctx-16). The reservoir is recurrent; a fair context baseline must
#      have comparable memory.
#   2. Do the CLASS-4 dynamics matter, or is any recurrent nonlinear memory as
#      good?  -> rebuild the SAME network with RANDOM (non-class-4) rules and
#      with a CLASS-3-ish chaotic foil, and compare.

import argparse, json, os
import numpy as np
import caca

def feat(gene, pool, data, warmup):
    net = caca.build_net(gene, pool, seed=1234)
    F = net.run(data, warmup=0)
    return F, net.dim

def score(Fres, data, s, e, ctx):
    return caca.evaluate(Fres[s:e], data, s, e, ctx=ctx, full=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="caga-news")
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--offset", type=int, default=400000)
    ap.add_argument("--bytes", type=int, default=16000)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--poolk", type=int, default=160)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    st = json.load(open(os.path.join(a.out, "state.json")))
    gene = st["best_gene"]; n = gene["n_nodes"]
    pool, names = caca.load_pool(a.poolk, seed=a.seed)
    data = open(a.file, "rb").read(a.offset + a.bytes)[a.offset:]
    s, e = a.warmup, len(data) - 1
    rng = np.random.default_rng(123)

    print(f"FRESH region {a.file}[{a.offset}:{a.offset+len(data)}]  ({len(data)} bytes)")
    print(f"winner gene: nodes={n} side={gene['side']} ticks={gene['ticks']} "
          f"decay={gene['decay']} couple={gene['couple']}")

    # 1) context-depth ladder (linear, no reservoir).
    print("\n--- context-depth ladder (linear control, no CA) ---")
    print(f"{'model':<22}{'acc':>8}{'bpb':>8}")
    for ctx in (4, 8, 16):
        r = caca.evaluate(np.zeros((e - s, 1), np.float32), data, s, e, ctx=ctx, full=True)
        print(f"{'ctx-'+str(ctx):<22}{r['ctx_acc']:>8.3f}{r['ctx_bpb']:>8.3f}")

    # reservoir variants: class-4 (evolved), random rules, same architecture.
    print("\n--- reservoir variants (each + ctx-4), fresh region ---")
    print(f"{'variant':<22}{'res acc':>9}{'both acc':>9}{'both bpb':>9}{'lift bpb':>9}")

    def report(label, Fres):
        r = score(Fres, data, s, e, ctx=4)
        lift = r['ctx_bpb'] - r['both_bpb']
        print(f"{label:<22}{r['res_acc']:>9.3f}{r['both_acc']:>9.3f}"
              f"{r['both_bpb']:>9.3f}{lift:>+9.3f}")
        return r

    # class-4 (the evolved winner)
    F4, _ = feat(gene, pool, data, a.warmup)
    report("class-4 (evolved)", F4)

    # random rules: same gene structure, LUTs replaced by uniform-random K=4.
    randpool = rng.integers(0, 4, size=(n, caca.LUT_SIZE)).astype(np.uint8)
    g_rand = dict(gene); g_rand["lut_ids"] = list(range(n))
    Fr, _ = feat(g_rand, randpool, data, a.warmup)
    report("random rules", Fr)

    # chaotic foil: rules biased toward high activity (less structure).
    # (random but full-entropy already ~ chaotic; add a 2nd random draw to confirm
    #  the random result is stable, not a lucky seed.)
    randpool2 = rng.integers(0, 4, size=(n, caca.LUT_SIZE)).astype(np.uint8)
    Fr2, _ = feat(g_rand, randpool2, data, a.warmup)
    report("random rules (seed2)", Fr2)

    print("\nreading: if class-4 >> random, the class-4 STRUCTURE matters (user's"
          " hunch). if class-4 ~ random, it's recurrent nonlinear memory, not the"
          " CA class. if reservoir lift <= 0 vs ctx-8/16, it's just longer memory.")

if __name__ == "__main__":
    main()
