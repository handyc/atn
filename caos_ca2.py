#!/usr/bin/env python3
# caos_ca2.py — CA-OS/2: a native 32-bit operating system for the CA-2 machine.
#
# CA-2 (ca1sys make_machine("CA-2")) is the 32-bit member of the family: 32-bit registers/ALU
# (the verified 32-bit CA adder — cacpu.verify_adder_ca), 1 MB of FLAT memory, word load/store.
# Unlike CA-OFFICE (the 8-bit CA-1 OS), this OS is written 32-bit-native:
#   * a 512x384 framebuffer (4x CA-1's area) living flat at 0x10000 — no banking,
#   * pixels written by a flat 32-bit indexed store (STAX FB, X = y*512 + x), no page tricks,
#   * coordinate math in 32-bit words (LDW/STW/ADDW/SUBW/CMPW).
# It boots a desktop, draws a system window of honest self-description, runs a live clock, and
# tracks the mouse with a save-under cursor. Proof that CA-2 runs an operating system.
import caos3 as c1          # reuse the verified 5x7 font + palette
from ca1sys import asm, make_machine

W, H = 512, 384
FB = 0x10000                # framebuffer base (flat); spans 0x10000..0x40000
PAL = c1.PAL
BLK, TEAL, SIL, GRY, WHT, NAV, LSV, BLU, RED, GRN = range(10)

# ---- 32-bit OS variables (4 bytes each, via LDW/STW) ----
AX, AY, AW, AH, ACOL = 0x00, 0x04, 0x08, 0x0C, 0x10
GX, GY, GCH, GCOL    = 0x14, 0x18, 0x1C, 0x20
T0, T1, T2, T3       = 0x24, 0x28, 0x2C, 0x30
MX, MY, MB, MBP      = 0x34, 0x38, 0x3C, 0x40
CX, CY, OCX, OCY     = 0x44, 0x48, 0x4C, 0x50
HAVES, CLKF, CSEC    = 0x54, 0x58, 0x5C
CURBUF = 0x0100             # 8x8 save-under buffer (64 bytes)
FONT   = 0x0400             # 5x7 font, 7 bytes/glyph
gi = c1.gi

def load_memory(m):
    for ch, idx in c1.GIDX.items():
        for r, b in enumerate(c1.enc_rows(c1.GART[ch])): m.M[FONT + idx*7 + r] = b

# arrow cursor (8 rows, MSB = leftmost column)
CURSOR = [0x80, 0xC0, 0xE0, 0xF0, 0xF8, 0xFC, 0xE0, 0x40]

def program():
    L = []; a = L.append
    def shl(n):
        for _ in range(n): a(("SHL",))
    # text: unrolled blitglyph calls for a fixed string at (x,y) in colour col (6 px/char)
    def puts(x, y, text, col):
        for i, ch in enumerate(text):
            a(("LDI", x + i*6)); a(("STW", GX)); a(("LDI", y)); a(("STW", GY))
            a(("LDI", gi(ch))); a(("STW", GCH)); a(("LDI", col)); a(("STW", GCOL)); a(("CALL", "blitglyph"))
    a(("JMP", "boot"))

    # ---- fillrect: AX,AY,AW,AH,ACOL (flat 32-bit indexed) ----
    a(("fillrect:",))
    a(("LDW", AY)); shl(9); a(("ADDW", AX)); a(("STW", T0))      # rowbase = AY*512 + AX
    a(("LDW", AH)); a(("STW", T1))                               # rows left
    a(("fr_row:",)); a(("LDW", T1)); a(("JZ", "fr_done"))
    a(("LDW", T0)); a(("ADDW", AW)); a(("STW", T3))              # rowend = rowbase + AW
    a(("LDW", T0)); a(("TAX",))
    a(("fr_col:",)); a(("TXA",)); a(("CMPW", T3)); a(("JC", "fr_nrow"))
    a(("LDA", ACOL)); a(("STAX", FB)); a(("INX",)); a(("JMP", "fr_col"))
    a(("fr_nrow:",)); a(("LDW", T0)); a(("ADDI", W)); a(("STW", T0)); a(("LDW", T1)); a(("SUBI", 1)); a(("STW", T1)); a(("JMP", "fr_row"))
    a(("fr_done:",)); a(("RET",))

    # ---- blitglyph: 5x7 glyph GCH at (GX,GY) in GCOL ----
    a(("blitglyph:",))
    a(("LDW", GCH)); shl(3); a(("SUBW", GCH)); a(("STW", T0))    # T0 = GCH*7 (font byte offset)
    a(("LDI", 0)); a(("STW", T2))                               # row = 0
    a(("bg_row:",)); a(("LDW", T2)); a(("CMPI", 7)); a(("JC", "bg_done"))
    a(("LDW", T0)); a(("ADDW", T2)); a(("TAX",)); a(("LDAX", FONT)); a(("STW", T3))   # T3 = rowbyte
    a(("LDW", GY)); a(("ADDW", T2)); shl(9); a(("ADDW", GX)); a(("STW", T1))          # T1 = rowpix base
    for col in range(5):
        a(("LDW", T3)); a(("ANDI", 0x10 >> col)); a(("JZ", f"bg_s{col}"))
        a(("LDW", T1)); a(("ADDI", col)); a(("TAX",)); a(("LDA", GCOL)); a(("STAX", FB))
        a((f"bg_s{col}:",))
    a(("LDW", T2)); a(("ADDI", 1)); a(("STW", T2)); a(("JMP", "bg_row"))
    a(("bg_done:",)); a(("RET",))

    # ---- desktop: background + taskbar + system window + text ----
    a(("drawdesktop:",))
    a(("LDI", 0)); a(("STW", AX)); a(("LDI", 0)); a(("STW", AY)); a(("LDI", W)); a(("STW", AW)); a(("LDI", H)); a(("STW", AH)); a(("LDI", TEAL)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    # taskbar
    a(("LDI", 0)); a(("STW", AX)); a(("LDI", H-18)); a(("STW", AY)); a(("LDI", W)); a(("STW", AW)); a(("LDI", 18)); a(("STW", AH)); a(("LDI", SIL)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    a(("LDI", 0)); a(("STW", AX)); a(("LDI", H-19)); a(("STW", AY)); a(("LDI", W)); a(("STW", AW)); a(("LDI", 1)); a(("STW", AH)); a(("LDI", WHT)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    puts(6, H-13, "CA-OS/2", BLK)
    # window
    WINX, WINY, WW, WH = 120, 96, 280, 190
    a(("LDI", WINX)); a(("STW", AX)); a(("LDI", WINY)); a(("STW", AY)); a(("LDI", WW)); a(("STW", AW)); a(("LDI", WH)); a(("STW", AH)); a(("LDI", SIL)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    a(("LDI", WINX)); a(("STW", AX)); a(("LDI", WINY)); a(("STW", AY)); a(("LDI", WW)); a(("STW", AW)); a(("LDI", 14)); a(("STW", AH)); a(("LDI", NAV)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    puts(WINX+6, WINY+4, "System", WHT)
    # body: honest self-description
    bx, by = WINX+10, WINY+24
    puts(bx, by,      "CA-2  -  32-bit processor", BLK)
    puts(bx, by+14,   "RAM:  1 MB  (flat address)", BLK)
    puts(bx, by+28,   "Screen: 512 x 384", BLK)
    puts(bx, by+46,   "Datapath: genuine cellular", GRY)
    puts(bx, by+58,   "automata (hex K=4 gliders)", GRY)
    puts(bx, by+76,   "ALU: 32-bit CA adder", BLU)
    puts(bx, by+88,   "verified == reference", BLU)
    puts(bx, by+110,  "one core generates the", BLK)
    puts(bx, by+122,  "whole family: CA-1 ... CA-2", BLK)
    a(("RET",))

    # ---- clock: draw seconds (2 digits) in the taskbar at right ----
    a(("drawclock:",))
    a(("LDI", W-40)); a(("STW", AX)); a(("LDI", H-15)); a(("STW", AY)); a(("LDI", 34)); a(("STW", AW)); a(("LDI", 11)); a(("STW", AH)); a(("LDI", SIL)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    # tens = CSEC/10, ones = CSEC%10  (CSEC kept 0..99)
    a(("LDW", CSEC)); a(("STW", T0)); a(("LDI", 0)); a(("STW", T1))
    a(("dc_t:",)); a(("LDW", T0)); a(("CMPI", 10)); a(("JNC", "dc_d")); a(("SUBI", 10)); a(("STW", T0)); a(("LDW", T1)); a(("ADDI", 1)); a(("STW", T1)); a(("JMP", "dc_t"))
    a(("dc_d:",))
    a(("LDI", W-34)); a(("STW", GX)); a(("LDI", H-14)); a(("STW", GY)); a(("LDW", T1)); a(("STW", GCH)); a(("LDI", BLK)); a(("STW", GCOL)); a(("CALL", "blitglyph"))
    a(("LDI", W-28)); a(("STW", GX)); a(("LDI", H-14)); a(("STW", GY)); a(("LDW", T0)); a(("STW", GCH)); a(("LDI", BLK)); a(("STW", GCOL)); a(("CALL", "blitglyph"))
    a(("RET",))

    # ---- cursor: 8x8 save-under + arrow ----
    a(("saveun:",)); a(("CALL", "cur_addr_init"))      # save M[FB..] under (CX,CY) into CURBUF
    a(("LDI", 0)); a(("STW", T1))
    a(("su_r:",)); a(("LDW", T1)); a(("CMPI", 8)); a(("JC", "su_d")); a(("LDI", 0)); a(("STW", T2))
    a(("su_c:",)); a(("LDW", T2)); a(("CMPI", 8)); a(("JC", "su_nr"))
    a(("LDW", CY)); a(("ADDW", T1)); shl(9); a(("STW", T0)); a(("LDW", CX)); a(("ADDW", T2)); a(("ADDW", T0)); a(("TAX",)); a(("LDAX", FB)); a(("STW", T3))
    a(("LDW", T1)); shl(3); a(("ADDW", T2)); a(("TAX",)); a(("LDA", T3)); a(("STAX", CURBUF))
    a(("LDW", T2)); a(("ADDI", 1)); a(("STW", T2)); a(("JMP", "su_c"))
    a(("su_nr:",)); a(("LDW", T1)); a(("ADDI", 1)); a(("STW", T1)); a(("JMP", "su_r"))
    a(("su_d:",)); a(("RET",))
    a(("cur_addr_init:",)); a(("RET",))                 # (placeholder hook, kept for clarity)

    a(("restun:",))                                     # restore CURBUF to M[FB..] at (OCX,OCY)
    a(("LDI", 0)); a(("STW", T1))
    a(("ru_r:",)); a(("LDW", T1)); a(("CMPI", 8)); a(("JC", "ru_d")); a(("LDI", 0)); a(("STW", T2))
    a(("ru_c:",)); a(("LDW", T2)); a(("CMPI", 8)); a(("JC", "ru_nr"))
    a(("LDW", T1)); shl(3); a(("ADDW", T2)); a(("TAX",)); a(("LDAX", CURBUF)); a(("STW", T3))
    a(("LDW", OCY)); a(("ADDW", T1)); shl(9); a(("STW", T0)); a(("LDW", OCX)); a(("ADDW", T2)); a(("ADDW", T0)); a(("TAX",)); a(("LDA", T3)); a(("STAX", FB))
    a(("LDW", T2)); a(("ADDI", 1)); a(("STW", T2)); a(("JMP", "ru_c"))
    a(("ru_nr:",)); a(("LDW", T1)); a(("ADDI", 1)); a(("STW", T1)); a(("JMP", "ru_r"))
    a(("ru_d:",)); a(("RET",))

    a(("drawcur:",))                                    # draw the arrow at (CX,CY) in BLK
    for dy, rowmask in enumerate(CURSOR):
        a(("LDW", CY)); a(("ADDI", dy)); shl(9); a(("STW", T0)); a(("LDW", CX)); a(("ADDW", T0)); a(("STW", T1))   # T1 = rowbase
        for dx in range(8):
            if rowmask & (0x80 >> dx):
                a(("LDW", T1)); a(("ADDI", dx)); a(("TAX",)); a(("LDI", BLK)); a(("STAX", FB))
    a(("RET",))

    # ============ boot + main ============
    a(("boot:",))
    for v in (MB, MBP, HAVES, CLKF, CSEC): a(("LDI", 0)); a(("STW", v))
    a(("LDI", W//2)); a(("STW", CX)); a(("STW", OCX)); a(("LDI", H//2)); a(("STW", CY)); a(("STW", OCY))
    a(("CALL", "drawdesktop")); a(("CALL", "drawclock"))
    a(("main:",))
    # mouse -> CX,CY (clamp to W-8 / H-8)
    a(("LDW", MX)); a(("CMPI", W-8)); a(("JNC", "mxok")); a(("LDI", W-8)); a(("STW", CX)); a(("JMP", "mxd")); a(("mxok:",)); a(("LDW", MX)); a(("STW", CX)); a(("mxd:",))
    a(("LDW", MY)); a(("CMPI", H-8)); a(("JNC", "myok")); a(("LDI", H-8)); a(("STW", CY)); a(("JMP", "myd")); a(("myok:",)); a(("LDW", MY)); a(("STW", CY)); a(("myd:",))
    # cursor: restore old, save new, draw
    a(("LDW", HAVES)); a(("JZ", "norest")); a(("CALL", "restun")); a(("norest:",))
    a(("CALL", "saveun")); a(("LDI", 1)); a(("STW", HAVES)); a(("LDW", CX)); a(("STW", OCX)); a(("LDW", CY)); a(("STW", OCY)); a(("CALL", "drawcur"))
    # clock: 60 frames = 1 second (0..99 wrap)
    a(("LDW", CLKF)); a(("ADDI", 1)); a(("STW", CLKF)); a(("CMPI", 60)); a(("JNC", "noclk"))
    a(("LDI", 0)); a(("STW", CLKF)); a(("LDW", CSEC)); a(("ADDI", 1)); a(("STW", T0)); a(("LDW", T0)); a(("CMPI", 100)); a(("JNC", "csok")); a(("LDI", 0)); a(("STW", T0)); a(("csok:",)); a(("LDW", T0)); a(("STW", CSEC))
    # redraw clock then re-save under cursor (it sits on the taskbar sometimes)
    a(("CALL", "restun")); a(("CALL", "drawclock")); a(("CALL", "saveun")); a(("CALL", "drawcur"))
    a(("noclk:",))
    a(("FRAME",)); a(("JMP", "main"))
    return asm(L)


if __name__ == "__main__":
    m = make_machine("CA-2", fb_addr=FB, fb_w=W, fb_h=H)
    load_memory(m)
    m.M[MX:MX+4] = (W//2).to_bytes(4, "little"); m.M[MY:MY+4] = (H//2).to_bytes(4, "little")
    m.run(program(), max_i=20_000_000, frame_on=lambda mm: True)
    px = m.M[FB:FB+W*H]
    print("CA-OS/2 booted on CA-2:", sum(1 for v in px if v != TEAL), "non-background pixels drawn /", W*H)
