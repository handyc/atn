#!/usr/bin/env python3
# calc.py — a CALCULATOR as a real CA-1 program. Given two operands and an op code in memory,
# it computes +, -, x, / using only CA-1 instructions (so every arithmetic step is a CA gate
# computation). Multiply = repeated CA addition; divide = repeated CA subtraction. The result
# is a genuine 16-bit value produced by the cellular-automaton datapath. Exported for the
# Win98 desktop lab (glider-lab12), which calls this program when you press a button.
import json
from ca1sys import CA1Sys, asm

OPA, OPB, OP, RLO, RHI, ERR, I, Q = 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17

def program():
    L = []; a = L.append
    a(("calc:",))
    a(("LDI", 0)); a(("STA", RLO)); a(("STA", RHI)); a(("STA", ERR)); a(("STA", Q))
    a(("LDA", OP)); a(("CMPI", 0)); a(("JZ", "do_add"))
    a(("LDA", OP)); a(("CMPI", 1)); a(("JZ", "do_sub"))
    a(("LDA", OP)); a(("CMPI", 2)); a(("JZ", "do_mul"))
    a(("JMP", "do_div"))
    # --- add: RES16 = OPA + OPB ---
    a(("do_add:",))
    a(("LDA", OPA)); a(("ADD", OPB)); a(("STA", RLO))
    a(("JNC", "add_nc")); a(("LDI", 1)); a(("STA", RHI)); a(("JMP", "done"))
    a(("add_nc:",)); a(("LDI", 0)); a(("STA", RHI)); a(("JMP", "done"))
    # --- sub: if OPA>=OPB -> OPA-OPB else ERR ---
    a(("do_sub:",))
    a(("LDA", OPA)); a(("CMP", OPB)); a(("JNC", "sub_neg"))
    a(("LDA", OPA)); a(("SUB", OPB)); a(("STA", RLO)); a(("JMP", "done"))
    a(("sub_neg:",)); a(("LDI", 1)); a(("STA", ERR)); a(("JMP", "done"))
    # --- mul: RES16 = OPA * OPB by repeated 16-bit addition ---
    a(("do_mul:",))
    a(("LDA", OPB)); a(("STA", I))
    a(("mul_loop:",))
    a(("LDA", I)); a(("JZ", "done"))
    a(("LDA", RLO)); a(("ADD", OPA)); a(("STA", RLO))
    a(("JNC", "mul_nc")); a(("LDA", RHI)); a(("ADDI", 1)); a(("STA", RHI))
    a(("mul_nc:",))
    a(("LDA", I)); a(("SUBI", 1)); a(("STA", I)); a(("JMP", "mul_loop"))
    # --- div: Q=OPA/OPB, RHI=remainder; ERR if OPB==0 ---
    a(("do_div:",))
    a(("LDA", OPB)); a(("JZ", "div_zero"))
    a(("div_loop:",))
    a(("LDA", OPA)); a(("CMP", OPB)); a(("JNC", "div_done"))
    a(("LDA", OPA)); a(("SUB", OPB)); a(("STA", OPA))
    a(("LDA", Q)); a(("ADDI", 1)); a(("STA", Q)); a(("JMP", "div_loop"))
    a(("div_done:",)); a(("LDA", Q)); a(("STA", RLO)); a(("LDA", OPA)); a(("STA", RHI)); a(("JMP", "done"))
    a(("div_zero:",)); a(("LDI", 1)); a(("STA", ERR))
    a(("done:",)); a(("HLT",))
    return asm(L)

def compute(a, b, op):
    m = CA1Sys(); m.M[OPA] = a; m.M[OPB] = b; m.M[OP] = op
    m.run(program(), max_i=2_000_000)
    return m.M[RHI] * 256 + m.M[RLO], m.M[RHI], m.M[RLO], m.M[ERR], m.icount

def reference(a, b, op):
    if op == 0: return a + b, 0
    if op == 1: return (a - b, 0) if a >= b else (None, 1)
    if op == 2: return a * b, 0
    if op == 3: return (a // b, 0) if b != 0 else (None, 1)

if __name__ == "__main__":
    import random
    random.seed(0); fails = 0; tests = 0
    for op in range(4):
        for _ in range(60):
            a = random.randint(0, 255); b = random.randint(0, 255)
            val, rhi, rlo, err, ic = compute(a, b, op)
            ref, referr = reference(a, b, op)
            if op == 3:  # quotient in RLO
                ok = (err == referr) and (err == 1 or rlo == ref)
            elif op == 1:
                ok = (err == referr) and (err == 1 or rlo == ref)
            else:
                ok = (err == 0) and (val == ref)
            tests += 1; fails += (not ok)
    print(f"CA-1 calculator: {tests-fails}/{tests} correct vs reference (+,-,x,/ on random bytes)")
    for a, b, op, sym in [(13, 11, 2, "x"), (47, 58, 0, "+"), (200, 37, 1, "-"), (144, 12, 3, "/")]:
        val, rhi, rlo, err, ic = compute(a, b, op)
        shown = rlo if op in (1, 3) else val
        print(f"   {a} {sym} {b} = {shown}   ({ic} CA-1 instructions)")
