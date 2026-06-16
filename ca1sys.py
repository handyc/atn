#!/usr/bin/env python3
# ca1sys.py — CA-1 scaled into a real (tiny) COMPUTER: the same 8-bit accumulator datapath
# whose arithmetic is genuine CA (cacpu.py), now wrapped with the rest of a computer:
#   * a 64 KB address space of 8-bit words (data words are what the CA latches store),
#   * a memory-mapped FRAMEBUFFER (a screen) and an INPUT register (keys),
#   * an index register X for array/table addressing,
#   * a richer but minimal ISA + a small assembler (labels, two-pass).
# This is the FAST, BIT-FAITHFUL emulator of CA-1's instruction set: every ALU result is
# masked to 8 bits exactly as the CA ripple-adder/gates produce it, so "runs on this
# emulator" == "would run on the CA datapath, just ~1e8x faster". `verify_against_ca()`
# cross-checks the ALU ops against the real CA gates (cacpu) on random operands.
# HONEST: control (PC/decode/clock) and address arithmetic are orchestrated, as in CA-1 /
# any CPU control unit; the DATA + arithmetic are the CA's job.
import numpy as np

MASK = 0xFF
class CA1Sys:
    def __init__(self, fb_addr=0x8000, fb_w=0, fb_h=0, inp_addr=0xFF00):
        self.M = bytearray(0x10000)
        self.A = 0; self.X = 0; self.P = 0; self.PC = 0    # P = 16-bit address pointer (control-side)
        self.Z = 1; self.C = 0; self.N = 0
        self.fb_addr = fb_addr; self.fb_w = fb_w; self.fb_h = fb_h; self.inp_addr = inp_addr
        self.icount = 0; self.frames = []
    # ---- flag helper: mask to 8 bits exactly like the CA datapath, set Z/N (and C if given)
    def _set(self, v, carry=None):
        v8 = v & MASK; self.Z = int(v8 == 0); self.N = (v8 >> 7) & 1
        if carry is not None: self.C = carry & 1
        return v8
    def snap_frame(self):
        if self.fb_w and self.fb_h:
            self.frames.append(bytes(self.M[self.fb_addr:self.fb_addr + self.fb_w * self.fb_h]))

    def run(self, code, max_i=5_000_000, frame_on=None, set_input=None):
        prog, labels = code
        while self.PC < len(prog) and self.icount < max_i:
            op, arg = prog[self.PC]; self.PC += 1; self.icount += 1
            a = self.A
            if op == "LDI":   self.A = self._set(arg)
            elif op == "LDA": self.A = self._set(self.M[arg])
            elif op == "STA": self.M[arg & 0xFFFF] = a
            elif op == "LDAX":self.A = self._set(self.M[(arg + self.X) & 0xFFFF])     # M[arg+X]
            elif op == "STAX":self.M[(arg + self.X) & 0xFFFF] = a                     # M[arg+X]=A
            elif op == "LDX": self.X = self._set(self.M[arg])
            elif op == "LXI": self.X = self._set(arg)
            elif op == "TAX": self.X = self._set(a)
            elif op == "TXA": self.A = self._set(self.X)
            elif op == "INX": self.X = self._set(self.X + 1)
            elif op == "DEX": self.X = self._set(self.X - 1)
            elif op == "ADD": self.A = self._set(a + self.M[arg], carry=(a + self.M[arg]) > MASK)
            elif op == "ADDI":self.A = self._set(a + arg, carry=(a + arg) > MASK)
            elif op == "SUB": self.A = self._set(a - self.M[arg], carry=int(a >= self.M[arg]))
            elif op == "SUBI":self.A = self._set(a - arg, carry=int(a >= arg))
            elif op == "AND": self.A = self._set(a & self.M[arg])
            elif op == "ANDI":self.A = self._set(a & arg)
            elif op == "OR":  self.A = self._set(a | self.M[arg])
            elif op == "XOR": self.A = self._set(a ^ self.M[arg])
            elif op == "INC": self.A = self._set(a + 1)
            elif op == "DEC": self.A = self._set(a - 1)
            elif op == "SHL": self.A = self._set(a << 1, carry=(a >> 7) & 1)
            elif op == "SHR": self.A = self._set(a >> 1, carry=a & 1)
            elif op == "CMP": d = (a - self.M[arg]); self._set(d, carry=int(a >= self.M[arg]))   # flags only
            elif op == "CMPI":d = (a - arg); self._set(d, carry=int(a >= arg))
            elif op == "JMP": self.PC = arg
            elif op == "JZ":  self.PC = arg if self.Z else self.PC
            elif op == "JNZ": self.PC = arg if not self.Z else self.PC
            elif op == "JC":  self.PC = arg if self.C else self.PC       # a >= operand (unsigned)
            elif op == "JNC": self.PC = arg if not self.C else self.PC   # a <  operand
            elif op == "JN":  self.PC = arg if self.N else self.PC
            elif op == "LDP":  self.P = arg & 0xFFFF                       # 16-bit fb/array pointer
            elif op == "ADDP": self.P = (self.P + arg) & 0xFFFF
            elif op == "STPX": self.M[(self.P + self.X) & 0xFFFF] = a      # M[P+X] = A
            elif op == "LDPX": self.A = self._set(self.M[(self.P + self.X) & 0xFFFF])
            elif op == "IN":  self.A = self._set(self.M[self.inp_addr])
            elif op == "FRAME":
                if set_input is not None: self.M[self.inp_addr] = set_input(self) & MASK
                self.snap_frame()
                if frame_on is not None and frame_on(self): break
            elif op == "NOP": pass
            elif op == "HLT": break
            else: raise ValueError(f"bad op {op} @ {self.PC-1}")
        return self

# ----------------------------- tiny two-pass assembler -----------------------------------
def asm(lines):
    """lines: list of ('label',) | (op,) | (op, arg) ; arg may be an int or a label string.
    Returns (prog, labels) with label args resolved to instruction indices."""
    prog = []; labels = {}
    for ln in lines:
        if len(ln) == 1 and isinstance(ln[0], str) and ln[0].endswith(":"):
            labels[ln[0][:-1]] = len(prog)
        else:
            op = ln[0]; arg = ln[1] if len(ln) > 1 else None; prog.append([op, arg])
    for ins in prog:
        if isinstance(ins[1], str): ins[1] = labels[ins[1]]
    return [tuple(p) for p in prog], labels

# ----------------------------- CA cross-verification -------------------------------------
def verify_against_ca(n=8, seed=1):
    """Confirm the fast emulator's 8-bit ALU == the genuine CA datapath (cacpu) on randoms."""
    import cacpu as cpu
    rng = np.random.default_rng(seed); ok = {"ADD": 0, "SUB": 0, "AND": 0, "OR": 0, "XOR": 0}
    for _ in range(n):
        x = int(rng.integers(0, 256)); y = int(rng.integers(0, 256))
        r, c = cpu.add8(cpu.bits(x), cpu.bits(y)); ca_add = cpu.val(r)
        ok["ADD"] += (ca_add == ((x + y) & MASK))
        ok["SUB"] += (cpu.val(cpu.sub8(cpu.bits(x), cpu.bits(y))) == ((x - y) & MASK))
        ok["AND"] += (cpu.val([cpu.AND(cpu.bits(x)[i], cpu.bits(y)[i]) for i in range(8)]) == (x & y))
        ok["OR"]  += (cpu.val([cpu.OR(cpu.bits(x)[i], cpu.bits(y)[i]) for i in range(8)]) == (x | y))
        ok["XOR"] += (cpu.val([cpu.XOR(cpu.bits(x)[i], cpu.bits(y)[i]) for i in range(8)]) == (x ^ y))
    return ok, n

if __name__ == "__main__":
    # smoke test: sum 1..10 on the emulator
    prog = asm([
        ("LDI", 0), ("STA", 0x10),         # sum=0
        ("LDI", 10), ("STA", 0x11),        # i=10
        ("loop:",),
        ("LDA", 0x10), ("ADD", 0x11), ("STA", 0x10),    # sum+=i
        ("LDA", 0x11), ("SUBI", 1), ("STA", 0x11),      # i--
        ("JNZ", "loop"),
        ("LDA", 0x10), ("HLT",),
    ])
    m = CA1Sys().run(prog)
    print("ca1sys smoke: sum 1..10 =", m.A, "(expect 55), instructions:", m.icount)
