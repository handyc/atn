#!/usr/bin/env python3
# run_task.py — one ALICE array task of the class-4 rule-LIBRARY scan.
# Self-contained (stdlib + numpy only; nothing fetched at runtime). Reads its
# shard spec from inputs/task_<id>.json, mass-scans escape-time fractals
# (julia / newton / burning / mandelbrot) into 7->1 hex CA rule LUTs (4^7=16384),
# classifies each as class-4 (mandelhunt tail-activity probe), and for every
# class-4 hit also records: 3D von-Neumann survival, and the class of its C6/D6
# symmetrised variants. Saves class-4 LUTs (raw uint8, concatenated) + a TSV
# manifest. Deterministic given the task seed.
#
#   python3 run_task.py <SLURM_ARRAY_TASK_ID>

import json, os, sys
import numpy as np

LUT7 = 1 << 14          # 4^7 = 16384 = 128*128
SIDE_IMG = 128

# ---- escape-time fractals -> 128x128 -> posterise to K=4 -> 4^7 LUT ----------
def _esc(zx, zy, cx, cy, kind, it):
    esc = np.full(zx.shape, it, np.int32); alive = np.ones(zx.shape, bool)
    with np.errstate(over="ignore", invalid="ignore"):
        for i in range(it):
            if kind == "burning":
                zx = np.abs(zx); zy = np.abs(zy)
            zx2 = zx * zx - zy * zy + cx; zy = 2 * zx * zy + cy; zx = zx2
            m = (zx * zx + zy * zy) >= 4.0; newly = m & alive
            esc[newly] = i; alive &= ~m; zx[~alive] = 0.0; zy[~alive] = 0.0
    return esc

def _newton(zx, zy, it):
    esc = np.full(zx.shape, it, np.int32); done = np.zeros(zx.shape, bool)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for i in range(it):
            d2x = zx * zx - zy * zy; d2y = 2 * zx * zy
            z3x = zx * d2x - zy * d2y; z3y = zx * d2y + zy * d2x
            nx = z3x - 1.0; ny = z3y; dx = 3 * d2x; dy = 3 * d2y
            dd = dx * dx + dy * dy + 1e-12
            qx = (nx * dx + ny * dy) / dd; qy = (ny * dx - nx * dy) / dd
            nzx = zx - qx; nzy = zy - qy
            conv = ((nzx - zx) ** 2 + (nzy - zy) ** 2) < 1e-6
            esc[conv & ~done] = i; done |= conv
            zx, zy = nzx, nzy; zx[done] = 0; zy[done] = 0
    return esc

def _posterise(esc, it):
    flat = esc.ravel(); fin = flat[flat < it]; lut = np.ones(flat.size, np.uint8)
    if fin.size < 3:
        b1, b2 = it // 3, 2 * it // 3
    else:
        b1 = np.quantile(fin, 1 / 3); b2 = np.quantile(fin, 2 / 3)
        if b2 <= b1: b2 = b1 + 1
    lut[flat < b1] = 0; lut[(flat >= b1) & (flat < b2)] = 2; lut[flat >= it] = 3
    return lut

JULIA_C = [(-0.4, 0.6), (0.285, 0.01), (-0.70176, -0.3842), (-0.8, 0.156),
           (-0.835, -0.2321), (0.45, 0.1428), (-0.7269, 0.1889)]
WINDOWS = {"mandelbrot": [(-0.5, 0.0, 3.0), (-0.745, 0.113, 0.05), (0.272, 0.005, 0.01)],
           "burning": [(-0.5, -0.5, 3.0), (-1.75, -0.03, 0.2)],
           "julia": [(0.0, 0.0, 3.2)], "newton": [(0.0, 0.0, 3.0), (0.0, 0.0, 0.6)]}

def gen_lut(fam, rng, it=200):
    win = WINDOWS[fam]; cx, cy, span = win[rng.integers(0, len(win))]
    cx += (rng.random() * 2 - 1) * 0.3 * span; cy += (rng.random() * 2 - 1) * 0.3 * span
    sp = span * (0.4 + 0.8 * rng.random())
    step = sp / SIDE_IMG; ox = cx - step * SIDE_IMG * .5; oy = cy - step * SIDE_IMG * .5
    gx, gy = np.meshgrid(ox + np.arange(SIDE_IMG) * step, oy + np.arange(SIDE_IMG) * step)
    if fam == "julia":
        cj = JULIA_C[rng.integers(0, len(JULIA_C))]
        esc = _esc(gx, gy, np.full_like(gx, cj[0]), np.full_like(gy, cj[1]), "mandel", it)
    elif fam == "newton":
        esc = _newton(gx, gy, it)
    else:
        esc = _esc(np.zeros_like(gx), np.zeros_like(gy), gx, gy,
                   "burning" if fam == "burning" else "mandel", it)
    return _posterise(esc, it), (cx, cy, sp)

# ---- hex CA (2D) + von Neumann (3D) steps + class probe ---------------------
def _hex_key(b):
    H = b.shape[0]; em = (np.arange(H) % 2 == 0).reshape(H, 1)
    up = np.roll(b, 1, 0); dn = np.roll(b, -1, 0); l = np.roll(b, 1, 1); rg = np.roll(b, -1, 1)
    nw = np.where(em, np.roll(up, 1, 1), up); ne = np.where(em, up, np.roll(up, -1, 1))
    sw = np.where(em, np.roll(dn, 1, 1), dn); se = np.where(em, dn, np.roll(dn, -1, 1))
    return (b << 12) | (nw << 10) | (ne << 8) | (rg << 6) | (se << 4) | (sw << 2) | l

def classify_hex(rule, side, ticks, seed):
    rng = np.random.default_rng(seed); b = rng.integers(0, 4, (side, side)).astype(np.int64)
    half = ticks // 2; tail = 0; cells = side * side
    for t in range(ticks):
        nb = rule[_hex_key(b)].astype(np.int64)
        if t >= half: tail += int((nb != b).sum())
        b = nb
    act = tail / ((ticks - half) * cells)
    cls = 1 if act < 0.02 else 2 if act < 0.08 else 3 if act > 0.55 else 4
    return cls, act

def step_3d(b, rule):
    key = (b << 12); slot = 5
    for ax in range(3):
        for d in (1, -1):
            key = key | (np.roll(b, d, axis=ax) << (2 * slot)); slot -= 1
    return rule[key]

def classify_3d(rule, side, ticks, seed):
    rng = np.random.default_rng(seed); b = rng.integers(0, 4, (side, side, side)).astype(np.int64)
    half = ticks // 2; tail = 0; cells = side ** 3
    for t in range(ticks):
        nb = step_3d(b, rule).astype(np.int64)
        if t >= half: tail += int((nb != b).sum())
        b = nb
    act = tail / ((ticks - half) * cells)
    return (1 if act < 0.02 else 2 if act < 0.08 else 3 if act > 0.55 else 4), act

# ---- hex symmetry (C6 / D6) -------------------------------------------------
_SH = [6, 8, 10, 0, 2, 4]
def _canon(reflect):
    canon = np.arange(LUT7, dtype=np.int64); seen = np.zeros(LUT7, bool)
    def mk(s, v):
        k = s << 12
        for sh, vv in zip(_SH, v): k |= vv << sh
        return k
    for kk in range(LUT7):
        if seen[kk]: continue
        s = (kk >> 12) & 3; base = [(kk >> sh) & 3 for sh in _SH]
        orb = set()
        for v0 in ([base, base[::-1]] if reflect else [base]):
            v = list(v0)
            for _ in range(6): orb.add(mk(s, v)); v = [v[-1]] + v[:-1]
        c = min(orb)
        for k in orb: canon[k] = c; seen[k] = True
    return canon

def main():
    tid = int(sys.argv[1])
    here = os.path.dirname(os.path.abspath(__file__))
    spec = json.load(open(os.path.join(here, "inputs", f"task_{tid:04d}.json")))
    rng = np.random.default_rng(spec["seed"])
    fams = spec["families"]; ncand = spec["n_candidates"]
    pside, pticks = spec.get("probe_side", 80), spec.get("probe_ticks", 12)
    side3, t3 = spec.get("side3d", 18), spec.get("ticks3d", 12)
    c6 = _canon(False); d6 = _canon(True)
    outdir = os.path.join(here, "outputs"); os.makedirs(outdir, exist_ok=True)
    luts = []; rows = ["idx\tfamily\tclass2d\tact2d\tc4\tclass3d\tclassC6\tclassD6\tcx\tcy\tspan"]
    kept = 0
    for i in range(ncand):
        fam = fams[i % len(fams)]
        lut, (cx, cy, sp) = gen_lut(fam, rng)
        cls, act = classify_hex(lut, pside, pticks, spec["seed"] + i)
        if cls != 4:
            continue
        c4 = max(0.0, 1.0 - 4.0 * abs(act - 0.32))
        cls3, _ = classify_3d(lut, side3, t3, spec["seed"] + i)
        clsC6, _ = classify_hex(lut[c6].astype(np.uint8), pside, pticks, spec["seed"] + i)
        clsD6, _ = classify_hex(lut[d6].astype(np.uint8), pside, pticks, spec["seed"] + i)
        rows.append(f"{kept}\t{fam}\t{cls}\t{act:.3f}\t{c4:.3f}\t{cls3}\t{clsC6}\t{clsD6}"
                    f"\t{cx:.6f}\t{cy:.6f}\t{sp:.6g}")
        luts.append(lut); kept += 1
    if luts:
        np.stack(luts).tofile(os.path.join(outdir, f"shard_{tid:04d}.u8"))
    open(os.path.join(outdir, f"shard_{tid:04d}.tsv"), "w").write("\n".join(rows) + "\n")
    print(f"task {tid}: scanned {ncand}, kept {kept} class-4 LUTs")

if __name__ == "__main__":
    main()
