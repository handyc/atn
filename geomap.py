#!/usr/bin/env python3
# geomap.py — does WHERE a rule sits in fractal-space predict its CA behaviour?
# Tests mandelhunt's founding hypothesis (fractal structure <-> class-4/complex
# dynamics) on the 164k-rule library: bin fractal coordinates per family and ask
# whether glider-rate / 3D-survival / symmetry / c4 vary SYSTEMATICALLY by region
# and zoom (span). If behaviour is concentrated in specific regions, a TARGETED
# generator beats the blind walk.
import argparse, json, os
import numpy as np

def load(outdir):
    lib = os.path.join(outdir, "library.json")
    return json.load(open(lib))

def gini_concentration(rate, count):
    """What fraction of all 'hits' come from the top-10% richest bins? 0.1=uniform,
    ->1 = highly concentrated."""
    hits = rate * count
    order = np.argsort(rate)[::-1]
    h = hits[order]; total = h.sum()
    if total <= 0: return 0.0
    top10 = h[:max(1, len(h) // 10)].sum()
    return float(top10 / total)

def analyse(recs, prop, nbins=12):
    print(f"\n=== {prop} vs fractal location (per family) ===")
    print(f"{'family':<11}{'global':>8}{'bin range':>16}{'top-10% bins hold':>20}{'span corr':>11}")
    for fam in ["julia", "newton", "burning", "mandelbrot"]:
        rs = [r for r in recs if r["family"] == fam]
        if len(rs) < 500: continue
        cx = np.array([r["cx"] for r in rs]); cy = np.array([r["cy"] for r in rs])
        val = np.array([float(r[prop]) for r in rs], float)
        span = np.array([r["span"] for r in rs])
        glob = val.mean()
        # bin (cx,cy)
        bx = np.clip(((cx - cx.min()) / (np.ptp(cx) + 1e-9) * nbins).astype(int), 0, nbins - 1)
        by = np.clip(((cy - cy.min()) / (np.ptp(cy) + 1e-9) * nbins).astype(int), 0, nbins - 1)
        bid = bx * nbins + by
        rate = np.zeros(nbins * nbins); cnt = np.zeros(nbins * nbins)
        for b, v in zip(bid, val):
            rate[b] += v; cnt[b] += 1
        nz = cnt > 20                      # only bins with enough samples
        br = np.where(cnt > 0, rate / np.maximum(cnt, 1), 0)
        lo, hi = br[nz].min(), br[nz].max()
        conc = gini_concentration(br[nz], cnt[nz])
        # correlation with zoom depth (log span)
        sc = np.corrcoef(np.log(span + 1e-9), val)[0, 1] if val.std() > 0 else 0.0
        print(f"{fam:<11}{glob:>8.3f}{f'{lo:.2f}-{hi:.2f}':>16}{conc*100:>18.0f}%{sc:>11.2f}")
    print("  (top-10% bins hold X% of all hits: 10%=uniform/no structure, >>10%=location predicts;")
    print("   span corr: behaviour vs zoom depth, |r|>0.1 = zoom matters)")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("outdir"); a = ap.parse_args()
    recs = load(a.outdir)
    print(f"fractal-geometry -> behaviour analysis on {len(recs)} class-4 rules")
    for prop in ["glider", "class3d_is4", "symD6_is4", "c4"]:
        if prop == "class3d_is4":
            for r in recs: r["class3d_is4"] = 1.0 if r["class3d"] == 4 else 0.0
        if prop == "symD6_is4":
            for r in recs: r["symD6_is4"] = 1.0 if r["symD6"] == 4 else 0.0
        analyse(recs, prop)
    print("\nverdict: if top-10% bins hold ~10% everywhere -> fractal location does NOT")
    print("predict behaviour (the walk is just a diverse sampler). If >>10% for some")
    print("property -> that behaviour is regionally concentrated -> a targeted generator")
    print("(sample those regions/zooms) would raise yield over the blind walk.")

if __name__ == "__main__":
    main()
