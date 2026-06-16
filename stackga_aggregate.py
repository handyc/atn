#!/usr/bin/env python3
# stackga_aggregate.py — collect the GA-island search over stacking schemes: which
# coupling schemes produce the most interesting emergent dynamics?
import glob, json, os, sys
import numpy as np
from collections import Counter

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/stackga-v1/outputs"
    R = [json.load(open(f)) for f in glob.glob(os.path.join(d, "result_*.json"))]
    if not R:
        print("no results yet"); return
    R.sort(key=lambda r: -r["fitness"])
    print(f"{len(R)} GA islands. fitness: best {R[0]['fitness']:.3f}, "
          f"median {np.median([r['fitness'] for r in R]):.3f}\n")
    print("winning coupling operator across islands:",
          dict(Counter(r["genome"]["op"] for r in R)))
    print("winning layer count L:", dict(Counter(r["genome"]["L"] for r in R)))
    print("\ntop 8 stacking schemes (most interesting emergent dynamics):")
    print("  fitness  op       L  mean_change  change_var  struct")
    for r in R[:8]:
        g = r["genome"]
        print(f"  {r['fitness']:.3f}   {g['op']:7s} {g['L']}   {r['mean_change']:.3f}        "
              f"{r['change_var']:.4f}     {r['structure']:.2f}")
    best = R[0]; g = best["genome"]
    print(f"\nBEST scheme (fitness {best['fitness']:.3f}):")
    print(f"  L={g['L']} layers, op={g['op']}, p={g['p']:.2f}, period={g['period']}")
    print(f"  directions (deg): {[round(t) for t in g['thetas']]}")
    print(f"  coupling W:")
    for row in g["W"]: print("    ", [round(x, 2) for x in row])
    print(f"  thresholds tau: {[round(x,2) for x in g['tau']]}")
    print(f"  -> mean change {best['mean_change']:.3f}/step (edge-of-chaos band ~0.12),")
    print(f"     change variance {best['change_var']:.4f} (fluctuation = structures coming/going),")
    print(f"     spatial structure {best['structure']:.2f}.")
    hi = [r for r in R if r["fitness"] > 0.3 and r["change_var"] > 0.003 and r["structure"] > 0.15]
    print(f"\n  islands with genuinely interesting dynamics (fit>0.3, fluctuating, structured): "
          f"{len(hi)}/{len(R)}")
    if hi:
        print("  -> promising: GA found stacking schemes with bounded, fluctuating, structured")
        print("     stack-level dynamics — emergent behaviour worth replaying/visualising.")
    else:
        print("  -> modest: best schemes are bounded+sustained but not strongly structured;")
        print("     report honestly and consider a structure-weighted fitness in v2.")

if __name__ == "__main__":
    main()
