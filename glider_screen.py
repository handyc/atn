#!/usr/bin/env python3
# glider_screen.py — detect rules whose class-4 dynamics TRANSPORT a localized
# signal (a glider): on a quiescent 0-background, a small seed patch should evolve
# into a bounded, alive, MOVING structure (center-of-mass drifts) without dying or
# filling the board. These are the rules that could carry signals for gated /
# collision-based computation (the cell-11 programmable frontier).
import argparse, time
import numpy as np
import caca

def glider_score(rule, side=80, ticks=40, seed=0):
    """Return (displacement, reason). disp>0 only for a bounded, alive, moving
    localized structure on a quiescent 0-background."""
    if rule[0] != 0:
        return 0.0, "no-quiescent-bg"          # all-0 not a fixed point
    rng = np.random.default_rng(seed)
    b = np.zeros((side, side), np.uint8); c = side // 2
    b[c - 2:c + 3, c - 2:c + 3] = rng.integers(1, 4, (5, 5))
    em = caca._even_mask(side)
    coms = []; acts = []
    for t in range(ticks):
        b = caca.hex_step(b[None], rule[None], em)[0]
        nz = np.flatnonzero(b)
        a = nz.size; acts.append(a)
        if a == 0:
            return 0.0, "died"
        ys, xs = np.divmod(nz, side)
        coms.append((ys.mean(), xs.mean()))
    acts = np.array(acts)
    if acts.max() > side * side * 0.12:
        return 0.0, "exploded"
    if acts.mean() > 300:
        return 0.0, "too-diffuse"
    coms = np.array(coms)
    disp = float(np.hypot(*(coms[-1] - coms[0])))
    return disp, "glider" if disp > 3.0 else "stationary"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", default="alice/c4lib-v2/outputs/c4lib.npy")
    ap.add_argument("--sample", type=int, default=1500)
    ap.add_argument("--side", type=int, default=80)
    ap.add_argument("--ticks", type=int, default=40)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    lib = np.load(a.lib, mmap_mode="r")
    rng = np.random.default_rng(a.seed)
    idx = np.sort(rng.choice(len(lib), size=min(a.sample, len(lib)), replace=False))
    print(f"screening {len(idx)} of {lib.shape[0]} class-4 rules for glider transport "
          f"(side {a.side}, {a.ticks} ticks)", flush=True)
    import collections
    reasons = collections.Counter(); scored = []
    t0 = time.time()
    for k, j in enumerate(idx):
        d, why = glider_score(np.array(lib[j]), a.side, a.ticks, a.seed)
        reasons[why] += 1
        if d > 0: scored.append((d, int(j)))
        if (k + 1) % 300 == 0:
            print(f"  {k+1}/{len(idx)}  [{time.time()-t0:.0f}s]  reasons={dict(reasons)}", flush=True)
    scored.sort(reverse=True)
    print(f"\ndone [{time.time()-t0:.0f}s]. reason counts: {dict(reasons)}")
    print(f"glider-positive (disp>3): {sum(1 for d,_ in scored if d>3)} ; "
          f"any-movement (disp>0): {len(scored)}")
    print("top movers (displacement, lib-index):")
    for d, j in scored[:10]:
        print(f"  disp {d:.1f}  rule#{j}")

if __name__ == "__main__":
    main()
