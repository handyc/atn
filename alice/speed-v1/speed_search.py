#!/usr/bin/env python3
# speed_search.py — ALICE worker: nail the SPEED law. The direction law is exact
# (kernel first moment); speed is the kernel's front-velocity saddle point. theory.py
# (local, newton) found drift speed |F|/(a_self+sum a_p) gives R^2=0.36 and the
# marginal-stability v* upper-bounds 82%. This collects, at scale across all four
# fractal families, per-glider: measured speed, drift speed, v*, |F|, lambda — so the
# aggregator can fit the best speed model and classify pulled vs pushed fronts.
# Needs rulehub.py + numpy. Reads {"family","ntry","seed0"}.
import argparse, json, os
import numpy as np
import rulehub

SHIFT = {"self": 12, "nw": 10, "ne": 8, "r": 6, "se": 4, "sw": 2, "l": 0}
_DIR = {"nw": (-1, -0.5), "ne": (-1, 0.5), "r": (0, 1.0), "se": (1, 0.5), "sw": (1, -0.5), "l": (0, -1.0)}
DIRV = {k: np.array(v) / np.hypot(*v) for k, v in _DIR.items()}
DSH = {k: SHIFT[k] for k in DIRV}

def rates(lut):
    a = {k: float(np.mean([lut[v << s] > 0 for v in (1, 2, 3)])) for k, s in DSH.items()}
    a_self = float(np.mean([lut[v << 12] > 0 for v in (1, 2, 3)]))
    return a, a_self

def Fvec(a):
    return np.array([sum(a[k] * DIRV[k][0] for k in DIRV), sum(a[k] * DIRV[k][1] for k in DIRV)])

def vstar(a, a_self, F):
    m = np.linalg.norm(F)
    if m < 1e-9: return np.nan
    proj = {k: float(np.dot(DIRV[k], F)) / m for k in DIRV}
    best = np.inf
    for lam in np.linspace(0.05, 25, 400):
        M = a_self + sum(a[k] * np.exp(lam * proj[k]) for k in DIRV)
        if M > 0: best = min(best, np.log(M) / lam)
    return float(best)

def measured_speed(lut, seeds=4, side=96):
    sps, angs = [], []
    for s in range(seeds):
        rng = np.random.default_rng(s); b = np.zeros((side, side), np.uint8); c = side // 2
        b[c-2:c+3, c-2:c+3] = rng.integers(1, 4, (5, 5)); coms = []
        ok = True
        for _ in range(20):
            b = lut[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
            nz = np.flatnonzero(b)
            if nz.size == 0 or nz.size > 0.1 * side * side: ok = False; break
            ys, xs = np.divmod(nz, side); coms.append((ys.mean(), xs.mean()))
        if not ok or len(coms) < 16: continue
        coms = np.array(coms); v = (coms[14] - coms[3]) / 11.0
        if np.hypot(*v) >= 0.15:
            sps.append(float(np.hypot(*v))); angs.append(float(np.arctan2(v[0], v[1])))
    if len(sps) < 3: return None
    R = np.hypot(np.cos(angs).mean(), np.sin(angs).mean())
    if R < 0.6: return None
    return float(np.mean(sps))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); s = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    fam, ntry, seed0 = s["family"], s["ntry"], s["seed0"]
    rng = np.random.default_rng(seed0); recs = []
    for _ in range(ntry):
        try:
            lut, _ = rulehub.gen_lut(fam, rng)
        except Exception:
            continue
        if lut[0] != 0: continue
        sp = measured_speed(lut)
        if sp is None: continue
        ad, a_self = rates(lut); F = Fvec(ad); mF = float(np.linalg.norm(F))
        if mF < 1e-6: continue
        recs.append(dict(speed=sp, drift=mF / (a_self + sum(ad.values())),
                         vstar=vstar(ad, a_self, F), Fmag=mF, lam=float(np.mean(lut > 0))))
    json.dump({"family": fam, "n_tried": ntry, "recs": recs},
              open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: {fam} -> {len(recs)} glider speed records")

if __name__ == "__main__":
    main()
