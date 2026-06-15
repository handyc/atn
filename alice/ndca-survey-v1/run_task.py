#!/usr/bin/env python3
# Higher-N STRUCTURED class-4 survey (one ALICE array task). Self-contained
# (numpy only). Question: do FRACTAL-walked rules (not random) stay class-4 as
# lattice dimension rises? von Neumann neighbourhood m=2N+1, LUT=4^(2N+1); the
# rule LUT is a posterised escape-time fractal rendered on a side=2^(2N+1) image.
# For each (dimension N, fractal family) we generate n_per rules and classify
# each as N-dim class-4 (mandelhunt tail-activity probe). Output = class counts.
#
#   python3 run_task.py <SLURM_ARRAY_TASK_ID>

import json, os, sys
import numpy as np

def esc(zx, zy, cx, cy, kind, it):
    e = np.full(zx.shape, it, np.int32); al = np.ones(zx.shape, bool)
    with np.errstate(over="ignore", invalid="ignore"):
        for i in range(it):
            if kind == "burning":
                zx = np.abs(zx); zy = np.abs(zy)
            zx2 = zx * zx - zy * zy + cx; zy = 2 * zx * zy + cy; zx = zx2
            m = (zx * zx + zy * zy) >= 4.0; nw = m & al
            e[nw] = i; al &= ~m; zx[~al] = 0; zy[~al] = 0
    return e

def newton(zx, zy, it):
    e = np.full(zx.shape, it, np.int32); done = np.zeros(zx.shape, bool)
    with np.errstate(all="ignore"):
        for i in range(it):
            d2x = zx * zx - zy * zy; d2y = 2 * zx * zy
            z3x = zx * d2x - zy * d2y; z3y = zx * d2y + zy * d2x
            nx = z3x - 1.0; ny = z3y; dx = 3 * d2x; dy = 3 * d2y
            dd = dx * dx + dy * dy + 1e-12
            qx = (nx * dx + ny * dy) / dd; qy = (ny * dx - nx * dy) / dd
            nzx = zx - qx; nzy = zy - qy
            conv = ((nzx - zx) ** 2 + (nzy - zy) ** 2) < 1e-6
            e[conv & ~done] = i; done |= conv
            zx, zy = nzx, nzy; zx[done] = 0; zy[done] = 0
    return e

def posterise(e, it):
    f = e.ravel(); fin = f[f < it]; lut = np.ones(f.size, np.uint8)
    if fin.size < 3:
        b1, b2 = it // 3, 2 * it // 3
    else:
        b1 = np.quantile(fin, 1 / 3); b2 = np.quantile(fin, 2 / 3)
        if b2 <= b1: b2 = b1 + 1
    lut[f < b1] = 0; lut[(f >= b1) & (f < b2)] = 2; lut[f >= it] = 3
    return lut

JC = [(-0.4, 0.6), (0.285, 0.01), (-0.70176, -0.3842), (-0.8, 0.156), (-0.835, -0.2321)]
WIN = {"mandelbrot": [(-0.5, 0, 3.0), (-0.745, 0.113, 0.05)],
       "burning": [(-0.5, -0.5, 3.0), (-1.75, -0.03, 0.2)],
       "julia": [(0, 0, 3.2)], "newton": [(0, 0, 3.0), (0, 0, 0.6)]}

def gen_lut(fam, N, rng, it=180):
    side = 2 ** (2 * N + 1)                 # side^2 == 4^(2N+1) == LUT size
    cx, cy, span = WIN[fam][rng.integers(0, len(WIN[fam]))]
    cx += (rng.random() * 2 - 1) * 0.3 * span; cy += (rng.random() * 2 - 1) * 0.3 * span
    sp = span * (0.4 + 0.8 * rng.random())
    st = sp / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    if fam == "julia":
        c = JC[rng.integers(0, len(JC))]
        e = esc(gx, gy, np.full_like(gx, c[0]), np.full_like(gy, c[1]), "mandel", it)
    elif fam == "newton":
        e = newton(gx, gy, it)
    else:
        e = esc(np.zeros_like(gx), np.zeros_like(gy), gx, gy,
                "burning" if fam == "burning" else "mandel", it)
    return posterise(e, it)

def step_nd(b, rule, N):
    m = 2 * N + 1; key = b.astype(np.int64) << (2 * (m - 1)); slot = m - 2
    for ax in range(N):
        for d in (1, -1):
            key |= np.roll(b, d, axis=ax).astype(np.int64) << (2 * slot); slot -= 1
    return rule[key].astype(np.uint8)

SIDE = {1: 400, 2: 48, 3: 18, 4: 9, 5: 6}
def classify(rule, N, ticks, seed):
    rng = np.random.default_rng(seed); s = SIDE[N]
    b = rng.integers(0, 4, (s,) * N).astype(np.uint8)
    half = ticks // 2; tail = 0; cells = b.size
    for t in range(ticks):
        nb = step_nd(b, rule, N)
        if t >= half: tail += int((nb != b).sum())
        b = nb
    act = tail / ((ticks - half) * cells)
    return (1 if act < 0.02 else 2 if act < 0.08 else 3 if act > 0.55 else 4), act

def main():
    tid = int(sys.argv[1]); here = os.path.dirname(os.path.abspath(__file__))
    spec = json.load(open(os.path.join(here, "inputs", f"task_{tid:04d}.json")))
    rng = np.random.default_rng(spec["seed"])
    ticks = spec.get("ticks", 14)
    rows = ["N\tfamily\tclass\tact"]
    for N in spec["dims"]:
        for fam in spec["families"]:
            for k in range(spec["n_per"]):
                lut = gen_lut(fam, N, rng)
                cls, act = classify(lut, N, ticks, spec["seed"] + 100000 * N + k)
                rows.append(f"{N}\t{fam}\t{cls}\t{act:.3f}")
    os.makedirs(os.path.join(here, "outputs"), exist_ok=True)
    open(os.path.join(here, "outputs", f"shard_{tid:04d}.tsv"), "w").write("\n".join(rows) + "\n")
    print(f"task {tid}: classified {len(rows)-1} rules across dims {spec['dims']}")

if __name__ == "__main__":
    main()
