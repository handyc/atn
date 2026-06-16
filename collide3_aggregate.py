#!/usr/bin/env python3
# collide3_aggregate.py — does any base give a ROBUST collision gate?
import glob, json, os, sys
import numpy as np

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/collide-v3/outputs"
    rows = []
    for f in glob.glob(os.path.join(d, "result_*.json")):
        rows += json.load(open(f))
    if not rows:
        print("no results yet"); return
    from collections import Counter
    print(f"{len(rows)} bases deep-scanned (impact × timing × seeds)")
    print(f"  stability classes: {dict(Counter(r['stable'] for r in rows))}")
    perfect_pt = [r for r in rows if r["best_xor"] >= 0.99 or r["best_and"] >= 0.99]
    print(f"  bases with a perfect-fidelity gate POINT: {len(perfect_pt)}/{len(rows)}")
    print("\n  largest XOR regions (fraction of (dy,px) grid that is a clean XOR):")
    for r in sorted(rows, key=lambda r: -r["xor_region"])[:6]:
        print(f"    xor_region {r['xor_region']:.2f}  best {r['best_xor']:.2f} @dy,px={r['best_xor_pt']}  "
              f"cx={r['cx']:+.3f} cy={r['cy']:+.3f} span={r['span']:.3f}")
    print("  largest AND regions:")
    for r in sorted(rows, key=lambda r: -r["and_region"])[:6]:
        print(f"    and_region {r['and_region']:.2f}  best {r['best_and']:.2f} @dy,px={r['best_and_pt']}  "
              f"cx={r['cx']:+.3f} cy={r['cy']:+.3f} span={r['span']:.3f}")
    stable = [r for r in rows if r["stable"] in ("XOR", "AND")]
    if stable:
        print(f"\n  -> {len(stable)} base(s) have a STABLE gate region (>25% of operating points):")
        print("     a robust glider-collision gate. The top base is the gate to feature.")
    else:
        print("\n  -> gates are POINT-like (clean at specific impact/timing, fidelity 1.0, but")
        print("     small regions): collision logic works at a tuned operating point, not")
        print("     robustly across impact parameter. Honest result for the paper.")

if __name__ == "__main__":
    main()
