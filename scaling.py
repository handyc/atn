#!/usr/bin/env python3
# scaling.py — does the class-4 CA reservoir's lift GROW with capacity, or plateau?
# For each size config, sample a few random class-4 networks, pick the best on the
# VAL split, then report its fresh-region (test) lift over the linear context
# control. Plateau => fixed-capacity feature trick; growth => real headroom.
#
# Usage: python3 scaling.py [--file demo-run/eval.txt] [--trials 6]

import argparse, random
import numpy as np
import caca

def rand_parents(n, rng):
    p = []
    for i in range(n):
        others = [j for j in range(n) if j != i]
        k = min(rng.choice([0, 1, 1, 2]), len(others))
        p.append(sorted(rng.sample(others, k)) if k else [])
    return p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--bytes", type=int, default=14000)
    ap.add_argument("--fresh-offset", type=int, default=400000)
    ap.add_argument("--trials", type=int, default=6)
    ap.add_argument("--poolk", type=int, default=160)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--ctx", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    pool, names = caca.load_pool(a.poolk, seed=a.seed)
    rng = random.Random(a.seed)
    # selection corpus (where we pick the best net) and a fresh test region.
    sel = open(a.file, "rb").read(a.bytes)
    fresh = open(a.file, "rb").read(a.fresh_offset + a.bytes)[a.fresh_offset:]

    # capacity ladder: (nodes, side, rcells)
    configs = [(2, 16, 32), (3, 16, 48), (3, 24, 64), (4, 24, 64),
               (6, 24, 64), (6, 32, 96)]

    # context baseline on fresh region (constant)
    s, e = a.warmup, len(fresh) - 1
    rb = caca.evaluate(np.zeros((e - s, 1), np.float32), fresh, s, e, ctx=a.ctx, full=True)
    print(f"corpus {a.file}   fresh region [{a.fresh_offset}:{a.fresh_offset+len(fresh)}]")
    print(f"context-{a.ctx} baseline (fresh): acc {rb['ctx_acc']:.3f}  bpb {rb['ctx_bpb']:.3f}\n")
    print(f"{'config (N,side,rc)':<20}{'dim':>6}{'res acc':>9}{'both acc':>9}"
          f"{'both bpb':>9}{'lift bpb':>9}")
    print("-" * 62)

    for (N, side, rc) in configs:
        # pick best of `trials` random class-4 nets on the SELECTION corpus (val).
        best = None
        for t in range(a.trials):
            ids = rng.sample(range(len(pool)), N)
            gene = dict(side=side, ticks=rng.choice([1, 2, 3, 4]),
                        decay=rng.choice([0.0, 0.05, 0.1, 0.2]),
                        couple=rng.choice([3, 4, 6, 8]), reps=18, rcells=rc,
                        n_nodes=N, lut_ids=ids, parents=rand_parents(N, rng))
            ss, ee = a.warmup, len(sel) - 1
            Fsel = caca.HexNet(gene, pool, seed=1234).run(sel, warmup=0)[ss:ee]
            rsel = caca.evaluate(Fsel, sel, ss, ee, ctx=a.ctx, full=False)  # ridge/acc
            score = rsel["both_acc"]
            if best is None or score > best[0]:
                best = (score, gene)
        gene = best[1]
        # report best net on the FRESH region with full logistic readout.
        Ff = caca.HexNet(gene, pool, seed=1234).run(fresh, warmup=0)[s:e]
        r = caca.evaluate(Ff, fresh, s, e, ctx=a.ctx, full=True)
        dim = N * rc * 4
        lift = r['ctx_bpb'] - r['both_bpb']
        print(f"{f'({N},{side},{rc})':<20}{dim:>6}{r['res_acc']:>9.3f}"
              f"{r['both_acc']:>9.3f}{r['both_bpb']:>9.3f}{lift:>+9.3f}")

if __name__ == "__main__":
    main()
