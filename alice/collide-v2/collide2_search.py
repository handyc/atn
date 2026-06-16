#!/usr/bin/env python3
# collide2_search.py — ALICE worker: turn the collide-v1 interactors into GATES.
# Annihilation implements presence-XOR (both gliders -> nothing; one glider ->
# survives). For each interacting base, surgery east|west domains and measure the
# truth table over INPUT combinations {(0,0),(L,0),(0,R),(L,R)} as a function of
# impact parameter (vertical offset) and seed, reading OUTPUT = surviving mass after
# the collision. A clean XOR gate: singles survive, the pair annihilates, robustly
# across impact params and seeds. Also flags AND (product) gates. Needs rulehub+numpy.
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

def final_mass(stack, reg, seeds, H, ticks, seedval):
    rng = np.random.default_rng(seedval)
    b = np.zeros((H, H), np.uint8)
    for (r, c) in seeds:
        b[r-2:r+3, c-2:c+3] = rng.integers(1, 4, (5, 5))
    for _ in range(ticks):
        b = het_step(b, stack, reg)
        if (b > 0).sum() > 0.18 * H * H: return None
    return int((b > 0).sum())

def gate_for_base(cx, cy, span, H=140, ticks=120):
    base = newton_lut(cx, cy, span)
    if base[0] != 0: base = base.copy(); base[0] = 0
    stack = np.stack([rule_for(base, 0), rule_for(base, 180)])
    cols = np.arange(H)[None, :].repeat(H, 0); reg = (cols >= H // 2).astype(int)
    cy0, D = H // 2, 34
    xor_hits = 0; tested = 0; and_hits = 0
    details = []
    for dy in (-6, -3, 0, 3, 6):
        for sv in (1, 2):                                   # two seed realisations
            mL = final_mass(stack, reg, [(cy0, H//2 - D)], H, ticks, sv)
            mR = final_mass(stack, reg, [(cy0 + dy, H//2 + D)], H, ticks, sv + 7)
            mB = final_mass(stack, reg, [(cy0, H//2 - D), (cy0 + dy, H//2 + D)], H, ticks, sv + 13)
            if None in (mL, mR, mB) or mL < 5 or mR < 5:     # need both singles to survive
                continue
            tested += 1
            exp = mL + mR
            if mB < 0.2 * exp: xor_hits += 1                 # pair annihilates -> XOR
            if mB > 1.6 * exp: and_hits += 1                 # product surge -> AND-ish
            details.append([dy, sv, mL, mR, mB])
    if tested < 3: return None
    return dict(cx=cx, cy=cy, span=span, tested=tested,
                xor_frac=xor_hits / tested, and_frac=and_hits / tested,
                gate=("XOR/annihilation" if xor_hits / tested > 0.6 else
                      "AND/product" if and_hits / tested > 0.6 else "inconsistent"),
                details=details)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); spec = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    res = []
    for cx, cy, span in spec["bases"]:
        try:
            r = gate_for_base(cx, cy, span)
        except Exception:
            r = None
        if r is not None: res.append(r)
    json.dump(res, open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    g = sum(1 for r in res if r["gate"] != "inconsistent")
    print(f"task {tag}: {len(res)} bases, {g} consistent gates")

if __name__ == "__main__":
    main()
