#!/usr/bin/env python3
# collide2.py — make gliders ACTUALLY collide. Per rule, launch many seeds, measure
# each glider's horizontal velocity, and find a CONVERGENT pair (one moving right,
# one moving left). Place them head-on and test interaction vs 2x solo. This fixes
# the flaw in collide.py (mirror-flipped seeds don't reliably reverse direction).
import argparse, time
import numpy as np
import caca

def launch(rule, side, ticks, patch, pos):
    b = np.zeros((side, side), np.uint8); r, c = pos
    b[r:r + 5, c:c + 5] = patch; em = caca._even_mask(side)
    xs = []
    for _ in range(ticks):
        b = caca.hex_step(b[None], rule[None], em)[0]
        nz = np.flatnonzero(b)
        if nz.size == 0: return None, b
        xs.append((nz % side).mean())
    return np.array(xs), b

def seed_velocity(rule, side, patch):
    """vx = horizontal drift of a glider from center; None if not a clean glider."""
    if rule[0] != 0: return None
    xs, b = launch(rule, side, 35, patch, (side // 2 - 2, side // 2 - 2))
    if xs is None: return None
    mass = int((b > 0).sum())
    if mass == 0 or mass > 250: return None
    vx = (xs[-1] - xs[0]) / len(xs)
    return vx if abs(vx) > 0.15 else None      # must actually drift horizontally

def find_collider(rule, side, ticks, seed):
    rng = np.random.default_rng(seed)
    seeds = [rng.integers(1, 4, (5, 5)) for _ in range(12)]
    vs = [(seed_velocity(rule, side, p), p) for p in seeds]
    right = [p for v, p in vs if v is not None and v > 0.15]
    left = [p for v, p in vs if v is not None and v < -0.15]
    if not right or not left: return None       # no convergent pair
    pr, pl = right[0], left[0]
    cy = side // 2
    # rightward glider on the left, leftward glider on the right -> converge
    _, bA = launch(rule, side, ticks, pr, (cy - 2, 6))
    _, bB = launch(rule, side, ticks, pl, (cy - 2, side - 11))
    bAB = np.zeros((side, side), np.uint8)
    bAB[cy - 2:cy + 3, 6:11] = pr; bAB[cy - 2:cy + 3, side - 11:side - 6] = pl
    em = caca._even_mask(side)
    for _ in range(ticks):
        bAB = caca.hex_step(bAB[None], rule[None], em)[0]
    solo = int((bA > 0).sum()) + int((bB > 0).sum())
    if solo == 0: return None
    return (bAB > 0).sum() / solo               # <0.4 annihilate, >1.6 product, ~1 pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", default="alice/c4lib-v2/outputs/c4lib.npy")
    ap.add_argument("--sample", type=int, default=6000)
    ap.add_argument("--topk", type=int, default=120)
    ap.add_argument("--side", type=int, default=80)
    ap.add_argument("--ticks", type=int, default=45)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    lib = np.load(a.lib, mmap_mode="r")
    rng = np.random.default_rng(a.seed)
    idx = np.sort(rng.choice(len(lib), size=min(a.sample, len(lib)), replace=False))
    print(f"scanning {len(idx)} rules for CONVERGENT glider pairs + collision...", flush=True)
    t0 = time.time(); n_conv = 0; hits = []
    tested = 0
    for j in idx:
        rule = np.array(lib[j])
        if rule[0] != 0: continue
        tested += 1
        r = find_collider(rule, a.side, a.ticks, a.seed)
        if r is None: continue
        n_conv += 1
        if r < 0.4 or r > 1.6:
            hits.append((abs(r - 1), int(j), float(r)))
        if tested % 400 == 0:
            print(f"  tested {tested}, convergent-pair rules {n_conv}, hits {len(hits)} [{time.time()-t0:.0f}s]", flush=True)
        if n_conv >= a.topk and tested > 1500: break
    hits.sort(reverse=True)
    print(f"\nrules with a convergent glider pair: {n_conv} (of {tested} quiescent rules tested)")
    print(f"non-trivial collisions (annihilate/product): {len(hits)}")
    for score, j, r in hits[:12]:
        print(f"  rule#{j}: collide/2solo={r:.2f}  [{'ANNIHILATE' if r<0.4 else 'PRODUCT'}]")
    if hits:
        print("\n-> genuine glider collisions found. Best candidates for hand-built AND/XOR.")
    else:
        print("\n-> convergent pairs exist but collisions stay pass-through; clean logic")
        print("   gates need finer geometry/timing. This is the hard research edge.")

if __name__ == "__main__":
    main()
