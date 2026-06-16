#!/usr/bin/env python3
# fractal_span.py — is SPAN (zoom) a second, ORTHOGONAL control knob (speed),
# independent of the coordinate dial (direction)? And does another zoom OPEN the
# 0deg/-90deg heading gaps the 2D field left? Two experiments:
#   A) ORTHOGONALITY: at fixed glider coordinates, sweep span; does speed respond
#      to span while DIRECTION stays put? (direction<-coord, speed<-span = 2 knobs)
#   B) GAP-FILLING: scan coordinates at several spans; do the scarce headings
#      (0deg ->, -90deg up) become reachable at some zoom?
import json, os
import numpy as np
import rulehub, glider_dir

LIB = "alice/swarm-v1/outputs"
ARROWS = "→↘↓↙←↖↑↗"

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    return rulehub._posterise(rulehub._newton(gx, gy, it), it)

def cmean(a): a = np.asarray(a); return float(np.arctan2(np.sin(a).mean(), np.cos(a).mean()))
def cR(a): a = np.asarray(a); return float(np.hypot(np.cos(a).mean(), np.sin(a).mean()))
def cdiff(a, b): return abs(np.angle(np.exp(1j * (a - b))))

def cell(cx, cy, span, ntry, rng, cj=0.012):
    dirs, sps = [], []
    for _ in range(ntry):
        lut = newton_lut(cx + rng.normal(0, cj), cy + rng.normal(0, cj), span)
        if rulehub.classify_hex(lut, ticks=12, seed=0) != 4: continue
        vs = [glider_dir.glider_velocity(lut, seed=s) for s in range(3)]
        vs = [v for v in vs if v is not None]
        if len(vs) >= 2 and cR([v[0] for v in vs]) > 0.6:
            dirs.append(cmean([v[0] for v in vs])); sps.append(np.mean([v[1] for v in vs]))
    return dirs, sps

def exp_orthogonality(rng):
    print("=== A) ORTHOGONALITY: does span set SPEED while coordinate keeps DIRECTION? ===")
    # coordinates that gave distinct clean directions in the 2D field
    coords = [("~90deg", -0.090, 0.017), ("~180deg", 0.000, -0.163),
              ("~-135deg", -0.180, 0.197), ("~45deg", -0.225, -0.028)]
    spans = [0.20, 0.32, 0.53, 0.85, 1.30]
    drift_all, corr_all = [], []
    for tag, cx, cy in coords:
        rows = []
        for sp in spans:
            d, s = cell(cx, cy, sp, 18, rng)
            if len(d) >= 3: rows.append((sp, cmean(d), cR(d), np.mean(s), np.std(s), len(d)))
        if len(rows) < 3:
            print(f"  {tag} ({cx:+.3f},{cy:+.3f}): too few gliders across spans"); continue
        sp_ = np.array([r[0] for r in rows]); dir_ = np.array([r[1] for r in rows])
        spd_ = np.array([r[3] for r in rows])
        drift = np.degrees(max(cdiff(dir_[i], dir_[j]) for i in range(len(dir_)) for j in range(i+1, len(dir_))))
        rc = np.corrcoef(np.log(sp_), spd_)[0, 1] if spd_.std() > 1e-9 else 0.0
        drift_all.append(drift); corr_all.append(rc)
        print(f"  {tag} ({cx:+.3f},{cy:+.3f}):")
        print("    span   dir(deg)  dirR   speed   sd    n")
        for sp, dd, R, ms, sd, n in rows:
            print(f"    {sp:.2f}  {np.degrees(dd):+7.1f}  {R:.2f}  {ms:.2f}  {sd:.2f}  {n}")
        print(f"    -> direction drift across spans = {drift:.0f} deg; corr(log span, speed) = {rc:+.2f}")
    if drift_all:
        print(f"\n  mean direction drift across span = {np.mean(drift_all):.0f} deg "
              f"(low => coordinate keeps direction regardless of zoom)")
        print(f"  mean |corr(log span, speed)| = {np.mean(np.abs(corr_all)):.2f} "
              f"(high => span is a speed knob)")
        if np.mean(drift_all) < 35 and np.mean(np.abs(corr_all)) > 0.4:
            print("  -> SPAN and COORDINATE are ~orthogonal knobs: zoom sets speed, location")
            print("     sets direction. Two-axis glider control.")
        elif np.mean(np.abs(corr_all)) <= 0.4:
            print("  -> span does NOT cleanly set speed (weak/inconsistent corr); not a speed knob.")
        else:
            print("  -> span changes speed BUT also drifts direction: knobs are coupled, not clean.")

def exp_gaps(rng):
    print("\n=== B) GAP-FILLING: do the scarce headings (0deg, -90deg) open at other zooms? ===")
    cym = -0.028
    for sp in [0.20, 0.53, 1.30]:
        hist = np.zeros(8, int)
        for cx in np.linspace(-0.27, 0.18, 9):
            d, _ = cell(cx, cym, sp, 12, rng)
            for a in d: hist[int(round(np.degrees(a) / 45.0)) % 8] += 1
        rep = " ".join(f"{ARROWS[k]}{hist[k]:>2}" for k in range(8))
        gap = (hist[0], hist[6])  # 0deg (->), -90deg (up, index 6)
        print(f"  span {sp:.2f}: {rep}   | 0deg(->)={gap[0]} -90deg(up)={gap[1]}")
    print("  (index order: -> ↘ ↓ ↙ ← ↖ ↑ ↗ ; 0deg=index0, -90deg=index6)")
    print("  -> if 0deg/-90deg counts stay ~0 at every zoom, those axes are a real hex-")
    print("     lattice anisotropy, not a sampling gap.")

def main():
    rng = np.random.default_rng(5)
    exp_orthogonality(rng)
    exp_gaps(rng)

if __name__ == "__main__":
    main()
