#!/usr/bin/env python3
# speed_law.py — companion to the direction law. Direction = angle(F)+180 from the
# single-neighbor activation vector F. Does a LUT-intrinsic statistic also predict
# glider SPEED (cells/tick)? Candidates, all computed from the LUT, no simulation:
#   |F|        : magnitude of the single-neighbor activation vector (net anisotropy)
#   births     : sum_p a_p  (total single-neighbor activation = how readily upstream
#                cells fire the center)
#   aniso      : |F| / (births+eps)  (directionality fraction)
#   lambda     : Langton's lambda = fraction of LUT entries that are nonzero
# Correlate each with measured speed across many glider rules; report the best.
import json, os
import numpy as np
import rulehub, glider_dir
from mechanism import flow_angle, cR, DIRV, SHIFT

LIB = "alice/swarm-v1/outputs"
DIR_SHIFT = {k: SHIFT[k] for k in DIRV}

def lut_feats(lut):
    a = {}
    for k, s in DIR_SHIFT.items():
        a[k] = np.mean([lut[v << s] > 0 for v in (1, 2, 3)])
    Fy = sum(a[k] * DIRV[k][0] for k in DIRV); Fx = sum(a[k] * DIRV[k][1] for k in DIRV)
    Fmag = float(np.hypot(Fy, Fx)); births = float(sum(a.values()))
    lam = float(np.mean(lut > 0))
    return Fmag, births, Fmag / (births + 1e-9), lam

def measured_speed(lut):
    out = [glider_dir.glider_velocity(lut, seed=s) for s in range(4)]
    out = [v for v in out if v is not None]
    if len(out) < 3 or cR([v[0] for v in out]) < 0.6: return None
    return float(np.mean([v[1] for v in out]))

def main():
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    blobs = os.path.join(LIB, "blobs")
    rng = np.random.default_rng(4)
    idx = rng.choice(len(recs), size=min(600, len(recs)), replace=False)
    sp, F = [], []
    for k in idx:
        lut = np.fromfile(os.path.join(blobs, recs[k]["hash"] + ".lut"), dtype=np.uint8, count=16384)
        s = measured_speed(lut)
        if s is None: continue
        sp.append(s); F.append(lut_feats(lut))
    sp = np.array(sp); F = np.array(F)
    names = ["|F|", "births", "aniso=|F|/births", "lambda"]
    print(f"speed sub-law: {len(sp)} Newton glider rules; "
          f"speed mean {sp.mean():.2f} +- {sp.std():.2f} cells/tick\n")
    print("  feature              corr(feature, speed)")
    best = None
    for i, nm in enumerate(names):
        r = np.corrcoef(F[:, i], sp)[0, 1]
        print(f"  {nm:<18}   {r:+.2f}")
        if best is None or abs(r) > abs(best[1]): best = (nm, r, i)
    # best single-feature linear fit + a 2-feature (|F|, births) fit
    bi = best[2]
    A = np.polyfit(F[:, bi], sp, 1); pred = np.polyval(A, F[:, bi])
    r2_1 = 1 - np.sum((sp - pred) ** 2) / np.sum((sp - sp.mean()) ** 2)
    X = np.column_stack([F[:, 0], F[:, 1], np.ones(len(sp))])   # |F|, births, bias
    coef, *_ = np.linalg.lstsq(X, sp, rcond=None); pred2 = X @ coef
    r2_2 = 1 - np.sum((sp - pred2) ** 2) / np.sum((sp - sp.mean()) ** 2)
    print(f"\n  best single feature: {best[0]} (corr {best[1]:+.2f}), linear R^2 = {r2_1:.2f}")
    print(f"  2-feature fit (|F|,births): R^2 = {r2_2:.2f}  "
          f"[speed ~ {coef[0]:+.2f}|F| {coef[1]:+.2f}births {coef[2]:+.2f}]")
    if max(abs(best[1]), np.sqrt(max(r2_2, 0))) > 0.5:
        print("  -> a LUT-intrinsic speed sub-law exists: speed is set by the activation")
        print("     magnitude/birth balance, computable without simulation.")
    else:
        print("  -> no strong closed-form speed law from these features; speed is more")
        print("     emergent than direction (which the 18-entry law nails).")

if __name__ == "__main__":
    main()
