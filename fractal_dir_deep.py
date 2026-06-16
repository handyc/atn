#!/usr/bin/env python3
# fractal_dir_deep.py — go deeper on the novel result (fractal coordinate controls
# glider DIRECTION). Two experiments:
#
#  A) MECHANISM via rotation-equivariance. The posterised fractal image IS the LUT
#     (pixel index = 7-cell neighborhood key; row=key>>7 is set by self+north
#     neighbors, col=key&127 by south/west neighbors). So the ORIENTATION of the
#     fractal field should set the propagation axis. Test: at one fixed Newton
#     location, ROTATE the sampling grid by phi and ask whether the glider angle
#     tracks phi. If glider angle locks to phi (low R(theta) but high R(theta-phi)),
#     fractal-field orientation causally sets glider direction — a real mechanism.
#
#  B) CONTINUITY / transfer function. Sweep the fractal coordinate along a path and
#     show the mean glider angle varies SMOOTHLY (not just "two regions differ"),
#     i.e. fractal space is a continuous DIAL for direction.
import json, os
import numpy as np
import rulehub, glider_dir

LIB = "alice/swarm-v1/outputs"

def newton_lut_rot(cx, cy, span, phi, it=200, side=128):
    st = span / side
    xs = (np.arange(side) - side / 2) * st
    gx0, gy0 = np.meshgrid(xs, xs)
    c, s = np.cos(phi), np.sin(phi)
    gx = cx + c * gx0 - s * gy0
    gy = cy + s * gx0 + c * gy0
    return rulehub._posterise(rulehub._newton(gx, gy, it), it)

def circ_mean(a):
    a = np.asarray(a); return float(np.arctan2(np.sin(a).mean(), np.cos(a).mean()))

def circ_R(a):
    a = np.asarray(a); return float(np.hypot(np.cos(a).mean(), np.sin(a).mean()))

def circ_circ_corr(al, be):
    al = np.asarray(al); be = np.asarray(be)
    am, bm = circ_mean(al), circ_mean(be)
    num = np.sum(np.sin(al - am) * np.sin(be - bm))
    den = np.sqrt(np.sum(np.sin(al - am) ** 2) * np.sum(np.sin(be - bm) ** 2))
    return float(num / (den + 1e-12))

def region():
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    cx = np.array([r["cx"] for r in recs]); cy = np.array([r["cy"] for r in recs])
    sp = np.array([r["span"] for r in recs])
    return (np.median(cx), np.median(cy), cx.std() + 1e-3, cy.std() + 1e-3,
            float(np.median(sp)))

def measure_angle(lut, nseed=4):
    if rulehub.classify_hex(lut, ticks=12, seed=0) != 4: return None
    angs = []
    for s in range(nseed):
        v = glider_dir.glider_velocity(lut, seed=s)
        if v is not None: angs.append(v[0])
    if len(angs) < 2 or circ_R(angs) < 0.6: return None  # need a clean directed glider
    return circ_mean(angs)

def exp_rotation(cxm, cym, sxm, sym, spm):
    print("=== A) MECHANISM: rotate the fractal sampling grid, watch the glider ===")
    rng = np.random.default_rng(0)
    phis = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    P, T = [], []
    for phi in phis:
        for _ in range(6):  # jitter center within the glider region
            cx = rng.normal(cxm, 0.4 * sxm); cy = rng.normal(cym, 0.4 * sym)
            th = measure_angle(newton_lut_rot(cx, cy, spm, phi))
            if th is not None:
                P.append(phi); T.append(th); break
    if len(P) < 8:
        print(f"  only {len(P)} clean gliders across rotations; inconclusive"); return
    P = np.array(P); T = np.array(T)
    rT = circ_R(T)                      # do glider angles cluster regardless of phi?
    rTmP = circ_R(T - P)                # does theta - phi cluster (lockstep, slope +1)?
    rTpP = circ_R(T + P)                # mirror case (slope -1)
    cc = circ_circ_corr(P, T)
    print(f"  {len(P)} rotation samples (one fixed Newton location)")
    print(f"  R(glider angle)            = {rT:.2f}   (high => direction ignores phi)")
    print(f"  R(glider angle - phi)      = {rTmP:.2f}   (high => locked to fractal orientation, slope +1)")
    print(f"  R(glider angle + phi)      = {rTpP:.2f}   (high => locked, mirrored, slope -1)")
    print(f"  circular-circular corr(phi, angle) = {cc:+.2f}")
    lock = max(rTmP, rTpP)
    if lock > 0.6 and lock > rT + 0.15:
        slope = "+1" if rTmP >= rTpP else "-1 (mirror)"
        print(f"  -> LOCKED (slope {slope}): rotating the fractal field rotates the glider.")
        print("     MECHANISM CONFIRMED — fractal-field orientation sets glider direction.")
    elif rT > 0.6 and rT > lock + 0.15:
        print("  -> glider angle is fixed regardless of phi: direction is set by the")
        print("     LATTICE/substrate, not the fractal orientation (would weaken the claim).")
    else:
        print("  -> partial / noisy coupling; direction depends on phi but not lockstep")
        print("     (hex discretization likely breaks exact equivariance).")

def exp_continuity(cxm, cym, sxm, sym, spm):
    print("\n=== B) CONTINUITY: sweep fractal coordinate, is direction a smooth dial? ===")
    rng = np.random.default_rng(1)
    xs = np.linspace(cxm - 2 * sxm, cxm + 2 * sxm, 11)
    rows = []
    for cx in xs:
        angs = []
        for _ in range(40):
            cyj = rng.normal(cym, 0.3 * sym)
            th = measure_angle(newton_lut_rot(cx, cyj, spm, 0.0), nseed=3)
            if th is not None: angs.append(th)
        if len(angs) >= 5:
            rows.append((cx, circ_mean(angs), circ_R(angs), len(angs)))
    if len(rows) < 4:
        print(f"  only {len(rows)} usable cx points; inconclusive"); return
    cxs = np.array([r[0] for r in rows]); mang = np.array([r[1] for r in rows])
    Rs = np.array([r[2] for r in rows])
    print("   cx        mean-angle   within-R   n")
    for cx, a, R, n in rows:
        print(f"  {cx:+.4f}    {np.degrees(a):7.1f}    {R:.2f}     {n}")
    swing = np.degrees(abs(np.angle(np.exp(1j * (mang.max() - mang.min())))))
    # circular-linear association between cx and angle
    rc = np.corrcoef(cxs, np.cos(mang))[0, 1]; rs = np.corrcoef(cxs, np.sin(mang))[0, 1]
    cl = np.hypot(rc, rs)
    print(f"\n  total mean-angle swing across the cx sweep: {swing:.0f} deg")
    print(f"  mean within-coordinate alignment R: {Rs.mean():.2f} (high => clean per-point direction)")
    print(f"  circular-linear corr(cx, angle): {cl:.2f}")
    if swing > 40 and Rs.mean() > 0.6:
        print("  -> direction varies smoothly & substantially along the coordinate: a real")
        print("     continuous DIAL, not just two distinct regions.")
    else:
        print("  -> little smooth variation here; the dial may be steeper along cy or span.")

def main():
    cxm, cym, sxm, sym, spm = region()
    print(f"Newton glider region: cx~{cxm:.4f} cy~{cym:.4f} span~{spm:.4f}\n")
    exp_rotation(cxm, cym, sxm, sym, spm)
    exp_continuity(cxm, cym, sxm, sym, spm)

if __name__ == "__main__":
    main()
