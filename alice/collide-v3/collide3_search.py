#!/usr/bin/env python3
# collide3_search.py — ALICE worker: lock in a STABLE collision-gate truth table.
# collide-v2 found gate primitives (an AND firing 100%, an XOR 70%) but most were
# impact-parameter-sensitive. Here we scan each interactor densely over impact
# parameter (vertical offset dy) AND timing/phase (horizontal offset px) x seeds, and
# report the best operating point and how robust the gate is there. A clean gate = a
# region of (dy,px) where singles survive and the pair consistently annihilates (XOR)
# or surges (AND), across seeds. Needs rulehub + numpy.
import argparse, json, os
import numpy as np
import rulehub

SHIFT = {"self": 12, "nw": 10, "ne": 8, "r": 6, "se": 4, "sw": 2, "l": 0}
_DIR = {"nw": (-1, -0.5), "ne": (-1, 0.5), "r": (0, 1.0), "se": (1, 0.5), "sw": (1, -0.5), "l": (0, -1.0)}
DIRV = {k: np.array(v) / np.hypot(*v) for k, v in _DIR.items()}
DIR_ANG = {k: float(np.arctan2(v[0], v[1])) for k, v in DIRV.items()}
DSH = {k: SHIFT[k] for k in DIRV}

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    return rulehub._posterise(rulehub._newton(gx, gy, it), it)

def rule_for(base, theta_deg):
    phi = np.radians(theta_deg) - np.pi; out = base.copy()
    for k, s in DSH.items():
        n = int(round(3 * max(0.0, np.cos(DIR_ANG[k] - phi))))
        for i, v in enumerate((1, 2, 3)):
            out[v << s] = v if i < n else 0
    return out

def het_step(b, stack, reg):
    return stack[reg, rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)

def run(stack, reg, seeds, H, ticks, seedval):
    rng = np.random.default_rng(seedval); b = np.zeros((H, H), np.uint8)
    for (r, c) in seeds:
        b[r-2:r+3, c-2:c+3] = rng.integers(1, 4, (5, 5))
    for _ in range(ticks):
        b = het_step(b, stack, reg)
        if (b > 0).sum() > 0.18 * H * H: return None
    return int((b > 0).sum())

def scan_base(cx, cy, span, H=120, ticks=110):
    base = newton_lut(cx, cy, span)
    if base[0] != 0: base = base.copy(); base[0] = 0
    stack = np.stack([rule_for(base, 0), rule_for(base, 180)])
    cols = np.arange(H)[None, :].repeat(H, 0); reg = (cols >= H // 2).astype(int)
    cy0, D = H // 2, 32
    pts = []
    for dy in range(-8, 9, 2):
        for px in (-4, -2, 0, 2, 4):
            xor = 0; ann = 0; ok = 0
            for sv in (1, 2, 3):
                mL = run(stack, reg, [(cy0, H//2 - D)], H, ticks, sv)
                mR = run(stack, reg, [(cy0 + dy, H//2 + D + px)], H, ticks, sv + 11)
                mB = run(stack, reg, [(cy0, H//2 - D), (cy0 + dy, H//2 + D + px)], H, ticks, sv + 23)
                if None in (mL, mR, mB) or mL < 5 or mR < 5: continue
                ok += 1
                if mB < 0.2 * (mL + mR): xor += 1
                if mB > 1.6 * (mL + mR): ann += 1
            if ok >= 2:
                pts.append(dict(dy=dy, px=px, seeds_ok=ok, xor=xor / ok, andp=ann / ok))
    if not pts: return None
    # best XOR / AND operating points (require all valid seeds agree)
    bx = max(pts, key=lambda p: (p["xor"], p["seeds_ok"]))
    ba = max(pts, key=lambda p: (p["andp"], p["seeds_ok"]))
    xor_region = np.mean([p["xor"] >= 0.99 for p in pts])   # fraction of grid that is a clean XOR
    and_region = np.mean([p["andp"] >= 0.99 for p in pts])
    return dict(cx=cx, cy=cy, span=span, npts=len(pts),
                best_xor=bx["xor"], best_xor_pt=[bx["dy"], bx["px"]],
                best_and=ba["andp"], best_and_pt=[ba["dy"], ba["px"]],
                xor_region=float(xor_region), and_region=float(and_region),
                stable=("XOR" if xor_region > 0.25 else "AND" if and_region > 0.25 else
                        "point" if (bx["xor"] >= 0.99 or ba["andp"] >= 0.99) else "none"))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); spec = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    res = []
    for cx, cy, span in spec["bases"]:
        try:
            r = scan_base(cx, cy, span)
        except Exception:
            r = None
        if r is not None: res.append(r)
    json.dump(res, open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    st = sum(1 for r in res if r["stable"] in ("XOR", "AND"))
    print(f"task {tag}: {len(res)} bases, {st} with a stable gate region")

if __name__ == "__main__":
    main()
