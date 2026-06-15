#!/usr/bin/env python3
# eval_finalist.py — take the GA's winning CA-network gene and evaluate it
# HONESTLY: with the full logistic readout, on (a) the eval corpus and (b) a
# FRESH, unseen corpus region the GA's selection never touched. The fresh-region
# number is the real test for "did the GA find something, or just overfit the
# scorekeeper?".

import argparse, json, os
import numpy as np
import caca

def run_on(gene, pool, path, offset, nbytes, ctx, warmup, label):
    data = open(path, "rb").read(offset + nbytes)[offset:]
    net = caca.build_net(gene, pool, seed=1234)
    F = net.run(data, warmup=0)
    s, e = warmup, len(data) - 1
    r = caca.evaluate(F[s:e], data, s, e, ctx=ctx, full=True)
    print(f"\n== {label}: {path}[{offset}:{offset+len(data)}]  "
          f"samples={r['n']} classes={r['C']} ==")
    print(f"{'model':<26}{'test acc':>10}{'test bpb':>10}")
    print("-" * 46)
    print(f"{'unigram floor':<26}{r['uni_acc']:>10.3f}{r['uni_bpb']:>10.3f}")
    print(f"{'linear ctx (control)':<26}{r['ctx_acc']:>10.3f}{r['ctx_bpb']:>10.3f}")
    print(f"{'CA reservoir':<26}{r['res_acc']:>10.3f}{r['res_bpb']:>10.3f}")
    print(f"{'reservoir + ctx':<26}{r['both_acc']:>10.3f}{r['both_bpb']:>10.3f}")
    print(f"lift over context:  acc {r['both_acc']-r['ctx_acc']:+.3f}   "
          f"bpb {r['ctx_bpb']-r['both_bpb']:+.3f}")
    return r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="caga-news")
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--fresh", default="demo-run/eval.txt")
    ap.add_argument("--fresh-offset", type=int, default=400000)
    ap.add_argument("--bytes", type=int, default=14000)
    ap.add_argument("--fresh-bytes", type=int, default=14000)
    ap.add_argument("--ctx", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--poolk", type=int, default=160)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    st = json.load(open(os.path.join(a.out, "state.json")))
    gene = st["best_gene"]
    pool, names = caca.load_pool(a.poolk, seed=a.seed)
    print(f"finalist from {a.out}/state.json (gen {st['gen']})")
    print(f"  gene: nodes={gene['n_nodes']} side={gene['side']} ticks={gene['ticks']} "
          f"decay={gene['decay']} couple={gene['couple']} reps={gene['reps']} "
          f"rcells={gene['rcells']}")
    print(f"  parents: {gene['parents']}")
    print(f"  rules: {st.get('rule_names')}")
    print(f"  GA val both_acc={st['best_result']['both_acc']:.4f} "
          f"(val lift {st['best_result']['lift']:+.4f})")

    run_on(gene, pool, a.file, 0, a.bytes, a.ctx, a.warmup,
           "IN-SAMPLE region (GA trained here)")
    run_on(gene, pool, a.fresh, a.fresh_offset, a.fresh_bytes, a.ctx, a.warmup,
           "FRESH region (GA never saw — the honest test)")

if __name__ == "__main__":
    main()
