#!/usr/bin/env python3
# boundary.py — can a SINGLE fractal rule emit gliders in MULTIPLE directions?
# dir_control showed direction is set by fractal location (one direction per
# region). If a rule near a direction-DOMAIN BOUNDARY is bistable, different seeds
# might launch gliders different ways within ONE rule -> two gliders, same lattice,
# opposing -> a COLLISION becomes possible (re-opening collision-based logic for
# our otherwise-anisotropic fractal rules). Test: per rule, launch many seeds,
# measure within-rule direction spread; flag multi-directional rules.
import json, os
import numpy as np
import rulehub, glider_dir

LIB = "alice/swarm-v1/outputs"

def within_rule_dirs(lut, nseeds=14):
    angs = []
    for s in range(nseeds):
        v = glider_dir.glider_velocity(lut, seed=1000 + s)
        if v is not None: angs.append(v[0])
    return angs

def main():
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    blobs = os.path.join(LIB, "blobs")
    rng = np.random.default_rng(0)
    idx = rng.choice(len(recs), size=min(400, len(recs)), replace=False)
    multi = []  # rules whose gliders span multiple directions
    Rs = []
    for k in idx:
        r = recs[k]
        lut = np.fromfile(os.path.join(blobs, r["hash"] + ".lut"), dtype=np.uint8, count=16384)
        angs = within_rule_dirs(lut)
        if len(angs) < 6:    # need enough glider-producing seeds to judge
            continue
        R = glider_dir.circ_stats(angs)
        Rs.append(R)
        # multi-directional = low within-rule alignment AND a real angular gap
        a = np.array(angs)
        # max pairwise angular distance
        gaps = [abs(np.angle(np.exp(1j * (a[i] - a[j])))) for i in range(len(a)) for j in range(i + 1, len(a))]
        maxgap = max(gaps) if gaps else 0
        if R < 0.6 and maxgap > 2.0:   # >~115 deg spread within one rule
            multi.append((R, maxgap, r["hash"], r["cx"], r["cy"], len(angs)))
    Rs = np.array(Rs)
    print(f"measured within-rule direction spread for {len(Rs)} Newton glider rules")
    print(f"within-rule alignment R: mean {Rs.mean():.2f}, "
          f"frac with R<0.6 (multi-directional): {100*(Rs<0.6).mean():.0f}%, "
          f"R<0.4: {100*(Rs<0.4).mean():.0f}%")
    multi.sort()
    print(f"\nrules emitting gliders in MULTIPLE directions (R<0.6, max gap>115deg): {len(multi)}")
    for R, gap, h, cx, cy, n in multi[:8]:
        print(f"  {h}  R={R:.2f} maxgap={np.degrees(gap):.0f}deg  cx={cx:.3f} cy={cy:.3f} ({n} gliders)")
    if multi:
        print("\n-> these single rules support gliders in opposing directions: COLLISION-")
        print("   CAPABLE candidates. Next: launch two opposing gliders from one and test.")
    else:
        print("\n-> every rule's gliders are essentially unidirectional (high within-rule R):")
        print("   single-rule collisions remain impossible with fractal rules; isotropic")
        print("   rules (Wuensche iso-rule / Spiral rule) are the route, as the literature says.")

if __name__ == "__main__":
    main()
