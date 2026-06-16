#!/usr/bin/env python3
# retain.py — classify rulesets by what they DO to an input image, and connect it to the
# CA-computer building blocks (the user's insight). Seed the full grid with a structured
# test image (posterized) and run each rule; measure:
#   RETENTION  = how much the state still matches the input (preserve = WIRE / MEMORY)
#   SHIFT/WIPE = the image translated coherently (the "wipe" effect = TRANSPORT/carrier)
#   GROW       = pattern expands/fills (the flooding carrier used in autowire)
#   CHAOS      = destroyed (useless for computation)
# Sweep fractal-rule coords, classify, and surface the best retain-rules (wires/memory)
# and shift-rules (transport) -- the components a controller-free CA computer needs.
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    return l

SIDE = 60
def test_image():
    img = np.zeros((SIDE, SIDE), np.uint8)
    for r in range(SIDE):
        for c in range(SIDE):
            d = max(abs(r-SIDE//2), abs(c-SIDE//2))           # concentric squares + a diagonal stripe
            img[r, c] = (d // 5) % 4
            if abs(r - c) < 4: img[r, c] = 3
    return img

IMG = test_image()
def match(a, b): return float(((a > 0) == (b > 0)).mean())   # binary-pattern agreement
def shift_match(a, b):
    best, bsh = 0.0, (0, 0)
    for dy in range(-8, 9, 2):
        for dx in range(-8, 9, 2):
            m = match(a, np.roll(np.roll(b, dy, 0), dx, 1))
            if m > best: best, bsh = m, (dy, dx)
    return best, bsh

def classify(cx, cy, span, T=10):
    lut = newton_lut(cx, cy, span)
    b = IMG.copy().astype(np.uint8); prev = b.copy(); chg = 0
    for _ in range(T):
        nb = lut[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
        chg = (nb != b).mean(); prev = b; b = nb
        if (b > 0).sum() == 0: return "die", 0, (0, 0), 0
    ret = match(b, IMG)                                       # retention vs input
    sm, sh = shift_match(b, IMG)                              # best translated match
    fill = (b > 0).mean()
    return None, ret, sh, sm, fill, float(chg), lut

def main():
    rng = np.random.default_rng(0)
    cats = {"RETAIN": [], "SHIFT/WIPE": [], "GROW": [], "CHAOS": [], "die": []}
    for _ in range(400):
        cx, cy, sp = rng.normal(-0.1, 0.18, 1)[0], rng.normal(-0.05, 0.18, 1)[0], rng.uniform(0.15, 1.2)
        r = classify(cx, cy, sp)
        if r[0] == "die": cats["die"].append((cx, cy, sp)); continue
        _, ret, sh, sm, fill, chg, lut = r
        coords = (round(cx, 3), round(cy, 3), round(sp, 3))
        if ret > 0.85: cats["RETAIN"].append((ret, coords))
        elif sm > 0.8 and sh != (0, 0) and ret < 0.8: cats["SHIFT/WIPE"].append((sm, sh, coords))
        elif fill > 0.55: cats["GROW"].append((fill, coords))
        else: cats["CHAOS"].append((ret, coords))
    print("ruleset census on a structured input image (400 Newton rules):\n")
    for k in ("RETAIN", "SHIFT/WIPE", "GROW", "CHAOS", "die"):
        print(f"  {k:11s}: {len(cats[k]):3d}")
    print("\n  best RETAIN rules (preserve image -> WIRE / MEMORY component):")
    for ret, co in sorted(cats["RETAIN"], reverse=True)[:5]:
        print(f"    retention {ret:.2f}  newton{co}")
    print("  best SHIFT/WIPE rules (translate image -> TRANSPORT / carrier component):")
    for sm, sh, co in sorted(cats["SHIFT/WIPE"], reverse=True)[:5]:
        print(f"    shift-match {sm:.2f} by {sh}  newton{co}")
    print("\n  -> RETAIN rules = identity-like (wires that hold a signal; the latch bias used one).")
    print("     SHIFT/WIPE rules = directional transport (the carrier that moves a signal down a")
    print("     wire). GROW = the flooding carrier (autowire). So image-behaviour CLASSIFIES the")
    print("     rule-types a controller-free CA computer is built from -- a useful map for the search.")

if __name__ == "__main__":
    main()
