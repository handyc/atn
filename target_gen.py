#!/usr/bin/env python3
# target_gen.py — close the loop on the geomap finding: if gliders are regionally
# concentrated, a TARGETED generator (sample the glider-rich Newton region at the
# glider-favoured zoom) should out-yield the blind walk. Causal test: generate in
# the targeted region vs blind, measure glider yield.
import argparse, json, os
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=200, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    return rulehub._posterise(rulehub._newton(gx, gy, it), it)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("outdir"); ap.add_argument("--n", type=int, default=400)
    a = ap.parse_args()
    recs = [r for r in json.load(open(os.path.join(a.outdir, "library.json"))) if r["family"] == "newton"]
    gl = [r for r in recs if r["glider"]]
    cx = np.array([r["cx"] for r in gl]); cy = np.array([r["cy"] for r in gl]); sp = np.array([r["span"] for r in gl])
    cxm, cym = np.median(cx), np.median(cy); cxs, cys = cx.std() + 1e-3, cy.std() + 1e-3
    sp_lo, sp_hi = np.quantile(sp, 0.25), np.quantile(sp, 0.75)
    print(f"newton glider region (from {len(gl)} library gliders): "
          f"cx~{cxm:.3f}+-{cxs:.3f} cy~{cym:.3f}+-{cys:.3f} span in [{sp_lo:.3f},{sp_hi:.3f}]")
    rng = np.random.default_rng(1)

    def yield_of(targeted):
        hits = 0
        for i in range(a.n):
            if targeted:
                lut = newton_lut(rng.normal(cxm, cxs), rng.normal(cym, cys), rng.uniform(sp_lo, sp_hi))
            else:
                c = [(0, 0, 3.0), (0, 0, 0.6)][i % 2]
                lut = newton_lut(c[0] + (rng.random() * 2 - 1) * 0.3 * c[2],
                                 c[1] + (rng.random() * 2 - 1) * 0.3 * c[2],
                                 c[2] * (0.4 + 0.8 * rng.random()))
            if rulehub.classify_hex(lut, ticks=12, seed=i) == 4 and rulehub.glider_disp(lut, seed=i) > 3.0:
                hits += 1
        return hits / a.n

    tb = yield_of(False); tt = yield_of(True)
    print(f"\nglider yield over {a.n} candidates:")
    print(f"  blind Newton walk : {tb*100:5.1f}%")
    print(f"  TARGETED region   : {tt*100:5.1f}%")
    print(f"  -> {tt/max(tb,1e-9):.1f}x  ({'TARGETING WORKS — fractal location is causal' if tt > tb*1.3 else 'no real gain'})")

if __name__ == "__main__":
    main()
