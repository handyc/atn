#!/usr/bin/env python3
# fractals.py — which fractal makes the best class-4 hex-CA rules? Generates
# 7->1 LUTs (4^7 = 16384 = 128x128) by posterising several escape-time fractals,
# classifies each as a 2D-hex CA (mandelhunt-style tail-activity probe), and
# reports the class-4 YIELD per family. Answers: is Mandelbrot special, or do
# Julia / Burning Ship / Newton / Multibrot do as well or better?

import argparse
import numpy as np
import caca, cell10

SIDE = 128                      # 128*128 = 16384 = 4^7

def _escape(zx, zy, cx, cy, kind, it):
    esc = np.full(zx.shape, it, dtype=np.int32)
    alive = np.ones(zx.shape, dtype=bool)
    with np.errstate(over="ignore", invalid="ignore"):
        for i in range(it):
            if kind == "burning":
                zx = np.abs(zx); zy = np.abs(zy)
            if kind == "multibrot3":
                # z^3 + c
                zx2 = zx * (zx * zx - 3 * zy * zy) + cx
                zy = zy * (3 * zx * zx - zy * zy) + cy
                zx = zx2
            else:                                  # z^2 + c (mandel/julia/burning)
                zx2 = zx * zx - zy * zy + cx
                zy = 2 * zx * zy + cy
                zx = zx2
            m = (zx * zx + zy * zy) >= 4.0
            newly = m & alive
            esc[newly] = i; alive &= ~m
            zx[~alive] = 0.0; zy[~alive] = 0.0
    return esc

def _newton(zx, zy, it):
    """Newton fractal for z^3-1: colour = iters to converge to a root."""
    esc = np.full(zx.shape, it, dtype=np.int32)
    done = np.zeros(zx.shape, dtype=bool)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for i in range(it):
            r2 = zx * zx + zy * zy + 1e-12         # |z|^2
            # z - (z^3-1)/(3 z^2)  in real arithmetic
            # 1/z = conj(z)/|z|^2 ; z^2 etc.
            z3x = zx * (zx * zx - 3 * zy * zy); z3y = zy * (3 * zx * zx - zy * zy)
            num_x = z3x - 1.0; num_y = z3y          # z^3 - 1
            d2x = zx * zx - zy * zy; d2y = 2 * zx * zy   # z^2
            den_x = 3 * d2x; den_y = 3 * d2y             # 3 z^2
            dd = den_x * den_x + den_y * den_y + 1e-12
            qx = (num_x * den_x + num_y * den_y) / dd
            qy = (num_y * den_x - num_x * den_y) / dd
            nzx = zx - qx; nzy = zy - qy
            conv = ((nzx - zx) ** 2 + (nzy - zy) ** 2) < 1e-6
            newly = conv & ~done
            esc[newly] = i; done |= conv
            zx, zy = nzx, nzy
            zx[done] = 0; zy[done] = 0
    return esc

def gen_lut(kind, cx, cy, span, rng, it=200):
    step = span / SIDE
    ox = cx - step * SIDE * 0.5; oy = cy - step * SIDE * 0.5
    gx, gy = np.meshgrid(ox + np.arange(SIDE) * step, oy + np.arange(SIDE) * step)
    if kind == "mandelbrot":
        esc = _escape(np.zeros_like(gx), np.zeros_like(gy), gx, gy, "mandel", it)
    elif kind == "multibrot3":
        esc = _escape(np.zeros_like(gx), np.zeros_like(gy), gx, gy, "multibrot3", it)
    elif kind == "burning":
        esc = _escape(np.zeros_like(gx), np.zeros_like(gy), gx, gy, "burning", it)
    elif kind == "julia":
        cjx, cjy = rng.choice(JULIA_C)              # a Julia constant near the boundary
        esc = _escape(gx, gy, np.full_like(gx, cjx), np.full_like(gy, cjy), "mandel", it)
    elif kind == "newton":
        esc = _newton(gx, gy, it)
    else:
        raise ValueError(kind)
    return cell10._posterise(esc, it)

JULIA_C = [(-0.4, 0.6), (0.285, 0.01), (-0.70176, -0.3842), (-0.8, 0.156),
           (-0.835, -0.2321), (0.45, 0.1428), (-0.7269, 0.1889)]

# fractal-specific "interesting" windows to walk within
WINDOWS = {
    "mandelbrot": [(-0.5, 0.0, 3.0), (-0.745, 0.113, 0.05), (0.272, 0.005, 0.01)],
    "multibrot3": [(0.0, 0.0, 3.0), (0.4, 0.0, 0.6)],
    "burning":    [(-0.5, -0.5, 3.0), (-1.75, -0.03, 0.2), (-1.62, -0.04, 0.1)],
    "julia":      [(0.0, 0.0, 3.2)],
    "newton":     [(0.0, 0.0, 3.0), (0.0, 0.0, 0.6)],
}

def classify_hex(rule, side=96, ticks=16, seed=0):
    rng = np.random.default_rng(seed)
    b = rng.integers(0, 4, (side, side)).astype(np.uint8)
    em = caca._even_mask(side); cells = side * side; half = ticks // 2; tail = 0
    for t in range(ticks):
        nb = caca.hex_step(b[None], rule[None], em)[0]
        if t >= half: tail += int((nb != b).sum())
        b = nb
    act = tail / ((ticks - half) * cells)
    if act < 0.02: return 1, act
    if act < 0.08: return 2, act
    if act > 0.55: return 3, act
    return 4, act

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=120)
    ap.add_argument("--ticks", type=int, default=16)
    ap.add_argument("--side", type=int, default=96)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--families", default="mandelbrot,julia,burning,multibrot3,newton")
    a = ap.parse_args()
    print(f"fractal -> class-4 hex-rule YIELD  ({a.samples} samples/family, "
          f"probe {a.side}x{a.side} x{a.ticks} ticks)")
    print(f"{'family':<12}{'c1':>4}{'c2':>4}{'c3':>4}{'c4':>4}  {'%c4':>6} {'mean_act':>9} {'diversity':>10}")
    for fam in a.families.split(","):
        rng = np.random.default_rng(a.seed)
        wins = WINDOWS[fam]
        hist = {1: 0, 2: 0, 3: 0, 4: 0}; acts = []; lut_hashes = set(); c4_luts = []
        for s in range(a.samples):
            cx, cy, span = wins[s % len(wins)]
            # jitter the window to walk the family
            cx += (rng.random() * 2 - 1) * 0.3 * span
            cy += (rng.random() * 2 - 1) * 0.3 * span
            sp = span * (0.4 + 0.8 * rng.random())
            lut = gen_lut(fam, cx, cy, sp, rng, it=200)
            cls, act = classify_hex(lut, side=a.side, ticks=a.ticks, seed=a.seed + s)
            hist[cls] += 1; acts.append(act)
            if cls == 4:
                c4_luts.append(lut.astype(np.int8))
        # diversity among class-4 rules: mean pairwise fraction-of-differing-entries
        div = 0.0
        if len(c4_luts) >= 2:
            arr = np.stack(c4_luts[:40])
            d = [(arr[i] != arr[j]).mean() for i in range(len(arr)) for j in range(i + 1, len(arr))]
            div = float(np.mean(d))
        n = a.samples
        print(f"{fam:<12}{hist[1]:>4}{hist[2]:>4}{hist[3]:>4}{hist[4]:>4}  "
              f"{100.0*hist[4]/n:>5.1f}% {np.mean(acts):>9.3f} {div:>10.3f}")
    print("\nreading: %c4 = class-4 yield (higher = better generator); diversity = how "
          "DIFFERENT the class-4 rules are from each other (higher = richer pool).")

if __name__ == "__main__":
    main()
