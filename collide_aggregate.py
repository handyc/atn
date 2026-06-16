#!/usr/bin/env python3
# collide_aggregate.py — summarise collide-v1: do any cross-domain glider collisions
# interact, or is it pass-through everywhere?
import glob, json, os, sys
import numpy as np

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/collide-v1/outputs"
    rows = []
    for f in glob.glob(os.path.join(d, "result_*.json")):
        rows += json.load(open(f))
    if not rows:
        print("no results yet"); return
    from collections import Counter
    v = Counter(r["verdict"] for r in rows)
    print(f"{len(rows)} clean cross-domain collision tests")
    print(f"  verdicts: {dict(v)}")
    inter = [r for r in rows if r["verdict"] != "passthrough"]
    mr = np.array([r["min_ratio"] for r in rows])
    print(f"  min mass ratio vs superposition: median {np.median(mr):.2f}, min {mr.min():.2f}")
    print(f"  interacting (non-passthrough): {len(inter)}/{len(rows)} "
          f"({100*len(inter)/len(rows):.0f}%)")
    if inter:
        print("\n  strongest interactions:")
        for r in sorted(inter, key=lambda r: r["min_ratio"])[:10]:
            print(f"    {r['verdict']:11s} min_ratio {r['min_ratio']:.2f} end {r['end_ratio']:.2f}  "
                  f"cx={r['cx']:+.3f} cy={r['cy']:+.3f} span={r['span']:.3f} D={r['D']}")
        print("\n  -> these cross-domain pairs INTERACT: candidate glider-collision gates.")
        print("     Next: replicate the strongest, vary impact parameter, look for a")
        print("     consistent product (gate primitive).")
    else:
        print("\n  -> all pass-through: cross-domain collisions don't interact either;")
        print("     collision logic stays blocked for these surgery'd anisotropic rules.")

if __name__ == "__main__":
    main()
