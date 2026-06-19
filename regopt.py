#!/usr/bin/env python3
# regopt.py — find minimum-cost-but-still-exact settings for the CA-latch register (cacpu.Reg storage).
# Cost per write ~ HOLD x 2 layers x H x W, W = n*(C+GAP).  Sweep the settle time then the board geometry,
# requiring a perfect roundtrip over many random words x seeds (adjacent-bit words stress cross-talk).
import time
import numpy as np
import rulehub
from cacpu import LO, LZ, stepf, bits, val

W8 = 8

def roundtrip_ok(C, GAP, H, PS, HOLD, words, seeds):
    """Write each word into an 8-bit CA-latch register, read it back; require every bit exact."""
    Wpx = W8 * (C + GAP)
    ok = 0; tot = 0
    for sd in seeds:
        rng = np.random.default_rng(sd)
        for v in words:
            A = np.zeros((H, Wpx), np.uint8); B = np.zeros((H, Wpx), np.uint8); cy = H // 2
            bs = bits(v)
            for i in range(W8):
                cx = i * (C + GAP) + GAP + C // 2; tgt = A if bs[i] else B
                tgt[cy-PS//2:cy-PS//2+PS, cx-PS//2:cx-PS//2+PS] = rng.integers(1, 4, (PS, PS))
            for _ in range(HOLD):
                A = stepf(A, LO, Wpx, H); B = stepf(B, LZ, Wpx, H)
                both = (A > 0) & (B > 0); A[both] = 0; B[both] = 0
            read = []
            for i in range(W8):
                x0 = i * (C + GAP); reg = slice(x0, x0 + C + GAP)
                read.append(1 if int((A[:, reg] > 0).sum()) > int((B[:, reg] > 0).sum()) else 0)
            ok += sum(int(r == b) for r, b in zip(read, bs)); tot += W8
    return ok / tot

if __name__ == "__main__":
    rng = np.random.default_rng(0)
    # words that stress cross-talk: include all-1s, alternating, adjacent pairs, and random
    words = [0x00, 0xFF, 0xAA, 0x55, 0x81, 0x18, 0xC3] + [int(rng.integers(0, 256)) for _ in range(25)]
    HO = range(300, 312)                                  # 12 held-out register seeds
    print("regopt — minimum exact settings for the CA-latch register (baseline C40 GAP10 H40 PS24 HOLD12)\n")

    print("  HOLD sweep (C40 GAP10 H40 PS24):")
    best_hold = 12
    for hold in (12, 8, 6, 4, 3, 2):
        a = roundtrip_ok(40, 10, 40, 24, hold, words, HO)
        print(f"     HOLD={hold:2d}  roundtrip = {100*a:.1f}%")
        if a == 1.0: best_hold = hold
    print(f"   -> min exact HOLD = {best_hold}\n")

    print(f"  HEIGHT sweep (C40 GAP10 PS<=H, HOLD={best_hold}):")
    best_H = 40
    for Hh in (40, 32, 24, 20, 16):
        ps = min(24, Hh - 2)
        a = roundtrip_ok(40, 10, Hh, ps, best_hold, words, HO)
        print(f"     H={Hh:2d} (PS={ps})  roundtrip = {100*a:.1f}%")
        if a == 1.0: best_H = Hh
    print(f"   -> min exact H = {best_H}\n")

    print(f"  CELL sweep (H={best_H}, HOLD={best_hold}):  (C,GAP,PS)")
    best_cell = (40, 10, 24)
    for (C, GAP, PS) in [(40, 10, 24), (32, 8, 20), (28, 6, 16), (24, 6, 14), (20, 5, 12), (16, 4, 10)]:
        ps = min(PS, best_H - 2)
        a = roundtrip_ok(C, GAP, best_H, ps, best_hold, words, HO)
        cell_w = C + GAP
        print(f"     C={C:2d} GAP={GAP} PS={ps:2d} (cell {cell_w}px)  roundtrip = {100*a:.1f}%")
        if a == 1.0: best_cell = (C, GAP, ps)
    print(f"   -> min exact cell = C{best_cell[0]} GAP{best_cell[1]} PS{best_cell[2]}\n")

    C, GAP, PS = best_cell
    old = 12 * 2 * 40 * (8 * 50)
    new = best_hold * 2 * best_H * (8 * (C + GAP))
    print(f"  RECOMMENDED: C={C} GAP={GAP} H={best_H} PS={PS} HOLD={best_hold}")
    print(f"  write cost: {old} -> {new} cell-updates  ({old/new:.1f}x cheaper)")
