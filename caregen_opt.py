#!/usr/bin/env python3
# caregen_opt.py — find the MINIMUM-cost-but-still-100% settings for the two CA gate primitives.
# Cost per gate ~ ticks x board_area; the inverter (112 ticks, 64^2) and the NAND latch (60 ticks, 60^2)
# dominate every datapath (full adder, the self-timed counter). We sweep hold-time AND board size with
# strict held-out discipline (fresh seeds the params never saw) and keep only settings at 100%.
import time
import numpy as np
import rulehub
import gatecell as GC
from caregen import L                                   # the write-once latch territory rule (newton)

# ---------- parametrized inverter (the caregen.NOT mechanism, with SIDE/hold/write window exposed) ----------
def inverter_p(inval, side, hold, win, pullA=False, seed=1):
    rng = np.random.default_rng(seed)
    A = np.zeros((side, side), np.uint8); B = np.zeros((side, side), np.uint8); c = side // 2
    PU, RST = (A, B) if pullA else (B, A)
    def step(ticks, inj=None):
        nonlocal A, B
        for t in range(ticks):
            if inj is not None and t < min(6, win): inj[c-5:c+5, c-5:c+5] = rng.integers(1, 4, (10, 10))
            A = L[rulehub.hex_key(A.astype(np.int64))].astype(np.uint8)
            B = L[rulehub.hex_key(B.astype(np.int64))].astype(np.uint8)
            both = (A > 0) & (B > 0); A[both] = 0; B[both] = 0
    if inval: step(win, inj=RST)
    else:     step(win)
    step(hold)
    step(win, inj=PU)
    step(hold)
    return 1 if ((int((A > 0).sum()) > int((B > 0).sum())) == pullA) else 0

def not_acc(side, hold, win, seeds):
    ok = 0
    for s in seeds:
        ok += (inverter_p(0, side, hold, win, seed=s) == 1)
        ok += (inverter_p(1, side, hold, win, seed=s) == 0)
    return ok / (2 * len(seeds))

# ---------- parametrized NAND latch (gatecell.decide with S/hold exposed) ----------
def decide_p(A, B, side, hold, bias=18, insz=14, seed=0):
    rng = np.random.default_rng(seed)
    O = np.zeros((side, side), np.uint8); Z = np.zeros((side, side), np.uint8)
    def patch(arr, r, c, sz): arr[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = rng.integers(1, 4, (sz, sz))
    patch(O, side//2, side//2, bias)
    if A: patch(Z, side//2 - 12, side//2, insz)
    if B: patch(Z, side//2 + 12, side//2, insz)
    for _ in range(hold):
        O = GC.LO[rulehub.hex_key(O.astype(np.int64))].astype(np.uint8)
        Z = GC.LZ[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        both = (O > 0) & (Z > 0); O[both] = 0; Z[both] = 0
    return 1 if int((O > 0).sum()) > int((Z > 0).sum()) else 0

NAND = {(0,0):1,(0,1):1,(1,0):1,(1,1):0}
def nand_acc(side, hold, seeds):
    ok = 0
    for k in [(0,0),(0,1),(1,0),(1,1)]:
        for s in seeds:
            ok += (decide_p(k[0], k[1], side, hold, seed=s + 7*(k[0]+2*k[1])) == NAND[k])
    return ok / (4 * len(seeds))

if __name__ == "__main__":
    HO = range(200, 240)                                 # 40 held-out seeds the sweeps never train on
    print("caregen_opt — minimum 100%-held-out settings for the CA gate primitives\n")

    # ---- inverter: hold sweep at full board, then board-size sweep at the chosen hold ----
    print("  INVERTER (NOT) — baseline side=64 hold=40 win=16  (= 112 ticks/gate)")
    print("   hold sweep (side=64, win=16):")
    best_hold = 40
    for hold in (40, 24, 16, 12, 8, 6, 4):
        a = not_acc(64, hold, 16, HO)
        print(f"     hold={hold:2d}  ({32+2*hold:3d} ticks)  held-out NOT = {100*a:.0f}%")
        if a == 1.0: best_hold = hold
    print(f"   -> min 100% hold = {best_hold}")
    print(f"   board sweep (hold={best_hold}, win=16):")
    best_side = 64
    for side in (64, 56, 48, 40, 32):
        a = not_acc(side, best_hold, 16, HO)
        print(f"     side={side:2d}  (area {side*side:4d})  held-out NOT = {100*a:.0f}%")
        if a == 1.0: best_side = side
    print(f"   -> min 100% side = {best_side}")
    win_old, win_new = 112*64*64, (32+2*best_hold)*best_side*best_side
    print(f"   INVERTER cost: {win_old} -> {win_new} cell-updates/gate  ({win_old/win_new:.1f}x cheaper)\n")

    # ---- NAND latch: hold sweep, then board sweep ----
    print("  NAND latch — baseline side=60 hold=60  (= 60 ticks/gate)")
    print("   hold sweep (side=60):")
    best_nhold = 60
    for hold in (60, 40, 30, 24, 18, 14, 10):
        a = nand_acc(60, hold, HO)
        print(f"     hold={hold:2d}  held-out NAND = {100*a:.0f}%")
        if a == 1.0: best_nhold = hold
    print(f"   -> min 100% hold = {best_nhold}")
    print(f"   board sweep (hold={best_nhold}):")
    best_nside = 60
    for side in (60, 52, 48, 44, 40):                    # >=40 so the +-12 input patches fit
        a = nand_acc(side, best_nhold, HO)
        print(f"     side={side:2d}  held-out NAND = {100*a:.0f}%")
        if a == 1.0: best_nside = side
    print(f"   -> min 100% side = {best_nside}")
    nold, nnew = 60*60*60, best_nhold*best_nside*best_nside
    print(f"   NAND cost: {nold} -> {nnew} cell-updates/gate  ({nold/nnew:.1f}x cheaper)\n")

    print(f"  RECOMMENDED: inverter side={best_side} hold={best_hold} ; NAND side={best_nside} hold={best_nhold}")
