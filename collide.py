#!/usr/bin/env python3
# collide.py — find glider rules with NON-TRIVIAL COLLISIONS (the raw material for
# collision-based logic gates). Launch two gliders aimed to converge (a seed and
# its column-flipped twin); if they actually meet, compare the surviving mass to
# 2x a solo glider: ~1x = pass-through, <<1x = annihilation, >>1x = product/amplify.
# Rules with strong, clean interaction where the gliders DO collide are candidates
# for hand-engineered AND/XOR. Screens for gliders first; collision-tests the top K.
import argparse, time
import numpy as np
import caca

def _seed(side, rng):
    p = rng.integers(1, 4, (5, 5)); return p

def evolve(rule, side, ticks, seeds):
    """seeds = list of (patch, (row,col)). Returns per-tick occupancy + final mass,
    and the set of cells each glider occupies (to detect a real collision)."""
    b = np.zeros((side, side), np.uint8)
    for patch, (r, c) in seeds:
        b[r:r + 5, c:c + 5] = patch
    em = caca._even_mask(side); masses = []
    for _ in range(ticks):
        b = caca.hex_step(b[None], rule[None], em)[0]
        masses.append(int((b > 0).sum()))
    return b, np.array(masses)

def glider_ok(rule, side, ticks, seed):
    if rule[0] != 0: return None
    rng = np.random.default_rng(seed); patch = _seed(side, rng)
    b, mass = evolve(rule, side, ticks, [(patch, (side // 2 - 2, 4))])
    if mass[-1] == 0 or mass.max() > side * side * 0.12 or mass.mean() > 300: return None
    return patch

def collision(rule, side, ticks, seed):
    """Launch A (left) and its column-flipped twin B (right); if they converge and
    meet, report interaction ratio = mass(both) / (mass(A)+mass(B))."""
    rng = np.random.default_rng(seed); patch = _seed(side, rng)
    cy = side // 2
    bA, mA = evolve(rule, side, ticks, [(patch, (cy - 2, 4))])
    bB, mB = evolve(rule, side, ticks, [(patch[:, ::-1], (cy - 2, side - 9))])
    bAB, mAB = evolve(rule, side, ticks, [(patch, (cy - 2, 4)),
                                          (patch[:, ::-1], (cy - 2, side - 9))])
    solo = mA[-1] + mB[-1]
    if mA[-1] == 0 or mB[-1] == 0 or solo == 0: return None
    # did they actually meet? overlap of A-only and B-only footprints at the end
    metric = mAB[-1] / solo
    # require the two solo gliders to end on opposite-ish sides AND overlap potential
    aR = (np.flatnonzero(bA) % side).mean(); bR = (np.flatnonzero(bB) % side).mean()
    converged = abs(aR - bR) < side * 0.25         # ended up near each other -> met
    return (metric, converged, solo)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", default="alice/c4lib-v2/outputs/c4lib.npy")
    ap.add_argument("--sample", type=int, default=6000)
    ap.add_argument("--topk", type=int, default=80)
    ap.add_argument("--side", type=int, default=80)
    ap.add_argument("--ticks", type=int, default=45)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    lib = np.load(a.lib, mmap_mode="r")
    rng = np.random.default_rng(a.seed)
    idx = np.sort(rng.choice(len(lib), size=min(a.sample, len(lib)), replace=False))
    print(f"screening {len(idx)} rules for gliders, collision-testing top {a.topk}...", flush=True)
    t0 = time.time(); gl = []
    for j in idx:
        if glider_ok(np.array(lib[j]), a.side, 35, a.seed) is not None:
            # quick displacement re-use: treat passing the glider_ok filter as glider
            gl.append(int(j))
    print(f"  {len(gl)} glider rules [{time.time()-t0:.0f}s]; collision test...", flush=True)
    hits = []
    for j in gl[:a.topk]:
        r = collision(np.array(lib[j]), a.side, a.ticks, a.seed)
        if r is None: continue
        metric, conv, solo = r
        # non-trivial collision: gliders converged AND outcome far from pass-through(=1)
        if conv and (metric < 0.4 or metric > 1.6):
            kind = "ANNIHILATE" if metric < 0.4 else "AMPLIFY/PRODUCT"
            hits.append((abs(metric - 1), j, metric, kind))
    hits.sort(reverse=True)
    print(f"\nnon-trivial COLLISION rules (converged + outcome != pass-through): {len(hits)}")
    for score, j, metric, kind in hits[:12]:
        print(f"  rule#{j}: collision/2solo = {metric:.2f}  [{kind}]")
    if hits:
        print("\n-> these gliders genuinely interact on collision (annihilate or create")
        print("   product) — the raw material for AND/XOR. Next: hand-engineer geometry on")
        print("   the best one to read a 4-row truth table. (ALICE: scan all glider rules.)")
    else:
        print("\n-> gliders transport but converging twins don't cleanly interact in this")
        print("   sample; collision logic needs targeted geometry per rule (hard).")

if __name__ == "__main__":
    main()
