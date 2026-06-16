#!/usr/bin/env python3
# dir_control.py — causal test of "fractal location controls glider direction".
# From the library, find two fractal regions whose gliders head DIFFERENT ways,
# then GENERATE fresh rules in each and check the new gliders go the predicted
# (different) directions. Correlation -> causation.
import json, os
import numpy as np
import rulehub, glider_dir, target_gen

LIB = "alice/swarm-v1/outputs"

def circ_mean(a):
    return np.arctan2(np.sin(a).mean(), np.cos(a).mean())

def main():
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    blobs = os.path.join(LIB, "blobs")
    rows = []
    for r in recs[:1200]:
        lut = np.fromfile(os.path.join(blobs, r["hash"] + ".lut"), dtype=np.uint8, count=16384)
        v = glider_dir.glider_velocity(lut)
        if v is not None:
            rows.append((r["cx"], r["cy"], r["span"], v[0]))
    cx, cy, sp, ang = map(np.array, zip(*rows))
    nb = 8
    bx = np.clip(((cx - cx.min()) / (np.ptp(cx) + 1e-9) * nb).astype(int), 0, nb - 1)
    by = np.clip(((cy - cy.min()) / (np.ptp(cy) + 1e-9) * nb).astype(int), 0, nb - 1)
    bid = bx * nb + by
    bins = {}
    for b in np.unique(bid):
        m = bid == b
        if m.sum() >= 15:
            bins[b] = (circ_mean(ang[m]), cx[m].mean(), cy[m].mean(), np.median(sp[m]), m.sum())
    # pick the two bins with the most different mean angle
    best = None
    ks = list(bins)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            d = abs(np.angle(np.exp(1j * (bins[ks[i]][0] - bins[ks[j]][0]))))
            if best is None or d > best[0]: best = (d, ks[i], ks[j])
    _, A, B = best
    for tag, k in (("A", A), ("B", B)):
        ang0, ccx, ccy, msp, cnt = bins[k]
        print(f"region {tag}: predicted heading {np.degrees(ang0):6.1f} deg  "
              f"(from {cnt} library gliders near cx={ccx:.3f},cy={ccy:.3f},span~{msp:.3f})")
    print()
    rng = np.random.default_rng(7)
    for tag, k in (("A", A), ("B", B)):
        ang0, ccx, ccy, msp, _ = bins[k]
        measured = []
        for _ in range(220):
            lut = target_gen.newton_lut(rng.normal(ccx, 0.05), rng.normal(ccy, 0.05),
                                        msp * rng.uniform(0.8, 1.2))
            if rulehub.classify_hex(lut, ticks=12, seed=0) != 4: continue
            v = glider_dir.glider_velocity(lut)
            if v is not None: measured.append(v[0])
        if measured:
            mm = np.degrees(circ_mean(np.array(measured)))
            R = glider_dir.circ_stats(measured)
            print(f"region {tag}: GENERATED {len(measured)} gliders -> mean heading {mm:6.1f} deg "
                  f"(alignment R={R:.2f}; predicted {np.degrees(ang0):.1f})")
    print("\nverdict: if generated headings match each region's prediction AND the two")
    print("regions differ, fractal location CAUSALLY controls glider direction.")

if __name__ == "__main__":
    main()
