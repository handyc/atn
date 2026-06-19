#!/usr/bin/env python3
# figs_glider.py — figure for GLIDER-STEERING.md.  Panel A: the direction law (predicted heading
# angle(F_single)+180° vs measured glider heading) across fractal families.  Panel B: the directional
# coverage of the library (polar histogram of measured glider headings — the reachable set + the gaps).
import os, json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import glider_dir
from mechanism import flow_angle, measured_heading

LIB = "alice/swarm-v1/outputs"
FAMS = {"newton": "#6db3ff", "julia": "#ffd27f", "mandelbrot": "#7ee0a0", "burning": "#ff9a9a"}

def collect(per_family=120):
    recs = json.load(open(os.path.join(LIB, "library.json")))
    blobs = os.path.join(LIB, "blobs")
    data = {f: {"pred": [], "meas": []} for f in FAMS}
    allmeas = []
    for fam in FAMS:
        g = [r for r in recs if r.get("glider") and r["family"] == fam][:per_family]
        for r in g:
            lut = np.fromfile(os.path.join(blobs, r["hash"] + ".lut"), dtype=np.uint8, count=16384)
            m = measured_heading(lut)
            if m is None: continue
            fa, fs = flow_angle(lut, "single")
            if fs < 1e-3: continue
            pred = (fa + math.pi) % (2*math.pi)
            data[fam]["pred"].append(math.degrees((pred + math.pi) % (2*math.pi) - math.pi))
            data[fam]["meas"].append(math.degrees((m + math.pi) % (2*math.pi) - math.pi))
            allmeas.append(m)
    return data, allmeas

def main():
    data, allmeas = collect()
    fig = plt.figure(figsize=(11, 4.6), facecolor="white")
    # Panel A — the law
    ax = fig.add_subplot(1, 2, 1)
    ax.plot([-180, 180], [-180, 180], "k--", lw=1, alpha=.5, label="ideal")
    n = 0
    for fam, col in FAMS.items():
        p, m = data[fam]["pred"], data[fam]["meas"]; n += len(m)
        ax.scatter(m, p, s=14, c=col, edgecolors="none", alpha=.8, label=f"{fam} ({len(m)})")
    ax.set_xlabel("measured glider heading (°)"); ax.set_ylabel("predicted  angle(F)+180°  (°)")
    ax.set_title(f"A. Direction law from the rule table alone  (n={n})", fontsize=11)
    ax.set_xlim(-185, 185); ax.set_ylim(-185, 185); ax.legend(fontsize=8, loc="upper left"); ax.grid(alpha=.25)
    # Panel B — directional coverage
    axp = fig.add_subplot(1, 2, 2, projection="polar")
    bins = np.linspace(-math.pi, math.pi, 25)
    h, _ = np.histogram(allmeas, bins=bins)
    centers = (bins[:-1] + bins[1:]) / 2
    axp.bar(centers, h, width=(2*math.pi/24)*0.9, color="#6db3ff", edgecolor="#244", alpha=.85)
    axp.set_title(f"B. Reachable glider headings ({len(allmeas)} rules)\n— note the sparse →0° / ↑ regions", fontsize=10, pad=18)
    axp.set_theta_zero_location("E"); axp.set_yticklabels([])
    fig.suptitle("Gliders in a hexagonal K=4 fractal-rule CA: a closed-form direction law + uneven coverage", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig("fig-glider-steering.png", dpi=120)
    print("wrote fig-glider-steering.png ; law points n =", sum(len(data[f]['meas']) for f in FAMS))

if __name__ == "__main__":
    main()
