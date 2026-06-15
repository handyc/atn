#!/usr/bin/env python3
# cell11.py — the user's "cell-11": the 7->1 hex rule + 4 EXTRA input ports that
# are INERT by default (all-ports-zero slice of the LUT == the base 7->1 rule) and
# can carry distinct, independently-set behaviours when 1-4 ports are "full".
# LUT = 4^11 = 4,194,304 entries. Two tests:
#   (a) conditional-multiplexer demo: build a cell-11 rule that does base dynamics
#       with ports off AND k distinct commanded actions when ports fire — verify
#       it executes all of them (the ports = extra address lines = a behaviour MUX).
#   (b) reservoir A/B: 4 additive ports vs base 7->1 (expected null, per cell10).
import sys
import numpy as np
import caca, cell10

LUT11 = 1 << 22          # 4^11
LUT7 = 1 << 14

def hex_step_cell11(state, ports, rule):
    """ports = list of 4 (H,W) K=4 grids (or scalar 0). key = base 7->1 (low 14
    bits) | in1<<14 | in2<<16 | in3<<18 | in4<<20."""
    key = cell10._hex_neigh(state.astype(np.int64))
    for i, p in enumerate(ports):
        g = 0 if np.isscalar(p) else np.asarray(p, np.int64)
        key = key | (g << (14 + 2 * i))
    return rule[key].astype(np.uint8)

def embed_7to1(rule7):
    """Lift a 7->1 LUT into a cell-11 LUT whose all-ports-zero slice IS rule7
    (ports inert by default). cell11[idx] = rule7[idx & 0x3FFF]."""
    idx = np.arange(LUT11, dtype=np.int64) & (LUT7 - 1)
    return rule7.astype(np.uint8)[idx]

def selftest():
    S = 16; rng = np.random.default_rng(5)
    rule7 = rng.integers(0, 4, LUT7).astype(np.uint8)
    rule11 = embed_7to1(rule7)
    b = rng.integers(0, 4, (S, S)).astype(np.uint8)
    out11 = hex_step_cell11(b, [0, 0, 0, 0], rule11)
    out7 = caca.hex_step(b[None], rule7[None], caca._even_mask(S))[0]
    ok = np.array_equal(out11, out7)
    # a port being full changes output only where the rule depends on it:
    r = rng.integers(0, 4, LUT11).astype(np.uint8)
    o0 = hex_step_cell11(b, [np.zeros((S, S), np.uint8)] * 4, r)
    o1 = hex_step_cell11(b, [np.full((S, S), 3, np.uint8), 0, 0, 0], r)
    print("cell-11 ports-off == 7->1:", ok, " | a port changes output:", not np.array_equal(o0, o1))
    return ok

def conditional_demo():
    """Build a cell-11 rule that is a behaviour MULTIPLEXER: ports-off -> base
    7->1; exactly one port full with value v in {1,2,3} commands a distinct fixed
    ACTION; verify it executes each branch on random states. A plain 7->1 cannot
    do this (it has no ports to condition on)."""
    rng = np.random.default_rng(1)
    rule7 = cell10.embed_7to1  # not used; we craft directly
    base7 = rng.integers(0, 4, LUT7).astype(np.uint8)
    rule = embed_7to1(base7).copy()              # ports off -> base (inert)
    # define commanded actions on the slice "port1 == v, others 0":
    #   v=1 -> output constant 0 ; v=2 -> constant 1 ; v=3 -> constant 2
    base_idx = np.arange(LUT7, dtype=np.int64)   # low 14 bits (the 7->1 key)
    actions = {1: 0, 2: 1, 3: 2}
    for v, target in actions.items():
        slice_idx = base_idx | (v << 14)         # port1=v, ports2-4=0
        rule[slice_idx] = target
    # verify on random hex boards
    S = 24; rng2 = np.random.default_rng(7); ok = True
    for trial in range(6):
        b = rng2.integers(0, 4, (S, S)).astype(np.uint8)
        # ports off -> must equal base 7->1
        off = hex_step_cell11(b, [0, 0, 0, 0], rule)
        ref = caca.hex_step(b[None], base7[None], caca._even_mask(S))[0]
        if not np.array_equal(off, ref): ok = False
        # port1=v everywhere -> must be the commanded constant
        for v, target in actions.items():
            cmd = hex_step_cell11(b, [np.full((S, S), v, np.uint8), 0, 0, 0], rule)
            if not np.all(cmd == target): ok = False
    print(f"conditional MUX: ports-off=base AND each command executes exactly -> {ok}")
    print("  (a plain 7->1 cannot condition on a command at all; cell-11's ports are")
    print("   extra address lines -> independent behaviour slices, base preserved.)")
    return ok

def reservoir_ab(nbytes=12000):
    """(b) quick reservoir A/B: 4 additive ports vs base 7->1, news fresh region."""
    rng = np.random.default_rng(1)
    pool7, _ = caca.load_pool(64, seed=1)
    ids = rng.choice(len(pool7), 3, replace=False)
    data = open("demo-run/eval.txt", "rb").read(400000 + nbytes)[400000:]
    S, ticks, rcells = 16, 2, 64
    em = caca._even_mask(S); cells = S * S
    rng2 = np.random.default_rng(2)
    drive = rng2.permutation(cells)[:48].reshape(4, 12)
    rsel = np.array([rng2.permutation(cells)[:rcells] for _ in range(3)])

    def run(use_ports, w=1):
        boards = np.zeros((3, S, S), np.uint8)
        rules = pool7[np.array(ids)]
        F = np.zeros((len(data), 3 * rcells * 4), np.float32)
        for t in range(len(data)):
            byte = data[t]; flat = boards.reshape(3, cells)
            for k in range(4): flat[0, drive[k]] = (byte >> (2 * k)) & 3
            for _ in range(ticks):
                prev = boards.copy(); nb = np.empty_like(boards)
                for i in range(3):
                    key = cell10._hex_neigh(prev[i].astype(np.int64))
                    out = rules[i][key].astype(np.int64)
                    if use_ports:                 # 4 ports: other boards + self + input
                        ps = (prev[(i + 1) % 3] + prev[(i + 2) % 3] + prev[i]
                              + np.full((S, S), byte & 3, np.int64))
                        out = (out + w * ps) & 3
                    nb[i] = (out & 3).astype(np.uint8)
                boards = nb
            fl = boards.reshape(3, cells); feats = np.zeros((3, rcells, 4), np.float32)
            for i in range(3): feats[i, np.arange(rcells), fl[i, rsel[i]]] = 1.0
            F[t] = feats.reshape(-1)
        return F
    s, e = 150, len(data) - 1
    base = caca.evaluate(run(False)[s:e], data, s, e, ctx=4, full=False)
    c11 = caca.evaluate(run(True)[s:e], data, s, e, ctx=4, full=False)
    print(f"reservoir A/B (fresh, ridge acc):  base 7->1 both={base['both_acc']:.3f}  "
          f"cell-11 (4 ports) both={c11['both_acc']:.3f}  ctx={base['ctx_acc']:.3f}")
    print(f"  -> {'4 ports help' if c11['both_acc']>base['both_acc']+0.01 else 'no gain (as expected, cf. cell10)'}")

if __name__ == "__main__":
    print("=== (substrate) ==="); selftest()
    print("\n=== (a) conditional multiplexer ==="); conditional_demo()
    print("\n=== (b) reservoir A/B ==="); reservoir_ab()
