#!/usr/bin/env python3
# cadual.py — the named frontier: a SECOND SPREADING LAYER. cainv showed an inverter whose
# suppressor was the STABLE layer O (can't be routed) -> inversion only on external inputs ->
# single-level autonomous logic. Fix: make BOTH layers spreading (Z and Y, two copies of the
# carrier rule that MUTUALLY ANNIHILATE). Now a ROUTED carrier on Y can suppress a Z-source
# (different layers annihilate), so:
#   complementary inverter — a Z-source emits Z unless a Y-input floods it -> Z = NOT(Y).
#   the dual emits Y unless a Z-input floods it -> Y = NOT(Z).
# Because each stage's output (one layer) annihilates the NEXT stage's source (the other
# layer), inverters CHAIN by alternating layers — the thing one spreading layer couldn't do.
# TEST 1: single complementary inverter (NOT / NOR, suppressor on the spreading Y layer).
# TEST 2: two stages in series = a BUFFER (NOT of NOT = identity) -> proves chaining.
# If both hold held-out, fully-autonomous universal logic is unlocked. rulehub + numpy only.
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

LW = newton_lut(-0.255, -0.077, 0.270)     # the spreading carrier rule (used on BOTH layers)

# ===================== TEST 1: single complementary inverter ============================
H1, W1 = 40, 96
M1 = np.zeros((H1, W1), bool)
M1[4:36, 4:34] = True       # source chamber
M1[17:23, 34:58] = True     # output channel
M1[4:36, 58:92] = True      # readout chamber
WALL1 = ~M1
def run1(inputs, T=200, seed=0, srcsz=7, insz=11):
    rng = np.random.default_rng(seed)
    Z = np.zeros((H1, W1), np.uint8); Y = np.zeros((H1, W1), np.uint8)
    def put(a, r, c, sz): a[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = rng.integers(1, 4, (sz, sz))
    sites = [(20, 12), (18, 12), (22, 12)]
    for t in range(T):
        put(Z, 20, 12, srcsz)                       # Z self-emitting source
        for i, on in enumerate(inputs):
            if on: put(Y, *sites[i], insz)          # Y-input suppressor (SPREADING layer)
        Z = LW[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        Y = LW[rulehub.hex_key(Y.astype(np.int64))].astype(np.uint8)
        Z[WALL1] = 0; Y[WALL1] = 0
        both = (Z > 0) & (Y > 0); Z[both] = 0; Y[both] = 0
    return 1 if int((Z[4:36, 74:92] > 0).sum()) > 20 else 0   # emit Z iff no Y-input = NOR

def truth1(nin, seeds):
    combos = [tuple((k >> b) & 1 for b in range(nin)) for k in range(2**nin)]
    ok = tot = 0; tbl = {}
    for cb in combos:
        tgt = 1 if not any(cb) else 0
        bits = [run1(list(cb), seed=s + 3*sum(cb)) for s in seeds]
        tbl["".join(map(str, cb))] = int(round(np.mean(bits))); ok += sum(b == tgt for b in bits); tot += len(bits)
    return ok/tot, tbl

# ===================== TEST 2: two stages in series = a buffer ==========================
# stage1 Z-source (suppressed by external Y-input) -> channel -> stage2 Y-source (suppressed
# by stage1's arriving Z) -> channel -> readout(Y). out = NOT(NOT(in)) = in.
H2, W2 = 40, 140
M2 = np.zeros((H2, W2), bool)
M2[4:36, 4:30] = True       # chamber1 (Z-source)
M2[17:23, 30:54] = True     # channel 1
M2[4:36, 54:80] = True      # chamber2 (Y-source)
M2[17:23, 80:104] = True    # channel 2
M2[4:36, 104:136] = True    # readout (read Y)
WALL2 = ~M2
def run2(inp, T=300, seed=0, srcsz=5, insz=11):
    rng = np.random.default_rng(seed)
    Z = np.zeros((H2, W2), np.uint8); Y = np.zeros((H2, W2), np.uint8)
    def put(a, r, c, sz): a[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = rng.integers(1, 4, (sz, sz))
    for t in range(T):
        put(Z, 20, 12, srcsz)                       # stage1 Z-source
        put(Y, 20, 66, srcsz)                       # stage2 Y-source
        if inp: put(Y, 20, 12, insz)                # external Y-input suppresses stage1
        Z = LW[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        Y = LW[rulehub.hex_key(Y.astype(np.int64))].astype(np.uint8)
        Z[WALL2] = 0; Y[WALL2] = 0
        both = (Z > 0) & (Y > 0); Z[both] = 0; Y[both] = 0
    return 1 if int((Y[4:36, 120:136] > 0).sum()) > 20 else 0   # out = Y at readout = in

def truth2(seeds):
    ok = tot = 0; tbl = {}
    for inp in (0, 1):
        bits = [run2(inp, seed=s + 3*inp) for s in seeds]
        tbl[str(inp)] = int(round(np.mean(bits))); ok += sum(b == inp for b in bits); tot += len(bits)
    return ok/tot, tbl

def main():
    print("cadual — a SECOND SPREADING LAYER: routed carriers can invert each other\n")
    print("TEST 1 — complementary inverter (suppressor on the spreading Y layer):")
    okall = True
    for nin, name in [(1, "NOT"), (2, "NOR2"), (3, "NOR3")]:
        tr, _ = truth1(nin, range(6)); ho, tbl = truth1(nin, range(100, 108))
        okall &= ho >= 0.95
        print(f"  {name:5s}: TRAIN {100*tr:4.0f}%  HELD-OUT {100*ho:4.0f}%   {tbl}")
    print("\nTEST 2 — two inverters in series = BUFFER (NOT of NOT = identity), proves chaining:")
    tr2, _ = truth2(range(6)); ho2, tbl2 = truth2(range(100, 108))
    okchain = ho2 >= 0.95
    print(f"  BUFFER: TRAIN {100*tr2:4.0f}%  HELD-OUT {100*ho2:4.0f}%   in->out {tbl2}")
    print()
    if okall and okchain:
        print("  ==> UNLOCKED: two spreading layers give a chainable inverting repeater. With OR-")
        print("      flood (same-layer merge) + walls/channels (routing, fan-out) + this inverter,")
        print("      fully-AUTONOMOUS UNIVERSAL logic is reachable — no controller. The named")
        print("      frontier primitive works; next is an autonomous place-and-route on it.")
    else:
        print("  ==> partial: " + ("inverter ok, chaining needs tuning (channel leakage/timing)"
              if okall and not okchain else "the complementary inverter itself needs tuning") +
              " — honest, and the next thing to fix.")

if __name__ == "__main__":
    main()
