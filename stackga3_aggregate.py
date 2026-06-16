#!/usr/bin/env python3
# stackga3_aggregate.py — did feedback-aware evolution find recurrent/memory stacks?
import glob, json, os, sys
import numpy as np
from collections import Counter
def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/stackga-v3/outputs"
    R = [json.load(open(f)) for f in glob.glob(os.path.join(d, "result_*.json"))]
    if not R: print("no results yet"); return
    R.sort(key=lambda r: -r["fitness"])
    mem = [r["memory"] for r in R]; per = [r["periodicity"] for r in R]
    print(f"{len(R)} feedback-aware islands. fitness best {R[0]['fitness']:.2f}, median {np.median([r['fitness'] for r in R]):.2f}")
    print(f"memory time: best {max(mem):.0f} steps, median {np.median(mem):.0f}")
    print(f"evolved feedback vf among top-20: mean {np.mean([r['genome']['vf'] for r in R[:20]]):.2f} "
          f"({sum(1 for r in R[:20] if r['genome']['vf']>0.05)}/20 keep feedback)")
    print("winning op:", dict(Counter(r['genome']['op'] for r in R[:30])), " L:", dict(Counter(r['genome']['L'] for r in R[:30])))
    strong = [r for r in R if r["memory"]>=15 and r["periodicity"]>0.5 and 0.03<r["activity"]<0.3]
    print(f"\nstacks with long memory (>=15) + recurrence + good activity: {len(strong)}/{len(R)}")
    print("\ntop 8 (recurrent/reservoir-like):")
    print("  fitness  op       L  vf    memory  period  activity")
    for r in R[:8]:
        g=r["genome"]; print(f"  {r['fitness']:.2f}    {g['op']:7s} {g['L']}  {g['vf']:.2f}  {r['memory']:5.0f}   {r['periodicity']:.2f}    {r['activity']:.3f}")
    b=R[0]; g=b["genome"]
    print(f"\nBEST: L={g['L']} op={g['op']} vf={g['vf']:.2f} p={g['p']:.2f} period={g['period']}")
    print(f"  layers (cx,cy,span): {[[round(x,3) for x in ly] for ly in g['layers']]}")
    print(f"  memory {b['memory']:.0f} steps, periodicity {b['periodicity']:.2f}, activity {b['activity']:.3f}")
    print("\n  NOTE: verify the top genome on HELD-OUT seeds before claiming (fitness used 3 seeds).")
if __name__ == "__main__": main()
