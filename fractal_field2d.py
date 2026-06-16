#!/usr/bin/env python3
# fractal_field2d.py — the 1D result (cx -> glider heading, corr 0.97, steering
# err 22deg, arc ~296deg) extended to the full 2D fractal plane. Map (cx,cy) ->
# mean glider heading over a grid at fixed span: a STEERING VECTOR FIELD. Then do
# 2D inverse control (request a heading, pick the best (cx,cy) cell, generate,
# verify) and check whether the extra axis closes the gaps the 1D dial had.
import json, os
import numpy as np
import rulehub, glider_dir

LIB = "alice/swarm-v1/outputs"
ARROWS = "→↘↓↙←↖↑↗"   # index = round(angle/45) mod 8; +angle = downward (row+)

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    return rulehub._posterise(rulehub._newton(gx, gy, it), it)

def cmean(a): a = np.asarray(a); return float(np.arctan2(np.sin(a).mean(), np.cos(a).mean()))
def cR(a): a = np.asarray(a); return float(np.hypot(np.cos(a).mean(), np.sin(a).mean()))
def cdiff(a, b): return abs(np.angle(np.exp(1j * (a - b))))
def arrow(a): return ARROWS[int(round(np.degrees(a) / 45.0)) % 8]

def region():
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    cy = np.array([r["cy"] for r in recs]); sp = np.array([r["span"] for r in recs])
    return float(np.median(cy)), float(np.median(sp))

def cell_angle(cx, cy, span, ntry, rng, cj=0.012):
    angs = []
    for _ in range(ntry):
        lut = newton_lut(cx, cy + rng.normal(0, cj), span)
        if rulehub.classify_hex(lut, ticks=12, seed=0) != 4: continue
        vs = [glider_dir.glider_velocity(lut, seed=s) for s in range(3)]
        vs = [v[0] for v in vs if v is not None]
        if len(vs) >= 2 and cR(vs) > 0.6: angs.append(cmean(vs))
    return angs

def main():
    cym, spm = region()
    rng = np.random.default_rng(3)
    N = 11
    xs = np.linspace(-0.27, 0.18, N)
    ys = np.linspace(cym - 0.225, cym + 0.225, N)
    print(f"Newton steering field: span~{spm:.3f}, {N}x{N} grid "
          f"cx[{xs[0]:.2f},{xs[-1]:.2f}] cy[{ys[0]:.2f},{ys[-1]:.2f}]\n")
    field = np.full((N, N), np.nan); Rfield = np.full((N, N), np.nan)
    nfield = np.zeros((N, N), int); cells = []
    for iy, cy in enumerate(ys):
        for ix, cx in enumerate(xs):
            angs = cell_angle(cx, cy, spm, 14, rng)
            nfield[iy, ix] = len(angs)
            if len(angs) >= 4:
                field[iy, ix] = cmean(angs); Rfield[iy, ix] = cR(angs)
                cells.append((cx, cy, field[iy, ix], Rfield[iy, ix], len(angs)))
    # ---- render the field (rows top->bottom = cy high->low for screen sanity) ----
    print("heading field (arrow = glider direction; '.' = no clean glider):")
    print("        cx:  " + " ".join(f"{x:+.2f}" for x in xs))
    for iy in range(N - 1, -1, -1):
        row = []
        for ix in range(N):
            row.append(arrow(field[iy, ix]) + " " if not np.isnan(field[iy, ix]) else ". ")
        print(f"  cy={ys[iy]:+.3f}  " + " ".join(r.strip().ljust(2) for r in row))
    filled = ~np.isnan(field)
    print(f"\ncells with a clean direction: {filled.sum()}/{N*N} "
          f"({100*filled.mean():.0f}%); mean within-cell R = {np.nanmean(Rfield):.2f}")
    # how is heading organized across the plane?
    cxs = np.array([c[0] for c in cells]); cys = np.array([c[1] for c in cells])
    ang = np.array([c[2] for c in cells])
    def cl(u):  # circular-linear corr of variable u with angle
        rc = np.corrcoef(u, np.cos(ang))[0, 1]; rs = np.corrcoef(u, np.sin(ang))[0, 1]
        return np.hypot(rc, rs)
    print(f"circular-linear corr: cx vs heading = {cl(cxs):.2f}, cy vs heading = {cl(cys):.2f}")
    arc = np.degrees(np.ptp(np.unwrap(np.sort(ang))))
    print(f"headings represented in the field span ~{arc:.0f} deg")
    # ---- 2D inverse control ----
    print("\n2D INVERSE CONTROL — request a heading, pick best (cx,cy) cell, verify:")
    print("  target    chosen(cx,cy)        realized   err    R    n")
    good = [c for c in cells if c[3] >= 0.7 and c[4] >= 5]
    errs = []
    for tg in np.radians([0, 45, 90, 135, 180, -135, -90, -45]):
        cand = min(good, key=lambda c: cdiff(tg, c[2]))
        angs = cell_angle(cand[0], cand[1], spm, 26, rng)
        if len(angs) < 4:
            print(f"  {np.degrees(tg):+6.0f}    ({cand[0]:+.3f},{cand[1]:+.3f})   (too few)"); continue
        real = cmean(angs); R = cR(angs); err = np.degrees(cdiff(tg, real)); errs.append(err)
        print(f"  {np.degrees(tg):+6.0f}    ({cand[0]:+.3f},{cand[1]:+.3f})    {np.degrees(real):+7.1f}  "
              f"{err:4.0f}  {R:.2f}  {len(angs)}")
    if errs:
        errs = np.array(errs)
        print(f"\n  mean 2D steering error: {errs.mean():.0f} deg (median {np.median(errs):.0f}) "
              f"— vs 22 deg for the 1D cx-only dial")
        print("  -> the (cx,cy) plane is a 2D steering field for glider heading"
              if errs.mean() < 35 else "  -> 2D adds coverage but per-cell scatter still limits precision")
    # ---- persist for possible web viz ----
    out = {"span": spm, "cx": xs.tolist(), "cy": ys.tolist(),
           "heading_deg": np.where(np.isnan(field), None, np.degrees(field)).tolist(),
           "R": np.where(np.isnan(Rfield), None, Rfield).tolist(), "n": nfield.tolist()}
    with open("fractal_field2d.json", "w") as f: json.dump(out, f)
    print("\nsaved field -> fractal_field2d.json")

if __name__ == "__main__":
    main()
