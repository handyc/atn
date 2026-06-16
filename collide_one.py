#!/usr/bin/env python3
# collide_one.py — the rare fractal rule 0d9ff49 was flagged (boundary.py) as
# emitting gliders ~179 deg apart from different seeds. Reproduce with the SAME
# measurement (glider_dir.glider_velocity, centered 5x5 patch), find the opposing
# seed pair, then place the two patches on their shared motion axis so they
# converge HEAD-ON. Test interaction: compare total mass of the collision run to
# the two solos (annihilate / product / pass-through). A real interaction = first
# collision-capable fractal rule.
import os
import numpy as np
import rulehub

LIB = "alice/swarm-v1/outputs"
HASH = "0d9ff49cd65b4b84"
SIDE = 120

def patch_for(seed):
    return np.random.default_rng(seed).integers(1, 4, (5, 5))

def angle_for(lut, seed):
    # mirror glider_dir.glider_velocity exactly (centered patch), return angle,speed
    b = np.zeros((SIDE, SIDE), np.uint8); c = SIDE // 2
    b[c-2:c+3, c-2:c+3] = patch_for(seed)
    coms = []
    for _ in range(20):
        b = lut[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
        nz = np.flatnonzero(b)
        if nz.size == 0 or nz.size > 0.1*SIDE*SIDE: return None
        ys, xs = np.divmod(nz, SIDE); coms.append((ys.mean(), xs.mean()))
    coms = np.array(coms); v = (coms[14] - coms[3]) / 11.0
    sp = float(np.hypot(*v))
    if sp < 0.15: return None
    return float(np.arctan2(v[0], v[1])), sp

def run(lut, placements, ticks):
    b = np.zeros((SIDE, SIDE), np.uint8)
    for patch, (r, c) in placements:
        b[r:r+5, c:c+5] = patch
    masses = []
    for _ in range(ticks):
        b = lut[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
        m = int((b > 0).sum())
        if m > 0.12*SIDE*SIDE: return None
        masses.append(m)
    return np.array(masses)

def main():
    lut = np.fromfile(os.path.join(LIB, "blobs", HASH + ".lut"), dtype=np.uint8, count=16384)
    meas = []
    for s in range(1000, 1080):
        a = angle_for(lut, s)
        if a is not None: meas.append((s, a[0], a[1]))
    print(f"{len(meas)} glider-producing seeds measured for {HASH}")
    if len(meas) < 2:
        print("too few gliders to test a collision"); return
    # find the most-opposed pair
    best = None
    for i in range(len(meas)):
        for j in range(i+1, len(meas)):
            d = abs(np.angle(np.exp(1j*(meas[i][1]-meas[j][1]))))
            if best is None or d > best[0]: best = (d, i, j)
    d, i, j = best
    si, ai, spi = meas[i]; sj, aj, spj = meas[j]
    print(f"most-opposed pair: seed {si} @ {np.degrees(ai):.0f}deg (sp {spi:.2f}) vs "
          f"seed {sj} @ {np.degrees(aj):.0f}deg (sp {spj:.2f}); gap={np.degrees(d):.0f}deg")
    if np.degrees(d) < 110:
        print("-> not actually opposing once measured consistently; the boundary.py flag")
        print("   was small-sample noise. This rule is effectively unidirectional too."); return
    # direction vectors in (row,col): (sin a, cos a). Place each patch so it moves
    # toward center: start at center - offset*dir.
    c = SIDE // 2; off = 32
    di = np.array([np.sin(ai), np.cos(ai)]); dj = np.array([np.sin(aj), np.cos(aj)])
    pi = (c - off*di).astype(int); pj = (c - off*dj).astype(int)
    pi = np.clip(pi, 6, SIDE-11); pj = np.clip(pj, 6, SIDE-11)
    ticks = int(off / max(spi, spj, 0.2)) + 12
    soloI = run(lut, [(patch_for(si), tuple(pi))], ticks)
    soloJ = run(lut, [(patch_for(sj), tuple(pj))], ticks)
    both  = run(lut, [(patch_for(si), tuple(pi)), (patch_for(sj), tuple(pj))], ticks)
    if soloI is None or soloJ is None or both is None:
        print("a configuration exploded; inconclusive"); return
    exp = soloI + soloJ           # expected if non-interacting (superposition)
    end_ratio = both[-1] / max(1, exp[-1])
    min_ratio = (both / np.maximum(exp, 1)).min()
    print(f"end mass: collide={both[-1]} expected(sum of solos)={exp[-1]}  ratio={end_ratio:.2f}")
    print(f"min mass ratio over run: {min_ratio:.2f}")
    if end_ratio < 0.6 or min_ratio < 0.5:
        print("-> the opposing gliders INTERACT (mass deviates from superposition):")
        print("   collision-capable fractal rule. Worth a proper gate study.")
    elif end_ratio > 1.6:
        print("-> collision produces NEW structure (mass amplifies): also interaction.")
    else:
        print("-> gliders pass through ~independently (mass ~ superposition): bidirectional")
        print("   but non-interacting. Collision logic still blocked for fractal rules.")

if __name__ == "__main__":
    main()
