#!/usr/bin/env python3
# route_search.py — ALICE worker: search for ROBUST glider-routing recipes. Local
# tests showed surgically-retargeted gliders follow a graded steering field only
# loosely (median ~37 deg). This sweeps many base Newton gliders x field configs
# (total turn, gradient gentleness, board/ticks) to find bases+fields that route
# cleanly (low heading-vs-field error, survival, real net turn). Self-contained:
# only needs rulehub.py + numpy. Reads inputs/task_XXXX.json = {"bases":[[cx,cy,span],...]},
# writes outputs/result_XXXX.json = [{base, best config + metrics}, ...].
import argparse, json, os
import numpy as np
import rulehub

SHIFT = {"self": 12, "nw": 10, "ne": 8, "r": 6, "se": 4, "sw": 2, "l": 0}
_DIR = {"nw": (-1, -0.5), "ne": (-1, 0.5), "r": (0, 1.0), "se": (1, 0.5), "sw": (1, -0.5), "l": (0, -1.0)}
DIRV = {k: np.array(v) / np.hypot(*v) for k, v in _DIR.items()}
DIR_ANG = {k: float(np.arctan2(v[0], v[1])) for k, v in DIRV.items()}
DIR_SHIFT = {k: SHIFT[k] for k in DIRV}

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    return rulehub._posterise(rulehub._newton(gx, gy, it), it)

def rule_for(base, theta_deg):
    phi = np.radians(theta_deg) - np.pi
    out = base.copy()
    for k, s in DIR_SHIFT.items():
        n = int(round(3 * max(0.0, np.cos(DIR_ANG[k] - phi))))
        for i, v in enumerate((1, 2, 3)):
            out[v << s] = v if i < n else 0
    return out

def het_step(b, stack, reg):
    return stack[reg, rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)

def cdiff(a, b):
    return abs(np.angle(np.exp(1j * (a - b))))

def hwin(traj, i, j):
    v = traj[j] - traj[i]
    return float(np.arctan2(v[0], v[1])) if np.hypot(*v) > 0.5 else None

def graded_trial(base, H, ticks, turn_deg, grad_frac, N=16):
    stack = np.stack([rule_for(base, h) for h in np.arange(N) * 360 / N])
    cols = np.arange(H); L = max(1, int(grad_frac * H))
    field = np.clip(cols / L * turn_deg, 0, turn_deg)         # heading per column
    reg = ((np.round(field / (360 / N)).astype(int)) % N)[None, :].repeat(H, 0)
    b = np.zeros((H, H), np.uint8); rng = np.random.default_rng(0)
    b[H // 2 - 2:H // 2 + 3, 16 - 2:16 + 3] = rng.integers(1, 4, (5, 5))
    traj = []
    for _ in range(ticks):
        b = het_step(b, stack, reg); nz = np.flatnonzero(b); m = nz.size
        if m == 0 or m > 0.16 * H * H: break
        ys, xs = np.divmod(nz, H); traj.append((ys.mean(), xs.mean()))
    if len(traj) < 25: return None
    traj = np.array(traj)
    errs = []
    for k in range(6, len(traj) - 4):
        v = traj[k + 4] - traj[k - 4]
        if np.hypot(*v) < 0.8: continue
        col = int(np.clip(traj[k, 1], 0, H - 1))
        errs.append(cdiff(np.arctan2(v[0], v[1]), np.radians(field[col])))
    if not errs: return None
    h0 = hwin(traj, 2, min(10, len(traj) - 1)); h1 = hwin(traj, max(0, len(traj) - 10), len(traj) - 1)
    net_turn = float(np.degrees(cdiff(h1, h0))) if (h0 is not None and h1 is not None) else 0.0
    disp = float(np.hypot(*(traj[-1] - traj[0])))
    return dict(med_err=float(np.degrees(np.median(errs))), survived=len(traj),
                frac=len(traj) / ticks, net_turn=net_turn, disp=disp)

def best_for_base(cx, cy, span, H=160, ticks=220):
    base = newton_lut(cx, cy, span)
    if base[0] != 0:  # quiescent background required
        base = base.copy(); base[0] = 0
    best = None
    for turn_deg in (60, 90, 120):
        for grad_frac in (0.85, 0.5):
            r = graded_trial(base, H, ticks, turn_deg, grad_frac)
            if r is None: continue
            r.update(turn_deg=turn_deg, grad_frac=grad_frac)
            # "good" = survives most of the run, actually turns, tracks the field
            score = r["med_err"] + 60 * (1 - r["frac"]) + max(0, 40 - r["net_turn"])
            if best is None or score < best[0]:
                best = (score, r)
    return best[1] if best else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    res = []
    for cx, cy, span in spec["bases"]:
        try:
            r = best_for_base(cx, cy, span)
        except Exception as e:
            r = None
        if r is not None:
            r.update(cx=cx, cy=cy, span=span); res.append(r)
    json.dump(res, open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    print(f"task {tag}: {len(res)}/{len(spec['bases'])} bases produced a routing result")

if __name__ == "__main__":
    main()
