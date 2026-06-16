#!/usr/bin/env python3
# gen_aggregate.py — pool gen-v1 universality results per (substrate,K): does the
# direction law heading=angle(-F) hold? Reports circular correlation (2D) / median
# angle error (3D), and the GROWTH(-F) vs COPY(+F) regime split.
import glob, json, os, sys
import numpy as np
from collections import defaultdict

def cdiff(a, b): return abs(np.angle(np.exp(1j * (a - b))))
def ccorr(al, be):
    al, be = np.radians(al), np.radians(be)
    am = np.arctan2(np.sin(al).mean(), np.cos(al).mean()); bm = np.arctan2(np.sin(be).mean(), np.cos(be).mean())
    num = np.sum(np.sin(al - am) * np.sin(be - bm))
    return float(num / (np.sqrt(np.sum(np.sin(al - am) ** 2) * np.sum(np.sin(be - bm) ** 2)) + 1e-12))

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/gen-v1/outputs"
    agg = defaultdict(lambda: {"dim": None, "pairs2d": [], "err3d": [], "ntry": 0})
    for f in glob.glob(os.path.join(d, "result_*.json")):
        r = json.load(open(f)); key = (r["substrate"], r["K"])
        agg[key]["dim"] = r["dim"]; agg[key]["ntry"] += r["n_tried"]
        if r["dim"] == 2: agg[key]["pairs2d"] += r["pairs"]
        else: agg[key]["err3d"] += r["pairs"]
    print(f"universality of heading=angle(-F) across substrates\n")
    print("  substrate   K  dim   gliders   law-fit                    growth/copy split")
    for (sub, K) in sorted(agg):
        a = agg[(sub, K)]
        if a["dim"] == 2:
            m = np.array([p[0] for p in a["pairs2d"]]); p = np.array([p[1] for p in a["pairs2d"]])
            if len(m) < 10: continue
            err_g = np.degrees([cdiff(np.radians(m[i]), np.radians(p[i])) for i in range(len(m))])
            err_c = np.degrees([cdiff(np.radians(m[i]), np.radians(p[i] + 180)) for i in range(len(m))])
            growth = float(np.mean(err_g < err_c))
            fit = f"corr {ccorr(m, p):+.2f}, med {np.median(err_g):3.0f}deg, <45 {100*(err_g<45).mean():3.0f}%"
            print(f"  {sub:9s} {K:2d}   2   {len(m):6d}   {fit:26s} growth {100*growth:3.0f}% / copy {100*(1-growth):3.0f}%")
        else:
            eg = np.array(a["err3d"]); ec = 180 - eg
            if len(eg) < 10: continue
            growth = float(np.mean(eg < ec))
            print(f"  {sub:9s} {K:2d}   3   {len(eg):6d}   med-angle(-F) {np.median(eg):3.0f}deg, <45 {100*(eg<45).mean():3.0f}%   "
                  f"growth {100*growth:3.0f}% / copy {100*(1-growth):3.0f}%")
    print("\n-> the law holds where 'growth%' is high & error low. High K / 3D shift toward")
    print("   the COPY regime (motion toward F, heading=angle(F)) — the +180 sign is")
    print("   growth-specific, as the linearization predicts.")

if __name__ == "__main__":
    main()
