#!/usr/bin/env python3
# gen_search.py (gen-v3) — map the GROWTH->COPY crossover of the direction law vs
# DIMENSION and K. von Neumann lattice in d=2..4 dims, K=2..6. Tests heading=angle(-F);
# reports per-glider law error and which regime (growth: motion opposite F; copy:
# motion toward F). gen-v1/v2 showed 2D low-K is pure growth (+180 law exact), 3D
# K=2 is copy-dominated. This pins how the copy regime grows with dimension/K.
# Self-contained: numpy only. Reads {"substrate":"vn<d>","K","ntry","seed0"}.
import argparse, json, os
import numpy as np

def vn_offsets(d):
    offs = [tuple([0] * d)]
    for ax in range(d):
        for s in (1, -1):
            o = [0] * d; o[ax] = s; offs.append(tuple(o))
    return offs

def key_nd(b, offs, K):
    key = np.zeros(b.shape, np.int64)
    for i, off in enumerate(offs):
        sh = b
        for ax, dd in enumerate(off):
            if dd: sh = np.roll(sh, -dd, ax)
        key += sh.astype(np.int64) * (K ** i)
    return key

def rand_lut(K, m, p, rng):
    n = K ** m; lut = np.zeros(n, np.uint8)
    mask = rng.random(n) < p; lut[mask] = rng.integers(1, K, int(mask.sum())); lut[0] = 0
    return lut

def Fvec(lut, offs, K):
    F = np.zeros(len(offs[0]))
    for i, off in enumerate(offs):
        if i == 0: continue
        a = np.mean([lut[v * (K ** i)] > 0 for v in range(1, K)])
        F = F + a * np.array(off, float)
    return F

def glider_vel(lut, offs, K, dim, side, seed, T):
    rng = np.random.default_rng(seed); shape = (side,) * dim
    b = np.zeros(shape, np.uint8); c = side // 2
    sl = tuple(slice(c - 1, c + 2) for _ in range(dim))
    b[sl] = rng.integers(1, K, (3,) * dim)
    coms = []
    for _ in range(T):
        b = lut[key_nd(b, offs, K)].astype(np.uint8); nz = np.flatnonzero(b); m = nz.size
        if m == 0 or m > 0.06 * b.size: return None
        coms.append(np.array(np.unravel_index(nz, shape)).mean(axis=1))
    coms = np.array(coms); h = len(coms) // 2; v = (coms[-1] - coms[h]) / (len(coms) - h)
    return v if np.linalg.norm(v) >= 0.15 else None

def cdiff(a, b): return abs(np.angle(np.exp(1j * (a - b))))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); s = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    sub, K, ntry, seed0 = s["substrate"], s["K"], s["ntry"], s["seed0"]
    dim = int(sub[2:]); offs = vn_offsets(dim); m = len(offs)
    side = {2: 60, 3: 26, 4: 14, 5: 10, 6: 8}[dim]; T = {2: 22, 3: 18, 4: 14, 5: 16, 6: 12}[dim]
    rng = np.random.default_rng(seed0); pairs = []; ng = 0
    for t in range(ntry):
        lut = rand_lut(K, m, rng.uniform(0.06, 0.5), rng)
        v1 = glider_vel(lut, offs, K, dim, side, t * 2, T)
        if v1 is None: continue
        v2 = glider_vel(lut, offs, K, dim, side, t * 2 + 1, T)
        if v2 is None: continue
        cs = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-12)
        if cs < 0.7: continue
        F = Fvec(lut, offs, K)
        if np.linalg.norm(F) < 1e-6: continue
        ng += 1; vmean = (v1 + v2) / 2
        if dim == 2:
            meas = float(np.arctan2(vmean[0], vmean[1])); pred = float(np.arctan2(-F[0], -F[1]))
            pairs.append([np.degrees(meas), np.degrees(pred)])
        else:
            cosang = np.dot(vmean, -F) / (np.linalg.norm(vmean) * np.linalg.norm(F) + 1e-12)
            pairs.append(float(np.degrees(np.arccos(np.clip(cosang, -1, 1)))))
    json.dump({"substrate": sub, "K": K, "dim": dim, "n_tried": ntry, "n_glider": ng, "pairs": pairs},
              open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: {sub} K={K} -> {ng} gliders")

if __name__ == "__main__":
    main()
