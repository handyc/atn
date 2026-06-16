#!/usr/bin/env python3
# cacpu.py — CA-1: a small accumulator machine whose DATAPATH is genuine cellular automata.
# Putting the proven primitives together into one system that runs a real program:
#   * STORAGE  — 16 bytes of RAM + an accumulator, every bit a real mutual-annihilation
#                latch (the verified flip-flop genome). Not toy: full write/read roundtrip
#                over all 128 RAM bits is checked.
#   * ALU      — add/sub/and/or/xor/zero-test, every bit computed by the verified CA NAND
#                gate (gatecell) composed into a ripple-carry adder. Real computation.
#   * CONTROL  — program counter, instruction decode, fetch-decode-execute loop: orchestrated
#                by the controller (HONEST: like a real CPU's clock + microcode ROM; the
#                latch "holds without decay" was separately verified over 600 steps, so idle
#                holding is not re-simulated every tick). Branches ARE decided by the CA
#                (the zero flag is a CA NOR-tree over the accumulator bits).
# We then run a program (multiply by repeated addition: a loop + a CA-decided conditional
# branch) and verify the machine's output equals the reference. rulehub + numpy only.
import glob, json
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

def best_genome():
    R = [json.load(open(f)) for f in glob.glob("alice/flipflopga-v1/outputs/result_*.json")]
    R.sort(key=lambda r: -r["fitness"]); return R[0]["genome"]

G = best_genome(); LO = newton_lut(*G["A"]); LZ = newton_lut(*G["B"])

def stepf(b, lut, W, H): return lut[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)

# ============================ STORAGE: a CA-latch register ===============================
C, GAP, H, PS, HOLD = 40, 10, 40, 24, 12
class Reg:
    """n bits, each a mutual-annihilation latch cell on a shared board (verified mechanism)."""
    def __init__(self, n, seed=0):
        self.n = n; self.W = n * (C + GAP); self.rng = np.random.default_rng(seed)
        self.A = np.zeros((H, self.W), np.uint8); self.B = np.zeros((H, self.W), np.uint8)
    def _settle(self):
        for _ in range(HOLD):
            self.A = stepf(self.A, LO, self.W, H); self.B = stepf(self.B, LZ, self.W, H)
            both = (self.A > 0) & (self.B > 0); self.A[both] = 0; self.B[both] = 0
    def write(self, bits):
        self.A[:] = 0; self.B[:] = 0; cy = H // 2
        for i in range(self.n):
            cx = i * (C + GAP) + GAP + C // 2; tgt = self.A if bits[i] else self.B
            tgt[cy-PS//2:cy-PS//2+PS, cx-PS//2:cx-PS//2+PS] = self.rng.integers(1, 4, (PS, PS))
        self._settle()
    def read(self):
        out = []
        for i in range(self.n):
            x0 = i * (C + GAP); reg = slice(x0, x0 + C + GAP)
            out.append(1 if int((self.A[:, reg] > 0).sum()) > int((self.B[:, reg] > 0).sum()) else 0)
        return out

# ============================ ALU: the verified CA NAND gate =============================
S, BIAS, INSZ, GHOLD = 60, 18, 14, 60
_grng = np.random.default_rng(0)
def ca_nand(a, b):
    O = np.zeros((S, S), np.uint8); Z = np.zeros((S, S), np.uint8)
    def patch(arr, r, c, sz): arr[r-sz//2:r-sz//2+sz, c-sz//2:c-sz//2+sz] = _grng.integers(1, 4, (sz, sz))
    patch(O, S//2, S//2, BIAS)
    if a: patch(Z, S//2 - 12, S//2, INSZ)
    if b: patch(Z, S//2 + 12, S//2, INSZ)
    for _ in range(GHOLD):
        O = stepf(O, LO, S, S); Z = stepf(Z, LZ, S, S)
        both = (O > 0) & (Z > 0); O[both] = 0; Z[both] = 0
    return 1 if int((O > 0).sum()) > int((Z > 0).sum()) else 0
def NOT(a): return ca_nand(a, a)
def AND(a, b): return NOT(ca_nand(a, b))
def OR(a, b): return ca_nand(NOT(a), NOT(b))
def XOR(a, b):
    n = ca_nand(a, b); return ca_nand(ca_nand(a, n), ca_nand(b, n))
def full_adder(a, b, cin):
    axb = XOR(a, b); s = XOR(axb, cin); cout = OR(AND(a, b), AND(cin, axb)); return s, cout
W = 8                                              # 8-bit words
def add8(x, y, cin=0):
    out = []; c = cin
    for i in range(W): s, c = full_adder(x[i], y[i], c); out.append(s)
    return out, c
def sub8(x, y):                                    # x - y  via two's complement (all CA)
    yinv = [NOT(b) for b in y]; res, _ = add8(x, yinv, 1); return res
def is_zero(x):                                    # CA zero flag: NOT(OR of all bits)
    acc = x[0]
    for i in range(1, W): acc = OR(acc, x[i])
    return NOT(acc)

# ============================ helpers ====================================================
def bits(v): return [(v >> i) & 1 for i in range(W)]      # LSB-first
def val(bs): return sum((b & 1) << i for i, b in enumerate(bs)) & 0xFF

# ============================ CA-1 machine ===============================================
# ISA (addr/imm are operands): LOADI imm | LOAD a | STORE a | ADD a | SUB a | AND a |
#                              JMP a | JZ a | OUT | HALT
class CA1:
    def __init__(self, nram=16):
        self.RAM = [Reg(W, seed=100 + i) for i in range(nram)]   # genuine CA-latch RAM
        self.ACC = Reg(W, seed=7)                                 # genuine CA-latch accumulator
        self.PC = 0; self.out = []; self.steps = 0
    def load_data(self, addr, v): self.RAM[addr].write(bits(v))
    def run(self, prog, trace=False, maxsteps=2000):
        while self.PC < len(prog) and self.steps < maxsteps:
            op, arg = prog[self.PC]; self.steps += 1; pc0 = self.PC; self.PC += 1
            if op == "LOADI": self.ACC.write(bits(arg))
            elif op == "LOAD": self.ACC.write(self.RAM[arg].read())
            elif op == "STORE": self.RAM[arg].write(self.ACC.read())
            elif op == "ADD":
                r, _ = add8(self.ACC.read(), self.RAM[arg].read()); self.ACC.write(r)
            elif op == "SUB": self.ACC.write(sub8(self.ACC.read(), self.RAM[arg].read()))
            elif op == "AND":
                a = self.ACC.read(); b = self.RAM[arg].read(); self.ACC.write([AND(a[i], b[i]) for i in range(W)])
            elif op == "JMP": self.PC = arg
            elif op == "JZ":
                if is_zero(self.ACC.read()): self.PC = arg          # branch DECIDED by CA
            elif op == "OUT": self.out.append(val(self.ACC.read()))
            elif op == "HALT": break
            if trace:
                print(f"   pc {pc0:2d}: {op:5s} {arg if arg is not None else '':<3}  ACC={val(self.ACC.read()):3d}  PC->{self.PC}")

def verify_alu(n=10):
    rng = np.random.default_rng(3); ok_add = ok_sub = 0
    for _ in range(n):
        x = int(rng.integers(0, 256)); y = int(rng.integers(0, 256))
        r, c = add8(bits(x), bits(y)); got = val(r) | (c << 8)
        ok_add += (got == (x + y))
        rs = val(sub8(bits(x), bits(y))); ok_sub += (rs == ((x - y) & 0xFF))
    z = all(is_zero(bits(0))[k] if False else True for k in [0]) and is_zero(bits(0)) == 1 and is_zero(bits(5)) == 0
    return ok_add, ok_sub, n, z

def main():
    print(f"CA-1: an accumulator machine on the CA latch+gate datapath (genome {[round(v,3) for v in G['A']]})\n")

    print("[1] STORAGE — RAM write/read roundtrip over all 16 bytes (real CA latches):")
    m = CA1(16); rng = np.random.default_rng(11); data = [int(rng.integers(0, 256)) for _ in range(16)]
    for a, v in enumerate(data): m.load_data(a, v)
    back = [val(m.RAM[a].read()) for a in range(16)]
    nok = sum(b == d for b, d in zip(back, data))
    print(f"    wrote {data}")
    print(f"    read  {back}")
    print(f"    => {nok}/16 bytes ({128} latch bits) round-trip exact: {'PASS' if nok==16 else 'FAIL'}\n")

    print("[2] ALU — add/sub/zero on random 8-bit operands (every bit via CA NAND):")
    oa, os_, n, zok = verify_alu(10)
    print(f"    add8 {oa}/{n} correct · sub8 {os_}/{n} correct · zero-flag {'ok' if zok else 'BAD'}\n")

    # [3] PROGRAM: result = M1 * M2 by repeated addition (loop + CA-decided branch)
    M1, M2 = 7, 6
    # RAM: [0]=result(0) [1]=M1 [2]=counter(M2) [3]=one(1)
    prog = [
        ("LOAD", 0), ("ADD", 1), ("STORE", 0),     # result += M1
        ("LOAD", 2), ("SUB", 3), ("STORE", 2),     # counter -= 1
        ("JZ", 9), ("JMP", 0),                      # if counter==0 -> done else loop
        ("HALT", None),                             # (index 8) unreachable filler
        ("LOAD", 0), ("OUT", None), ("HALT", None), # index 9: output result
    ]
    print(f"[3] PROGRAM — compute {M1} * {M2} by repeated addition (a real loop, branch decided by the CA):")
    print(f"    {len(prog)} instructions; RAM[0]=0 RAM[1]={M1} RAM[2]={M2} RAM[3]=1")
    m2 = CA1(16)
    for a, v in [(0, 0), (1, M1), (2, M2), (3, 1)]: m2.load_data(a, v)
    m2.run(prog, trace=False)
    got = m2.out[0] if m2.out else None
    print(f"    machine OUT = {got}   reference {M1}*{M2} = {M1*M2}   instructions executed: {m2.steps}")
    print(f"    => program result {'CORRECT' if got == M1*M2 else 'WRONG'}\n")

    ok = (nok == 16 and oa == n and os_ == n and zok and got == M1*M2)
    print("  ==> CA-1 ran a real program on a genuine CA datapath:" if ok else "  ==> something failed:")
    print("      16 bytes of latch RAM (verified roundtrip), a CA-NAND ALU (add/sub/logic/zero),")
    print("      and a fetch-decode-execute loop with a CA-decided conditional branch.")
    print("      HONEST scope: the storage cells and every arithmetic bit are real CA; the program")
    print("      counter / instruction decode / clock are controller-orchestrated (as in any CPU's")
    print("      control unit). Next rung: place RAM+ALU as autonomous walled regions (autowire2).")

if __name__ == "__main__":
    main()
