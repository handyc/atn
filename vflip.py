#!/usr/bin/env python3
# vflip.py — explain the de-novo synthesis vertical 180-deg flip. Hex has NO pure
# north/south neighbor: "up" must be built from the SYMMETRIC pair (nw,ne) whose
# horizontal parts cancel. Hypotheses:
#   (1) The LAW (heading=angle(F)+180) is clean at vertical — surgery on a real
#       glider bulk hits 90/270 correctly; only the crude excitable TEMPLATE flips.
#   (2) The flip is the degenerate-tie artifact: a symmetric (nw+ne) up-vector flips,
#       but an asymmetric single-neighbor up-ish vector obeys the law.
import numpy as np
import rulehub
from mechanism import DIRV, SHIFT, cmean, cR, cdiff, measured_heading
from design import design_edit
from synthesize import build, evolve

LIB = "alice/swarm-v1/outputs"
DIR_SHIFT = {k: SHIFT[k] for k in DIRV}
DIR_ANG = {k: float(np.arctan2(v[0], v[1])) for k, v in DIRV.items()}
KEYS = np.arange(16384); SELF = (KEYS >> 12) & 3
NB = {k: (KEYS >> s) & 3 for k, s in DIR_SHIFT.items()}

def build_from_dirs(dirset, birth="one"):
    cnt = sum((NB[k] > 0).astype(int) for k in dirset)
    out = np.zeros(16384, np.uint8)
    trig = (cnt == 1) if birth == "one" else (cnt >= 1)
    out[(SELF == 0) & trig] = 1
    m = (SELF > 0) & (cnt >= 1); out[m] = SELF[m]
    return out

def denovo_heading(lut, seeds=6):
    hs = [evolve(lut, s) for s in range(seeds)]
    hs = [h for k, h in hs if k == "translating" and h is not None]
    return (cmean(hs), cR(hs), len(hs)) if len(hs) >= 3 and cR(hs) > 0.6 else (None, None, len(hs))

def main():
    import json, os
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    blobs = os.path.join(LIB, "blobs")
    rng = np.random.default_rng(0)
    luts = [np.fromfile(os.path.join(blobs, recs[i]["hash"] + ".lut"), dtype=np.uint8, count=16384)
            for i in rng.choice(len(recs), 12, replace=False)]

    print("=== (1) Does the LAW flip at vertical? Surgery on real glider bulks ===")
    for tg in (70, 80, 90, 100, 110, 250, 260, 270, 280, 290):
        phi = np.radians(tg) - np.pi
        hh = [measured_heading(design_edit(l, phi)) for l in luts]
        hh = [h for h in hh if h is not None]
        if hh:
            mh = np.degrees(cmean(hh)); err = np.degrees(cdiff(cmean(hh), np.radians(tg)))
            print(f"  target {tg:3d}: realized {mh:+7.1f}  err {err:3.0f}  (n={len(hh)})")
    print("  -> if errors stay small through 90/270, the LAW has no vertical flip;")
    print("     the de-novo flip is a TEMPLATE artifact.\n")

    print("=== (2) De-novo near vertical: where does the flip turn on? ===")
    for tg in (60, 75, 90, 105, 120, 240, 255, 270, 285, 300):
        phi = np.radians(tg) - np.pi
        mh, R, n = denovo_heading(build(phi, 0.3, "one"))
        if mh is not None:
            err = np.degrees(cdiff(mh, np.radians(tg)))
            flip = "FLIP" if err > 120 else ("ok" if err < 30 else "partial")
            print(f"  target {tg:3d}: {np.degrees(mh):+7.1f}  err {err:3.0f}  [{flip}]")
        else:
            print(f"  target {tg:3d}: (no clean mover, n={n})")
    print()

    print("=== (3) Symmetric vs asymmetric 'up' vector (the degeneracy test) ===")
    cases = {"nw+ne (symmetric up)": ["nw", "ne"], "nw only (asym up-left)": ["nw"],
             "ne only (asym up-right)": ["ne"], "sw+se (symmetric down)": ["sw", "se"]}
    for name, ds in cases.items():
        Fy = sum(DIRV[k][0] for k in ds); Fx = sum(DIRV[k][1] for k in ds)
        predicted = np.degrees((np.arctan2(Fy, Fx) + np.pi + np.pi) % (2*np.pi) - np.pi)
        mh, R, n = denovo_heading(build_from_dirs(ds))
        got = f"{np.degrees(mh):+.0f}" if mh is not None else f"(no mover n={n})"
        print(f"  {name:<26} law predicts {predicted:+6.0f}  ->  de-novo {got}"
              + (f"  R={R:.2f}" if R else ""))
    print("\n  -> if asymmetric single-neighbor builds OBEY the law but the symmetric")
    print("     pairs flip, the flip is the vertical-degeneracy tie-break of the")
    print("     excitable front, not the direction law.")

if __name__ == "__main__":
    main()
