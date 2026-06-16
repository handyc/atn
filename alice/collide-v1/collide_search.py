#!/usr/bin/env python3
# collide_search.py — ALICE worker: can surgery RE-OPEN glider collisions? Single-rule
# collisions are blocked (these rules are unidirectional). But with TWO domains built
# from one base by surgery — left steers east (->), right steers west (<-) — two gliders
# converge at the domain wall. Do they INTERACT (annihilate / make a product) or pass
# through? We run solo-left, solo-right, and both, and compare the combined mass to the
# superposition (sum of solos). Search over many verified-good base gliders x meeting
# offsets. Self-contained: rulehub.py + numpy. Reads {"bases":[[cx,cy,span],...]};
# writes per-base interaction verdicts.
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
    phi = np.radians(theta_deg) - np.pi; out = base.copy()
    for k, s in DIR_SHIFT.items():
        n = int(round(3 * max(0.0, np.cos(DIR_ANG[k] - phi))))
        for i, v in enumerate((1, 2, 3)):
            out[v << s] = v if i < n else 0
    return out

def het_step(b, stack, reg):
    return stack[reg, rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)

def run(stack, reg, seeds, H, ticks, rng):
    b = np.zeros((H, H), np.uint8)
    for (r, c) in seeds:
        b[r-2:r+3, c-2:c+3] = rng.integers(1, 4, (5, 5))
    mass = []
    for _ in range(ticks):
        b = het_step(b, stack, reg); m = int((b > 0).sum())
        if m > 0.18 * H * H: return None        # exploded
        mass.append(m)
    return np.array(mass)

def collide_base(cx, cy, span, H=140, ticks=130):
    base = newton_lut(cx, cy, span)
    if base[0] != 0: base = base.copy(); base[0] = 0
    stack = np.stack([rule_for(base, 0), rule_for(base, 180)])   # left east, right west
    cols = np.arange(H)[None, :].repeat(H, 0); reg = (cols >= H // 2).astype(int)
    rng = np.random.default_rng(0); cy0 = H // 2
    best = None
    for D in (30, 40):
        sl = (cy0, H // 2 - D); sr = (cy0, H // 2 + D)
        L = run(stack, reg, [sl], H, ticks, np.random.default_rng(1))
        R = run(stack, reg, [sr], H, ticks, np.random.default_rng(2))
        B = run(stack, reg, [sl, sr], H, ticks, np.random.default_rng(3))
        if L is None or R is None or B is None: continue
        if L[-1] < 3 or R[-1] < 3: continue       # a solo glider died -> not a clean test
        exp = L + R
        end_ratio = float(B[-1] / max(1, exp[-1]))
        min_ratio = float((B / np.maximum(exp, 1)).min())
        score = abs(1 - min_ratio)                # how far from pure superposition
        rec = dict(D=D, end_ratio=end_ratio, min_ratio=min_ratio,
                   soloL=int(L[-1]), soloR=int(R[-1]), both=int(B[-1]))
        if best is None or score > best[0]: best = (score, rec)
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
            r = collide_base(cx, cy, span)
        except Exception:
            r = None
        if r is not None:
            r.update(cx=cx, cy=cy, span=span)
            r["verdict"] = ("annihilate" if r["min_ratio"] < 0.5 else
                            "product" if r["end_ratio"] > 1.6 else "passthrough")
            res.append(r)
    json.dump(res, open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    inter = sum(1 for r in res if r["verdict"] != "passthrough")
    print(f"task {tag}: {len(res)} clean collision tests, {inter} show interaction")

if __name__ == "__main__":
    main()
