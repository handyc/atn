#!/usr/bin/env python3
# route.py — GLIDER ROUTING in a heterogeneous CA. Using glider surgery, build rules
# from ONE base that differ only in the 18 direction-entries, so a glider keeps its
# (shared) bulk morphology but turns to each region's drift. Tile them across space:
#   (A) sharp 90-deg bend across a vertical domain wall (east domain | south domain);
#   (B) a GRADED steering field heading(col): 0->90 deg, which should curve the glider;
#   (C) cross-domain head-on: east domain | west domain, two gliders meet at the wall
#       (single-rule collisions are blocked by anisotropy; can surgery make them meet?).
import json, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rulehub, glider_dir
from design import design_edit
from mechanism import cmean, cR, cdiff

LIB = "alice/swarm-v1/outputs"; BLOBS = os.path.join(LIB, "blobs")

def rule_for(base, theta_deg):
    return design_edit(base, np.radians(theta_deg) - np.pi)

def het_step(b, stack, reg):
    return stack[reg, rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)

def seed_at(b, r, c, rng):
    b[r-2:r+3, c-2:c+3] = rng.integers(1, 4, (5, 5))

def track(b, stack, reg, T, fill_cap=0.16):
    H = b.shape[0]; traj = []
    for t in range(T):
        b = het_step(b, stack, reg)
        nz = np.flatnonzero(b); m = nz.size
        if m == 0 or m > fill_cap * b.size: break
        ys, xs = np.divmod(nz, H); traj.append((t, ys.mean(), xs.mean(), m))
    return np.array(traj), b

def seg_heading(traj, mask):
    p = traj[mask]
    if len(p) < 4: return None
    v = (p[-1, 1:3] - p[0, 1:3])
    if np.hypot(*v) < 1.0: return None
    return float(np.arctan2(v[0], v[1]))

def base_rule(rng):
    recs = [r for r in json.load(open(os.path.join(LIB, "library.json")))
            if r["glider"] and r["family"] == "newton"]
    # pick a base whose surgery reliably glides east and south
    for i in rng.choice(len(recs), 30, replace=False):
        lut = np.fromfile(os.path.join(BLOBS, recs[i]["hash"] + ".lut"), dtype=np.uint8, count=16384)
        ok = True
        for th in (0, 90, 180):
            ed = rule_for(lut, th)
            v = glider_dir.glider_velocity(ed, seed=0)
            if v is None: ok = False; break
        if ok: return lut
    return lut

def exp_A(base, H=150, T=170):
    print("=== (A) sharp 90-deg bend across a domain wall (east | south) ===")
    wall = H // 2
    ruleE, ruleS = rule_for(base, 0), rule_for(base, 90)
    stack = np.stack([ruleE, ruleS])
    cols = np.arange(H)[None, :].repeat(H, 0)
    reg = (cols >= wall).astype(int)
    b = np.zeros((H, H), np.uint8); rng = np.random.default_rng(1)
    seed_at(b, H // 2, 22, rng)
    traj, _ = track(b, stack, reg, T)
    if len(traj) < 20:
        print("  glider died early; inconclusive"); return traj, reg, wall
    tx = next((traj[k, 0] for k in range(len(traj)) if traj[k, 2] >= wall), None)
    hb = seg_heading(traj, (traj[:, 2] < wall - 3) & (traj[:, 0] < (tx or 1e9)))
    ha = seg_heading(traj, traj[:, 0] > (tx + 4)) if tx is not None else None
    print(f"  survived {len(traj)} ticks; crossed wall at tick {tx}")
    if hb is not None: print(f"  heading BEFORE wall: {np.degrees(hb):+.0f} deg (east domain = 0)")
    if ha is not None: print(f"  heading AFTER  wall: {np.degrees(ha):+.0f} deg (south domain = 90)")
    if hb is not None and ha is not None:
        turn = np.degrees(cdiff(ha, hb))
        print(f"  -> glider TURNED {turn:.0f} deg at the wall "
              f"({'routed ~90deg, waveguide works' if 60 < turn < 120 else 'turn off-target'})")
    return traj, reg, wall

def exp_B(base, H=150, T=200, N=16):
    print("\n=== (B) graded steering field heading(col): 0 -> 90 deg (curve a glider) ===")
    headings = np.arange(N) * 360 / N
    stack = np.stack([rule_for(base, h) for h in headings])
    cols = np.arange(H)
    field = np.clip(cols / (H - 1) * 90.0, 0, 90)          # desired heading per column
    bins = (np.round(field / (360 / N)).astype(int) % N)
    reg = bins[None, :].repeat(H, 0)
    b = np.zeros((H, H), np.uint8); rng = np.random.default_rng(2)
    seed_at(b, 30, 18, rng)
    traj, _ = track(b, stack, reg, T)
    if len(traj) < 20:
        print("  glider died early; inconclusive"); return traj, field
    # instantaneous heading vs field at the glider's column
    errs = []
    for k in range(6, len(traj) - 4):
        v = traj[k + 4, 1:3] - traj[k - 4, 1:3]
        if np.hypot(*v) < 0.8: continue
        h = np.arctan2(v[0], v[1]); col = int(np.clip(traj[k, 2], 0, H - 1))
        errs.append(np.degrees(cdiff(h, np.radians(field[col]))))
    print(f"  survived {len(traj)} ticks; col {traj[0,2]:.0f}->{traj[-1,2]:.0f}, "
          f"row {traj[0,1]:.0f}->{traj[-1,1]:.0f}")
    if errs:
        print(f"  glider heading vs local steering field: median err {np.median(errs):.0f} deg "
              f"({'follows the field — programmable waveguide' if np.median(errs) < 30 else 'loose tracking'})")
    return traj, field

def exp_C(base, H=150, T=150):
    print("\n=== (C) cross-domain head-on: east | west, two gliders meet at the wall ===")
    wall = H // 2
    stack = np.stack([rule_for(base, 0), rule_for(base, 180)])
    cols = np.arange(H)[None, :].repeat(H, 0); reg = (cols >= wall).astype(int)
    rng = np.random.default_rng(3)
    def run(which):
        b = np.zeros((H, H), np.uint8)
        if which in ("L", "both"): seed_at(b, H//2, wall - 38, rng)
        if which in ("R", "both"): seed_at(b, H//2, wall + 38, rng)
        masses = []
        for _ in range(T):
            b = het_step(b, stack, reg); m = int((b > 0).sum())
            if m > 0.18 * b.size: return None
            masses.append(m)
        return np.array(masses)
    L, R, B = run("L"), run("R"), run("both")
    if L is None or R is None or B is None:
        print("  a run exploded; inconclusive"); return
    exp = L + R; ratio = B[-1] / max(1, exp[-1])
    print(f"  end mass: both={B[-1]} expected(sum of solos)={exp[-1]}  ratio={ratio:.2f}")
    print("  -> " + ("gliders INTERACT at the domain wall (mass deviates from superposition):"
                     " cross-domain collision — a route to logic" if ratio < 0.6 or ratio > 1.6
                     else "pass-through / independent (no interaction at the wall)"))

def figure(tA, regA, wallA, tB, fieldB, H=150):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.5, 4.6))
    a1.imshow(regA, cmap="Pastel1", origin="upper", alpha=0.5)
    if len(tA): a1.plot(tA[:, 2], tA[:, 1], "r.-", ms=3, lw=1)
    a1.axvline(wallA, color="k", ls="--", lw=1); a1.set_title("A. 90° bend: east domain | south domain", fontsize=9)
    a1.set_xlabel("col"); a1.set_ylabel("row")
    fld = np.tile(fieldB, (H, 1))
    im = a2.imshow(fld, cmap="twilight", origin="upper", alpha=0.7)
    if len(tB): a2.plot(tB[:, 2], tB[:, 1], "r.-", ms=3, lw=1)
    a2.set_title("B. graded steering field (0→90°): glider curves", fontsize=9)
    a2.set_xlabel("col"); a2.set_ylabel("row"); fig.colorbar(im, ax=a2, label="field heading (deg)", shrink=0.8)
    fig.tight_layout(); fig.savefig("fig_route.png", dpi=130); plt.close()
    print("\nsaved fig_route.png")

def main():
    rng = np.random.default_rng(0); base = base_rule(rng)
    tA, regA, wallA = exp_A(base)
    tB, fieldB = exp_B(base)
    exp_C(base)
    figure(tA, regA, wallA, tB, fieldB)

if __name__ == "__main__":
    main()
