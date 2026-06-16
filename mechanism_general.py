#!/usr/bin/env python3
# mechanism_general.py — confirm the single-neighbor activation law (glider heading
# = angle(F_single) + 180deg, found in mechanism.py: corr 0.95, median err 4deg) is
# a SUBSTRATE law, not Newton-specific. The probe and the glider are both LUT/lattice
# only; the fractal family merely generates the LUT — so it must hold for every
# family. Test per family on held-out rules.
import json, os
import numpy as np
import rulehub, glider_dir
from mechanism import flow_angle, measured_heading, cmean, cR, cdiff, ccorr

LIB = "alice/swarm-v1/outputs"

def main():
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json"))) if r["glider"]]
    blobs = os.path.join(LIB, "blobs")
    rng = np.random.default_rng(11)
    print("single-neighbor activation law (predicted heading = angle(F)+180deg) per family:")
    print("  family       n   circ-circ-corr  residual-R  med-err  <45deg")
    for fam in ("newton", "julia", "mandelbrot", "burning"):
        fr = [r for r in recs if r["family"] == fam]
        idx = rng.choice(len(fr), size=min(160, len(fr)), replace=False)
        meas, pred = [], []
        for k in idx:
            lut = np.fromfile(os.path.join(blobs, fr[k]["hash"] + ".lut"), dtype=np.uint8, count=16384)
            m = measured_heading(lut)
            if m is None: continue
            fa, fs = flow_angle(lut, "single")
            if fs < 1e-3: continue
            meas.append(m); pred.append(fa)
        if len(meas) < 15:
            print(f"  {fam:<10} {len(meas):>4}   (too few)"); continue
        meas, pred = np.array(meas), np.array(pred)
        base = pred + np.pi                                   # the fixed +180deg law
        R = cR(meas - base)
        err = np.array([np.degrees(cdiff(meas[i], base[i])) for i in range(len(meas))])
        print(f"  {fam:<10} {len(meas):>4}      {ccorr(pred, meas):+.2f}        {R:.2f}      "
              f"{np.median(err):4.0f}     {100*(err<45).mean():.0f}%")
    print("\n-> if all families show high corr + low error, the law is a property of the")
    print("   HEX SUBSTRATE (LUT geometry), independent of how the LUT was generated.")

if __name__ == "__main__":
    main()
