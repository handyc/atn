#!/usr/bin/env python3
# cell11_prog.py — cell-11 as a PROGRAMMABLE cellular automaton. The 4 ports carry
# an INSTRUCTION each tick; a sequence of instructions is a PROGRAM. We build a
# small instruction set into the cell-11 LUT (base class-4 dynamics when ports
# off; a distinct op when port1 carries a command), then verify the CA executes
# programs exactly and that base dynamics resume when ports go quiet.
#
# Instruction set (port1 = v, ports 2-4 = 0):
#   v=0  RUN   : base 7->1 class-4 dynamics (inert ports)
#   v=1  INC   : next = (self+1) mod 4
#   v=2  SHIFT : next = left neighbour (signal transport)
#   v=3  CLEAR : next = 0
import numpy as np
import caca, cell10, cell11

S = 20
EM = caca._even_mask(S)

def build_program_rule(base7):
    """cell-11 LUT: v=0 slice = base 7->1; v=1/2/3 slices = INC/SHIFT/CLEAR,
    written as functions of the decoded neighbourhood. Ports 2-4 unused (0)."""
    rule = cell11.embed_7to1(base7).copy()           # v=0 (ports off) = base
    keys = np.arange(cell11.LUT7, dtype=np.int64)
    self_ = (keys >> 12) & 3
    l = keys & 3                                      # left neighbour (bits 0-1)
    ops = {1: (self_ + 1) & 3,                        # INC
           2: l,                                      # SHIFT (= left neighbour)
           3: np.zeros_like(keys)}                    # CLEAR
    for v, out in ops.items():
        rule[keys | (v << 14)] = out.astype(np.uint8)
    return rule

def step(board, cmd, rule):
    p1 = np.full((S, S), cmd, np.uint8) if cmd else 0
    return cell11.hex_step_cell11(board, [p1, 0, 0, 0], rule)

def reference(board, cmd, base7):
    if cmd == 0: return caca.hex_step(board[None], base7[None], EM)[0]
    if cmd == 1: return (board + 1) & 3
    if cmd == 2: return np.roll(board, 1, axis=1)     # each cell <- its left neighbour
    if cmd == 3: return np.zeros_like(board)
    raise ValueError(cmd)

def run_program(board, program, rule):
    b = board.copy()
    for cmd in program: b = step(b, cmd, rule)
    return b

def run_reference(board, program, base7):
    b = board.copy()
    for cmd in program: b = reference(b, cmd, base7)
    return b

def main():
    rng = np.random.default_rng(0)
    pool7, _ = caca.load_pool(32, seed=1)
    base7 = pool7[0]                                  # a class-4 base
    rule = build_program_rule(base7)
    names = {0: "RUN(base)", 1: "INC", 2: "SHIFT", 3: "CLEAR"}

    # 1) each instruction executes exactly, on random boards
    print("per-instruction exactness (10 random boards each):")
    for v in (0, 1, 2, 3):
        good = 0
        for _ in range(10):
            b = rng.integers(0, 4, (S, S)).astype(np.uint8)
            good += int(np.array_equal(step(b, v, rule), reference(b, v, base7)))
        print(f"  v={v} {names[v]:<10} {good}/10 exact")

    # 2) a PROGRAM (instruction sequence) executes correctly + base resumes
    programs = [
        [1, 1, 1],            # INC x3  -> +3 mod 4
        [3, 1, 1],            # CLEAR then INC x2 -> all = 2
        [2, 2],               # SHIFT x2 -> board shifted left by 2
        [1, 0, 0, 3, 0],      # INC, base, base, CLEAR, base  (mix compute + dynamics)
    ]
    print("\nprogram execution (CA vs reference interpreter, 8 random boards):")
    for prog in programs:
        good = 0
        for _ in range(8):
            b = rng.integers(0, 4, (S, S)).astype(np.uint8)
            good += int(np.array_equal(run_program(b, prog, rule), run_reference(b, prog, base7)))
        print(f"  program {str(prog):<22} {good}/8 exact")

    # 3) base dynamics are byte-identical to plain 7->1 when ports stay off
    b = rng.integers(0, 4, (S, S)).astype(np.uint8)
    bp = run_program(b, [0] * 12, rule)
    br = b.copy()
    for _ in range(12): br = caca.hex_step(br[None], base7[None], EM)[0]
    print(f"\n12 ticks RUN(base) == plain 7->1 evolution: {np.array_equal(bp, br)}")
    print("\n-> cell-11 runs as a programmable CA: instruction-stream drives distinct ops,")
    print("   composes over ticks, and falls back to the class-4 base when ports are off.")

if __name__ == "__main__":
    main()
