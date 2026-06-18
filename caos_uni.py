#!/usr/bin/env python3
# caos_uni.py — CA Unicode Writer: a CA-2 program (in a 4 MB machine) that renders typed text in ANY
# language by blitting 16x16 GNU-Unifont glyphs it holds in its OWN memory. The browser only captures
# keystrokes (as Unicode codepoints) and blits the framebuffer — the cellular-automaton computer does
# all the glyph rendering, exactly like the other CA-OS labs, just with a 16x16 full-BMP font.
#
# Memory map (4 MB flat CA-2):
#   0x000000  OS variables (VS-byte slots) + code
#   0x010000  framebuffer 512x384 (1 byte/pixel)  .. 0x040000
#   0x040000  UBUF: typed text as 16-bit codepoints (little-endian), up to ~8000 chars
#   0x080000  WTAB: advance width per codepoint (8 or 16), 1 byte x 0x10000
#   0x100000  FONT16: direct codepoint->glyph table, 32 bytes/glyph (16 rows x 2 bytes)
from ca1sys import asm, make_machine

W, H   = 512, 384
FB     = 0x010000
UBUF   = 0x040000
WTAB   = 0x080000
FONT16 = 0x100000
MEMSIZE = 0x800000        # 8 MB (power of two; the 64 B/glyph antialiased table at 0x100000 is 4 MB)
PALMAP  = 0x000340        # glyph level (1..3) -> palette index
PAL = ["#000000","#008080","#c0c0c0","#808080","#ffffff","#000080","#dfdfdf","#1084d0","#b00000","#107010","#aaaaaa","#555555"]
BLK, TEAL, SIL, GRY, WHT, NAV, LSV, BLU, RED, GRN = range(10)
TXL, TXD = 10, 11         # antialias greys: light / dark (full ink = BLK)

VS = 16
_V = ("AX AY AW AH ACOL PX PY CP GA ROW T0 T1 T2 T3 MX MY MB MBP KEY ULEN DIRTY CW WI").split()
for _i, _n in enumerate(_V): globals()[_n] = _i * VS

# text-area geometry
MARGX, MARGY = 8, 26          # left/top of the text body
LINEH        = 18             # line height (16px glyph + 2px gap)
RIGHTX       = W - 18         # wrap margin

def make():
    return make_machine("CA-2", fb_addr=FB, fb_w=W, fb_h=H, memsize=MEMSIZE)

def program():
    L = []; a = L.append
    def shl(n):
        for _ in range(n): a(("SHL",))
    def rect(x, y, w, h, col):
        a(("LDI", x)); a(("STW", AX)); a(("LDI", y)); a(("STW", AY)); a(("LDI", w)); a(("STW", AW)); a(("LDI", h)); a(("STW", AH)); a(("LDI", col)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    a(("JMP", "boot"))

    # ---- fillrect (flat 32-bit indexed store) ----
    a(("fillrect:",))
    a(("LDW", AY)); shl(9); a(("ADDW", AX)); a(("STW", T0))
    a(("LDW", AH)); a(("STW", T1))
    a(("fr_row:",)); a(("LDW", T1)); a(("JZ", "fr_done"))
    a(("LDW", T0)); a(("ADDW", AW)); a(("STW", T3))
    a(("LDW", T0)); a(("TAX",))
    a(("fr_col:",)); a(("TXA",)); a(("CMPW", T3)); a(("JC", "fr_nrow"))
    a(("LDA", ACOL)); a(("STAX", FB)); a(("INX",)); a(("JMP", "fr_col"))
    a(("fr_nrow:",)); a(("LDW", T0)); a(("ADDI", W)); a(("STW", T0)); a(("LDW", T1)); a(("SUBI", 1)); a(("STW", T1)); a(("JMP", "fr_row"))
    a(("fr_done:",)); a(("RET",))

    # ---- blit16: draw the 16x16 glyph for codepoint CP at (PX,PY) in black ----
    a(("blit16:",))
    a(("LDW", CP)); shl(6); a(("STW", GA))                 # GA = CP*64  (offset into FONT16, 64 B/glyph)
    a(("LDI", 0)); a(("STW", ROW))
    a(("b16_row:",)); a(("LDW", ROW)); a(("CMPI", 16)); a(("JC", "b16_done"))
    a(("LDW", PY)); a(("ADDW", ROW)); shl(9); a(("ADDW", PX)); a(("STW", T1))   # T1 = FB index of (PX, PY+ROW)
    a(("LDW", ROW)); a(("SHL",)); a(("SHL",)); a(("ADDW", GA)); a(("TAX",))     # X = GA + ROW*4 (4 bytes/row)
    a(("LDAX", FONT16)); a(("STW", T2))                                         # assemble the 16x2-bit row into T2
    a(("INX",)); a(("LDAX", FONT16)); shl(8);  a(("ADDW", T2)); a(("STW", T2))
    a(("INX",)); a(("LDAX", FONT16)); shl(16); a(("ADDW", T2)); a(("STW", T2))
    a(("INX",)); a(("LDAX", FONT16)); shl(24); a(("ADDW", T2)); a(("STW", T2))
    for col in range(16):                                                       # consume px low-end, 2 bits each
        a(("LDW", T2)); a(("ANDI", 3)); a(("JZ", f"b16s{col}"))
        a(("TAX",)); a(("LDAX", PALMAP)); a(("STW", T3))
        a(("LDW", T1)); a(("ADDI", col)); a(("TAX",)); a(("LDW", T3)); a(("STAX", FB))
        a((f"b16s{col}:",)); a(("LDW", T2)); a(("SHR",)); a(("SHR",)); a(("STW", T2))
    a(("LDW", ROW)); a(("ADDI", 1)); a(("STW", ROW)); a(("JMP", "b16_row"))
    a(("b16_done:",)); a(("RET",))

    # ---- render the whole document ----
    a(("render:",))
    rect(0, 0, W, H, TEAL)                                  # desktop
    rect(0, 0, W, 20, NAV)                                  # title bar
    rect(0, 20, W, H-20, WHT)                               # paper
    a(("LDI", MARGX)); a(("STW", PX)); a(("LDI", MARGY)); a(("STW", PY))
    a(("LDI", 0)); a(("STW", WI))
    a(("rd_l:",)); a(("LDW", WI)); a(("CMPW", ULEN)); a(("JC", "rd_car"))
    # CP = UBUF[WI] (16-bit LE: two bytes)
    a(("LDW", WI)); a(("SHL",)); a(("TAX",)); a(("LDAX", UBUF)); a(("STW", CP))      # low byte
    a(("LDW", WI)); a(("SHL",)); a(("ADDI", 1)); a(("TAX",)); a(("LDAX", UBUF)); shl(8); a(("ADDW", CP)); a(("STW", CP))   # | high<<8
    a(("LDW", CP)); a(("CMPI", 0x0A)); a(("JZ", "rd_nl"))    # newline
    a(("CALL", "blit16"))
    a(("LDW", CP)); a(("TAX",)); a(("LDAX", WTAB)); a(("STW", CW))   # advance width
    a(("LDW", PX)); a(("ADDW", CW)); a(("STW", PX)); a(("CMPI", RIGHTX)); a(("JNC", "rd_nx"))
    a(("rd_nl:",)); a(("LDI", MARGX)); a(("STW", PX)); a(("LDW", PY)); a(("ADDI", LINEH)); a(("STW", PY))
    a(("rd_nx:",)); a(("LDW", WI)); a(("ADDI", 1)); a(("STW", WI)); a(("JMP", "rd_l"))
    a(("rd_car:",)); a(("LDW", PX)); a(("STW", AX)); a(("LDW", PY)); a(("STW", AY)); a(("LDI", 2)); a(("STW", AW)); a(("LDI", 16)); a(("STW", AH)); a(("LDI", BLK)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    a(("RET",))

    # ---- keyboard: KEY holds a Unicode codepoint (0=none, 8=backspace, 10=newline append) ----
    a(("keyin:",))
    a(("LDW", KEY)); a(("CMPI", 8)); a(("JZ", "ki_bs"))
    a(("LDW", ULEN)); a(("CMPI", 8000)); a(("JC", "ki_d"))   # full
    a(("LDW", ULEN)); a(("SHL",)); a(("TAX",)); a(("LDW", KEY)); a(("STAX", UBUF))           # UBUF[ULEN] low byte
    a(("LDW", ULEN)); a(("SHL",)); a(("ADDI", 1)); a(("TAX",))                               # X = ULEN*2+1
    a(("LDW", KEY))
    for _ in range(8): a(("SHR",))                                                           # A = KEY>>8 (high byte)
    a(("STAX", UBUF))
    a(("LDW", ULEN)); a(("ADDI", 1)); a(("STW", ULEN)); a(("JMP", "ki_d"))
    a(("ki_bs:",)); a(("LDW", ULEN)); a(("JZ", "ki_d")); a(("SUBI", 1)); a(("STW", ULEN))
    a(("ki_d:",)); a(("LDI", 1)); a(("STW", DIRTY)); a(("RET",))

    # ---- boot + main ----
    a(("boot:",))
    for v in (ULEN, KEY, MB, MBP): a(("LDI", 0)); a(("STW", v))
    a(("LDI", TXL)); a(("STA", PALMAP+1)); a(("LDI", TXD)); a(("STA", PALMAP+2)); a(("LDI", BLK)); a(("STA", PALMAP+3))
    a(("LDI", 1)); a(("STW", DIRTY))
    a(("main:",))
    a(("LDW", KEY)); a(("JZ", "nokey")); a(("CALL", "keyin")); a(("LDI", 0)); a(("STW", KEY)); a(("nokey:",))
    a(("LDW", DIRTY)); a(("JZ", "nodraw")); a(("CALL", "render")); a(("LDI", 0)); a(("STW", DIRTY)); a(("nodraw:",))
    a(("FRAME",)); a(("JMP", "main"))
    return asm(L)


if __name__ == "__main__":
    m = make(); m.run(program(), max_i=5_000_000, frame_on=lambda mm: True)
    print("caos_uni boots; memsize", hex(m.memsize), "FONT16", hex(FONT16))
