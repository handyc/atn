#!/usr/bin/env python3
# caos_ca2.py — CA-OS/2: a native 32-bit operating system for the CA-2 machine, now with APPS.
#
# CA-2 (ca1sys make_machine("CA-2")) is the 32-bit member of the family: 32-bit registers/ALU
# (the verified 32-bit CA adder — cacpu.verify_adder_ca), 16 MB FLAT memory, word load/store.
# Written 32-bit-native: 512x384 framebuffer flat at 0x10000; pixels via a flat 32-bit indexed
# store (STAX FB, X = y*512 + x); coordinate math in 32-bit words (LDW/STW/ADDW/SUBW/CMPW).
#
# Desktop + taskbar LAUNCHER -> three real apps in a window:
#   * About  — honest self-description of the machine.
#   * Paint  — pick a colour, drag on the canvas to draw (uses the big screen).
#   * Calc   — a 32-bit calculator: + - x on numbers the 8-bit CA-1 literally cannot hold
#              (e.g. 12345 x 1000 = 12,345,000). Multiply is shift-add on the CA datapath.
import caos3 as c1                      # reuse the verified 5x7 font + palette
from ca1sys import asm, make_machine

W, H = 512, 384
FB = 0x10000
BLK, TEAL, SIL, GRY, WHT, NAV, LSV, BLU, RED, GRN = range(10)
# Book-quality 16x16 text needs a REAL alpha ramp, not 3 inks. And antialiasing only looks right when
# the ramp blends the actual INK over the actual PAPER — so every (ink, paper) pair the desktop uses
# gets its own 15-step ramp in the palette. A glyph carries a level 0..15 per pixel: level 0 stays
# transparent (the paper shows through); level L (1..15) -> palette index GRAMP+L, where GRAMP is the
# ramp base the current text is drawn with.  This is what makes both the page AND the chrome read as
# printed rather than as grey mush.
TXN = 15                                         # grey levels (4-bit minus the transparent 0)
def _hex(ci): return tuple(int(c1.PAL[ci][k:k+2], 16) for k in (1, 3, 5))
def _ramp(ink, paper, n=TXN):
    fi, bg = _hex(ink), _hex(paper)
    return ["#%02x%02x%02x" % tuple(round(bg[k]*(1-L/n) + fi[k]*L/n) for k in range(3)) for L in range(1, n+1)]
_PAL = list(c1.PAL); RAMP = {}
def _addramp(name, ink, paper): RAMP[name] = len(_PAL); _PAL.extend(_ramp(ink, paper))
_addramp("inkw", BLK, WHT)    # black on white  — Writer page / Calc display / anything on the page
_addramp("wnav", WHT, NAV)    # white on navy   — window titles, active launcher button
_addramp("ksil", BLK, SIL)    # black on silver — window-body labels, launcher, keypad, clock digits
_addramp("gsil", GRY, SIL)    # grey on silver  — secondary labels
_addramp("bsil", BLU, SIL)    # blue on silver  — accents
_addramp("nsil", NAV, SIL)    # navy on silver  — the Sheet total
PAL = _PAL
# advance widths (proportional) per codepoint, read at build time so chrome text lays out at compile time
def _load_adv(path="unifont16.json"):
    import json, base64, struct
    d = json.load(open(path)); cps = struct.unpack("<%dH" % d["n"], base64.b64decode(d["cps_b64"]))
    w = base64.b64decode(d["w_b64"]); return {cp: w[i] for i, cp in enumerate(cps)}
ADV = _load_adv()

# ---- OS variables, each given a slot of VS bytes so the SAME program runs on ANY word width up to
#      VS*8 bits: CA-2 (32-bit) uses 4 bytes of each slot, CA-3 (128-bit) uses all 16 — STW never
#      overruns into the next variable. (A word store writes word_bits/8 bytes, so 4-byte spacing
#      only worked on 32-bit; that was the bug that made the OS break on CA-3.) ----
VS = 16                                              # bytes per variable/cell slot -> word widths up to 128-bit
CELL_SHL = (VS).bit_length() - 1                     # log2(VS): SELC*VS via shifts
_VARS = ("AX AY AW AH ACOL GX GY GCH GCOL T0 T1 T2 T3 MX MY MB MBP "
         "CX CY OCX OCY HAVES CLKF CSEC DNV DH DT APP DIRTY PCOL "
         "CACC CCUR COP CFRESH TLEN KEY SELC CWV BDIRTY WI PFRESH "
         "WVX WVY DRAG DGX DGY MRX MRY "
         "UCP UGA UROW UCW GRAMP").split()        # + window/drag state + 16x16-glyph blitter registers (GRAMP = current text ramp base-1)
for _i, _n in enumerate(_VARS): globals()[_n] = _i * VS   # AX=0, AY=VS, ... laid out contiguously
CURBUF  = 0x0380          # cursor 8x8 save-under (byte-addressed -> width-independent)
CELLS   = 0x0F00          # sheet cells (12 x VS-byte words)
CSTRIDE = VS              # spacing between sheet cells (>= bytes-per-word on any supported machine)
# Writer goes Unicode: the document is 16x16 GNU-Unifont, so the machine needs more (virtual) RAM.
MEMSIZE = 0x1000000       # 16 MB — MUST be a power of two (memsize-1 is the address mask) so the 8 MB
                          #         FONT16 table at 0x100000..0x900000 (128 B/glyph antialiased) is addressable
TBUF    = 0x040000        # writer document as 16-bit codepoints (LE), just above the framebuffer
WTAB    = 0x080000        # advance width per codepoint (8 or 16), 1 byte x 0x10000
FONT16  = 0x100000        # direct codepoint->glyph table, 128 bytes/glyph (16 rows x 8 bytes, 4-bit AA)
CURSOR = [0x80, 0xC0, 0xE0, 0xF0, 0xF8, 0xFC, 0xE0, 0x40]

# window + taskbar geometry
WINX, WINY, WW, WH = 86, 38, 340, 306
# Sheet: 8x8 grid (column headers A-H, row headers 1-8)
SHX, SHY   = 22, 36     # grid origin: x after the row-number gutter, y after the column-header strip
SHCW, SHCH = 39, 30     # cell width / height
SHTOT      = SHY + 8*SHCH + 4    # y of the Total line (= 280)
TBY = H - 22                                # taskbar top (taller, to fit antialiased labels)
PSWATCH = [BLK, GRY, WHT, RED, GRN, BLU, NAV, TEAL]                # 8 paint colours
# calc keypad: (label, kind, value) ; kind: d=digit o=op(0+,1-,2x) e== c=clear
CALC_KEYS = [['7','8','9','x'], ['4','5','6','-'], ['1','2','3','+'], ['C','0','=','']]

def make():
    return make_machine("CA-2", fb_addr=FB, fb_w=W, fb_h=H, memsize=MEMSIZE)

def load_unifont(m, path="unifont16.json"):
    # expand the 16x16 GNU-Unifont table into FONT16 (direct cp->glyph) + WTAB (per-cp advance width)
    import json, zlib, base64, struct
    d = json.load(open(path)); blob = zlib.decompress(base64.b64decode(d["b64"]))
    cps = struct.unpack("<%dH" % d["n"], base64.b64decode(d["cps_b64"]))
    w = base64.b64decode(d["w_b64"])
    for i, cp in enumerate(cps):
        m.M[FONT16 + cp*128: FONT16 + cp*128 + 128] = blob[i*128:(i+1)*128]   # 4-bit AA, 128 B/glyph
        m.M[WTAB + cp] = w[i]                                            # proportional advance width

def program():
    L = []; a = L.append
    def shl(n):
        for _ in range(n): a(("SHL",))
    def shr(n):
        for _ in range(n): a(("SHR",))
    def rect(x, y, w, h, col):
        a(("LDI", x)); a(("STW", AX)); a(("LDI", y)); a(("STW", AY)); a(("LDI", w)); a(("STW", AW)); a(("LDI", h)); a(("STW", AH)); a(("LDI", col)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    # window-relative draw: coords are relative to the (draggable) window origin WVX/WVY
    def wrect(x, y, w, h, col):
        a(("LDW", WVX)); a(("ADDI", x)); a(("STW", AX)); a(("LDW", WVY)); a(("ADDI", y)); a(("STW", AY))
        a(("LDI", w)); a(("STW", AW)); a(("LDI", h)); a(("STW", AH)); a(("LDI", col)); a(("STW", ACOL)); a(("CALL", "fillrect"))
    # ---- antialiased chrome text: lay glyphs out proportionally (widths baked at build time) and draw
    #      them through the named ramp via blit16.  rel=True positions relative to the window origin. ----
    def textw(text):                                            # pixel width of a string in the AA font
        return sum(ADV.get(ord(ch), 8) for ch in text)
    def puts16(x, y, text, ramp=None, rel=False):
        if ramp is not None:                                    # ramp=None -> draw in whatever GRAMP the caller set
            a(("LDI", RAMP[ramp] - 1)); a(("STW", GRAMP))       # GRAMP = ramp base-1  (palette idx = GRAMP+level)
        cx = x
        for ch in text:
            cp = ord(ch)
            if rel:
                a(("LDW", WVX)); a(("ADDI", cx)); a(("STW", GX)); a(("LDW", WVY)); a(("ADDI", y)); a(("STW", GY))
            else:
                a(("LDI", cx)); a(("STW", GX)); a(("LDI", y)); a(("STW", GY))
            a(("LDI", cp)); a(("STW", UCP)); a(("CALL", "blit16"))
            cx += ADV.get(cp, 8)
    def wputs16(x, y, text, ramp): puts16(x, y, text, ramp, rel=True)
    def wctr16(cx, y, text, ramp):                              # window-relative, horizontally centred on cx
        wputs16(cx - textw(text)//2, y, text, ramp)
    a(("JMP", "boot"))

    # ---- fillrect ----
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

    # ---- blit16: draw the 16x16 antialiased glyph for codepoint UCP at (GX,GY) in the current ramp.
    #      128 B/glyph: 16 rows x 8 bytes, 2 px/byte (low nibble = left px); level 0 transparent,
    #      level 1..15 -> palette index GRAMP+level (GRAMP = ramp base-1, set by the caller). ----
    a(("blit16:",))
    a(("LDW", UCP)); shl(7); a(("STW", UGA))                # UGA = UCP*128 (offset into FONT16, 128 B/glyph)
    a(("LDI", 0)); a(("STW", UROW))
    a(("b16_row:",)); a(("LDW", UROW)); a(("CMPI", 16)); a(("JC", "b16_done"))
    a(("LDW", GY)); a(("ADDW", UROW)); shl(9); a(("ADDW", GX)); a(("STW", T1))   # T1 = FB index of (GX, GY+UROW)
    a(("LDW", UROW)); shl(3); a(("ADDW", UGA)); a(("STW", T0))                   # T0 = UGA + UROW*8 (8 bytes/row)
    for b in range(8):                                                          # 8 bytes -> 16 px (2 px/byte)
        a(("LDW", T0)); a(("ADDI", b)); a(("TAX",)); a(("LDAX", FONT16)); a(("STW", T2))
        a(("LDW", T2)); a(("ANDI", 0xF)); a(("JZ", f"b16lo{b}"))                 # left px = low nibble
        a(("ADDW", GRAMP)); a(("STW", T3))                                       # palette idx = GRAMP + level
        a(("LDW", T1)); a(("ADDI", b*2)); a(("TAX",)); a(("LDW", T3)); a(("STAX", FB))
        a((f"b16lo{b}:",))
        a(("LDW", T2)); shr(4); a(("ANDI", 0xF)); a(("JZ", f"b16hi{b}"))         # right px = high nibble
        a(("ADDW", GRAMP)); a(("STW", T3))
        a(("LDW", T1)); a(("ADDI", b*2+1)); a(("TAX",)); a(("LDW", T3)); a(("STAX", FB))
        a((f"b16hi{b}:",))
    a(("LDW", UROW)); a(("ADDI", 1)); a(("STW", UROW)); a(("JMP", "b16_row"))
    a(("b16_done:",)); a(("RET",))

    powers = [1000000000, 100000000, 10000000, 1000000, 100000, 10000, 1000, 100, 10, 1]
    # ---- dnum16: draw DNV as decimal at (GX,GY) in the current ramp via blit16 (leading zeros suppressed) ----
    dw = ADV.get(ord("0"), 9)                                   # tabular digit advance
    a(("dnum16:",)); a(("LDI", 0)); a(("STW", DT))
    for ip, p in enumerate(powers):
        a(("LDI", 0)); a(("STW", DH))
        a((f"d16n{ip}:",)); a(("LDW", DNV)); a(("CMPI", p)); a(("JNC", f"d16d{ip}")); a(("SUBI", p)); a(("STW", DNV)); a(("LDW", DH)); a(("ADDI", 1)); a(("STW", DH)); a(("JMP", f"d16n{ip}"))
        a((f"d16d{ip}:",))
        a(("LDW", DH)); a(("JNZ", f"d16s{ip}")); a(("LDW", DT)); a(("JNZ", f"d16s{ip}"))
        a(("JMP", (f"d16s{ip}" if p == 1 else f"d16k{ip}")))
        a((f"d16s{ip}:",)); a(("LDI", 1)); a(("STW", DT))
        a(("LDW", DH)); a(("ADDI", 48)); a(("STW", UCP)); a(("CALL", "blit16")); a(("LDW", GX)); a(("ADDI", dw)); a(("STW", GX))   # digit '0'+DH
        a((f"d16k{ip}:",))
    a(("RET",))

    # ---- 32-bit multiply (shift-add): CACC = CACC * CCUR ----
    a(("mul32:",)); a(("LDI", 0)); a(("STW", T0)); a(("LDW", CACC)); a(("STW", T1)); a(("LDW", CCUR)); a(("STW", T2))
    a(("ml:",)); a(("LDW", T2)); a(("JZ", "mld"))
    a(("LDW", T2)); a(("ANDI", 1)); a(("JZ", "mlno")); a(("LDW", T0)); a(("ADDW", T1)); a(("STW", T0))
    a(("mlno:",)); a(("LDW", T1)); a(("SHL",)); a(("STW", T1)); a(("LDW", T2)); a(("SHR",)); a(("STW", T2)); a(("JMP", "ml"))
    a(("mld:",)); a(("LDW", T0)); a(("STW", CACC)); a(("RET",))

    # ============ DESKTOP + WINDOW + APPS ============
    a(("draw:",))
    rect(0, 0, W, H, TEAL)                                   # background
    rect(0, TBY, W, 22, SIL); rect(0, TBY-1, W, 1, WHT)      # taskbar
    # launcher buttons (index == APP id); active button -> navy fill + white label
    for i, name in enumerate(["About", "Paint", "Calc", "Writer", "Sheet"]):
        bx = 4 + i*54
        rect(bx, TBY+3, 50, 16, SIL)
        a(("LDI", bx)); a(("STW", AX)); a(("LDI", TBY+3)); a(("STW", AY)); a(("LDI", 50)); a(("STW", AW)); a(("LDI", 16)); a(("STW", AH))
        a(("LDW", APP)); a(("CMPI", i)); a(("JNZ", f"lb{i}")); a(("LDI", NAV)); a(("STW", ACOL)); a(("CALL", "fillrect")); a((f"lb{i}:",))
        a(("LDI", RAMP["ksil"] - 1)); a(("STW", GRAMP))                                                                  # inactive: black on silver
        a(("LDW", APP)); a(("CMPI", i)); a(("JNZ", f"lg{i}")); a(("LDI", RAMP["wnav"] - 1)); a(("STW", GRAMP)); a((f"lg{i}:",))   # active: white on navy
        puts16(bx + (50 - textw(name))//2, TBY+3, name, rel=False)
    # window frame + title
    wrect(0, 0, WW, WH, SIL)
    wrect(0, 0, WW, 18, NAV)
    a(("LDW", APP)); a(("CMPI", 1)); a(("JZ", "ti_p")); a(("CMPI", 2)); a(("JZ", "ti_c")); a(("CMPI", 3)); a(("JZ", "ti_w")); a(("CMPI", 4)); a(("JZ", "ti_s"))
    wputs16(8, 1, "About CA-OS/2", "wnav"); a(("JMP", "ti_d"))
    a(("ti_p:",)); wputs16(8, 1, "Paint", "wnav"); a(("JMP", "ti_d"))
    a(("ti_c:",)); wputs16(8, 1, "Calc — 32-bit", "wnav"); a(("JMP", "ti_d"))
    a(("ti_w:",)); wputs16(8, 1, "Writer", "wnav"); a(("JMP", "ti_d"))
    a(("ti_s:",)); wputs16(8, 1, "Sheet — 32-bit cells", "wnav")
    a(("ti_d:",))
    # body by app
    a(("LDW", APP)); a(("CMPI", 1)); a(("JZ", "body_p")); a(("CMPI", 2)); a(("JZ", "body_c")); a(("CMPI", 3)); a(("JZ", "body_w")); a(("CMPI", 4)); a(("JZ", "body_s"))
    a(("CALL", "draw_about")); a(("JMP", "draw_d"))
    a(("body_p:",)); a(("CALL", "draw_paint")); a(("JMP", "draw_d"))
    a(("body_c:",)); a(("CALL", "draw_calc")); a(("JMP", "draw_d"))
    a(("body_w:",)); a(("CALL", "draw_writer")); a(("JMP", "draw_d"))
    a(("body_s:",)); a(("CALL", "draw_sheet"))
    a(("draw_d:",)); a(("CALL", "drawclock")); a(("RET",))
    # body-only redraw: just the active app's window interior (skips the 196608-px desktop fill)
    a(("drawbody:",))
    a(("LDW", APP)); a(("CMPI", 1)); a(("JZ", "db_p")); a(("CMPI", 2)); a(("JZ", "db_c")); a(("CMPI", 3)); a(("JZ", "db_w")); a(("CMPI", 4)); a(("JZ", "db_s"))
    a(("CALL", "draw_about")); a(("RET",))
    a(("db_p:",)); a(("CALL", "draw_paint")); a(("RET",))
    a(("db_c:",)); a(("CALL", "draw_calc")); a(("RET",))
    a(("db_w:",)); a(("CALL", "draw_writer")); a(("RET",))
    a(("db_s:",)); a(("CALL", "draw_sheet")); a(("RET",))

    # ---- About app ----
    a(("draw_about:",))
    bx, by, ph = 14, 26, 19
    wputs16(bx, by+0*ph, "CA-2 — a 32-bit processor", "ksil")
    wputs16(bx, by+1*ph, "RAM: 16 MB (flat)   Screen: 512×384", "ksil")
    wputs16(bx, by+2*ph, "Datapath: genuine cellular automata", "gsil")
    wputs16(bx, by+3*ph, "(hex K=4 gliders) — NAND + latch", "gsil")
    wputs16(bx, by+4*ph, "ALU: 32-bit CA adder, verified", "bsil")
    wputs16(bx, by+5*ph, "One core builds the whole family:", "ksil")
    wputs16(bx, by+6*ph, "CA-1 (8-bit) … CA-2 (32-bit) …", "ksil")
    wputs16(bx, by+7*ph, "Apps: Paint · Calc · Writer · Sheet", "ksil")
    wputs16(bx, by+8*ph, "— use the launcher in the taskbar.", "gsil")
    a(("RET",))

    # ---- Paint app: palette strip + canvas ----
    a(("draw_paint:",))
    for i, col in enumerate(PSWATCH):
        sx = 10 + i*30
        wrect(sx, 20, 26, 16, col)
        a(("LDW", PCOL)); a(("CMPI", col)); a(("JNZ", f"ps{i}"))
        wrect(sx, 18, 26, 2, WHT); wrect(sx, 36, 26, 2, WHT); a((f"ps{i}:",))
    a(("LDW", PFRESH)); a(("JZ", "dp_keep"))                 # only wipe the canvas on open, not on every palette pick
    wrect(10, 42, WW-20, WH-54, WHT)               # canvas (white)
    a(("LDI", 0)); a(("STW", PFRESH))
    a(("dp_keep:",)); a(("RET",))

    # ---- Calc app: 32-bit display + keypad ----
    a(("draw_calc:",))
    wrect(12, 22, WW-24, 28, WHT)                  # display
    a(("LDI", RAMP["inkw"] - 1)); a(("STW", GRAMP))
    a(("LDW", CCUR)); a(("STW", DNV)); a(("LDW", WVX)); a(("ADDI", 18)); a(("STW", GX)); a(("LDW", WVY)); a(("ADDI", 28)); a(("STW", GY)); a(("CALL", "dnum16"))
    for r in range(4):
        for c in range(4):
            lab = CALC_KEYS[r][c]
            if not lab: continue
            bx = 18 + c*78; by = 58 + r*52
            wrect(bx, by, 70, 44, SIL)
            wrect(bx, by, 70, 1, WHT); wrect(bx, by, 1, 44, WHT)            # raised highlight (top/left)
            wrect(bx, by+43, 70, 1, GRY); wrect(bx+69, by, 1, 44, GRY)     # shadow (bottom/right)
            wctr16(bx+35, by+14, lab, "ksil")
    a(("RET",))

    # ---- clock (taskbar, right): "up <seconds> s" ----
    a(("drawclock:",))
    rect(W-80, TBY+3, 76, 16, SIL)
    puts16(W-78, TBY+3, "up", "gsil")
    a(("LDI", RAMP["ksil"] - 1)); a(("STW", GRAMP))
    a(("LDW", CSEC)); a(("STW", DNV)); a(("LDI", W-56)); a(("STW", GX)); a(("LDI", TBY+3)); a(("STW", GY)); a(("CALL", "dnum16"))
    puts16(W-20, TBY+3, "s", "gsil")
    a(("RET",))

    # ---- cursor (8x8 save-under + arrow) ----
    a(("saveun:",)); a(("LDI", 0)); a(("STW", T1))
    a(("su_r:",)); a(("LDW", T1)); a(("CMPI", 8)); a(("JC", "su_d")); a(("LDI", 0)); a(("STW", T2))
    a(("su_c:",)); a(("LDW", T2)); a(("CMPI", 8)); a(("JC", "su_nr"))
    a(("LDW", CY)); a(("ADDW", T1)); shl(9); a(("STW", T0)); a(("LDW", CX)); a(("ADDW", T2)); a(("ADDW", T0)); a(("TAX",)); a(("LDAX", FB)); a(("STW", T3))
    a(("LDW", T1)); shl(3); a(("ADDW", T2)); a(("TAX",)); a(("LDA", T3)); a(("STAX", CURBUF))
    a(("LDW", T2)); a(("ADDI", 1)); a(("STW", T2)); a(("JMP", "su_c"))
    a(("su_nr:",)); a(("LDW", T1)); a(("ADDI", 1)); a(("STW", T1)); a(("JMP", "su_r"))
    a(("su_d:",)); a(("RET",))
    a(("restun:",)); a(("LDI", 0)); a(("STW", T1))
    a(("ru_r:",)); a(("LDW", T1)); a(("CMPI", 8)); a(("JC", "ru_d")); a(("LDI", 0)); a(("STW", T2))
    a(("ru_c:",)); a(("LDW", T2)); a(("CMPI", 8)); a(("JC", "ru_nr"))
    a(("LDW", T1)); shl(3); a(("ADDW", T2)); a(("TAX",)); a(("LDAX", CURBUF)); a(("STW", T3))
    a(("LDW", OCY)); a(("ADDW", T1)); shl(9); a(("STW", T0)); a(("LDW", OCX)); a(("ADDW", T2)); a(("ADDW", T0)); a(("TAX",)); a(("LDA", T3)); a(("STAX", FB))
    a(("LDW", T2)); a(("ADDI", 1)); a(("STW", T2)); a(("JMP", "ru_c"))
    a(("ru_nr:",)); a(("LDW", T1)); a(("ADDI", 1)); a(("STW", T1)); a(("JMP", "ru_r"))
    a(("ru_d:",)); a(("RET",))
    a(("drawcur:",))
    for dy, rowmask in enumerate(CURSOR):
        a(("LDW", CY)); a(("ADDI", dy)); shl(9); a(("STW", T0)); a(("LDW", CX)); a(("ADDW", T0)); a(("STW", T1))
        for dx in range(8):
            if rowmask & (0x80 >> dx):
                a(("LDW", T1)); a(("ADDI", dx)); a(("TAX",)); a(("LDI", BLK)); a(("STAX", FB))
    a(("RET",))

    # ---- paint dab: 4x4 block at (CX,CY) in PCOL (only if over the Paint canvas) ----
    a(("paintdab:",))
    a(("LDW", APP)); a(("CMPI", 1)); a(("JNZ", "pd_no"))
    a(("LDW", CX)); a(("SUBW", WVX)); a(("CMPI", 10)); a(("JNC", "pd_no")); a(("LDW", CX)); a(("SUBW", WVX)); a(("CMPI", WW-12)); a(("JC", "pd_no"))
    a(("LDW", CY)); a(("SUBW", WVY)); a(("CMPI", 42)); a(("JNC", "pd_no")); a(("LDW", CY)); a(("SUBW", WVY)); a(("CMPI", WH-12)); a(("JC", "pd_no"))
    a(("LDI", 0)); a(("STW", T2))                            # dy
    a(("pd_r:",)); a(("LDW", T2)); a(("CMPI", 4)); a(("JC", "pd_no")); a(("LDI", 0)); a(("STW", T3))
    a(("pd_c:",)); a(("LDW", T3)); a(("CMPI", 4)); a(("JC", "pd_nr"))
    a(("LDW", CY)); a(("ADDW", T2)); shl(9); a(("STW", T0)); a(("LDW", CX)); a(("ADDW", T3)); a(("ADDW", T0)); a(("TAX",)); a(("LDA", PCOL)); a(("STAX", FB))
    a(("LDW", T3)); a(("ADDI", 1)); a(("STW", T3)); a(("JMP", "pd_c"))
    a(("pd_nr:",)); a(("LDW", T2)); a(("ADDI", 1)); a(("STW", T2)); a(("JMP", "pd_r"))
    a(("pd_no:",)); a(("RET",))

    # ============ click handling ============
    a(("onclick:",))
    a(("LDW", MX)); a(("SUBW", WVX)); a(("STW", MRX))     # mouse position relative to the window origin
    a(("LDW", MY)); a(("SUBW", WVY)); a(("STW", MRY))
    # launcher buttons (taskbar): About/Paint/Calc/Writer/Sheet
    for i in range(5):
        bx = 4 + i*54
        a(("LDW", MX)); a(("CMPI", bx)); a(("JNC", f"nl{i}")); a(("CMPI", bx+50)); a(("JC", f"nl{i}"))
        a(("LDW", MY)); a(("CMPI", TBY+3)); a(("JNC", f"nl{i}")); a(("CMPI", TBY+19)); a(("JC", f"nl{i}"))
        a(("LDI", i)); a(("STW", APP)); a(("LDI", 1)); a(("STW", DIRTY))
        if i == 1: a(("LDI", 1)); a(("STW", PFRESH))          # opening Paint -> fresh white canvas
        a(("RET",)); a((f"nl{i}:",))
    # title bar grab -> start dragging (MRX in [0,WW), MRY in [0,18); underflow wraps high -> skipped)
    a(("LDW", MRY)); a(("CMPI", 18)); a(("JC", "no_grab")); a(("LDW", MRX)); a(("CMPI", WW)); a(("JC", "no_grab"))
    a(("LDI", 1)); a(("STW", DRAG)); a(("LDW", MRX)); a(("STW", DGX)); a(("LDW", MRY)); a(("STW", DGY)); a(("RET",))
    a(("no_grab:",))
    # in-app clicks
    a(("LDW", APP)); a(("CMPI", 1)); a(("JZ", "oc_paint")); a(("CMPI", 2)); a(("JZ", "oc_calc")); a(("CMPI", 4)); a(("JZ", "oc_sheet")); a(("RET",))
    # Sheet: click selects a cell — compute col/row by repeated subtraction (no divide op), SELC=row*8+col
    a(("oc_sheet:",))
    a(("LDW", MRX)); a(("CMPI", SHX)); a(("JNC", "oc_s_no")); a(("CMPI", SHX+8*SHCW)); a(("JC", "oc_s_no"))
    a(("LDW", MRY)); a(("CMPI", SHY)); a(("JNC", "oc_s_no")); a(("CMPI", SHY+8*SHCH)); a(("JC", "oc_s_no"))
    a(("LDW", MRX)); a(("SUBI", SHX)); a(("STW", T2)); a(("LDI", 0)); a(("STW", T0))      # col
    a(("ocsc:",)); a(("LDW", T2)); a(("CMPI", SHCW)); a(("JNC", "ocsc_d")); a(("SUBI", SHCW)); a(("STW", T2)); a(("LDW", T0)); a(("ADDI", 1)); a(("STW", T0)); a(("JMP", "ocsc"))
    a(("ocsc_d:",))
    a(("LDW", MRY)); a(("SUBI", SHY)); a(("STW", T2)); a(("LDI", 0)); a(("STW", T1))      # row
    a(("ocsr:",)); a(("LDW", T2)); a(("CMPI", SHCH)); a(("JNC", "ocsr_d")); a(("SUBI", SHCH)); a(("STW", T2)); a(("LDW", T1)); a(("ADDI", 1)); a(("STW", T1)); a(("JMP", "ocsr"))
    a(("ocsr_d:",))
    a(("LDW", T1)); shl(3); a(("ADDW", T0)); a(("STW", SELC)); a(("LDI", 1)); a(("STW", BDIRTY)); a(("RET",))
    a(("oc_s_no:",)); a(("RET",))
    # Paint: palette swatches
    a(("oc_paint:",))
    for i, col in enumerate(PSWATCH):
        sx = 10 + i*30
        a(("LDW", MRX)); a(("CMPI", sx)); a(("JNC", f"np{i}")); a(("CMPI", sx+26)); a(("JC", f"np{i}"))
        a(("LDW", MRY)); a(("CMPI", 20)); a(("JNC", f"np{i}")); a(("CMPI", 36)); a(("JC", f"np{i}"))
        a(("LDI", col)); a(("STW", PCOL)); a(("LDI", 1)); a(("STW", BDIRTY)); a(("RET",)); a((f"np{i}:",))
    a(("RET",))
    # Calc: keypad
    a(("oc_calc:",))
    for r in range(4):
        for c in range(4):
            lab = CALC_KEYS[r][c]
            if not lab: continue
            bx = 18 + c*78; by = 58 + r*52; t = f"ck{r}_{c}"
            a(("LDW", MRX)); a(("CMPI", bx)); a(("JNC", t)); a(("CMPI", bx+70)); a(("JC", t))
            a(("LDW", MRY)); a(("CMPI", by)); a(("JNC", t)); a(("CMPI", by+44)); a(("JC", t))
            if lab.isdigit():
                # CCUR = CCUR*10 + d   (10x via *8 + *2)
                a(("LDW", CFRESH)); a(("JZ", f"cd{r}_{c}")); a(("LDI", 0)); a(("STW", CCUR)); a(("LDI", 0)); a(("STW", CFRESH)); a((f"cd{r}_{c}:",))
                a(("LDW", CCUR)); shl(3); a(("STW", T0)); a(("LDW", CCUR)); a(("SHL",)); a(("ADDW", T0)); a(("ADDI", int(lab))); a(("STW", CCUR))
            elif lab == 'C':
                a(("LDI", 0)); a(("STW", CCUR)); a(("STW", CACC)); a(("STW", COP)); a(("LDI", 1)); a(("STW", CFRESH))
            elif lab in '+-x':
                a(("CALL", "calc_apply"))
                a(("LDI", {'+':0,'-':1,'x':2}[lab])); a(("STW", COP)); a(("LDI", 1)); a(("STW", CFRESH))
            elif lab == '=':
                a(("CALL", "calc_apply")); a(("LDW", CACC)); a(("STW", CCUR)); a(("LDI", 0)); a(("STW", COP)); a(("LDI", 1)); a(("STW", CFRESH))
            a(("LDI", 1)); a(("STW", BDIRTY)); a(("RET",)); a((f"{t}:",))
    a(("RET",))
    # calc_apply: fold CCUR into CACC using COP (first op just loads CACC)
    a(("calc_apply:",))
    a(("LDW", COP)); a(("CMPI", 0)); a(("JNZ", "ca_ns")); a(("LDW", CACC)); a(("ADDW", CCUR)); a(("STW", CACC)); a(("RET",))
    a(("ca_ns:",)); a(("CMPI", 1)); a(("JNZ", "ca_nm")); a(("LDW", CACC)); a(("SUBW", CCUR)); a(("STW", CACC)); a(("RET",))
    a(("ca_nm:",)); a(("CMPI", 2)); a(("JNZ", "ca_load")); a(("CALL", "mul32")); a(("RET",))
    a(("ca_load:",)); a(("LDW", CCUR)); a(("STW", CACC)); a(("RET",))

    # ---- Writer: a text editor (renders TBUF with wrap + caret) ----
    a(("draw_writer:",))               # 16x16 Unicode document: TBUF holds 16-bit codepoints
    wrect(10, 22, WW-20, WH-32, WHT)
    a(("LDI", RAMP["inkw"] - 1)); a(("STW", GRAMP))    # black-on-white page ramp for the document text
    a(("LDI", 0)); a(("STW", WI)); a(("LDW", WVX)); a(("ADDI", 12)); a(("STW", GX)); a(("LDW", WVY)); a(("ADDI", 24)); a(("STW", GY))
    a(("dw_l:",)); a(("LDW", WI)); a(("CMPW", TLEN)); a(("JC", "dw_car"))
    a(("LDW", WI)); a(("SHL",)); a(("TAX",)); a(("LDAX", TBUF)); a(("STW", UCP))                                  # CP low byte
    a(("LDW", WI)); a(("SHL",)); a(("ADDI", 1)); a(("TAX",)); a(("LDAX", TBUF)); shl(8); a(("ADDW", UCP)); a(("STW", UCP))   # | high<<8
    a(("LDW", UCP)); a(("CMPI", 0x0A)); a(("JZ", "dw_nl"))                                                       # newline
    a(("CALL", "blit16"))
    a(("LDW", UCP)); a(("TAX",)); a(("LDAX", WTAB)); a(("STW", UCW))                                             # advance width (8/16)
    a(("LDW", GX)); a(("ADDW", UCW)); a(("STW", GX)); a(("SUBW", WVX)); a(("CMPI", WW-18)); a(("JNC", "dw_nx"))   # wrap
    a(("dw_nl:",)); a(("LDW", WVX)); a(("ADDI", 12)); a(("STW", GX)); a(("LDW", GY)); a(("ADDI", 18)); a(("STW", GY))
    a(("dw_nx:",)); a(("LDW", WI)); a(("ADDI", 1)); a(("STW", WI)); a(("JMP", "dw_l"))
    a(("dw_car:",)); a(("LDW", GX)); a(("STW", AX)); a(("LDW", GY)); a(("STW", AY)); a(("LDI", 2)); a(("STW", AW)); a(("LDI", 16)); a(("STW", AH)); a(("LDI", BLK)); a(("STW", ACOL)); a(("CALL", "fillrect")); a(("RET",))

    # ---- Sheet: 8x8 grid of 32-bit cells (A-H x 1-8) + a CA-summed Total ----
    a(("draw_sheet:",))
    for c in range(8):                                                     # column headers A-H
        wctr16(SHX + c*SHCW + SHCW//2, 21, chr(ord("A")+c), "gsil")
    for r in range(8):                                                     # row headers 1-8
        wctr16(12, SHY + r*SHCH + (SHCH-16)//2, chr(ord("1")+r), "gsil")
    for idx in range(64):
        r, c = idx//8, idx%8; cx, cy = SHX + c*SHCW, SHY + r*SHCH
        wrect(cx, cy, SHCW, SHCH, GRY)                                     # cell border
        a(("LDW", SELC)); a(("CMPI", idx)); a(("JNZ", f"shw{idx}"))
        wrect(cx+1, cy+1, SHCW-2, SHCH-2, LSV); a(("JMP", f"shv{idx}"))    # selected cell highlighted
        a((f"shw{idx}:",)); wrect(cx+1, cy+1, SHCW-2, SHCH-2, WHT); a((f"shv{idx}:",))
        a(("LDI", RAMP["inkw"] - 1)); a(("STW", GRAMP)); a(("LDW", CELLS+idx*CSTRIDE)); a(("STW", DNV)); a(("LDW", WVX)); a(("ADDI", cx+4)); a(("STW", GX)); a(("LDW", WVY)); a(("ADDI", cy+(SHCH-16)//2)); a(("STW", GY)); a(("CALL", "dnum16"))
    a(("LDW", CELLS))                                                      # Total = sum of all 64 cells
    for i in range(1, 64): a(("ADDW", CELLS+i*CSTRIDE))
    a(("STW", DNV))
    wrect(8, SHTOT, WW-16, 18, SIL)                                        # clear the total line (redraws each keystroke)
    wputs16(10, SHTOT, "Total =", "ksil")
    a(("LDI", RAMP["nsil"] - 1)); a(("STW", GRAMP)); a(("LDW", WVX)); a(("ADDI", 10 + textw("Total = "))); a(("STW", GX)); a(("LDW", WVY)); a(("ADDI", SHTOT)); a(("STW", GY)); a(("CALL", "dnum16")); a(("RET",))

    # ---- keyboard input (Writer append/backspace ; Sheet digit -> selected cell) ----
    a(("keyin:",)); a(("LDW", APP)); a(("CMPI", 3)); a(("JZ", "ki_w")); a(("LDW", APP)); a(("CMPI", 4)); a(("JZ", "ki_s")); a(("RET",))
    a(("ki_w:",)); a(("LDW", KEY)); a(("CMPI", 8)); a(("JZ", "ki_bs"))            # backspace = codepoint 8
    a(("LDW", TLEN)); a(("CMPI", 1800)); a(("JC", "ki_wd"))
    a(("LDW", TLEN)); a(("SHL",)); a(("TAX",)); a(("LDW", KEY)); a(("STAX", TBUF))   # TBUF[TLEN] low byte
    a(("LDW", TLEN)); a(("SHL",)); a(("ADDI", 1)); a(("TAX",)); a(("LDW", KEY))
    for _ in range(8): a(("SHR",))                                                  # high byte = KEY>>8
    a(("STAX", TBUF)); a(("LDW", TLEN)); a(("ADDI", 1)); a(("STW", TLEN)); a(("JMP", "ki_wdt"))
    a(("ki_bs:",)); a(("LDW", TLEN)); a(("JZ", "ki_wd")); a(("SUBI", 1)); a(("STW", TLEN))
    a(("ki_wdt:",)); a(("LDI", 1)); a(("STW", BDIRTY)); a(("ki_wd:",)); a(("RET",))
    a(("ki_s:",)); a(("LDW", KEY)); a(("CMPI", 8)); a(("JZ", "ks_clr"))            # backspace clears the cell
    a(("LDW", KEY)); a(("CMPI", 0x30)); a(("JNC", "ki_sd")); a(("LDW", KEY)); a(("CMPI", 0x3A)); a(("JC", "ki_sd"))   # only '0'..'9'
    a(("ks_dig:",)); a(("CALL", "cell_read")); a(("STW", T3)); a(("CMPI", 100000000)); a(("JC", "ki_sd"))
    a(("LDW", T3)); shl(3); a(("STW", T2)); a(("LDW", T3)); a(("SHL",)); a(("ADDW", T2)); a(("ADDW", KEY)); a(("SUBI", 0x30)); a(("STW", CWV)); a(("CALL", "cell_write"))
    a(("ks_d:",)); a(("LDI", 1)); a(("STW", BDIRTY)); a(("ki_sd:",)); a(("RET",))
    a(("ks_clr:",)); a(("LDI", 0)); a(("STW", CWV)); a(("CALL", "cell_write")); a(("JMP", "ks_d"))
    # cell_read -> A = CELLS[SELC] (assemble 4 bytes) ; cell_write: CWV -> CELLS[SELC]
    a(("cell_read:",)); a(("LDW", SELC)); shl(CELL_SHL); a(("STW", T0)); a(("LDI", 0)); a(("STW", T1))   # T0 = SELC*VS
    for b in range(4):
        a(("LDW", T0)); a(("ADDI", b)); a(("TAX",)); a(("LDAX", CELLS))
        for _ in range(8*b): a(("SHL",))
        a(("ADDW", T1)); a(("STW", T1))
    a(("LDW", T1)); a(("RET",))
    a(("cell_write:",)); a(("LDW", SELC)); shl(CELL_SHL); a(("STW", T0))   # T0 = SELC*VS
    for b in range(4):
        a(("LDW", CWV))
        for _ in range(8*b): a(("SHR",))
        a(("ANDI", 0xFF)); a(("STW", T1)); a(("LDW", T0)); a(("ADDI", b)); a(("TAX",)); a(("LDW", T1)); a(("STAX", CELLS))
    a(("RET",))

    # ============ boot + main ============
    a(("boot:",))
    for v in (MB, MBP, HAVES, CLKF, CSEC, APP, PCOL, CACC, CCUR, COP, TLEN, KEY, SELC, CWV, BDIRTY, PFRESH, DRAG): a(("LDI", 0)); a(("STW", v))
    for i in range(64): a(("LDI", 0)); a(("STW", CELLS+i*CSTRIDE))   # clear all 64 sheet cells (full VS-byte slot)
    a(("LDI", 1)); a(("STW", CFRESH)); a(("STW", DIRTY)); a(("LDI", RED)); a(("STW", PCOL))
    a(("LDI", WINX)); a(("STW", WVX)); a(("LDI", WINY)); a(("STW", WVY))    # window starts at the default position
    a(("LDI", W//2)); a(("STW", CX)); a(("STW", OCX)); a(("LDI", H//2)); a(("STW", CY)); a(("STW", OCY))
    a(("main:",))
    # mouse -> CX,CY (clamp)
    a(("LDW", MX)); a(("CMPI", W-8)); a(("JNC", "mxok")); a(("LDI", W-8)); a(("STW", CX)); a(("JMP", "mxd")); a(("mxok:",)); a(("LDW", MX)); a(("STW", CX)); a(("mxd:",))
    a(("LDW", MY)); a(("CMPI", H-8)); a(("JNC", "myok")); a(("LDI", H-8)); a(("STW", CY)); a(("JMP", "myd")); a(("myok:",)); a(("LDW", MY)); a(("STW", CY)); a(("myd:",))
    # click edge -> onclick
    a(("LDW", MB)); a(("JZ", "noclick")); a(("LDW", MBP)); a(("JNZ", "noclick")); a(("CALL", "onclick")); a(("noclick:",))
    # window drag: while held, move the window to follow the cursor (origin = mouse - grab offset, clamped on-screen)
    a(("LDW", DRAG)); a(("JZ", "nodrag"))
    a(("LDW", MB)); a(("JNZ", "dragmv")); a(("LDI", 0)); a(("STW", DRAG)); a(("JMP", "nodrag"))
    a(("dragmv:",))
    a(("LDW", MX)); a(("CMPW", DGX)); a(("JNC", "drg_xlo")); a(("LDW", MX)); a(("SUBW", DGX)); a(("STW", WVX)); a(("JMP", "drg_xhi"))
    a(("drg_xlo:",)); a(("LDI", 0)); a(("STW", WVX))
    a(("drg_xhi:",)); a(("LDW", WVX)); a(("CMPI", W-WW+1)); a(("JNC", "drg_xok")); a(("LDI", W-WW)); a(("STW", WVX)); a(("drg_xok:",))
    a(("LDW", MY)); a(("CMPW", DGY)); a(("JNC", "drg_ylo")); a(("LDW", MY)); a(("SUBW", DGY)); a(("STW", WVY)); a(("JMP", "drg_yhi"))
    a(("drg_ylo:",)); a(("LDI", 0)); a(("STW", WVY))
    a(("drg_yhi:",)); a(("LDW", WVY)); a(("CMPI", H-18-WH+1)); a(("JNC", "drg_yok")); a(("LDI", H-18-WH)); a(("STW", WVY)); a(("drg_yok:",))
    a(("LDI", 1)); a(("STW", DIRTY))                       # window moved -> full redraw clears the old position
    a(("nodrag:",))
    # paint: while button held over canvas, draw (but not while dragging the window)
    a(("LDW", DRAG)); a(("JNZ", "nopaint")); a(("LDW", MB)); a(("JZ", "nopaint")); a(("CALL", "paintdab")); a(("nopaint:",))
    a(("LDW", MB)); a(("STW", MBP))
    # keyboard: KEY holds (glyph index + 1), 0 = none (so digit '0' = glyph 0 isn't lost); decode -1
    a(("LDW", KEY)); a(("JZ", "nokey")); a(("CALL", "keyin")); a(("LDI", 0)); a(("STW", KEY)); a(("nokey:",))   # KEY = Unicode codepoint (0=none, 8=BS, 10=NL)
    # full redraw on DIRTY (app switch / button / palette / paint stroke region)
    a(("LDW", DIRTY)); a(("JZ", "chkbody"))
    a(("LDW", HAVES)); a(("JZ", "nrd1")); a(("CALL", "restun")); a(("nrd1:",))
    a(("CALL", "draw")); a(("LDI", 0)); a(("STW", DIRTY)); a(("LDI", 0)); a(("STW", BDIRTY)); a(("LDI", 0)); a(("STW", HAVES)); a(("JMP", "nodraw"))
    a(("chkbody:",)); a(("LDW", BDIRTY)); a(("JZ", "nodraw")); a(("LDW", HAVES)); a(("JZ", "nrd2")); a(("CALL", "restun")); a(("nrd2:",))
    a(("CALL", "drawbody")); a(("LDI", 0)); a(("STW", BDIRTY)); a(("LDI", 0)); a(("STW", HAVES)); a(("nodraw:",))
    # clock tick (uptime seconds, 0..999)
    a(("LDW", CLKF)); a(("ADDI", 1)); a(("STW", CLKF)); a(("CMPI", 60)); a(("JNC", "noclk"))
    a(("LDI", 0)); a(("STW", CLKF)); a(("LDW", CSEC)); a(("ADDI", 1)); a(("STW", T0)); a(("LDW", T0)); a(("CMPI", 1000)); a(("JNC", "csok")); a(("LDI", 0)); a(("STW", T0)); a(("csok:",)); a(("LDW", T0)); a(("STW", CSEC))
    a(("LDW", HAVES)); a(("JZ", "ck_nr")); a(("CALL", "restun")); a(("ck_nr:",)); a(("CALL", "drawclock")); a(("LDI", 0)); a(("STW", HAVES))
    a(("noclk:",))
    # cursor: restore old, save new, draw
    a(("LDW", HAVES)); a(("JZ", "norest")); a(("CALL", "restun")); a(("norest:",))
    a(("CALL", "saveun")); a(("LDI", 1)); a(("STW", HAVES)); a(("LDW", CX)); a(("STW", OCX)); a(("LDW", CY)); a(("STW", OCY)); a(("CALL", "drawcur"))
    a(("FRAME",)); a(("JMP", "main"))
    return asm(L)


if __name__ == "__main__":
    m = make(); load_unifont(m)
    m.M[MX:MX+4] = (W//2).to_bytes(4, "little"); m.M[MY:MY+4] = (H//2).to_bytes(4, "little")
    m.run(program(), max_i=30_000_000, frame_on=lambda mm: True)
    print("CA-OS/2 booted:", sum(1 for v in m.M[FB:FB+W*H] if v != TEAL), "non-bg px; Writer is 16x16 Unicode")
