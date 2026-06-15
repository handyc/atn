#!/usr/bin/env python3
# genpool.py — build a class-4 7->1 rule pool from JULIA + NEWTON fractals (the
# higher-yield / higher-diversity generators found by fractals.py), saved as
# 16384-byte .lut files compatible with caca.load_pool (filenames carry a c4 score
# so load_pool's c4-sorted spread works).

import argparse, os
import numpy as np
import fractals

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="julnewt-pool")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--min-c4", type=float, default=0.25)
    ap.add_argument("--side", type=int, default=80)
    ap.add_argument("--ticks", type=int, default=16)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    fams = ["julia", "newton"]
    saved = 0; scanned = 0
    while saved < a.n and scanned < a.n * 12:
        fam = fams[scanned % 2]
        wins = fractals.WINDOWS[fam]
        cx, cy, span = wins[rng.integers(0, len(wins))]
        cx += (rng.random() * 2 - 1) * 0.3 * span
        cy += (rng.random() * 2 - 1) * 0.3 * span
        sp = span * (0.4 + 0.8 * rng.random())
        lut = fractals.gen_lut(fam, cx, cy, sp, rng, it=200)
        cls, act = fractals.classify_hex(lut, side=a.side, ticks=a.ticks, seed=a.seed + scanned)
        scanned += 1
        if cls == 4:
            c4 = max(0.0, 1.0 - 4.0 * abs(act - 0.32))
            if c4 >= a.min_c4:
                lut.tofile(os.path.join(a.out, f"jn_{fam}_{saved:04d}_c4{c4:.3f}.lut"))
                saved += 1
                if saved % 25 == 0:
                    print(f"  saved {saved}/{a.n} (scanned {scanned})", flush=True)
    print(f"done: {saved} class-4 LUTs from Julia+Newton -> {a.out} (scanned {scanned})")

if __name__ == "__main__":
    main()
