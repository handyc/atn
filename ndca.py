#!/usr/bin/env python3
# ndca.py — N-DIMENSIONAL "neighbour + self" cellular automata, and a survey of
# how class-4 (edge-of-chaos) behaviour scales with dimension.
#
# Generalises the 7->1 hex rule to any dimension N using the von Neumann
# neighbourhood (self + the 2N face neighbours, ±1 along each axis):
#     neighbourhood size  m = 2N + 1
#     LUT size            K^m = 4^(2N+1)
# Key fact: 2D-hex and 3D-cubic-von-Neumann BOTH have m=7, so the existing 4^7
# mandelhunt class-4 LUTs ARE valid 3D rules — `hex3d` tests whether they stay
# class-4 when run on a 3D lattice.
#
#   1D m=3  4^3=64        2D m=5  4^5=1024     3D m=7  4^7=16384
#   4D m=9  4^9=262144    5D m=11 4^11=4.2M
#
# Class is judged exactly as mandelhunt.c: seed a noisy board, run T ticks,
# measure tail activity (fraction of cells changing per tick in the 2nd half):
#   <0.02 -> class 1 (dies) | <0.08 -> class 2 | >0.55 -> class 3 (chaos)
#   else  -> class 4, c4 = 1 - 4|act-0.32|  (peaks at act~0.32)

import argparse, glob, os
import numpy as np

def step_nd(board, rule, N):
    """One generation of an N-dim K=4 von Neumann CA. board has N axes."""
    m = 2 * N + 1
    key = board.astype(np.int64) << (2 * (m - 1))     # self in the top slot
    slot = m - 2
    for ax in range(N):
        for d in (1, -1):
            key |= np.roll(board, d, axis=ax).astype(np.int64) << (2 * slot)
            slot -= 1
    return rule[key].astype(np.uint8)

def classify_nd(rule, N, side, ticks=16, seed=0):
    rng = np.random.default_rng(seed)
    b = rng.integers(0, 4, (side,) * N).astype(np.uint8)
    cells = b.size; half = ticks // 2; tail = 0
    for t in range(ticks):
        nb = step_nd(b, rule, N)
        if t >= half: tail += int((nb != b).sum())
        b = nb
    act = tail / ((ticks - half) * cells)
    if act < 0.02: return 1, 0.0, act
    if act < 0.08: return 2, 0.1, act
    if act > 0.55: return 3, 0.05, act
    return 4, max(0.0, 1.0 - 4.0 * abs(act - 0.32)), act

# board side per dimension so total cells stay comparable (~5-8k), N=1 bigger.
SIDE_FOR_N = {1: 512, 2: 64, 3: 20, 4: 9, 5: 6}

def cmd_survey(a):
    print("N-dimensional class-4 SURVEY (von Neumann, K=4, random rules)")
    print(f"{'N':>2} {'m':>3} {'LUT':>10} {'side':>5} {'cells':>7}  "
          f"{'c1':>4} {'c2':>4} {'c3':>4} {'c4':>4}  {'%c4':>6} {'mean_act':>8}")
    for N in range(1, a.maxn + 1):
        m = 2 * N + 1; lut = 4 ** m
        if lut > a.lut_cap:
            print(f"{N:>2} {m:>3} {lut:>10}  -- LUT exceeds cap {a.lut_cap}, skipping")
            continue
        side = SIDE_FOR_N.get(N, 6); cells = side ** N
        rng = np.random.default_rng(a.seed + N)
        hist = {1: 0, 2: 0, 3: 0, 4: 0}; acts = []
        for r in range(a.samples):
            rule = rng.integers(0, 4, lut, dtype=np.uint8)
            cls, c4, act = classify_nd(rule, N, side, ticks=a.ticks, seed=a.seed + r)
            hist[cls] += 1; acts.append(act)
        pc4 = 100.0 * hist[4] / a.samples
        print(f"{N:>2} {m:>3} {lut:>10} {side:>5} {cells:>7}  "
              f"{hist[1]:>4} {hist[2]:>4} {hist[3]:>4} {hist[4]:>4}  {pc4:>5.1f}% "
              f"{np.mean(acts):>8.3f}")
    print("\nreading: %c4 = fraction of RANDOM rules that are class-4. If it falls "
          "with N, edge-of-chaos is a narrower target in higher dimensions.")

def cmd_hex3d(a):
    """Do the existing 2D-hex class-4 LUTs (4^7) stay class-4 as 3D von Neumann?"""
    import caca
    pool, names = caca.load_pool(a.samples, seed=1)
    print(f"running {len(pool)} mandelhunt hex class-4 LUTs as 3D von Neumann "
          f"(side {SIDE_FOR_N[3]})...")
    hist = {1: 0, 2: 0, 3: 0, 4: 0}; acts = []
    for i in range(len(pool)):
        cls, c4, act = classify_nd(pool[i], 3, SIDE_FOR_N[3], ticks=a.ticks, seed=a.seed + i)
        hist[cls] += 1; acts.append(act)
    n = len(pool)
    print(f"  class dist: c1={hist[1]} c2={hist[2]} c3={hist[3]} c4={hist[4]}  "
          f"({100.0*hist[4]/n:.1f}% stay class-4)  mean_act {np.mean(acts):.3f}")
    print("reading: these rules were bred class-4 on a 2D HEX lattice; this is the "
          "fraction still class-4 with the SAME LUT on a 3D cubic lattice (different "
          "geometry, same rule space).")

def cmd_selftest(a):
    """N=2 von Neumann sanity: a rule still steps without error in 1..4 D."""
    for N in range(1, 5):
        m = 2 * N + 1
        rng = np.random.default_rng(0)
        rule = rng.integers(0, 4, 4 ** m, dtype=np.uint8)
        b = rng.integers(0, 4, (6,) * N).astype(np.uint8)
        nb = step_nd(b, rule, N)
        assert nb.shape == b.shape and nb.dtype == np.uint8
        print(f"N={N} m={m} LUT=4^{m}={4**m}: step ok, shape {nb.shape}")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    for name in ("survey", "hex3d", "selftest"):
        p = sub.add_parser(name)
        p.add_argument("--samples", type=int, default=150)
        p.add_argument("--ticks", type=int, default=16)
        p.add_argument("--seed", type=int, default=1)
        if name == "survey":
            p.add_argument("--maxn", type=int, default=5)
            p.add_argument("--lut-cap", type=int, default=5_000_000)
    a = ap.parse_args()
    {"survey": cmd_survey, "hex3d": cmd_hex3d, "selftest": cmd_selftest}.get(
        a.cmd, lambda _a: ap.print_help())(a)

if __name__ == "__main__":
    main()
