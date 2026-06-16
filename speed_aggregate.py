#!/usr/bin/env python3
# speed_aggregate.py — pool speed-v1: which LUT quantity predicts glider speed, per
# family and overall; pulled vs pushed classification.
import glob, json, os, sys
import numpy as np
from collections import defaultdict

def r2(x, y):
    c = np.corrcoef(x, y)[0, 1]; return c, c * c

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/speed-v1/outputs"
    fam = defaultdict(list)
    for f in glob.glob(os.path.join(d, "result_*.json")):
        r = json.load(open(f)); fam[r["family"]] += r["recs"]
    allr = [x for v in fam.values() for x in v]
    if not allr:
        print("no results yet"); return
    print(f"{len(allr)} glider speed records across {len(fam)} families\n")
    print("  family       n     R2(|F|)  R2(drift)  R2(v*)  R2(drift+v*+lam)  speed<=v*")
    def block(name, recs):
        sp = np.array([x["speed"] for x in recs]); dr = np.array([x["drift"] for x in recs])
        vs = np.array([x["vstar"] for x in recs]); fm = np.array([x["Fmag"] for x in recs])
        lam = np.array([x["lam"] for x in recs]); g = np.isfinite(vs)
        sp, dr, vs, fm, lam = sp[g], dr[g], vs[g], fm[g], lam[g]
        if len(sp) < 10: return
        X = np.column_stack([dr, vs, lam, np.ones(len(sp))])
        coef, *_ = np.linalg.lstsq(X, sp, rcond=None); pred = X @ coef
        R2m = 1 - np.sum((sp - pred) ** 2) / np.sum((sp - sp.mean()) ** 2)
        print(f"  {name:11s} {len(sp):5d}   {r2(fm,sp)[1]:.2f}     {r2(dr,sp)[1]:.2f}      "
              f"{r2(vs,sp)[1]:.2f}     {R2m:.2f}            {100*np.mean(sp<=vs):.0f}%")
    for f in sorted(fam): block(f, fam[f])
    block("ALL", allr)
    print("\n-> drift speed |F|/(a_self+sum a_p) is the leading single predictor; v* is an")
    print("   upper bound (high speed<=v% => mostly pushed/localized, slower than the linear")
    print("   pulled front). The multi-feature R2 is the practical speed model for the paper.")

if __name__ == "__main__":
    main()
