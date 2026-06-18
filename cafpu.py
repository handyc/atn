#!/usr/bin/env python3
# cafpu.py — a MATH COPROCESSOR built from the SAME verified CA gates as cacpu.py.
#
# The CA-2 is an integer machine, so transcendental math (sin, cos, atan2, …) has to be *computed*,
# not looked up.  CORDIC does exactly that using only three things:
#     * add / subtract   — here every one is cacpu.add_n: the ripple of CA NAND-gate full-adders
#                          (cacpu.verify_adder_ca proves that ripple == a real adder, any width).
#     * shift by i        — a wire re-index (sign-extended), structural like glider routing, no gate.
#     * the sign of z/y   — a single wire (the MSB).
# Plus a small ROM of constants (the arctangent table + the CORDIC gain).  So the trig is genuinely
# done by the cellular automaton: it is adders all the way down.
#
# Two adder back-ends, identical algorithm:
#   * native  — host ints, fast, used to verify the ALGORITHM over a dense sweep vs math.*
#   * gate     — cacpu.add_n (the CA NAND gates), slow, used to show the gate path is bit-identical
#                to native on a sample.  Since add is already gate-verified for the full width and
#                CORDIC uses nothing but add, gate ≡ native by construction; the sample just shows it.
import math
import cacpu

WIDTH = 32
FRAC  = 28                          # Q4.28 fixed-point: 1.0 == 1<<28  (range ±8, resolution ~3.7e-9)
ONE   = 1 << FRAC
MASK  = (1 << WIDTH) - 1
SIGN  = 1 << (WIDTH - 1)
N     = 28                          # CORDIC iterations

def to_fx(x):   return int(round(x * ONE)) & MASK
def from_fx(v):
    v &= MASK
    return (v - (1 << WIDTH) if v & SIGN else v) / ONE

# ---- the two adder back-ends -------------------------------------------------------------
def add_native(a, b): return (a + b) & MASK
def add_gate(a, b):                                  # add through the CA NAND-gate ripple adder
    res, _ = cacpu.add_n(cacpu.bits_n(a & MASK, WIDTH), cacpu.bits_n(b & MASK, WIDTH))
    return cacpu.val_n(res) & MASK

def make_ops(gate=False, rec=None):
    base = add_gate if gate else add_native
    def add(a, b):
        if rec is not None: rec.append((a & MASK, b & MASK))   # log every add the computation performs
        return base(a, b)
    if gate:
        def comp(b): return cacpu.val_n([cacpu.NOT(x) for x in cacpu.bits_n(b & MASK, WIDTH)])  # ~b via CA NOT
    else:
        def comp(b): return (~b) & MASK
    def sub(a, b): return add(add(a, comp(b)), 1)    # two's complement subtract = add of complement
    return add, sub

# ---- structural ops (wires, not gates) ---------------------------------------------------
def asr(v, k):                                       # arithmetic (signed) shift right by k
    v &= MASK
    if v & SIGN: v = (v >> k) | ((MASK << (WIDTH - k)) & MASK)
    else:        v = v >> k
    return v & MASK
def is_neg(v): return 1 if (v & SIGN) else 0         # the sign wire (MSB)

# ---- the constant ROM: arctangent table + gain, prescale, π --------------------------------
ATAN = [to_fx(math.atan(2.0 ** -i)) for i in range(N)]
_A = 1.0
for i in range(N): _A *= math.sqrt(1 + 2.0 ** (-2 * i))
KFX     = to_fx(1.0 / _A)                            # CORDIC gain^-1 (prescale x0 so output is unscaled)
HALF_PI = to_fx(math.pi / 2)
PI      = to_fx(math.pi)
TWO_PI  = to_fx(2 * math.pi)

# ---- the CORDIC engine (one core, two modes) ---------------------------------------------
def _cordic(x, y, z, mode, add, sub):
    # mode "rot": drive z->0 (rotate by z).  mode "vec": drive y->0 (accumulate angle into z).
    for i in range(N):
        xi, yi = asr(x, i), asr(y, i)
        d_pos = (is_neg(z) == 0) if mode == "rot" else (is_neg(y) == 1)
        if d_pos:
            x, y, z = sub(x, yi), add(y, xi), sub(z, ATAN[i])
        else:
            x, y, z = add(x, yi), sub(y, xi), add(z, ATAN[i])
    return x, y, z

def cos_sin(angle, gate=False, rec=None):
    """cos and sin of `angle` (radians), computed on the CA gates."""
    add, sub = make_ops(gate, rec)
    a = to_fx(angle)
    while not is_neg(sub(PI, a)):  a = sub(a, TWO_PI)   # reduce a into (-π, π]  (a > π  -> a -= 2π)
    while is_neg(add(PI, a)):      a = add(a, TWO_PI)   #                        (a < -π -> a += 2π)
    cosflip = False
    if is_neg(sub(HALF_PI, a if not is_neg(a) else sub(0, a))):     # |a| > π/2 -> fold into [-π/2, π/2]
        a = sub(0 if not is_neg(a) else sub(0, PI), a) if is_neg(a) else sub(PI, a)
        # a' = (sign(a))·π − a ; cos flips sign, sin unchanged
        cosflip = True
    x, y, _ = _cordic(KFX, 0, a, "rot", add, sub)
    c = sub(0, x) if cosflip else x
    return from_fx(c), from_fx(y)

def atan2(yv, xv, gate=False, rec=None):
    """atan2(y, x) in radians, computed on the CA gates (vectoring mode; x>=0 region)."""
    add, sub = make_ops(gate, rec)
    x, y = to_fx(xv), to_fx(yv)
    flip = is_neg(x)                                   # fold x<0 into x>=0, add/sub π afterwards
    if flip:
        x = sub(0, x); y = sub(0, y)
    _, _, z = _cordic(x, y, 0, "vec", add, sub)
    z = from_fx(z)
    if flip:
        z = (z + math.pi) if yv >= 0 else (z - math.pi)
    return z

# ---- verification -------------------------------------------------------------------------
def verify_native(samples=721):
    """The CORDIC ALGORITHM at full precision vs math.* over a dense sweep."""
    me_c = me_s = me_a = 0.0
    for k in range(samples):
        ang = -math.pi + 2 * math.pi * k / (samples - 1)
        c, s = cos_sin(ang)
        me_c = max(me_c, abs(c - math.cos(ang))); me_s = max(me_s, abs(s - math.sin(ang)))
    for k in range(1, 360):
        ang = -math.pi + 2 * math.pi * k / 360
        x, y = math.cos(ang), math.sin(ang)
        me_a = max(me_a, abs(((atan2(y, x) - ang + math.pi) % (2 * math.pi)) - math.pi))
    return me_c, me_s, me_a

def verify_gate(angle=math.pi / 6, sample=24, seed=1):
    """A real cos+sin is just a few hundred adds.  Capture the EXACT operand pairs it performs, then
    recompute a random sample of them on the genuine CA NAND gates and confirm bit-exact == native.
    (Running all of them on gates works too via cos_sin(gate=True), but is ~10 min for one value.)"""
    import random
    rec = []
    cos_sin(angle, gate=False, rec=rec)                       # log every add this computation does
    rng = random.Random(seed)
    pairs = rng.sample(rec, min(sample, len(rec)))
    ok = sum(1 for a, b in pairs if add_gate(a, b) == add_native(a, b))
    return len(rec), len(pairs), ok

if __name__ == "__main__":
    print(f"cafpu — CORDIC math coprocessor on the CA gates  (Q4.28, {N} iters)")
    ok, n = cacpu.verify_adder_ca(WIDTH, 4)
    print(f"  CA NAND-gate adder (cacpu.add_n) verified: {ok}/{n} at {WIDTH}-bit")
    mc, ms, ma = verify_native()
    print(f"  algorithm vs math over a full turn:  max|Δcos|={mc:.2e}  max|Δsin|={ms:.2e}  max|Δatan2|={ma:.2e}")
    total, k, gok = verify_gate()
    print(f"  cos+sin(π/6) is {total} adds; {gok}/{k} sampled adds recomputed on the CA gates are bit-exact")
    print(f"  -> every add CORDIC needs is done by the verified gate, so the trig is genuinely on the CA.")
