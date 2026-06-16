#!/usr/bin/env python3
# stack.py — stack L hex-CA "glider environments", each a different steered ruleset,
# and couple them at INTERSECTIONS: where >=2 layers are simultaneously active, that
# site ignites in every layer (cross-talk). Each layer alone is a clean unidirectional
# glider medium; the question is whether the coupling at moving intersections breeds
# emergent structure that no single layer has. Honest exploratory probe: we measure
# whether the stack self-organises (mass settles vs dies vs explodes), how much
# intersection activity persists, and whether NEW localized movers appear.
import argparse
import numpy as np
import rulehub, target_gen
from mechanism import SHIFT, DIRV

DSH = {k: SHIFT[k] for k in DIRV}; DANG = {k: np.arctan2(v[0], v[1]) for k, v in DIRV.items()}

def surgery(base, theta_deg):
    phi = np.radians(theta_deg) - np.pi; out = base.copy()
    for k, s in DSH.items():
        n = int(round(3 * max(0, np.cos(DANG[k] - phi))))
        for i, v in enumerate((1, 2, 3)): out[v << s] = v if i < n else 0
    return out

def run(L, side, ticks, mode, seed=0):
    base = target_gen.newton_lut(-0.10, -0.02, 0.52)
    thetas = [i * 360 / L for i in range(L)]
    luts = [surgery(base, t) for t in thetas]
    rng = np.random.default_rng(seed)
    B = [np.zeros((side, side), np.uint8) for _ in range(L)]
    c = side // 2
    for k in range(L):                      # seed each layer with its own glider
        r0, c0 = rng.integers(20, side - 20, 2)
        B[k][r0-2:r0+3, c0-2:c0+3] = rng.integers(1, 4, (5, 5))
    hist = []
    for t in range(ticks):
        for k in range(L):
            B[k] = luts[k][rulehub.hex_key(B[k].astype(np.int64))].astype(np.uint8)
        inter = sum((b > 0).astype(np.int16) for b in B)     # how many layers active per cell
        hot = inter >= 2
        if mode == "ignite":
            for k in range(L):
                B[k] = np.where(hot & (B[k] == 0), np.uint8(1), B[k])
        elif mode == "annihilate":
            for k in range(L):
                B[k] = np.where(hot, np.uint8(0), B[k])
        mass = [int((b > 0).sum()) for b in B]
        hist.append((t, sum(mass), int(hot.sum())))
        if sum(mass) > 0.5 * L * side * side:                # runaway
            return hist, "explode"
        if sum(mass) == 0:
            return hist, "dead"
    return hist, "alive"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--L", type=int, default=3)
    ap.add_argument("--side", type=int, default=90); ap.add_argument("--ticks", type=int, default=120)
    a = ap.parse_args()
    print(f"stacking {a.L} steered glider environments ({a.side}x{a.side}), intersection coupling\n")
    for mode in ("none", "ignite", "annihilate"):
        outs = [run(a.L, a.side, a.ticks, mode, seed=s) for s in range(6)]
        ends = [o[1] for o in outs]
        # average late-time total mass + intersection activity (over surviving runs)
        alive = [o[0] for o in outs if o[1] == "alive"]
        if alive:
            lm = np.mean([h[-1][1] for h in alive]); li = np.mean([h[-1][2] for h in alive])
            # intersection persistence: mean hot-cell count over last third
            pers = np.mean([np.mean([row[2] for row in h[-a.ticks//3:]]) for h in alive])
        else:
            lm = li = pers = 0
        from collections import Counter
        tag = mode
        print(f"  {tag}: outcomes {dict(Counter(ends))}")
        print(f"    late total mass ~{lm:.0f}, intersection cells ~{li:.0f}, "
              f"persistent intersection activity ~{pers:.0f} cells/step")
    print("\n  interpretation: if COUPLED runs stay alive with sustained intersection")
    print("  activity (vs independent layers just passing through), the stack self-")
    print("  organises around moving intersections — emergent structure from the overlap.")

if __name__ == "__main__":
    main()
