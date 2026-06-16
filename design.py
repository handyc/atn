#!/usr/bin/env python3
# design.py — direct-design inversion of the single-neighbor activation law
# (glider heading = angle(F)+180deg, F = sum_p a_p*unit_dir(p), a_p = fraction of
# the 3 "only neighbor p active" LUT entries that fire the center). If the law is
# GENERATIVE not just predictive, then taking a working glider rule and EDITING
# ONLY those 18 entries to aim F at a chosen heading should STEER the glider there,
# no fractal search. Test: "glider surgery" over many base rules x target headings.
# Measure (1) does it still glide, (2) realized heading vs target, (3) does the
# edited rule's own predicted angle(F)+180 still match (law holds on designed LUTs),
# (4) do off-axis targets snap to hex bond axes?
import json, os
import numpy as np
import rulehub, glider_dir
from mechanism import flow_angle, measured_heading, cmean, cR, cdiff, DIRV, SHIFT

LIB = "alice/swarm-v1/outputs"
DIR_SHIFT = {k: SHIFT[k] for k in DIRV}                 # 6 directional positions
DIR_ANG = {k: np.arctan2(v[0], v[1]) for k, v in DIRV.items()}
HEX_AXES = sorted(((a + np.pi + np.pi) % (2 * np.pi) - np.pi for a in DIR_ANG.values()))

def design_edit(lut, phi):
    # set F to point at phi: each direction p gets a_p ~ max(0, cos(ang_p - phi))
    out = lut.copy()
    for k, s in DIR_SHIFT.items():
        c = max(0.0, np.cos(DIR_ANG[k] - phi))
        nalive = int(round(3 * c))
        for i, v in enumerate((1, 2, 3)):
            out[v << s] = v if i < nalive else 0
    return out

def nearest_axis_err(theta):
    return min(np.degrees(cdiff(theta, a)) for a in HEX_AXES)

def main():
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    blobs = os.path.join(LIB, "blobs")
    rng = np.random.default_rng(9)
    bases = [recs[i] for i in rng.choice(len(recs), size=18, replace=False)]
    base_luts = [np.fromfile(os.path.join(blobs, b["hash"] + ".lut"), dtype=np.uint8, count=16384)
                 for b in bases]
    targets = np.radians(np.arange(0, 360, 30))         # 12 headings, on- and off-axis
    print(f"glider surgery: {len(base_luts)} base rules x {len(targets)} target headings")
    print("editing only 18 single-neighbor LUT entries to aim F at each target.\n")
    print("  target   survive   realized(mean)  err->target  err->nearest-hex-axis  lawR")
    rows = []
    for tg in targets:
        phi = tg - np.pi                                # want angle(F) = tg - 180
        reals, lawpred = [], []
        survive = 0
        for lut in base_luts:
            ed = design_edit(lut, phi)
            h = measured_heading(ed)
            if h is None: continue
            survive += 1
            reals.append(h)
            fa, fs = flow_angle(ed, "single")
            lawpred.append(fa + np.pi)                   # the law's own prediction on the edited rule
        sr = survive / len(base_luts)
        if reals:
            mr = cmean(reals)
            err_t = np.degrees(cdiff(mr, tg))
            err_ax = nearest_axis_err(mr)
            lawR = cR(np.array(reals) - np.array(lawpred))
            rows.append((tg, sr, mr, err_t, err_ax, lawR, len(reals)))
            print(f"  {np.degrees(tg):+6.0f}    {sr*100:3.0f}%      {np.degrees(mr):+7.1f}        "
                  f"{err_t:4.0f}            {err_ax:4.0f}              {lawR:.2f}")
        else:
            print(f"  {np.degrees(tg):+6.0f}    {sr*100:3.0f}%      (no surviving glider)")
    if rows:
        err_t = np.array([r[3] for r in rows]); err_ax = np.array([r[4] for r in rows])
        lawR = np.array([r[5] for r in rows]); sr = np.array([r[1] for r in rows])
        print(f"\n  mean glider survival after surgery: {sr.mean()*100:.0f}%")
        print(f"  mean steering error to requested target: {err_t.mean():.0f} deg")
        print(f"  mean error to nearest hex bond axis:     {err_ax.mean():.0f} deg")
        print(f"  law still predicts edited rules (residual R): {lawR.mean():.2f}")
        print(f"\n  hex bond axes (achievable heading set): "
              f"{[round(np.degrees(a)) for a in HEX_AXES]}")
        if err_ax.mean() + 8 < err_t.mean():
            print("  -> gliders SNAP to hex bond axes: F sets the intended direction but the")
            print("     LATTICE quantizes the realized heading (off-axis targets pull to axis).")
        elif err_t.mean() < 25:
            print("  -> gliders go where designed: the activation law is GENERATIVE — steer a")
            print("     glider by editing 18 LUT entries, no fractal search needed.")
        else:
            print("  -> surgery shifts direction but imprecisely; law is predictive > generative.")

if __name__ == "__main__":
    main()
