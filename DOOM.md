# Can the CA computer run Doom?

Short answer: **its *algorithm*, yes — the full game, no, by about a factor of two billion.**
Here is the honest, measured account.

## What we built (this is real and verified)

Starting from the CA-1 accumulator machine (an 8-bit computer whose datapath — storage and
arithmetic — is a genuine cellular automaton; see `cacpu.py`), we added the rest of a computer:

- **`ca1sys.py`** — CA-1 scaled into a real (tiny) machine: a 64 KB address space of 8-bit
  words, a **memory-mapped framebuffer** (a screen), an **input register** (keys), an index
  register and a 16-bit address pointer, a full ISA, and a small assembler. The emulator is
  **bit-faithful**: every ALU result is masked exactly as the CA ripple-adder/gates produce it,
  and `verify_against_ca()` confirms ADD/SUB/AND/OR/XOR equal the genuine CA gates (8/8 each).
- **`raycaster.py`** — Doom's core idea (a first-person **raycaster**) written as a
  **195-instruction CA-1 program**. It renders a tiny maze column-by-column into the
  framebuffer, with movement + a collision check, using only table lookups, adds, shifts and
  compares — all CA-computable. Its output is **bit-identical** to a pure-Python reference.
- **`glider-lab11.html`** (local) — a **playable** in-browser CA-1 virtual machine running the
  exact same machine code, driven by WASD/arrows. The VM is the identical ISA; it just runs
  ~10⁸× faster than the real CA so it's interactive.
- **`genuine_ca_replay.py`** — logs every arithmetic op a frame performs and **replays a sample
  on the genuine CA gates**, confirming the CA reproduces the raycaster's arithmetic exactly.

So: **Doom's rendering algorithm runs on a real CA computer.** That part is done and honest.

## The measured numbers

| quantity | measured |
|---|---|
| one CA NAND gate | 12.5 ms (a 60×60 board run 60 steps = 216,000 cell-updates) |
| one CA 8-bit ADD | 1.47 s (~118 NAND gates) |
| CA-1 instruction rate | **2.5 instructions / second** (400 ms/instr) |
| raycaster frame (48×28) | **39,846 CA-1 instructions** |
| → one frame on the genuine CA | ~15,900 s ≈ **4.4 hours per frame** |

## Why the full game is ~2 billion× out of reach

- **Speed.** Doom on a 486 needs ~15 **million** 32-bit instructions/second to play. Emulating
  one 32-bit instruction (with multiply/divide) on an 8-bit accumulator with no multiply takes
  ~hundreds of CA-1 instructions. At 2.5 CA-1 instr/s that's ≈0.01 effective 486-instr/s — a
  slowdown of **~1.5–2 × 10⁹**. One Doom *frame* (~430k 486-instructions) would take **years**.
- **Memory.** Doom needs ~4 MB. CA-1 stores each data bit as a latch board (~18,000 CA cells);
  4 MB = 33.5 M bits ≈ 6 × 10¹¹ cells to simulate every cycle — and we have 16–256 bytes.
- **The deepest point.** This "CA computer" is itself *simulated* on a PC that runs Doom at
  thousands of fps. It is a **demonstration of universality**, not a practical machine. CA-1 is
  Turing-complete (universal gate + memory + conditional branch + loop), so *in principle* it can
  compute anything Doom computes, given unbounded memory and time. "Given unbounded time" is
  doing all the work in that sentence.

## What scales easily, and what doesn't

Scaling **capability** is trivial: wider words, more latch RAM, a richer ISA, memory-mapped I/O —
all just more of the same components, no new physics. We did exactly this to add a screen and
input. Scaling **speed** does not budge: the cost is ~216,000 CA cell-updates per gate, times the
gate-count of the program, and real software is astronomically gate-heavy. That ceiling is the
honest boundary of the whole project: a beautiful, verifiable teaching computer — that renders
Doom's algorithm, and will never run Doom.
