#!/usr/bin/env python3
# stackga2_aggregate.py — collect the DEEPER stacking search: did the GA find emergent,
# localized, coherently-translating structures at the layer intersections?
import glob, json, os, sys
import numpy as np
from collections import Counter

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/stackga-v2/outputs"
    R = [json.load(open(f)) for f in glob.glob(os.path.join(d, "result_*.json"))]
    if not R:
        print("no results yet"); return
    R.sort(key=lambda r: -r["fitness"])
    fits = [r["fitness"] for r in R]
    print(f"{len(R)} deeper GA islands. fitness: best {fits[0]:.3f}, median {np.median(fits):.3f}\n")
    print("winning operator:", dict(Counter(r["genome"]["op"] for r in R)))
    print("winning L:", dict(Counter(r["genome"]["L"] for r in R)))
    print("vertical coupling vc among top-20:",
          f"{np.mean([r['genome'].get('vc',0) for r in R[:20]]):.2f} mean "
          f"({sum(1 for r in R[:20] if r['genome'].get('vc',0)>0.05)}/20 use it)")
    # genuine emergent glider = localized + coherently translating + persistent
    glide = [r for r in R if r["inter_motion"] > 0.4 and r["drift_R"] > 0.6
             and r["inter_occ"] < 0.06 and r["inter_mass"] > 12]
    print(f"\nislands with an EMERGENT intersection glider (motion>0.4, driftR>0.6, "
          f"localized, persistent): {len(glide)}/{len(R)}")
    print("\ntop 8:")
    print("  fitness  op       L  vc    motion  driftR  occ     mass")
    for r in R[:8]:
        g = r["genome"]
        print(f"  {r['fitness']:.3f}   {g['op']:7s} {g['L']}  {g.get('vc',0):.2f}  "
              f"{r['inter_motion']:.2f}    {r['drift_R']:.2f}    {r['inter_occ']:.3f}   {r['inter_mass']:.0f}")
    b = R[0]; g = b["genome"]
    print(f"\nBEST (fitness {b['fitness']:.3f}): L={g['L']}, op={g['op']}, vc={g.get('vc',0):.2f}, "
          f"p={g['p']:.2f}, period={g['period']}")
    print(f"  layer rules (cx,cy,span): {[[round(x,3) for x in ly] for ly in g['layers']]}")
    print(f"  emergent intersection structure: motion {b['inter_motion']:.2f}, drift coherence "
          f"R={b['drift_R']:.2f}, occupancy {b['inter_occ']:.3f}, mass {b['inter_mass']:.0f} cells")
    if glide:
        print(f"\n  -> REAL RESULT: {len(glide)} stacking schemes breed a localized, coherently")
        print("     moving structure at the layer overlap — an emergent glider the individual")
        print("     layers do not have. Replay the top genome to visualise / verify.")
    else:
        print("\n  -> no clean emergent glider cleared the bar; report best partial dynamics.")

if __name__ == "__main__":
    main()
