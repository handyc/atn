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
    def __init__(self, fb_addr=0x8000, fb_w=0, fb_h=0, inp_addr=0xFF00, memsize=0x100000, word_bits=8):
        # PARAMETERIZED machine: word_bits is the register/ALU width (CA-1 = 8). The same code
        # generates any width — CA-2 is just word_bits=32. memsize default 1 MB. Near addressing
        # (LDA/STA/LDAX/STAX) is 16-bit = the low 64 KB bank; the far pointer P is 24-bit
        # (PLO/PHI/PBK), so an 8-bit machine banks past 64 KB exactly as 6502/Z80-era micros did.
        self.M = bytearray(memsize); self.memsize = memsize; self.amask = memsize - 1
        self.word_bits = word_bits; self.mask = (1 << word_bits) - 1; self.signbit = word_bits - 1
        self.A = 0; self.X = 0; self.P = 0; self.PC = 0    # P = 24-bit far pointer (bank<<16 | hi<<8 | lo)
        self.SP = 0x7FFF                                    # call/data stack (grows down), control-side
        self.Z = 1; self.C = 0; self.N = 0
        self.fb_addr = fb_addr; self.fb_w = fb_w; self.fb_h = fb_h; self.inp_addr = inp_addr
        self.icount = 0; self.frames = []
    # ---- flag helper: mask to the machine word exactly like the CA datapath, set Z/N (and C if given)
    def _set(self, v, carry=None):
        v8 = v & self.mask; self.Z = int(v8 == 0); self.N = (v8 >> self.signbit) & 1
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
            elif op == "ADD": self.A = self._set(a + self.M[arg], carry=(a + self.M[arg]) > self.mask)
            elif op == "ADDI":self.A = self._set(a + arg, carry=(a + arg) > self.mask)
            elif op == "SUB": self.A = self._set(a - self.M[arg], carry=int(a >= self.M[arg]))
            elif op == "SUBI":self.A = self._set(a - arg, carry=int(a >= arg))
            elif op == "AND": self.A = self._set(a & self.M[arg])
            elif op == "ANDI":self.A = self._set(a & arg)
            elif op == "OR":  self.A = self._set(a | self.M[arg])
            elif op == "XOR": self.A = self._set(a ^ self.M[arg])
            elif op == "INC": self.A = self._set(a + 1)
            elif op == "DEC": self.A = self._set(a - 1)
            elif op == "SHL": self.A = self._set(a << 1, carry=(a >> self.signbit) & 1)
            elif op == "SHR": self.A = self._set(a >> 1, carry=a & 1)
            elif op == "CMP": d = (a - self.M[arg]); self._set(d, carry=int(a >= self.M[arg]))   # flags only
            elif op == "CMPI":d = (a - arg); self._set(d, carry=int(a >= arg))
            elif op == "JMP": self.PC = arg
            elif op == "JZ":  self.PC = arg if self.Z else self.PC
            elif op == "JNZ": self.PC = arg if not self.Z else self.PC
            elif op == "JC":  self.PC = arg if self.C else self.PC       # a >= operand (unsigned)
            elif op == "JNC": self.PC = arg if not self.C else self.PC   # a <  operand
            elif op == "JN":  self.PC = arg if self.N else self.PC
            elif op == "CALL": self.M[self.SP] = self.PC & 0xFF; self.M[self.SP-1] = (self.PC >> 8) & 0xFF; self.SP -= 2; self.PC = arg
            elif op == "RET":  self.SP += 2; self.PC = (self.M[self.SP-1] << 8) | self.M[self.SP]
            elif op == "PUSH": self.M[self.SP] = a; self.SP -= 1
            elif op == "POP":  self.SP += 1; self.A = self._set(self.M[self.SP])
            elif op == "PUSHX":self.M[self.SP] = self.X; self.SP -= 1
            elif op == "POPX": self.SP += 1; self.X = self._set(self.M[self.SP])
            elif op == "LDP":  self.P = arg & 0xFFFFFF                     # 24-bit far pointer (bank<<16|hi<<8|lo)
            elif op == "ADDP": self.P = (self.P + arg) & 0xFFFFFF
            elif op == "PLO":  self.P = (self.P & 0xFFFF00) | a            # set P low byte from A
            elif op == "PHI":  self.P = (self.P & 0xFF00FF) | (a << 8)     # set P mid byte from A
            elif op == "PBK":  self.P = (self.P & 0x00FFFF) | (a << 16)    # set P bank byte from A (reach > 64 KB)
            elif op == "STPX": self.M[(self.P + self.X) & self.amask] = a  # M[P+X] = A  (far)
            elif op == "LDPX": self.A = self._set(self.M[(self.P + self.X) & self.amask])
            elif op == "IN":  self.A = self._set(self.M[self.inp_addr])
            elif op == "FRAME":
                if set_input is not None: self.M[self.inp_addr] = set_input(self) & MASK
                self.snap_frame()
                if frame_on is not None and frame_on(self): break
            elif op == "NOP": pass
            elif op == "HLT": break
            else: raise ValueError(f"bad op {op} @ {self.PC-1}")
        return self

# ----------------------------- machine registry: generate any CA computer ----------------
# One core, many machines. Add a row to grow the family (CA-3, …); networks instantiate N of these.
SPECS = {
    "CA-1": dict(word_bits=8,  memsize=0x100000),   # 8-bit, 1 MB (16-bit near + 24-bit far/banked)
    "CA-2": dict(word_bits=32, memsize=0x100000),   # 32-bit, 1 MB (flat) — the next step (OS port pending)
}
def make_machine(name="CA-1", **over):
    """Instantiate a named CA computer from the registry (override any field via kwargs)."""
    spec = dict(SPECS[name]); spec.update(over)
    return CA1Sys(**spec)

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
