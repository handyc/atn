#!/usr/bin/env python3
# cell10.py — the user's 2D-hex CA with THREE routable extra inputs ("cell10":
# self + 6 hex neighbours + in1,in2,in3). Generalises cell8 (one input port,
# velour-caml caformer/cell8.py) the same way cell8 generalised the 7->1 rule.
# Each port is a per-cell (H,W) value, routable to anything: another CA board,
# the input signal, the board itself, a constant — the natural way to wire a
# graph of CAs at the cell level.
#
# Bit layout (high -> low, 2 bits each), cell8-consistent so cell8 is the strict
# sub-case (in2=in3=0 -> only the low 16 bits used):
#   in3 | in2 | in1 | self | nw | ne | r | se | sw | l
# LUT: 4^10 = 1,048,576 entries (1 byte each, K=4). Toroidal hex, pointy-top,
# even/odd-row column shift — identical topology to mandelhunt.c hex_step.
#
# Rule discovery uses the user's Mandelbrot walk, extended: render a 1024x1024
# escape-time image (1,048,576 px = one cell10 LUT) and posterise to K=4.

import argparse, glob, os, sys
import numpy as np

LUT_SIZE_10 = 1 << 20          # 4^10 = 1,048,576
LUT_SIZE_7 = 1 << 14           # 4^7  = 16,384
GEN_SIDE = 1024                # 1024*1024 = 1,048,576 = one cell10 LUT

def _even_mask(H):
    return (np.arange(H) % 2 == 0).reshape(H, 1)

def _hex_neigh(b):
    """Return the 7->1 base-14-bit key for board b (H,W) int array, K=4."""
    H = b.shape[0]; em = _even_mask(H)
    up = np.roll(b, 1, axis=0); dn = np.roll(b, -1, axis=0)
    l = np.roll(b, 1, axis=1); rg = np.roll(b, -1, axis=1)
    up_l = np.roll(up, 1, axis=1); up_r = np.roll(up, -1, axis=1)
    dn_l = np.roll(dn, 1, axis=1); dn_r = np.roll(dn, -1, axis=1)
    nw = np.where(em, up_l, up); ne = np.where(em, up, up_r)
    sw = np.where(em, dn_l, dn); se = np.where(em, dn, dn_r)
    return (b << 12) | (nw << 10) | (ne << 8) | (rg << 6) | (se << 4) | (sw << 2) | l

def hex_step_cell10(state, in1, in2, in3, rule):
    """One generation. state and in1/in2/in3 are (H,W) uint8 K=4 grids; any port
    may be a scalar 0 (off). rule has LUT_SIZE_10 entries. Returns new (H,W)."""
    b = state.astype(np.int64)
    key = _hex_neigh(b)
    def g(x):
        return 0 if np.isscalar(x) else np.asarray(x, dtype=np.int64)
    key = key | (g(in1) << 14) | (g(in2) << 16) | (g(in3) << 18)
    return rule[key].astype(np.uint8)

def embed_7to1(rule7):
    """Lift a 7->1 LUT (16384) into a cell10 LUT that IGNORES the 3 ports — a
    guaranteed-class-4 starting point whose ports do nothing until the LUT is
    perturbed to depend on them. cell10_lut[k] = rule7[k & 0x3FFF]."""
    idx = np.arange(LUT_SIZE_10, dtype=np.int64) & (LUT_SIZE_7 - 1)
    return rule7.astype(np.uint8)[idx]

# ── Mandelbrot-walk rule generation (extended to 1024x1024) ──────────────────
def _mandel_grid(cx, cy, span, side=GEN_SIDE, it=256):
    step = span / side
    ox = cx - step * side * 0.5; oy = cy - step * side * 0.5
    xs = ox + np.arange(side) * step
    ys = oy + np.arange(side) * step
    cxg, cyg = np.meshgrid(xs, ys)
    zx = np.zeros_like(cxg); zy = np.zeros_like(cyg)
    esc = np.full(cxg.shape, it, dtype=np.int32)
    alive = np.ones(cxg.shape, dtype=bool)
    with np.errstate(over="ignore", invalid="ignore"):
        for i in range(it):
            zx2 = zx * zx - zy * zy + cxg
            zy = 2 * zx * zy + cyg
            zx = zx2
            m = (zx * zx + zy * zy) >= 4.0
            newly = m & alive
            esc[newly] = i; alive &= ~m
            # freeze escaped cells so they don't overflow to inf/nan
            zx[~alive] = 0.0; zy[~alive] = 0.0
    return esc, it

def _posterise(esc, it):
    flat = esc.ravel()
    finite = flat[flat < it]
    lut = np.empty(flat.size, dtype=np.uint8)
    if finite.size < 3:
        b1, b2 = it // 3, 2 * it // 3
    else:
        b1 = np.quantile(finite, 1/3); b2 = np.quantile(finite, 2/3)
        if b2 <= b1: b2 = b1 + 1
    lut[:] = 1
    lut[flat < b1] = 0
    lut[(flat >= b1) & (flat < b2)] = 2
    lut[flat >= it] = 3
    return lut

SEEDS = [(-0.5, 0.0, 3.0), (-0.745, 0.113, 0.05), (-1.25, 0.0, 0.1),
         (-0.16, 1.04, 0.04), (0.272, 0.005, 0.01)]

def mandel_cell10_lut(cx, cy, span):
    esc, it = _mandel_grid(cx, cy, span)
    return _posterise(esc, it)

def classify_cell10(rule, side=64, ticks=16, seed=0):
    """Class-4 probe with the 3 ports SELF-ROUTED (rolled copies of the board),
    so the rule's port-dependence is exercised. Returns (class, c4, tail_act)."""
    rng = np.random.default_rng(seed)
    b = rng.integers(0, 4, (side, side)).astype(np.uint8)
    tail = 0; half = ticks // 2
    for t in range(ticks):
        in1 = np.roll(b, (3, 5), (0, 1)); in2 = np.roll(b, (7, 11), (0, 1))
        in3 = np.roll(b, (13, 17), (0, 1))
        nb = hex_step_cell10(b, in1, in2, in3, rule)
        if t >= half: tail += int((nb != b).sum())
        b = nb
    act = tail / ((ticks - half) * side * side)
    if act < 0.02: return 1, 0.0, act
    if act < 0.08: return 2, 0.1, act
    if act > 0.55: return 3, 0.05, act
    return 4, max(0.0, 1.0 - 4.0 * abs(act - 0.32)), act


def cmd_gen(a):
    """Mandelbrot-walk to collect class-4 cell10 LUTs into --out."""
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    cur = SEEDS[rng.integers(0, len(SEEDS))]
    saved = 0; scanned = 0; step_in_walk = 0
    while saved < a.n and scanned < a.max_scan:
        cx, cy, span = cur
        lut = mandel_cell10_lut(cx, cy, span)
        cls, c4, act = classify_cell10(lut, side=a.probe_side, ticks=a.ticks, seed=a.seed)
        scanned += 1
        if cls == 4 and c4 >= a.min_c4:
            path = os.path.join(a.out, f"c10_n{saved:04d}_c4{c4:.3f}_a{act:.2f}.lut")
            lut.tofile(path)
            saved += 1
            print(f"  + {os.path.basename(path)}  cx={cx:+.5f} cy={cy:+.5f} span={span:.3g} (scanned {scanned})")
            sys.stdout.flush()
        # walk: zoom into a random sub-region
        cx += (rng.random() * 2 - 1) * 0.4 * span
        cy += (rng.random() * 2 - 1) * 0.4 * span
        span *= 0.6 + 0.35 * rng.random()
        if span < 1e-12: span = 1.0
        cur = (cx, cy, span); step_in_walk += 1
        if step_in_walk >= a.walk: step_in_walk = 0; cur = SEEDS[rng.integers(0, len(SEEDS))]
    print(f"done: saved {saved} class-4 cell10 LUTs of {scanned} scanned -> {a.out}")

def load_pool10(pool_dir, k=None):
    files = sorted(glob.glob(os.path.join(pool_dir, "*.lut")))
    files = [f for f in files if os.path.getsize(f) == LUT_SIZE_10]
    if k: files = files[:k]
    rules = np.stack([np.fromfile(f, dtype=np.uint8, count=LUT_SIZE_10) for f in files]) \
            if files else np.zeros((0, LUT_SIZE_10), np.uint8)
    return rules, [os.path.basename(f) for f in files]


def selftest():
    """cell10 with ports off + a 7->1-embedded LUT must equal the 7->1 step."""
    import caca
    S = 24
    rng = np.random.default_rng(3)
    rule7 = rng.integers(0, 4, LUT_SIZE_7).astype(np.uint8)
    rule10 = embed_7to1(rule7)
    board = rng.integers(0, 4, (S, S)).astype(np.uint8)
    out10 = hex_step_cell10(board, 0, 0, 0, rule10)
    out7 = caca.hex_step(board[None], rule7[None], caca._even_mask(S))[0]
    ok = np.array_equal(out10, out7)
    print("cell10(ports off, embedded 7->1) == caca.hex_step:", ok)
    # and ports actually matter: flip a port, expect a different result on a rule
    # that depends on bit 14+.
    rule10b = rng.integers(0, 4, LUT_SIZE_10).astype(np.uint8)
    o0 = hex_step_cell10(board, np.zeros((S, S), np.uint8), 0, 0, rule10b)
    o1 = hex_step_cell10(board, np.full((S, S), 3, np.uint8), 0, 0, rule10b)
    print("ports influence output (random rule):", not np.array_equal(o0, o1))
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("gen")
    g.add_argument("--out", default="cell10-pool")
    g.add_argument("--n", type=int, default=16)
    g.add_argument("--min-c4", type=float, default=0.3)
    g.add_argument("--walk", type=int, default=24)
    g.add_argument("--probe-side", type=int, default=64)
    g.add_argument("--ticks", type=int, default=16)
    g.add_argument("--max-scan", type=int, default=4000)
    g.add_argument("--seed", type=int, default=1)
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "gen": cmd_gen(a)
    elif a.cmd == "selftest": selftest()
    else: ap.print_help()

if __name__ == "__main__":
    main()
