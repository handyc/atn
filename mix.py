#!/usr/bin/env python3
# mix.py — does the CA reservoir ADD complementary info to a strong n-gram decoder?
# Build two next-byte predictors on the SAME samples: (A) an interpolated byte
# n-gram, (B) the class-4 CA reservoir + logistic readout. Mix arithmetically:
#   p_mix(true) = a*p_ngram(true) + (1-a)*p_res(true)
# tune a on val, report bpb on test. If the best a is interior AND mix beats the
# n-gram alone, the reservoir captures something the n-gram misses.
import argparse, collections
import numpy as np
import caca

def ngram_probs(data, s, e, y, C, i1, order=5):
    """Interpolated byte n-gram: per-sample distribution over the C classes,
    trained on samples [0,i1). Returns p_true for every sample (len m)."""
    raw = np.frombuffer(data, dtype=np.uint8).astype(np.int64)
    # sample j predicts byte at pos s+1+j; context = raw[s+1+j-order : s+1+j]
    seen = sorted(set(y.tolist())); cls_of = {}
    # map raw byte -> class index used by y (caca.make_targets remap); rebuild it
    targ = raw[s + 1:e + 1]
    remap = {b: i for i, b in enumerate(sorted(set(targ.tolist())))}
    tables = [collections.defaultdict(lambda: np.zeros(C)) for _ in range(order + 1)]
    uni = np.zeros(C)
    m = e - s
    def ctx(j, o):
        a = s + 1 + j
        return tuple(raw[a - o:a].tolist()) if a - o >= 0 else None
    for j in range(i1):
        c = y[j]; uni[c] += 1
        for o in range(1, order + 1):
            k = ctx(j, o)
            if k is not None: tables[o][k][c] += 1
    uni = (uni + 0.1); uni /= uni.sum()
    w = np.array([0.02, 0.05, 0.10, 0.18, 0.28, 0.37][:order + 1]); w = w / w.sum()
    ptrue = np.zeros(m)
    for j in range(m):
        p = w[0] * uni
        for o in range(1, order + 1):
            k = ctx(j, o); cnt = tables[o].get(k)
            po = (cnt / cnt.sum()) if (cnt is not None and cnt.sum() > 0) else uni
            p = p + w[o] * po
        p /= p.sum()
        ptrue[j] = p[y[j]]
    return ptrue

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--bytes", type=int, default=16000)
    ap.add_argument("--lib", default="alice/c4lib-v2/outputs/c4lib.npy")
    ap.add_argument("--K", type=int, default=6)
    ap.add_argument("--side", type=int, default=24)
    ap.add_argument("--ticks", type=int, default=2)
    ap.add_argument("--rcells", type=int, default=96)
    ap.add_argument("--order", type=int, default=5)
    ap.add_argument("--ctx", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    data = open(a.file, "rb").read(a.bytes)
    n = len(data); s, e = a.warmup, n - 1
    y, C = caca.make_targets(data, s, e)
    m = len(y); i1, i2 = int(m * 0.7), int(m * 0.85)
    Xctx = caca.context_features(data, s, e, a.ctx)

    # (B) reservoir + logistic -> p_res(true) for all samples
    lib = np.load(a.lib, mmap_mode="r")
    ids = np.sort(rng.choice(len(lib), size=a.K, replace=False))
    pool = np.array(lib[ids])
    gene = dict(side=a.side, ticks=a.ticks, rcells=a.rcells, reps=12, decay=0.1,
                n_nodes=a.K, lut_ids=list(range(a.K)),
                parents=[[] for _ in range(a.K)])     # independent nodes (cleaner features)
    F = caca.HexNet(gene, pool, seed=1234).run(data)[s:e]
    Xall = np.hstack([Xctx, F])
    Xtr, Xva, Xte = caca.standardize(*caca.split3(Xall, i1, i2))
    ytr = y[:i1]
    W, b = caca.softmax_fit(Xtr, ytr, C, lam=1e-2, iters=400, lr=0.1)  # stable LR for wide input
    p_res = np.zeros(m)
    for name, X, lo in (("va", Xva, i1), ("te", Xte, i2)):
        pr = caca._softmax(X @ W + b)
        idx = np.arange(X.shape[0])
        p_res[lo:lo + X.shape[0]] = pr[idx, y[lo:lo + X.shape[0]]]

    # (A) n-gram -> p_ngram(true)
    p_ng = ngram_probs(data, s, e, y, C, i1, order=a.order)

    def bpb(pt): return float(np.mean(-np.log2(np.maximum(pt, 1e-9))))
    va = slice(i1, i2); te = slice(i2, m)
    # tune mixture weight a on VAL
    best = (1e9, 1.0)
    for al in np.linspace(0, 1, 41):
        v = bpb(al * p_ng[va] + (1 - al) * p_res[va])
        if v < best[0]: best = (v, al)
    al = best[1]
    print(f"corpus {a.file} {n}B; reservoir K={a.K} {a.side}x{a.side}; n-gram order {a.order}")
    print(f"tuned mixture weight a (n-gram share) = {al:.2f}\n")
    print(f"{'predictor (TEST)':<24}{'bpb':>8}")
    print(f"{'n-gram alone':<24}{bpb(p_ng[te]):>8.3f}")
    print(f"{'reservoir alone':<24}{bpb(p_res[te]):>8.3f}")
    print(f"{'mixture a*ng+(1-a)*res':<24}{bpb(al * p_ng[te] + (1 - al) * p_res[te]):>8.3f}")
    d = bpb(p_ng[te]) - bpb(al * p_ng[te] + (1 - al) * p_res[te])
    print(f"\nmixture vs n-gram: {d:+.3f} bpb  -> "
          + ("reservoir ADDS complementary info" if d > 0.005 else
             "no gain; reservoir is redundant with the n-gram" if al > 0.95 else
             "marginal"))

if __name__ == "__main__":
    main()
