#!/usr/bin/env python3
# flipflop.py — can a NETWORK of CAs store a bit, like a flip-flop? The reservoir route
# failed (evolved feedback -> oscillators, no input memory). A flip-flop is the other
# kind of memory: a BISTABLE LATCH that holds a discrete state by design. The natural
# CA latch = two mutually-inhibiting layers (each annihilates the other where they
# overlap -> winner-take-all). Protocol: SET (seed layer A) -> HOLD (no input) -> read;
# RESET (seed layer B) -> HOLD -> read. If after SET A dominates & PERSISTS, and after
# RESET B dominates & persists, the network stores 1 bit (a set/reset latch).
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

def fill_from_seed(lut, side=64, T=30, seed=0):
    rng = np.random.default_rng(seed); b = np.zeros((side, side), np.uint8); c = side // 2
    b[c-2:c+3, c-2:c+3] = rng.integers(1, 4, (5, 5)); fills = []
    for _ in range(T):
        b = lut[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8); fills.append((b > 0).mean())
    return np.mean(fills[T//2:])   # late-time fill fraction

def find_spreader():
    rng = np.random.default_rng(0); best = None
    for _ in range(120):
        cx, cy, sp = rng.normal(-0.1, 0.12), rng.normal(-0.02, 0.12), rng.uniform(0.2, 1.0)
        lut = newton_lut(cx, cy, sp)
        f = fill_from_seed(lut)
        if 0.1 < f < 0.6:                     # spreads to a sustained, bounded fill (good for a territory)
            if best is None or abs(f - 0.35) < abs(best[1] - 0.35): best = ((cx, cy, sp), f, lut)
    return best

def seedpatch(b, side, rng, frac=0.5):
    # seed one half of the board (a strong SET/RESET pulse) for layer ownership
    h = int(side * frac); b[:, :h] = 0; b[side//2-6:side//2+6, 4:16] = rng.integers(1, 4, (12, 12))

def latch_run(lut, side=64, hold=50):
    rng = np.random.default_rng(1)
    A = np.zeros((side, side), np.uint8); B = np.zeros((side, side), np.uint8)
    def step_pair(A, B, ticks, injA=None, injB=None):
        for t in range(ticks):
            if injA is not None and t < 6: A[injA[0]:injA[0]+10, injA[1]:injA[1]+10] = rng.integers(1, 4, (10, 10))
            if injB is not None and t < 6: B[injB[0]:injB[0]+10, injB[1]:injB[1]+10] = rng.integers(1, 4, (10, 10))
            A = lut[rulehub.hex_key(A.astype(np.int64))].astype(np.uint8)
            B = lut[rulehub.hex_key(B.astype(np.int64))].astype(np.uint8)
            both = (A > 0) & (B > 0); A[both] = 0; B[both] = 0   # mutual annihilation (winner-take-all)
        return A, B
    A, B = step_pair(A, B, 16, injA=(side//2-5, side//2-5))      # SET: pulse layer A
    A, B = step_pair(A, B, hold)                                  # HOLD (no input)
    set_state = ((A > 0).sum(), (B > 0).sum())
    A, B = step_pair(A, B, 16, injB=(side//2-5, side//2-5))      # RESET: pulse layer B
    A, B = step_pair(A, B, hold)                                  # HOLD
    reset_state = ((A > 0).sum(), (B > 0).sum())
    # persistence check: continue holding, see if states drift
    A, B = step_pair(A, B, hold); reset_state2 = ((A > 0).sum(), (B > 0).sum())
    return set_state, reset_state, reset_state2

def main():
    print("CA flip-flop: two mutually-annihilating layers; SET layer A, RESET layer B\n")
    sp = find_spreader()
    if sp is None:
        print("no suitable spreading rule found"); return
    (cx, cy, span), fill, lut = sp
    print(f"territory rule: newton cx={cx:.3f} cy={cy:.3f} span={span:.3f} (sustained fill {fill:.2f})\n")
    s, r, r2 = latch_run(lut)
    print(f"after SET  (pulsed A): massA={s[0]:5d}  massB={s[1]:5d}  -> {'A holds' if s[0]>2*max(1,s[1]) else 'mixed/B' }")
    print(f"after RESET(pulsed B): massA={r[0]:5d}  massB={r[1]:5d}  -> {'B holds' if r[1]>2*max(1,r[0]) else 'mixed/A'}")
    print(f"after extra HOLD:      massA={r2[0]:5d}  massB={r2[1]:5d}  (persistence check)")
    set_ok = s[0] > 2*max(1, s[1]); reset_ok = r[1] > 2*max(1, r[0])
    persist = abs(r2[1]-r[1]) < 0.5*max(1, r[1]) and r2[1] > r2[0]
    print()
    if set_ok and reset_ok and persist:
        print("-> LATCH WORKS: SET puts it in state A, RESET flips to state B, and the state")
        print("   PERSISTS with no input. The CA network stores 1 bit (a set/reset flip-flop).")
    elif set_ok and reset_ok:
        print("-> bistable but drifting: it switches on SET/RESET but the held state isn't stable;")
        print("   needs tuning (the latch isn't clean yet).")
    elif set_ok and not reset_ok:
        print("-> WRITE-ONCE latch: SET holds A, but RESET can't overpower A (first-writer-wins).")
        print("   That's persistent memory, but not yet a flippable flip-flop.")
    else:
        print("-> no clean latching with this rule/coupling; the territories don't hold or compete")
        print("   cleanly. Needs a GA search over rule + coupling for robust bistability.")

if __name__ == "__main__":
    main()
