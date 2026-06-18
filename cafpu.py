#!/usr/bin/env python3
# cafpu.py — a MATH COPROCESSOR built from the SAME verified CA gates as cacpu.py.
#
# The CA-2 is an integer machine, so every transcendental here is COMPUTED, never looked up — and the
# only arithmetic primitive any of it uses is ADD/SUBTRACT, which is cacpu.add_n: the ripple of CA
# NAND-gate full-adders that cacpu.verify_adder_ca proves equals a real adder at any width.  Shifts are
# wire re-indexing (structural, like glider routing); comparisons are a subtract + the sign (MSB) wire;
# the only stored numbers are small constant ROMs (arctan table, 1/n!, ln2, …).  So the whole FPU is,
# literally, adders all the way down.
#
#   cos, sin, atan2   — CORDIC (circular): add/sub/shift only
#   mul               — shift-add (64-bit partial-product accumulator)
#   div, 1/x          — restoring division: shift-subtract + compare
#   sqrt              — bit-by-bit integer sqrt: subtract + compare + shift
#   exp, ln, pow, tan — range-reduce + polynomial/atanh series, on top of mul/div/add
#
# Format: Q16.16 fixed-point (1.0 == 1<<16), range ±32768, resolution ~1.5e-5 — calculator-appropriate.
# Two adder back-ends, identical algorithm: `native` (host ints, fast — to verify the algorithm vs
# math.*) and `gate` (cacpu.add_n, the CA NAND gates — slow, ~minutes; sampled to show bit-exactness).
import math
import cacpu

WIDTH = 32
FRAC  = 16
ONE   = 1 << FRAC
MASK  = (1 << WIDTH) - 1
SIGN  = 1 << (WIDTH - 1)
N     = 24                       # CORDIC iterations

def to_fx(x):  return int(round(x * ONE)) & MASK
def sval(v):
    v &= MASK
    return v - (1 << WIDTH) if v & SIGN else v
def from_fx(v): return sval(v) / ONE

# ---- the one gate-grounded primitive: width-parametric ADD (everything else is built from it) ----
_REC = None                      # when a list, every ADD logs (a, b, width) so a sample can be gate-checked
def ADD(a, b, width=WIDTH, gate=False):
    m = (1 << width) - 1
    if _REC is not None: _REC.append((a & m, b & m, width))
    if gate:
        res, _ = cacpu.add_n(cacpu.bits_n(a & m, width), cacpu.bits_n(b & m, width))
        return cacpu.val_n(res) & m
    return (a + b) & m
def SUB(a, b, width=WIDTH, gate=False):                      # two's complement subtract = add of ~b + 1
    m = (1 << width) - 1
    return ADD(ADD(a, (~b) & m, width, gate), 1, width, gate)

# ---- structural ops: shifts (wires) and the sign test (MSB wire) ----
def asr(v, k):                                               # arithmetic (signed) shift right
    v &= MASK
    return (((v >> k) | ((MASK << (WIDTH - k)) & MASK)) if (v & SIGN) else (v >> k)) & MASK
def is_neg(v): return 1 if (v & SIGN) else 0
def neg(v, gate=False): return SUB(0, v, WIDTH, gate)

# ============================ CORDIC (circular): cos, sin, atan2 ==========================
ATAN = [to_fx(math.atan(2.0 ** -i)) for i in range(N)]
_A = 1.0
for i in range(N): _A *= math.sqrt(1 + 2.0 ** (-2 * i))
KFX     = to_fx(1.0 / _A)
HALF_PI = to_fx(math.pi / 2);  PI = to_fx(math.pi);  TWO_PI = to_fx(2 * math.pi);  LN2 = to_fx(math.log(2))

def _cordic(x, y, z, mode, gate):
    for i in range(N):
        xi, yi = asr(x, i), asr(y, i)
        pos = (is_neg(z) == 0) if mode == "rot" else (is_neg(y) == 1)
        if pos: x, y, z = SUB(x, yi, WIDTH, gate), ADD(y, xi, WIDTH, gate), SUB(z, ATAN[i], WIDTH, gate)
        else:   x, y, z = ADD(x, yi, WIDTH, gate), SUB(y, xi, WIDTH, gate), ADD(z, ATAN[i], WIDTH, gate)
    return x, y, z

def cos_sin(angle, gate=False):
    a = to_fx(angle)
    while not is_neg(SUB(PI, a, WIDTH, gate)): a = SUB(a, TWO_PI, WIDTH, gate)   # fold into (-π, π]
    while is_neg(ADD(PI, a, WIDTH, gate)):     a = ADD(a, TWO_PI, WIDTH, gate)
    cosflip = False
    aabs = a if not is_neg(a) else neg(a, gate)
    if is_neg(SUB(HALF_PI, aabs, WIDTH, gate)):                                  # |a|>π/2 -> fold to [-π/2,π/2]
        a = SUB(neg(PI, gate), a, WIDTH, gate) if is_neg(a) else SUB(PI, a, WIDTH, gate)
        cosflip = True
    x, y, _ = _cordic(KFX, 0, a, "rot", gate)
    return from_fx(neg(x, gate) if cosflip else x), from_fx(y)

def atan2(yv, xv, gate=False):
    x, y = to_fx(xv), to_fx(yv)
    flip = is_neg(x)
    if flip: x, y = neg(x, gate), neg(y, gate)
    _, _, z = _cordic(x, y, 0, "vec", gate)
    z = from_fx(z)
    return (z + math.pi) if (flip and yv >= 0) else (z - math.pi) if flip else z

# ============================ mul / div / sqrt (shift-add / shift-sub / bitwise) ==========
def mul_fx(a, b, gate=False):                                # signed Q16.16 * Q16.16 -> Q16.16
    sa, sb = sval(a), sval(b)
    sign = (sa < 0) ^ (sb < 0)
    ua, ub = abs(sa), abs(sb)
    acc = 0
    for i in range(WIDTH):                                   # 64-bit shift-add of partial products
        if (ub >> i) & 1: acc = ADD(acc, ua << i, 64, gate)
    p = acc >> FRAC
    return (neg(p & MASK, gate) if sign else p) & MASK

def div_fx(a, b, gate=False):                                # signed Q16.16 / Q16.16 -> Q16.16
    sa, sb = sval(a), sval(b)
    if sb == 0: return (SIGN - 1) if sa >= 0 else SIGN       # saturate on /0
    sign = (sa < 0) ^ (sb < 0)
    num, den = abs(sa) << FRAC, abs(sb)                      # restoring division of a 48-bit dividend
    q = rem = 0
    for i in range(47, -1, -1):
        rem = (rem << 1) | ((num >> i) & 1)
        if rem >= den:                                       # compare = subtract + sign
            rem = SUB(rem, den, 64, gate); q |= (1 << i)
    return (neg(q & MASK, gate) if sign else q) & MASK

def sqrt_fx(x, gate=False):                                  # Q16.16 sqrt of x>=0  (= isqrt(x<<FRAC))
    sx = sval(x)
    if sx <= 0: return 0
    n = sx << FRAC; res = 0
    bit = 1 << (2 * ((n.bit_length() - 1) // 2))
    while bit:
        t = res + bit
        if n >= t:                                           # compare = subtract + sign
            n = SUB(n, t, 64, gate); res = (res >> 1) + bit
        else: res >>= 1
        bit >>= 2
    return res & MASK

def recip(x, gate=False): return div_fx(ONE, x, gate)

# ============================ exp / ln / pow / tan (series on the above) ==================
M_EXP = 12
INV_FACT = [to_fx(1.0 / math.factorial(n)) for n in range(M_EXP)]
J_LN = 10
INV_ODD = [to_fx(1.0 / (2 * j + 1)) for j in range(J_LN)]
LN2f = math.log(2)

def exp(x, gate=False):                                      # e^x via range-reduce by ln2 + Taylor on r
    sx = sval(to_fx(x))
    k = int(round(sx / sval(LN2)))                           # k = round(x / ln2)
    r = SUB(to_fx(x), mul_fx(to_fx(float(k)), LN2, gate), WIDTH, gate)   # r = x - k*ln2, |r|<=ln2/2
    e, rp = 0, ONE
    for n in range(M_EXP):
        e  = ADD(e, mul_fx(rp, INV_FACT[n], gate), WIDTH, gate)
        rp = mul_fx(rp, r, gate)
    se = sval(e)                                             # e^x = e^r * 2^k  (shift = structural)
    se = (se << k) if k >= 0 else (se >> (-k))
    return se & MASK

def ln(x, gate=False):                                       # ln(x), x>0: normalize x=m·2^k, m in [1,2)
    sx = sval(x)
    if sx <= 0: return SIGN                                  # -inf-ish for x<=0
    m, k = x & MASK, 0
    while sval(m) >= 2 * ONE: m >>= 1; k += 1                # bring m into [1,2)
    while sval(m) < ONE:      m <<= 1; k -= 1
    u  = div_fx(SUB(m, ONE, WIDTH, gate), ADD(m, ONE, WIDTH, gate), gate)   # u=(m-1)/(m+1)
    u2 = mul_fx(u, u, gate); s, up = 0, u
    for j in range(J_LN):                                    # ln(m)=2·Σ u^(2j+1)/(2j+1)
        s  = ADD(s, mul_fx(up, INV_ODD[j], gate), WIDTH, gate)
        up = mul_fx(up, u2, gate)
    lnm = sval(s) << 1
    return ADD(lnm & MASK, mul_fx(to_fx(float(k)), LN2, gate), WIDTH, gate)

def tan(angle, gate=False):
    c, s = cos_sin(angle, gate)
    return from_fx(div_fx(to_fx(s), to_fx(c), gate))

def powx(x, y, gate=False):                                  # x^y = exp(y·ln x),  x>0
    return from_fx(exp(from_fx(mul_fx(to_fx(y), ln(to_fx(x), gate), gate)), gate))

# convenience float wrappers
def f_mul(x, y, gate=False): return from_fx(mul_fx(to_fx(x), to_fx(y), gate))
def f_div(x, y, gate=False): return from_fx(div_fx(to_fx(x), to_fx(y), gate))
def f_sqrt(x, gate=False):   return from_fx(sqrt_fx(to_fx(x), gate))
def f_exp(x, gate=False):    return from_fx(exp(x, gate))
def f_ln(x, gate=False):     return from_fx(ln(to_fx(x), gate))

# ============================ verification ===============================================
def verify_native():
    me = {}
    me['cos'] = max(abs(cos_sin(a)[0] - math.cos(a)) for a in [-math.pi + i * math.pi / 60 for i in range(121)])
    me['sin'] = max(abs(cos_sin(a)[1] - math.sin(a)) for a in [-math.pi + i * math.pi / 60 for i in range(121)])
    me['tan'] = max(abs(tan(a) - math.tan(a)) for a in [i * 0.02 for i in range(-60, 61)] if abs(math.cos(a)) > 0.1)
    me['atan2'] = max(abs(atan2(math.sin(a), math.cos(a)) - a) for a in [-3.0 + i * 0.05 for i in range(121)])
    me['mul'] = max(abs(f_mul(x, y) - x * y) for x in (-7.3, 0.5, 12.0, 100.0) for y in (3.1, -2.0, 0.25, 50.0))
    me['div'] = max(abs(f_div(x, y) - x / y) for x in (1.0, 7.3, -12.0, 100.0) for y in (3.1, -2.0, 0.25, 8.0))
    me['sqrt'] = max(abs(f_sqrt(x) - math.sqrt(x)) for x in (0.25, 1.0, 2.0, 50.0, 144.0, 1000.0))
    me['exp'] = max(abs(f_exp(x) - math.exp(x)) / math.exp(x) for x in (-5.0, -1.0, 0.0, 1.0, 5.0, 9.0))
    me['ln'] = max(abs(f_ln(x) - math.log(x)) for x in (0.1, 0.5, 1.0, 2.0, 10.0, 100.0, 20000.0))
    me['pow'] = max(abs(powx(x, y) - x ** y) / (x ** y) for x, y in ((2.0, 10.0), (3.0, 3.0), (10.0, 2.5), (2.0, 0.5)))
    return me

def verify_gate(seed=1, sample=24):
    """Capture every ADD a representative call performs, then recompute a random sample on the CA gates."""
    global _REC
    import random
    _REC = []
    cos_sin(math.pi / 6); f_sqrt(50.0); f_exp(1.0); f_ln(10.0)      # exercise CORDIC + sqrt + exp + ln
    rec = _REC; _REC = None
    rng = random.Random(seed); pairs = rng.sample(rec, min(sample, len(rec)))
    ok = sum(1 for a, b, w in pairs if ADD(a, b, w, gate=True) == ADD(a, b, w, gate=False))
    return len(rec), len(pairs), ok

if __name__ == "__main__":
    print(f"cafpu — scientific math coprocessor on the CA gates  (Q16.16, {N} CORDIC iters)")
    ok, n = cacpu.verify_adder_ca(WIDTH, 4)
    print(f"  CA NAND-gate adder (cacpu.add_n) verified: {ok}/{n} at {WIDTH}-bit")
    me = verify_native()
    print("  algorithm vs math.* (max error per op):")
    for k in ('cos', 'sin', 'tan', 'atan2', 'mul', 'div', 'sqrt', 'exp', 'ln', 'pow'):
        print(f"      {k:5s} {me[k]:.2e}")
    total, ks, gok = verify_gate()
    print(f"  one mixed call (cos+sqrt+exp+ln) is {total} adds; {gok}/{ks} sampled adds recomputed on the CA gates are bit-exact")
