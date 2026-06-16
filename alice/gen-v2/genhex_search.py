#!/usr/bin/env python3
# genhex_search.py — ALICE worker: does the direction law heading=angle(-F) hold on
# the HEXAGONAL substrate at state counts K other than 4? gen-v1 tested square/cube;
# this tests the paper's own lattice across K=2,3,4,5,8 (LUT size K^7). Same generic
# recipe: random low-density rules, detect gliders, compare measured heading to
# angle(-F) with F = single-neighbor activation vector over the 6 hex directions.
# Self-contained: numpy only (hex neighbor geometry inlined). Reads {"K","ntry","seed0"}.
import argparse, json, os
import numpy as np

# hex neighbor directions (screen coords, row down) matching the field order below
DIRS = [None, (-1, -0.5), (-1, 0.5), (0, 1.0), (1, 0.5), (1, -0.5), (0, -1.0)]  # self,nw,ne,e,se,sw,w
DVEC = [None] + [np.array(d) / np.hypot(*d) for d in DIRS[1:]]

def hex_fields(b):
    H = b.shape[0]; em = (np.arange(H) % 2 == 0).reshape(H, 1)
    up = np.roll(b, 1, 0); dn = np.roll(b, -1, 0); l = np.roll(b, 1, 1); rg = np.roll(b, -1, 1)
    nw = np.where(em, np.roll(up, 1, 1), up); ne = np.where(em, up, np.roll(up, -1, 1))
    sw = np.where(em, np.roll(dn, 1, 1), dn); se = np.where(em, dn, np.roll(dn, -1, 1))
    return [b, nw, ne, rg, se, sw, l]

def hex_key(b, K):
    key = np.zeros(b.shape, np.int64)
    for i, f in enumerate(hex_fields(b)):
        key += f.astype(np.int64) * (K ** i)
    return key

def rand_lut(K, p, rng):
    n = K ** 7; lut = np.zeros(n, np.uint8)
    mask = rng.random(n) < p; lut[mask] = rng.integers(1, K, int(mask.sum())); lut[0] = 0
    return lut

def Fvec(lut, K):
    F = np.zeros(2)
    for i in range(1, 7):
        a = np.mean([lut[v * (K ** i)] > 0 for v in range(1, K)])
        F = F + a * DVEC[i]
    return F

def glider_vel(lut, K, side, seed, T=22):
    rng = np.random.default_rng(seed); b = np.zeros((side, side), np.uint8); c = side // 2
    b[c-2:c+3, c-2:c+3] = rng.integers(1, K, (5, 5)); coms = []
    for _ in range(T):
        b = lut[hex_key(b, K)].astype(np.uint8); nz = np.flatnonzero(b); m = nz.size
        if m == 0 or m > 0.06 * b.size: return None
        ys, xs = np.divmod(nz, side); coms.append((ys.mean(), xs.mean()))
    coms = np.array(coms); v = (coms[14] - coms[3]) / 11.0
    return v if np.hypot(*v) >= 0.15 else None

def ang(v): return float(np.arctan2(v[0], v[1]))
def cdiff(a, b): return abs(np.angle(np.exp(1j * (a - b))))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); s = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    K, ntry, seed0 = s["K"], s["ntry"], s["seed0"]
    side = 60; rng = np.random.default_rng(seed0); pairs = []; ng = 0
    for t in range(ntry):
        lut = rand_lut(K, rng.uniform(0.06, 0.5), rng)
        v1 = glider_vel(lut, K, side, t * 2)
        if v1 is None: continue
        v2 = glider_vel(lut, K, side, t * 2 + 1)
        if v2 is None or cdiff(ang(v1), ang(v2)) > 0.5: continue
        F = Fvec(lut, K)
        if np.linalg.norm(F) < 1e-6: continue
        ng += 1
        pairs.append([np.degrees(ang((v1 + v2) / 2)), float(np.degrees(np.arctan2(-F[0], -F[1])))])
    json.dump({"substrate": "hex", "K": K, "dim": 2, "n_tried": ntry, "n_glider": ng, "pairs": pairs},
              open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: hex K={K} -> {ng} gliders from {ntry} rules")

if __name__ == "__main__":
    main()
