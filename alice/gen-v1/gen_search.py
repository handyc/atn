#!/usr/bin/env python3
# gen_search.py — ALICE worker: test UNIVERSALITY of the direction law
#   glider heading = angle(F) + 180deg,   F = sum_p a_p d_p
# (a_p = single-neighbor activation, d_p = neighbor offset vector) on substrates
# OTHER than hex-K4: square von Neumann / square Moore (2D) and cubic von Neumann
# (3D), at various state counts K. If the law holds everywhere, it is a property of
# local CA gliders in general, not a hex-K4 quirk. Generic engine: a CA is a list of
# neighbor offsets (self first), a state count K, and a LUT of size K^m. We generate
# random low-density (near-class-4) rules, detect gliders, and for each glider compare
# measured heading to angle(-F). Self-contained: numpy only. Reads spec JSON
# {"substrate","K","ntry","seed0"}; writes outputs/result_XXXX.json with the raw
# (measured, predicted) pairs (pooled across tasks by the aggregator).
import argparse, json, os
import numpy as np

def offsets(sub):
    if sub == "sq-vn":   return [(0, 0), (-1, 0), (0, 1), (1, 0), (0, -1)]            # self,N,E,S,W
    if sub == "sq-moore":return [(0, 0)] + [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                                            if not (dy == 0 and dx == 0)]
    if sub == "cube-vn": return [(0, 0, 0), (-1, 0, 0), (1, 0, 0), (0, -1, 0),
                                 (0, 1, 0), (0, 0, -1), (0, 0, 1)]
    raise ValueError(sub)

def key_nd(b, offs, K):
    key = np.zeros(b.shape, np.int64)
    for i, off in enumerate(offs):
        shifted = b
        for ax, d in enumerate(off):
            if d: shifted = np.roll(shifted, -d, ax)
        key += shifted.astype(np.int64) * (K ** i)
    return key

def rand_lut(K, m, p, rng):
    n = K ** m; lut = np.zeros(n, np.uint8)
    mask = rng.random(n) < p; lut[mask] = rng.integers(1, K, int(mask.sum()))
    lut[0] = 0
    return lut

def Fvec(lut, offs, K):
    F = np.zeros(len(offs[0]))
    for i, off in enumerate(offs):
        if i == 0: continue
        a = np.mean([lut[v * (K ** i)] > 0 for v in range(1, K)])
        F = F + a * np.array(off, float)
    return F

def glider_vel(lut, offs, K, dim, side, seed, T=22):
    rng = np.random.default_rng(seed)
    shape = (side,) * dim
    b = np.zeros(shape, np.uint8); c = side // 2
    if dim == 2: b[c-2:c+3, c-2:c+3] = rng.integers(1, K, (5, 5))
    else:        b[c-1:c+2, c-1:c+2, c-1:c+2] = rng.integers(1, K, (3, 3, 3))
    coms = []
    for _ in range(T):
        b = lut[key_nd(b, offs, K)].astype(np.uint8)
        nz = np.flatnonzero(b); m = nz.size
        if m == 0 or m > 0.06 * b.size: return None
        coms.append(np.array(np.unravel_index(nz, shape)).mean(axis=1))
    coms = np.array(coms); v = (coms[14] - coms[3]) / 11.0
    if np.linalg.norm(v) < 0.15: return None
    return v

def ang2(v): return float(np.arctan2(v[0], v[1]))
def cdiff(a, b): return abs(np.angle(np.exp(1j * (a - b))))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    s = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    sub, K, ntry, seed0 = s["substrate"], s["K"], s["ntry"], s["seed0"]
    offs = offsets(sub); m = len(offs); dim = len(offs[0]); side = 60 if dim == 2 else 26
    rng = np.random.default_rng(seed0)
    pairs = []          # 2D: (measured_deg, predicted_deg) ; 3D: angle-error deg
    n_glider = 0
    for t in range(ntry):
        p = rng.uniform(0.06, 0.5)              # activation density (near class-4 band)
        lut = rand_lut(K, m, p, rng)
        v1 = glider_vel(lut, offs, K, dim, side, seed=t * 2)
        if v1 is None: continue
        v2 = glider_vel(lut, offs, K, dim, side, seed=t * 2 + 1)
        if v2 is None: continue
        # require a consistent translating glider across two seeds
        if dim == 2:
            if cdiff(ang2(v1), ang2(v2)) > 0.5: continue
            F = Fvec(lut, offs, K)
            if np.linalg.norm(F) < 1e-6: continue
            n_glider += 1
            meas = ang2((v1 + v2) / 2); pred = float(np.arctan2(-F[0], -F[1]))
            pairs.append([np.degrees(meas), np.degrees(pred)])
        else:
            if np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)) < 0.7: continue
            F = Fvec(lut, offs, K)
            if np.linalg.norm(F) < 1e-6: continue
            n_glider += 1
            vmean = (v1 + v2) / 2; pred = -F
            cosang = np.dot(vmean, pred) / (np.linalg.norm(vmean) * np.linalg.norm(pred) + 1e-12)
            pairs.append(float(np.degrees(np.arccos(np.clip(cosang, -1, 1)))))
    json.dump({"substrate": sub, "K": K, "dim": dim, "n_tried": ntry,
               "n_glider": n_glider, "pairs": pairs},
              open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: {sub} K={K} -> {n_glider} gliders from {ntry} rules")

if __name__ == "__main__":
    main()
