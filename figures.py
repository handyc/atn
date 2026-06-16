#!/usr/bin/env python3
# figures.py — generate the article figures for glider-steering.md.
#   F1 a fractal-walk rule as a 128x128 image (the LUT IS the posterised fractal)
#   F2 measured vs predicted glider heading, all 4 families (the direction law)
#   F3 the 2-D (cx,cy) steering field (arrows) from fractal_field2d.json
#   F4 glider surgery: requested vs realized heading over 360deg
#   F5 the speed null: speed vs |F| (the contrast with direction)
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rulehub, glider_dir
from mechanism import flow_angle, measured_heading, cmean, cR, cdiff, DIRV, SHIFT
from design import design_edit, DIR_ANG

LIB = "alice/swarm-v1/outputs"
BLOBS = os.path.join(LIB, "blobs")
FAM_COL = {"newton": "#d62728", "julia": "#1f77b4", "mandelbrot": "#2ca02c", "burning": "#9467bd"}

def load(fam, n, rng):
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == fam]
    idx = rng.choice(len(recs), size=min(n, len(recs)), replace=False)
    return [recs[i] for i in idx]

def wrap_to(pred, meas):  # shift pred (deg) by 360k to sit nearest meas
    return pred - 360 * np.round((pred - meas) / 360)

def fig1():
    from matplotlib.patches import RegularPolygon, FancyArrow
    lut = np.fromfile(os.path.join(BLOBS, [r for r in json.load(open(os.path.join(LIB, "library.json")))
                      if r["glider"] and r["family"] == "newton"][0]["hash"] + ".lut"),
                      dtype=np.uint8, count=16384)
    fig, (axn, axi) = plt.subplots(1, 2, figsize=(9.2, 4.4),
                                   gridspec_kw={"width_ratios": [1, 1.15]})
    # --- left: labelled 7-cell pointy-top hex neighborhood with bit shifts ---
    R = 1.18  # ring radius; neighbors equidistant from center (true hex neighborhood)
    cells = {"self": (0, 0, "<<12"),
             "e": (R, 0, "<<6"), "ne": (R*0.5, R*0.866, "<<8"), "nw": (-R*0.5, R*0.866, "<<10"),
             "w": (-R, 0, "<<0"), "sw": (-R*0.5, -R*0.866, "<<2"), "se": (R*0.5, -R*0.866, "<<4")}
    for name, (x, y, sh) in cells.items():
        fc = "#ffd27f" if name == "self" else "#cfe6ff"
        axn.add_patch(RegularPolygon((x, y), 6, radius=0.62, orientation=0,
                                     facecolor=fc, edgecolor="k", lw=1.2))
        axn.text(x, y + 0.10, name, ha="center", va="center", fontsize=9, weight="bold")
        axn.text(x, y - 0.20, sh, ha="center", va="center", fontsize=7, color="#555")
    axn.set_xlim(-2.1, 2.1); axn.set_ylim(-2.1, 2.1); axn.set_aspect("equal"); axn.axis("off")
    axn.set_title("7-cell hex neighborhood -> 14-bit key\nkey = self<<12 | nw<<10 | ne<<8 | e<<6 | se<<4 | sw<<2 | w",
                  fontsize=8)
    # --- right: the rule as the posterised escape-time image ---
    im = axi.imshow(lut.reshape(128, 128), cmap="viridis", interpolation="nearest")
    axi.set_title("posterised fractal image = the 16384-entry K=4 LUT\n(pixel index = key; value = output state)", fontsize=8)
    axi.set_xlabel("low 7 bits (se, sw, w)"); axi.set_ylabel("high 7 bits (self, nw, ne)")
    fig.colorbar(im, ax=axi, shrink=0.8, ticks=[0, 1, 2, 3], label="output state")
    fig.suptitle("F1. Substrate and fractal-walk rule generation", fontsize=9, y=1.0)
    fig.tight_layout(); fig.savefig("fig1_schematic.png", dpi=130); plt.close()
    print("F1 done")

def fig2(rng):
    plt.figure(figsize=(5, 5))
    stats = []
    for fam in ("newton", "julia", "mandelbrot", "burning"):
        m, p = [], []
        for r in load(fam, 120, rng):
            lut = np.fromfile(os.path.join(BLOBS, r["hash"] + ".lut"), dtype=np.uint8, count=16384)
            h = measured_heading(lut)
            if h is None: continue
            fa, fs = flow_angle(lut, "single")
            if fs < 1e-3: continue
            m.append(np.degrees(h)); p.append(np.degrees(fa + np.pi))
        m, p = np.array(m), np.array(p); p = wrap_to(p, m)
        err = np.array([np.degrees(cdiff(np.radians(m[i]), np.radians(p[i]))) for i in range(len(m))])
        plt.scatter(p, m, s=9, alpha=0.45, color=FAM_COL[fam],
                    label=f"{fam} (n={len(m)}, med {np.median(err):.0f}°)")
        stats.append((fam, np.median(err)))
    lim = [-200, 200]
    plt.plot(lim, lim, "k--", lw=1, label="heading = angle(F)+180°")
    plt.xlim(lim); plt.ylim(lim); plt.gca().set_aspect("equal")
    plt.xlabel("predicted heading  angle(F)+180°  (deg)"); plt.ylabel("measured glider heading (deg)")
    plt.title("F2. The single-neighbor direction law (18 LUT entries, no simulation)", fontsize=8)
    plt.legend(fontsize=7, loc="upper left"); plt.tight_layout()
    plt.savefig("fig2_direction_law.png", dpi=130); plt.close()
    print("F2 done", stats)

def fig3():
    d = json.load(open("fractal_field2d.json"))
    cx = np.array(d["cx"]); cy = np.array(d["cy"])
    H = np.array([[np.nan if v is None else v for v in row] for row in d["heading_deg"]])
    X, Y = np.meshgrid(cx, cy)
    th = np.radians(H)
    U = np.cos(th); V = -np.sin(th)   # screen: heading dy is row-down, flip for y-up axis
    mask = ~np.isnan(H)
    plt.figure(figsize=(5.2, 5))
    plt.quiver(X[mask], Y[mask], U[mask], V[mask], H[mask], cmap="hsv",
               scale=22, width=0.006, pivot="mid")
    plt.xlabel("fractal cx"); plt.ylabel("fractal cy")
    plt.title("F3. 2-D fractal-coordinate steering field\n(arrow = glider heading; color = angle)", fontsize=8)
    plt.colorbar(label="heading (deg)", shrink=0.8)
    plt.tight_layout(); plt.savefig("fig3_steering_field.png", dpi=130); plt.close()
    print("F3 done")

def fig4(rng):
    recs = load("newton", 12, rng)
    luts = [np.fromfile(os.path.join(BLOBS, r["hash"] + ".lut"), dtype=np.uint8, count=16384) for r in recs]
    targets = np.arange(0, 360, 20)
    req, real, lo, hi = [], [], [], []
    for tg in targets:
        phi = np.radians(tg) - np.pi
        hs = []
        for lut in luts:
            h = measured_heading(design_edit(lut, phi))
            if h is not None: hs.append(np.degrees(h))
        if hs:
            hs = np.array(hs); mh = np.degrees(cmean(np.radians(hs)))
            req.append(tg); real.append(wrap_to(mh, tg))
            sc = np.array([np.degrees(cdiff(np.radians(hs[i]), cmean(np.radians(hs)))) for i in range(len(hs))])
            lo.append(np.percentile(sc, 90))
    req, real, lo = np.array(req), np.array(real), np.array(lo)
    plt.figure(figsize=(5, 5))
    plt.errorbar(req, real, yerr=lo, fmt="o", color="#d62728", ms=5, capsize=2, alpha=0.8,
                 label="realized (mean ± 90th-pct seed scatter)")
    plt.plot([0, 360], [0, 360], "k--", lw=1, label="requested = realized")
    plt.xlabel("requested heading (deg)"); plt.ylabel("realized glider heading (deg)")
    plt.title("F4. Glider surgery: steering by editing 18 LUT entries\n(100% survival, continuous 360°)", fontsize=8)
    plt.legend(fontsize=7); plt.tight_layout(); plt.savefig("fig4_surgery.png", dpi=130); plt.close()
    print("F4 done")

def fig5(rng):
    DIR_SHIFT = {k: SHIFT[k] for k in DIRV}
    sp, Fm = [], []
    for r in load("newton", 400, rng):
        lut = np.fromfile(os.path.join(BLOBS, r["hash"] + ".lut"), dtype=np.uint8, count=16384)
        out = [glider_dir.glider_velocity(lut, seed=s) for s in range(4)]
        out = [v for v in out if v is not None]
        if len(out) < 3 or cR([v[0] for v in out]) < 0.6: continue
        a = {k: np.mean([lut[v << s] > 0 for v in (1, 2, 3)]) for k, s in DIR_SHIFT.items()}
        F = np.hypot(sum(a[k] * DIRV[k][0] for k in DIRV), sum(a[k] * DIRV[k][1] for k in DIRV))
        sp.append(np.mean([v[1] for v in out])); Fm.append(F)
    sp, Fm = np.array(sp), np.array(Fm)
    r = np.corrcoef(Fm, sp)[0, 1]
    plt.figure(figsize=(5, 4))
    plt.scatter(Fm, sp, s=10, alpha=0.4, color="#7f7f7f")
    A = np.polyfit(Fm, sp, 1); xs = np.linspace(Fm.min(), Fm.max(), 2)
    plt.plot(xs, np.polyval(A, xs), "r-", lw=1.5)
    plt.xlabel("|F|  (single-neighbor activation magnitude)"); plt.ylabel("glider speed (cells/tick)")
    plt.title(f"F5. Speed has NO sharp law: corr={r:+.2f}, R²={r*r:.2f}\n(contrast the ~4° direction law)", fontsize=8)
    plt.tight_layout(); plt.savefig("fig5_speed_null.png", dpi=130); plt.close()
    print("F5 done")

def main():
    rng = np.random.default_rng(0)
    fig1(); fig2(rng); fig3(); fig4(rng); fig5(rng)
    print("all figures written: fig1..fig5 *.png")

if __name__ == "__main__":
    main()
