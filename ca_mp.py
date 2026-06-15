#!/usr/bin/env python3
# ca_mp.py — DATA-CONDITIONED greedy CA selection (matching pursuit / boosting)
# over the class-4 dictionary. Each "expert" = a single hex-CA reservoir; at each
# step we add the rule whose feature block best explains the current RESIDUAL
# (the part of the next-byte target the context + already-chosen experts miss),
# measured on training data and tracked on held-out val. Compares to random
# K-rule draws at matched K. Tests the user's idea: select CAs by usefulness on
# the data so the reservoir grows TOWARD the data.
import argparse, time
import numpy as np
import caca

def feat_for_rule(rule, data, side, ticks, rcells, reps, decay, seed=1234):
    gene = dict(side=side, ticks=ticks, rcells=rcells, reps=reps, decay=decay,
                n_nodes=1, lut_ids=[0], parents=[[]])
    return caca.HexNet(gene, rule[None], seed=seed).run(data)

def ridge_fit(X, Y, lam=1.0):
    d = X.shape[1]
    return np.linalg.solve(X.T @ X + lam * np.eye(d), X.T @ Y)

def acc(X, W, yt):
    return float(((X @ W).argmax(1) == yt).mean())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--bytes", type=int, default=7000)
    ap.add_argument("--lib", default="alice/c4lib-v2/outputs/c4lib.npy")
    ap.add_argument("--cands", type=int, default=250)
    ap.add_argument("--K", type=int, default=8)
    ap.add_argument("--side", type=int, default=16)
    ap.add_argument("--ticks", type=int, default=2)
    ap.add_argument("--rcells", type=int, default=48)
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--decay", type=float, default=0.1)
    ap.add_argument("--ctx", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--select", choices=["train", "val"], default="train",
                    help="residual used to pick each expert: train (overfits) or val (held-out)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    data = open(a.file, "rb").read(a.bytes)
    n = len(data); s, e = a.warmup, n - 1
    y, C = caca.make_targets(data, s, e)
    Xctx = caca.context_features(data, s, e, a.ctx)
    m = len(y); i1, i2 = int(m * 0.7), int(m * 0.85)
    ytr, yva, yte = caca.split3(y, i1, i2)
    Xc_tr, Xc_va, Xc_te = caca.standardize(*caca.split3(Xctx, i1, i2))
    Yoh = np.eye(C)[ytr]

    lib = np.load(a.lib, mmap_mode="r")
    idx = np.sort(rng.choice(len(lib), size=min(a.cands, len(lib)), replace=False))
    cands = np.array(lib[idx])
    print(f"corpus {a.file} {n}B; {len(cands)} candidate rules from {lib.shape[0]}-rule library; K={a.K}", flush=True)

    # precompute each candidate's standardized feature splits (the expensive step)
    t0 = time.time(); feats = []
    for j in range(len(cands)):
        F = feat_for_rule(cands[j], data, a.side, a.ticks, a.rcells, a.reps, a.decay)[s:e]
        feats.append(caca.standardize(*caca.split3(F, i1, i2)))
        if (j + 1) % 50 == 0:
            print(f"  precomputed {j+1}/{len(cands)} [{time.time()-t0:.0f}s]", flush=True)
    print(f"precompute done [{time.time()-t0:.0f}s]\n", flush=True)

    base_acc = acc(Xc_va, ridge_fit(Xc_tr, Yoh), yva)
    ctx_te = acc(Xc_te, ridge_fit(Xc_tr, Yoh), yte)
    print(f"context-only:  val {base_acc:.3f}   test {ctx_te:.3f}\n")

    # --- matching pursuit: greedily add the rule that best explains the residual ---
    sel = []; Xtr = Xc_tr.copy(); Yoh_va = np.eye(C)[yva]
    print(f"greedy data-conditioned selection (matching pursuit, select={a.select}):")
    for k in range(a.K):
        W = ridge_fit(Xtr, Yoh)
        if a.select == "val":                            # held-out residual (less overfit)
            Xva_cur = np.hstack([Xc_va] + [feats[i][1] for i in sel]) if sel else Xc_va
            R = Yoh_va - Xva_cur @ W; col = 1
        else:                                            # train residual (overfits)
            R = Yoh - Xtr @ W; col = 0
        best = (-1.0, None)
        for j in range(len(cands)):
            if j in sel: continue
            score = float(np.sum((feats[j][col].T @ R) ** 2))   # block's explained residual
            if score > best[0]: best = (score, j)
        j = best[1]; sel.append(j)
        Xtr = np.hstack([Xtr, feats[j][0]])
        Xva = np.hstack([Xc_va] + [feats[i][1] for i in sel])
        va = acc(Xva, ridge_fit(Xtr, Yoh), yva)
        print(f"  +expert {k+1}: rule#{j}  -> val acc {va:.3f}", flush=True)

    # --- baseline: random K-rule draws at matched K ---
    rand = []
    for _ in range(5):
        ridx = rng.choice(len(cands), size=a.K, replace=False)
        Xtr_r = np.hstack([Xc_tr] + [feats[i][0] for i in ridx])
        Xva_r = np.hstack([Xc_va] + [feats[i][1] for i in ridx])
        rand.append(acc(Xva_r, ridge_fit(Xtr_r, Yoh), yva))

    # --- final held-out TEST comparison ---
    Xtr_mp = np.hstack([Xc_tr] + [feats[i][0] for i in sel])
    Xte_mp = np.hstack([Xc_te] + [feats[i][2] for i in sel])
    mp_te = acc(Xte_mp, ridge_fit(Xtr_mp, Yoh), yte)
    # one random draw's test acc for reference
    ridx = rng.choice(len(cands), size=a.K, replace=False)
    Xtr_r = np.hstack([Xc_tr] + [feats[i][0] for i in ridx])
    Xte_r = np.hstack([Xc_te] + [feats[i][2] for i in ridx])
    rand_te = acc(Xte_r, ridge_fit(Xtr_r, Yoh), yte)

    print(f"\n=== K={a.K} experts ===")
    print(f"{'model':<28}{'val acc':>9}{'test acc':>10}")
    print(f"{'context only':<28}{base_acc:>9.3f}{ctx_te:>10.3f}")
    print(f"{'random K draw':<28}{np.mean(rand):>9.3f}{rand_te:>10.3f}  (val +-{np.std(rand):.3f})")
    print(f"{'matching-pursuit K':<28}{va:>9.3f}{mp_te:>10.3f}")
    gain = mp_te - rand_te
    print(f"\nMP vs random (test): {gain:+.3f}  -> "
          + ("data-conditioned selection HELPS" if gain > 0.01 else
             "no clear gain over random draw"))

if __name__ == "__main__":
    main()
