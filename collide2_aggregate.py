#!/usr/bin/env python3
# collide2_aggregate.py — rank collide-v2 collision-gate candidates.
import glob, json, os, sys
import numpy as np

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/collide-v2/outputs"
    rows = []
    for f in glob.glob(os.path.join(d, "result_*.json")):
        rows += json.load(open(f))
    if not rows:
        print("no results yet"); return
    from collections import Counter
    g = Counter(r["gate"] for r in rows)
    print(f"{len(rows)} bases characterised as collision gates")
    print(f"  gate types: {dict(g)}")
    best_xor = sorted(rows, key=lambda r: -r["xor_frac"])[:8]
    best_and = sorted(rows, key=lambda r: -r["and_frac"])[:5]
    print("\n  best XOR/annihilation gates (singles survive, pair annihilates):")
    for r in best_xor:
        print(f"    xor_frac {r['xor_frac']:.2f} (tested {r['tested']})  "
              f"cx={r['cx']:+.3f} cy={r['cy']:+.3f} span={r['span']:.3f}")
    print("\n  best AND/product gates (pair makes a new structure):")
    for r in best_and:
        print(f"    and_frac {r['and_frac']:.2f} (tested {r['tested']})  "
              f"cx={r['cx']:+.3f} cy={r['cy']:+.3f} span={r['span']:.3f}")
    nclean = sum(1 for r in rows if r["gate"] != "inconsistent")
    print(f"\n  consistent gates (>60% one type): {nclean}/{len(rows)}")
    if best_xor and best_xor[0]["xor_frac"] >= 0.8:
        print("  -> a robust glider-collision XOR gate exists: surgery-built domains give")
        print("     collision logic. This is the computational primitive.")
    else:
        print("  -> gates are impact-parameter-sensitive; the best candidates are above.")
        print("     Next: fine impact/timing scan around the top base for a stable truth table.")

if __name__ == "__main__":
    main()
