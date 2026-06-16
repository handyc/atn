#!/usr/bin/env python3
# fractal_steer.py — capstone on the (now-confirmed) continuous dial: cx -> glider
# direction has circular-linear corr 0.97 (fractal_dir_deep.py). Turn that into
# INVERSE CONTROL: build the cx->angle transfer function, then for requested target
# headings, invert it to a coordinate, GENERATE fresh rules there, and measure how
# close the realized glider heading is. Low steering error = a steerable glider
# driven by a fractal coordinate (the engineering payoff of fractal->direction).
import json, os
import numpy as np
import rulehub, glider_dir

LIB = "alice/swarm-v1/outputs"

def newton_lut(cx, cy, span, it=200, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    return rulehub._posterise(rulehub._newton(gx, gy, it), it)

def circ_mean(a): a = np.asarray(a); return float(np.arctan2(np.sin(a).mean(), np.cos(a).mean()))
def circ_R(a): a = np.asarray(a); return float(np.hypot(np.cos(a).mean(), np.sin(a).mean()))
def cdiff(a, b): return abs(np.angle(np.exp(1j * (a - b))))  # circular distance

def region():
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    cy = np.array([r["cy"] for r in recs]); sp = np.array([r["span"] for r in recs])
    return float(np.median(cy)), float(np.median(sp))

def angle_at(cx, cy, span, ntry, rng, cyj):
    angs = []
    for _ in range(ntry):
        th_lut = newton_lut(cx, rng.normal(cy, cyj), span)
        if rulehub.classify_hex(th_lut, ticks=12, seed=0) != 4: continue
        vs = [glider_dir.glider_velocity(th_lut, seed=s) for s in range(3)]
        vs = [v[0] for v in vs if v is not None]
        if len(vs) >= 2 and circ_R(vs) > 0.6: angs.append(circ_mean(vs))
    return angs

def main():
    cym, spm = region()
    rng = np.random.default_rng(2)
    # 1) build transfer function cx -> angle
    print("building cx -> glider-angle transfer function ...")
    xs = np.linspace(-0.27, 0.18, 19)
    table = []
    for cx in xs:
        angs = angle_at(cx, cym, spm, 26, rng, 0.3 * 0.05)
        if len(angs) >= 5: table.append((cx, circ_mean(angs), circ_R(angs)))
    print(f"  {len(table)} usable control points\n")
    if len(table) < 6:
        print("transfer function too sparse to invert; stop."); return
    tcx = np.array([t[0] for t in table]); tang = np.array([t[1] for t in table])
    # 2) inverse control: for each target heading, pick the cx whose mean angle is closest
    targets = np.radians([0, 45, 90, 135, 180, -135, -90, -45])
    print("INVERSE CONTROL — request a heading, invert to cx, generate, measure:")
    print("  target    chosen-cx   realized   err     R    n")
    errs = []
    for tg in targets:
        k = int(np.argmin([cdiff(tg, a) for a in tang]))
        cx = tcx[k]
        angs = angle_at(cx, cym, spm, 30, rng, 0.3 * 0.05)
        if len(angs) < 4:
            print(f"  {np.degrees(tg):+6.0f}    {cx:+.4f}     (too few gliders)"); continue
        real = circ_mean(angs); R = circ_R(angs); err = np.degrees(cdiff(tg, real))
        errs.append(err)
        print(f"  {np.degrees(tg):+6.0f}    {cx:+.4f}    {np.degrees(real):+7.1f}   {err:4.0f}   {R:.2f}  {len(angs)}")
    if errs:
        errs = np.array(errs)
        reach = np.degrees(cdiff(tang.max(), tang.min()))
        print(f"\n  reachable heading arc (table span): ~{np.degrees(np.ptp(np.unwrap(np.sort(tang)))):.0f} deg")
        print(f"  mean steering error: {errs.mean():.0f} deg  (median {np.median(errs):.0f})")
        if errs.mean() < 35:
            print("  -> gliders are STEERABLE by a fractal coordinate: request a heading,")
            print("     get it within tens of degrees. A fractal-coordinate glider compass.")
        else:
            print("  -> coarse control only; cx sets a region but per-rule scatter is large.")

if __name__ == "__main__":
    main()
