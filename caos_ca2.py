#!/usr/bin/env python3
# caos_ca2.py — CA-OS/2: a native 32-bit operating system for the CA-2 machine, now with APPS.
#
# CA-2 (ca1sys make_machine("CA-2")) is the 32-bit member of the family: 32-bit registers/ALU
# (the verified 32-bit CA adder — cacpu.verify_adder_ca), 1 MB FLAT memory, word load/store.
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
PAL = c1.PAL
BLK, TEAL, SIL, GRY, WHT, NAV, LSV, BLU, RED, GRN = range(10)
gi = c1.gi

# ---- 32-bit OS variables (4 bytes each) ----
AX, AY, AW, AH, ACOL = 0x00, 0x04, 0x08, 0x0C, 0x10
GX, GY, GCH, GCOL    = 0x14, 0x18, 0x1C, 0x20
T0, T1, T2, T3       = 0x24, 0x28, 0x2C, 0x30
MX, MY, MB, MBP      = 0x34, 0x38, 0x3C, 0x40
CX, CY, OCX, OCY     = 0x44, 0x48, 0x4C, 0x50
HAVES, CLKF, CSEC    = 0x54, 0x58, 0x5C
DNV, DH, DT          = 0x60, 0x64, 0x68     # decimal renderer temps (blitglyph-safe)
APP, DIRTY, PCOL     = 0x6C, 0x70, 0x74     # active app (0 About,1 Paint,2 Calc); redraw flag; paint colour
CACC, CCUR, COP, CFRESH = 0x78, 0x7C, 0x80, 0x84   # calculator state (all 32-bit)
CURBUF = 0x0100
FONT   = 0x0400
CURSOR = [0x80, 0xC0, 0xE0, 0xF0, 0xF8, 0xFC, 0xE0, 0x40]

# window + taskbar geometry
WINX, WINY, WW, WH = 86, 38, 340, 306
TBY = H - 18                                # taskbar top
PSWATCH = [BLK, GRY, WHT, RED, GRN, BLU, NAV, TEAL]                # 8 paint colours
# calc keypad: (label, kind, value) ; kind: d=digit o=op(0+,1-,2x) e== c=clear
CALC_KEYS = [['7','8','9','x'], ['4','5','6','-'], ['1','2','3','+'], ['C','0','=','']]

def load_memory(m):
    for ch, idx in c1.GIDX.items():
        for r, b in enumerate(c1.enc_rows(c1.GART[ch])): m.M[FONT + idx*7 + r] = b

def program():
    L = []; a = L.append
    def shl(n):
        for _ in range(n): a(("SHL",))
    def puts(x, y, text, col):
        for i, ch in enumerate(text):
            a(("LDI", x + i*6)); a(("STW", GX)); a(("LDI", y)); a(("STW", GY))
            a(("LDI", gi(ch))); a(("STW", GCH)); a(("LDI", col)); a(("STW", GCOL)); a(("CALL", "blitglyph"))
    def rect(x, y, w, h, col):
        a(("LDI", x)); a(("STW", AX)); a(("LDI", y)); a(("STW", AY)); a(("LDI", w)); a(("STW", AW)); a(("LDI", h)); a(("STW", AH)); a(("LDI", col)); a(("STW", ACOL)); a(("CALL", "fillrect"))
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

    # ---- blitglyph ----
    a(("blitglyph:",))
    a(("LDW", GCH)); shl(3); a(("SUBW", GCH)); a(("STW", T0))
    a(("LDI", 0)); a(("STW", T2))
    a(("bg_row:",)); a(("LDW", T2)); a(("CMPI", 7)); a(("JC", "bg_done"))
    a(("LDW", T0)); a(("ADDW", T2)); a(("TAX",)); a(("LDAX", FONT)); a(("STW", T3))
    a(("LDW", GY)); a(("ADDW", T2)); shl(9); a(("ADDW", GX)); a(("STW", T1))
    for col in range(5):
        a(("LDW", T3)); a(("ANDI", 0x10 >> col)); a(("JZ", f"bg_s{col}"))
        a(("LDW", T1)); a(("ADDI", col)); a(("TAX",)); a(("LDA", GCOL)); a(("STAX", FB))
        a((f"bg_s{col}:",))
    a(("LDW", T2)); a(("ADDI", 1)); a(("STW", T2)); a(("JMP", "bg_row"))
    a(("bg_done:",)); a(("RET",))

    # ---- dnum: draw DNV as decimal at (GX,GY) in GCOL, leading zeros suppressed (efficient: powers of 10) ----
    a(("dnum:",)); a(("LDI", 0)); a(("STW", DT))
    powers = [1000000000, 100000000, 10000000, 1000000, 100000, 10000, 1000, 100, 10, 1]
    for ip, p in enumerate(powers):
        a(("LDI", 0)); a(("STW", DH))
        a((f"dn{ip}:",)); a(("LDW", DNV)); a(("CMPI", p)); a(("JNC", f"dnd{ip}")); a(("SUBI", p)); a(("STW", DNV)); a(("LDW", DH)); a(("ADDI", 1)); a(("STW", DH)); a(("JMP", f"dn{ip}"))
        a((f"dnd{ip}:",))
        a(("LDW", DH)); a(("JNZ", f"dnshow{ip}")); a(("LDW", DT)); a(("JNZ", f"dnshow{ip}"))
        a(("JMP", (f"dnshow{ip}" if p == 1 else f"dnskip{ip}")))
        a((f"dnshow{ip}:",)); a(("LDI", 1)); a(("STW", DT))
        a(("LDW", DH)); a(("STW", GCH)); a(("CALL", "blitglyph")); a(("LDW", GX)); a(("ADDI", 6)); a(("STW", GX))
        a((f"dnskip{ip}:",))
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
    rect(0, TBY, W, 18, SIL); rect(0, TBY-1, W, 1, WHT)      # taskbar
    # launcher buttons
    for i, name in enumerate(["About", "Paint", "Calc"]):
        bx = 4 + i*54
        rect(bx, TBY+3, 50, 12, SIL);
        a(("LDI", bx)); a(("STW", AX)); a(("LDI", TBY+3)); a(("STW", AY)); a(("LDI", 50)); a(("STW", AW)); a(("LDI", 12)); a(("STW", AH))
        a(("LDW", APP)); a(("CMPI", i)); a(("JNZ", f"lb{i}")); a(("LDI", NAV)); a(("STW", ACOL)); a(("CALL", "fillrect")); a((f"lb{i}:",))
        puts(bx+6, TBY+5, name, BLK)
    # window frame + title
    rect(WINX, WINY, WW, WH, SIL)
    rect(WINX, WINY, WW, 14, NAV)
    a(("LDW", APP)); a(("CMPI", 1)); a(("JZ", "ti_p")); a(("CMPI", 2)); a(("JZ", "ti_c"))
    puts(WINX+6, WINY+4, "About CA-OS/2", WHT); a(("JMP", "ti_d"))
    a(("ti_p:",)); puts(WINX+6, WINY+4, "Paint", WHT); a(("JMP", "ti_d"))
    a(("ti_c:",)); puts(WINX+6, WINY+4, "Calc  (32-bit)", WHT)
    a(("ti_d:",))
    # body by app
    a(("LDW", APP)); a(("CMPI", 1)); a(("JZ", "body_p")); a(("CMPI", 2)); a(("JZ", "body_c"))
    a(("CALL", "draw_about")); a(("JMP", "draw_d"))
    a(("body_p:",)); a(("CALL", "draw_paint")); a(("JMP", "draw_d"))
    a(("body_c:",)); a(("CALL", "draw_calc"))
    a(("draw_d:",)); a(("CALL", "drawclock")); a(("RET",))

    # ---- About app ----
    a(("draw_about:",))
    bx, by = WINX+12, WINY+26
    puts(bx, by,     "CA-2  -  32-bit processor", BLK)
    puts(bx, by+16,  "RAM: 1 MB (flat)   Screen: 512x384", BLK)
    puts(bx, by+38,  "Datapath: genuine cellular automata", GRY)
    puts(bx, by+50,  "(hex K=4 gliders): NAND + latch", GRY)
    puts(bx, by+72,  "ALU: 32-bit CA adder, verified", BLU)
    puts(bx, by+94,  "One core builds the whole family:", BLK)
    puts(bx, by+106, "CA-1 (8-bit) ... CA-2 (32-bit) ...", BLK)
    puts(bx, by+132, "Apps: Paint, Calc -- use the", BLK)
    puts(bx, by+144, "launcher buttons in the taskbar.", BLK)
    a(("RET",))

    # ---- Paint app: palette strip + canvas ----
    a(("draw_paint:",))
    for i, col in enumerate(PSWATCH):
        sx = WINX+10 + i*30
        rect(sx, WINY+20, 26, 16, col)
        a(("LDW", PCOL)); a(("CMPI", col)); a(("JNZ", f"ps{i}"))
        rect(sx, WINY+18, 26, 2, WHT); rect(sx, WINY+36, 26, 2, WHT); a((f"ps{i}:",))
    rect(WINX+10, WINY+42, WW-20, WH-54, WHT)               # canvas (white)
    a(("RET",))

    # ---- Calc app: 32-bit display + keypad ----
    a(("draw_calc:",))
    rect(WINX+12, WINY+22, WW-24, 26, WHT)                  # display
    a(("LDW", CCUR)); a(("STW", DNV)); a(("LDI", WINX+18)); a(("STW", GX)); a(("LDI", WINY+30)); a(("STW", GY)); a(("LDI", BLK)); a(("STW", GCOL)); a(("CALL", "dnum"))
    for r in range(4):
        for c in range(4):
            lab = CALC_KEYS[r][c]
            if not lab: continue
            bx = WINX+18 + c*78; by = WINY+58 + r*52
            rect(bx, by, 70, 44, SIL)
            puts(bx+30, by+18, lab, BLK)
    a(("RET",))

    # ---- clock (taskbar, right) ----
    a(("drawclock:",))
    rect(W-58, TBY+3, 54, 12, SIL)
    puts(W-54, TBY+5, "up", GRY)
    a(("LDW", CSEC)); a(("STW", DNV)); a(("LDI", W-40)); a(("STW", GX)); a(("LDI", TBY+5)); a(("STW", GY)); a(("LDI", BLK)); a(("STW", GCOL)); a(("CALL", "dnum"))
    puts(W-16, TBY+5, "s", GRY)
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
    a(("LDW", CX)); a(("CMPI", WINX+10)); a(("JNC", "pd_no")); a(("CMPI", WINX+WW-12)); a(("JC", "pd_no"))
    a(("LDW", CY)); a(("CMPI", WINY+42)); a(("JNC", "pd_no")); a(("CMPI", WINY+WH-12)); a(("JC", "pd_no"))
    a(("LDI", 0)); a(("STW", T2))                            # dy
    a(("pd_r:",)); a(("LDW", T2)); a(("CMPI", 4)); a(("JC", "pd_no")); a(("LDI", 0)); a(("STW", T3))
    a(("pd_c:",)); a(("LDW", T3)); a(("CMPI", 4)); a(("JC", "pd_nr"))
    a(("LDW", CY)); a(("ADDW", T2)); shl(9); a(("STW", T0)); a(("LDW", CX)); a(("ADDW", T3)); a(("ADDW", T0)); a(("TAX",)); a(("LDA", PCOL)); a(("STAX", FB))
    a(("LDW", T3)); a(("ADDI", 1)); a(("STW", T3)); a(("JMP", "pd_c"))
    a(("pd_nr:",)); a(("LDW", T2)); a(("ADDI", 1)); a(("STW", T2)); a(("JMP", "pd_r"))
    a(("pd_no:",)); a(("RET",))

    # ============ click handling ============
    a(("onclick:",))
    # launcher buttons (taskbar): About/Paint/Calc
    for i in range(3):
        bx = 4 + i*54
        a(("LDW", MX)); a(("CMPI", bx)); a(("JNC", f"nl{i}")); a(("CMPI", bx+50)); a(("JC", f"nl{i}"))
        a(("LDW", MY)); a(("CMPI", TBY+3)); a(("JNC", f"nl{i}")); a(("CMPI", TBY+15)); a(("JC", f"nl{i}"))
        a(("LDI", i)); a(("STW", APP)); a(("LDI", 1)); a(("STW", DIRTY)); a(("RET",)); a((f"nl{i}:",))
    # in-app clicks
    a(("LDW", APP)); a(("CMPI", 1)); a(("JZ", "oc_paint")); a(("CMPI", 2)); a(("JZ", "oc_calc")); a(("RET",))
    # Paint: palette swatches
    a(("oc_paint:",))
    for i, col in enumerate(PSWATCH):
        sx = WINX+10 + i*30
        a(("LDW", MX)); a(("CMPI", sx)); a(("JNC", f"np{i}")); a(("CMPI", sx+26)); a(("JC", f"np{i}"))
        a(("LDW", MY)); a(("CMPI", WINY+20)); a(("JNC", f"np{i}")); a(("CMPI", WINY+36)); a(("JC", f"np{i}"))
        a(("LDI", col)); a(("STW", PCOL)); a(("LDI", 1)); a(("STW", DIRTY)); a(("RET",)); a((f"np{i}:",))
    a(("RET",))
    # Calc: keypad
    a(("oc_calc:",))
    for r in range(4):
        for c in range(4):
            lab = CALC_KEYS[r][c]
            if not lab: continue
            bx = WINX+18 + c*78; by = WINY+58 + r*52; t = f"ck{r}_{c}"
            a(("LDW", MX)); a(("CMPI", bx)); a(("JNC", t)); a(("CMPI", bx+70)); a(("JC", t))
            a(("LDW", MY)); a(("CMPI", by)); a(("JNC", t)); a(("CMPI", by+44)); a(("JC", t))
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
            a(("LDI", 1)); a(("STW", DIRTY)); a(("RET",)); a((f"{t}:",))
    a(("RET",))
    # calc_apply: fold CCUR into CACC using COP (first op just loads CACC)
    a(("calc_apply:",))
    a(("LDW", COP)); a(("CMPI", 0)); a(("JNZ", "ca_ns")); a(("LDW", CACC)); a(("ADDW", CCUR)); a(("STW", CACC)); a(("RET",))
    a(("ca_ns:",)); a(("CMPI", 1)); a(("JNZ", "ca_nm")); a(("LDW", CACC)); a(("SUBW", CCUR)); a(("STW", CACC)); a(("RET",))
    a(("ca_nm:",)); a(("CMPI", 2)); a(("JNZ", "ca_load")); a(("CALL", "mul32")); a(("RET",))
    a(("ca_load:",)); a(("LDW", CCUR)); a(("STW", CACC)); a(("RET",))

    # ============ boot + main ============
    a(("boot:",))
    for v in (MB, MBP, HAVES, CLKF, CSEC, APP, PCOL, CACC, CCUR, COP): a(("LDI", 0)); a(("STW", v))
    a(("LDI", 1)); a(("STW", CFRESH)); a(("STW", DIRTY)); a(("LDI", RED)); a(("STW", PCOL))
    a(("LDI", W//2)); a(("STW", CX)); a(("STW", OCX)); a(("LDI", H//2)); a(("STW", CY)); a(("STW", OCY))
    a(("main:",))
    # mouse -> CX,CY (clamp)
    a(("LDW", MX)); a(("CMPI", W-8)); a(("JNC", "mxok")); a(("LDI", W-8)); a(("STW", CX)); a(("JMP", "mxd")); a(("mxok:",)); a(("LDW", MX)); a(("STW", CX)); a(("mxd:",))
    a(("LDW", MY)); a(("CMPI", H-8)); a(("JNC", "myok")); a(("LDI", H-8)); a(("STW", CY)); a(("JMP", "myd")); a(("myok:",)); a(("LDW", MY)); a(("STW", CY)); a(("myd:",))
    # click edge -> onclick
    a(("LDW", MB)); a(("JZ", "noclick")); a(("LDW", MBP)); a(("JNZ", "noclick")); a(("CALL", "onclick")); a(("noclick:",))
    # paint: while button held over canvas, draw
    a(("LDW", MB)); a(("JZ", "nopaint")); a(("CALL", "paintdab")); a(("nopaint:",))
    a(("LDW", MB)); a(("STW", MBP))
    # full redraw on DIRTY (app switch / button / palette / paint stroke region)
    a(("LDW", DIRTY)); a(("JZ", "nodraw")); a(("LDW", HAVES)); a(("JZ", "nrd")); a(("CALL", "restun")); a(("nrd:",))
    a(("CALL", "draw")); a(("LDI", 0)); a(("STW", DIRTY)); a(("LDI", 0)); a(("STW", HAVES)); a(("nodraw:",))
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
    m = make_machine("CA-2", fb_addr=FB, fb_w=W, fb_h=H); load_memory(m)
    m.M[MX:MX+4] = (W//2).to_bytes(4, "little"); m.M[MY:MY+4] = (H//2).to_bytes(4, "little")
    m.run(program(), max_i=30_000_000, frame_on=lambda mm: True)
    print("CA-OS/2 booted:", sum(1 for v in m.M[FB:FB+W*H] if v != TEAL), "non-bg px; apps: About/Paint/Calc")
