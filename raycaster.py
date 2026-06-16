#!/usr/bin/env python3
# raycaster.py — Doom's core (a first-person raycaster) as a CA-1 PROGRAM. A tiny maze is
# rendered column-by-column into the memory-mapped framebuffer, with WASD/arrow movement.
# Every ALU op the program uses (ADD/SUB/AND/OR/SHL/SHR/CMP) is one the genuine CA datapath
# computes (verified in cacpu/ca1sys). Run on the fast faithful emulator here; the browser
# (glider-lab11) runs the identical machine code live and interactively.
import math, json
import numpy as np
from ca1sys import CA1Sys, asm

SW, SH, NANG, MAXST = 48, 28, 64, 96
DXT_A, DYT_A, HTT_A, MAP_A, COLA_A, FB_A = 0x100, 0x140, 0x180, 0x200, 0x300, 0x8000
# zero-page vars
PX, PY, PA, COL, ANG, RX, RY, STEPN, HT, TOP, BOT, SHADE, Y, MIDX, TMP, CX, CY = \
    (0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x20)

MAPROWS = ['1111111111111111','1000000000000001','1000000000000001','1000010000100001',
           '1000000000000001','1001000000000101','1000000110000001','1000000110000001',
           '1000000000001001','1010000000000001','1000000001000001','1000100000000001',
           '1000000000010001','1000001000000001','1000000000000001','1111111111111111']

def tables():
    COS = [max(-64, min(64, round(64*math.cos(2*math.pi*a/NANG)))) for a in range(NANG)]
    SIN = [max(-64, min(64, round(64*math.sin(2*math.pi*a/NANG)))) for a in range(NANG)]
    DXT = [(round(c/8)) & 0xFF for c in COS]                       # ~1/8 cell step, signed byte
    DYT = [(round(c/8)) & 0xFF for c in SIN]
    HTT = [min(SH, (3*SH)//max(s, 1)) for s in range(128)]
    COLA = [((c - SW//2)*16//SW) & 63 for c in range(SW)]
    MAP = [int(ch) for r in MAPROWS for ch in r]
    return DXT, DYT, HTT, COLA, MAP

def load_memory(m):
    DXT, DYT, HTT, COLA, MAP = tables()
    for i, v in enumerate(DXT):  m.M[DXT_A + i] = v
    for i, v in enumerate(DYT):  m.M[DYT_A + i] = v
    for i, v in enumerate(HTT):  m.M[HTT_A + i] = v
    for i, v in enumerate(COLA): m.M[COLA_A + i] = v
    for i, v in enumerate(MAP):  m.M[MAP_A + i] = v
    m.M[PX] = 8*16; m.M[PY] = 8*16; m.M[PA] = 8                    # start cell (8,8), angle 8

def program(loop=True):
    L = []
    a = L.append
    a(("main:",))
    # ---- input & movement (bit0 left, bit1 right, bit2 fwd, bit3 back) ----
    a(("IN",)); a(("STA", TMP))
    a(("ANDI", 1)); a(("JZ", "n_left")); a(("LDA", PA)); a(("SUBI", 1)); a(("ANDI", 63)); a(("STA", PA))
    a(("n_left:",))
    a(("LDA", TMP)); a(("ANDI", 2)); a(("JZ", "n_right")); a(("LDA", PA)); a(("ADDI", 1)); a(("ANDI", 63)); a(("STA", PA))
    a(("n_right:",))
    # forward: cand = P +/- 3*step; collision-check the target cell
    for sign, bit, lbl in ((+1, 4, "fwd"), (-1, 8, "back")):
        a(("LDA", TMP)); a(("ANDI", bit)); a(("JZ", f"n_{lbl}"))
        a(("LDX", PA)); a(("LDAX", DXT_A))
        a(("SHL",)); a(("STA", TMP))                              # TMP = 2*DXT[PA]
        if sign > 0: a(("LDA", PX)); a(("ADD", TMP))
        else:        a(("LDA", PX)); a(("SUB", TMP))
        a(("STA", CX))
        a(("LDX", PA)); a(("LDAX", DYT_A)); a(("SHL",)); a(("STA", TMP))
        if sign > 0: a(("LDA", PY)); a(("ADD", TMP))
        else:        a(("LDA", PY)); a(("SUB", TMP))
        a(("STA", CY))
        # idx = (CY>>4<<4) | (CX>>4) ; if MAP[idx]==0 commit
        a(("LDA", CY)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("ANDI", 15))
        a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("STA", MIDX))
        a(("LDA", CX)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("ANDI", 15)); a(("OR", MIDX)); a(("TAX",))
        a(("LDAX", MAP_A)); a(("JNZ", f"n_{lbl}"))                # blocked -> skip move
        a(("LDA", CX)); a(("STA", PX)); a(("LDA", CY)); a(("STA", PY))
        a((f"n_{lbl}:",))
    # ---- render columns ----
    a(("LDI", 0)); a(("STA", COL))
    a(("LDP", FB_A))
    a(("col:",))
    a(("LDX", COL)); a(("LDAX", COLA_A)); a(("ADD", PA)); a(("ANDI", 63)); a(("STA", ANG))
    a(("LDA", PX)); a(("STA", RX)); a(("LDA", PY)); a(("STA", RY)); a(("LDI", 0)); a(("STA", STEPN))
    a(("ray:",))
    a(("LDX", ANG)); a(("LDAX", DXT_A)); a(("ADD", RX)); a(("STA", RX))
    a(("LDX", ANG)); a(("LDAX", DYT_A)); a(("ADD", RY)); a(("STA", RY))
    a(("LDA", STEPN)); a(("ADDI", 1)); a(("STA", STEPN)); a(("CMPI", MAXST)); a(("JC", "raydone"))  # stepn>=MAX
    a(("LDA", RY)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("ANDI", 15))
    a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("STA", MIDX))
    a(("LDA", RX)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("ANDI", 15)); a(("OR", MIDX)); a(("TAX",))
    a(("LDAX", MAP_A)); a(("JZ", "ray"))                         # empty cell -> keep stepping
    a(("raydone:",))
    a(("LDX", STEPN)); a(("LDAX", HTT_A)); a(("STA", HT))
    a(("LDI", SH)); a(("SUB", HT)); a(("SHR",)); a(("STA", TOP)); a(("ADD", HT)); a(("STA", BOT))
    a(("LDA", STEPN)); a(("CMPI", 8)); a(("JNC", "sh2")); a(("CMPI", 16)); a(("JNC", "sh3")); a(("LDI", 4)); a(("JMP", "shset"))
    a(("sh2:",)); a(("LDI", 2)); a(("JMP", "shset")); a(("sh3:",)); a(("LDI", 3)); a(("shset:",)); a(("STA", SHADE))
    # draw column y=0..SH-1
    a(("LDI", 0)); a(("STA", Y))
    a(("draw:",))
    a(("LDA", Y)); a(("CMP", TOP)); a(("JNC", "pceil"))           # y<top -> ceiling
    a(("LDA", Y)); a(("CMP", BOT)); a(("JNC", "pwall"))           # y<bot -> wall
    a(("LDI", 5)); a(("JMP", "pput"))                            # floor
    a(("pceil:",)); a(("LDI", 1)); a(("JMP", "pput"))
    a(("pwall:",)); a(("LDA", SHADE))
    a(("pput:",)); a(("LDX", Y)); a(("STPX",))
    a(("LDA", Y)); a(("ADDI", 1)); a(("STA", Y)); a(("CMPI", SH)); a(("JNC", "draw"))
    a(("ADDP", SH))                                              # next column base
    a(("LDA", COL)); a(("ADDI", 1)); a(("STA", COL)); a(("CMPI", SW)); a(("JNC", "col"))
    a(("FRAME",))
    if loop: a(("JMP", "main"))
    else:    a(("HLT",))
    return asm(L)

# ---------- python reference (identical integer ops) to validate the program ----------
def reference_frame(px, py, pa):
    DXT, DYT, HTT, COLA, MAP = tables()
    fb = bytearray(SW*SH)
    for c in range(SW):
        ang = (pa + COLA[c]) & 63
        rx, ry, st = px, py, 0
        while True:
            rx = (rx + DXT[ang]) & 0xFF; ry = (ry + DYT[ang]) & 0xFF; st += 1
            if st >= MAXST: break
            idx = (((ry >> 4) & 15) << 4) | ((rx >> 4) & 15)
            if MAP[idx]: break
        ht = HTT[st & 0x7F]; top = ((SH - ht) & 0xFF) >> 1; bot = (top + ht) & 0xFF
        shade = 2 if st < 8 else 3 if st < 16 else 4
        for y in range(SH):
            fb[c*SH + y] = 1 if y < top else (shade if y < bot else 5)
    return bytes(fb)

if __name__ == "__main__":
    m = CA1Sys(fb_addr=FB_A, fb_w=SH, fb_h=SW)     # column-major: "w"=SH rows packed per col
    load_memory(m)
    code = program(loop=False)
    m.M[m.inp_addr] = 0
    m.run(code, max_i=2_000_000)
    got = bytes(m.M[FB_A:FB_A + SW*SH])
    ref = reference_frame(8*16, 8*16, 8)
    print(f"CA-1 raycaster: {m.icount} instructions for one frame ({SW}x{SH})")
    print(f"emulator frame == reference: {got == ref}")
    # show it
    chs = {0: ' ', 1: '`', 2: '@', 3: '#', 4: '=', 5: '.'}
    for y in range(SH):
        print("".join(chs[got[c*SH + y]] for c in range(SW)))
