#!/usr/bin/env python3
# mechanism.py — WHY does the fractal coordinate set glider direction? Rotation-
# equivariance is out (fractal_dir_deep.py). New candidate: a LUT-INTRINSIC flow
# vector. The 7->1 rule maps a neighborhood (self + 6 hex neighbors) to a new
# center value. If the OUTPUT correlates more with the neighbor on one side than
# the opposite side, activity advects that way -> a glider direction. Define
#   F = sum_p  corr(neighbor_p value, output value) * unit_dir(p)
# over the 6 directional neighbors, and test whether angle(F) predicts the
# measured glider heading across the library. A hit = a closed-form, LUT-only
# explanation of the fractal->direction map (coordinate re-weights the corrs).
import json, os
import numpy as np
import rulehub, glider_dir

LIB = "alice/swarm-v1/outputs"
KEYS = np.arange(16384)
SHIFT = {"self": 12, "nw": 10, "ne": 8, "r": 6, "se": 4, "sw": 2, "l": 0}
VAL = {k: ((KEYS >> s) & 3) for k, s in SHIFT.items()}
# neighbor unit directions in (dy=row-down, dx=col) — same frame as glider_velocity
_DIR = {"nw": (-1, -0.5), "ne": (-1, 0.5), "r": (0, 1.0),
        "se": (1, 0.5), "sw": (1, -0.5), "l": (0, -1.0)}
DIRV = {k: np.array(v) / np.hypot(*v) for k, v in _DIR.items()}

def cmean(a): a = np.asarray(a); return float(np.arctan2(np.sin(a).mean(), np.cos(a).mean()))
def cR(a): a = np.asarray(a); return float(np.hypot(np.cos(a).mean(), np.sin(a).mean()))
def cdiff(a, b): return abs(np.angle(np.exp(1j * (a - b))))
def ccorr(al, be):
    al, be = np.asarray(al), np.asarray(be); am, bm = cmean(al), cmean(be)
    num = np.sum(np.sin(al - am) * np.sin(be - bm))
    den = np.sqrt(np.sum(np.sin(al - am) ** 2) * np.sum(np.sin(be - bm) ** 2))
    return float(num / (den + 1e-12))

def flow_angle(lut, mode="corr"):
    Fy = Fx = 0.0
    if mode == "single":
        # isolate each direction: output when ONLY neighbor k is active, center dead.
        # key = v << shift (everything else 0). Does an upstream cell at k fire center?
        for k, (dy, dx) in DIRV.items():
            s = SHIFT[k]
            a = float(np.mean([lut[v << s] > 0 for v in (1, 2, 3)]))
            Fy += a * dy; Fx += a * dx
        return float(np.arctan2(Fy, Fx)), float(np.hypot(Fy, Fx))
    out = lut.astype(float)
    if mode == "alive": out = (out > 0).astype(float)
    for k, (dy, dx) in DIRV.items():
        x = VAL[k].astype(float)
        if mode == "alive": x = (x > 0).astype(float)
        if x.std() < 1e-9 or out.std() < 1e-9: w = 0.0
        else: w = np.corrcoef(x, out)[0, 1]
        Fy += w * dy; Fx += w * dx
    return float(np.arctan2(Fy, Fx)), float(np.hypot(Fy, Fx))

def measured_heading(lut):
    vs = [glider_dir.glider_velocity(lut, seed=s) for s in range(4)]
    vs = [v[0] for v in vs if v is not None]
    if len(vs) >= 3 and cR(vs) > 0.6: return cmean(vs)
    return None

def main():
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    blobs = os.path.join(LIB, "blobs")
    for mode in ("corr", "alive", "single"):
        meas, pred, strength = [], [], []
        for r in recs[:600]:
            lut = np.fromfile(os.path.join(blobs, r["hash"] + ".lut"), dtype=np.uint8, count=16384)
            m = measured_heading(lut)
            if m is None: continue
            fa, fs = flow_angle(lut, mode)
            if fs < 1e-3: continue
            meas.append(m); pred.append(fa); strength.append(fs)
        if len(meas) < 20:
            print(f"[{mode}] too few clean gliders ({len(meas)})"); continue
        meas, pred = np.array(meas), np.array(pred)
        # the flow may predict heading up to a +/-180 sign (advect vs gradient); pick the better
        R_plus = cR(meas - pred); R_minus = cR(meas - (pred + np.pi))
        sign, Rres = ("+F", R_plus) if R_plus >= R_minus else ("-F", R_minus)
        off = cmean(meas - pred) if sign == "+F" else cmean(meas - (pred + np.pi))
        base = pred if sign == "+F" else pred + np.pi
        err = np.array([np.degrees(cdiff(meas[i], base[i] + off)) for i in range(len(meas))])
        print(f"[{mode}] {len(meas)} rules | circ-circ corr(flow, heading) = {ccorr(pred, meas):+.2f}")
        print(f"        best sign {sign}, fixed offset {np.degrees(off):+.0f} deg, "
              f"residual alignment R = {Rres:.2f}")
        print(f"        heading error after offset: mean {err.mean():.0f} deg, median {np.median(err):.0f}, "
              f"<45deg: {100*(err<45).mean():.0f}%, <90deg: {100*(err<90).mean():.0f}%")
    print("\n-> if circ-circ corr is high and most rules land <45-90 deg, the glider")
    print("   direction is PREDICTED by the LUT's neighbor-influence asymmetry: a")
    print("   closed-form mechanism, and fractal coordinate steers by re-weighting it.")

if __name__ == "__main__":
    main()
