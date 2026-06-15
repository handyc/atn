#!/usr/bin/env python3
# symmetry.py — does enforcing HEX symmetry on the rule help class-4 yield, and
# how much does it shrink the search space? Tests the user's "wallpaper / symmetry
# as structure" idea at the RULE level: make the 7->1 hex rule invariant under the
# neighbourhood's rotation group C6 (6 rotations) or full point group D6 (rotations
# + reflections), then compare class-4 yield to the raw (asymmetric) rule.
#
# Symmetrising collapses each neighbourhood's rotation orbit to one output, so the
# free rule space drops from 4^7=16384 entries to #orbits — a concrete "search
# more efficiently" reduction. Whether it also RAISES class-4 yield is the question.

import argparse
import numpy as np
import fractals

# the 6 hex neighbours in cyclic (CCW) order, with their 2-bit positions in the
# mandelhunt key (self is bits 12-13, fixed under the point group):
#   r=6, ne=8, nw=10, l=0, sw=2, se=4
SHIFTS = [6, 8, 10, 0, 2, 4]

def _vals(key):
    return [(key >> s) & 3 for s in SHIFTS]

def _mk(selfv, vals):
    k = selfv << 12
    for s, v in zip(SHIFTS, vals):
        k |= v << s
    return k

def _orbit(key, reflect):
    selfv = (key >> 12) & 3
    base = _vals(key)
    variants = [base, base[::-1]] if reflect else [base]
    orb = set()
    for v0 in variants:
        v = list(v0)
        for _ in range(6):                 # 6 rotations
            orb.add(_mk(selfv, v))
            v = [v[-1]] + v[:-1]
    return orb

def canon_map(reflect):
    """canon[key] = the smallest key in its symmetry orbit (the representative)."""
    canon = np.arange(16384, dtype=np.int64)
    seen = np.zeros(16384, dtype=bool)
    for key in range(16384):
        if seen[key]:
            continue
        orb = _orbit(key, reflect)
        c = min(orb)
        for k in orb:
            canon[k] = c; seen[k] = True
    return canon

def symmetrize(rule, canon):
    return rule[canon].astype(np.uint8)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=120)
    ap.add_argument("--family", default="julia", help="generator (julia is best)")
    ap.add_argument("--side", type=int, default=80)
    ap.add_argument("--ticks", type=int, default=16)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    c6 = canon_map(reflect=False)
    d6 = canon_map(reflect=True)
    n_c6 = len(np.unique(c6)); n_d6 = len(np.unique(d6))
    print(f"search-space reduction: raw 4^7={16384} free entries  ->  "
          f"C6 {n_c6} ({16384/n_c6:.1f}x smaller)  ->  D6 {n_d6} ({16384/n_d6:.1f}x smaller)\n")

    rng = np.random.default_rng(a.seed)
    wins = fractals.WINDOWS[a.family]
    rows = {"raw": {1: 0, 2: 0, 3: 0, 4: 0}, "C6": {1: 0, 2: 0, 3: 0, 4: 0},
            "D6": {1: 0, 2: 0, 3: 0, 4: 0}}
    acts = {"raw": [], "C6": [], "D6": []}
    for s in range(a.samples):
        cx, cy, span = wins[s % len(wins)]
        cx += (rng.random() * 2 - 1) * 0.3 * span
        cy += (rng.random() * 2 - 1) * 0.3 * span
        sp = span * (0.4 + 0.8 * rng.random())
        raw = fractals.gen_lut(a.family, cx, cy, sp, rng, it=200)
        for name, rule in (("raw", raw), ("C6", symmetrize(raw, c6)), ("D6", symmetrize(raw, d6))):
            cls, act = fractals.classify_hex(rule, side=a.side, ticks=a.ticks, seed=a.seed + s)
            rows[name][cls] += 1; acts[name].append(act)

    print(f"{'rule':<6}{'c1':>4}{'c2':>4}{'c3':>4}{'c4':>4}  {'%c4':>6} {'mean_act':>9}")
    for name in ("raw", "C6", "D6"):
        h = rows[name]; n = a.samples
        print(f"{name:<6}{h[1]:>4}{h[2]:>4}{h[3]:>4}{h[4]:>4}  "
              f"{100.0*h[4]/n:>5.1f}% {np.mean(acts[name]):>9.3f}")
    print("\nreading: if C6/D6 %c4 >= raw with a much smaller space, symmetry is a free "
          "efficiency win for the search. If it tanks activity (more c1/c2), enforced "
          "isotropy over-stabilises and symmetry should be a soft prior, not a hard one.")

if __name__ == "__main__":
    main()
