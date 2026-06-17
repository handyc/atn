#!/usr/bin/env python3
# caos.py — CA-OS: a GUI desktop that runs ENTIRELY on the CA-1 machine. CA-1 code draws the
# whole screen (desktop, taskbar, a calculator window, the mouse cursor) into a memory-mapped
# framebuffer and hit-tests the mouse — the browser is a dumb terminal (blit framebuffer +
# forward mouse). Every pixel and every event is CA-1 instructions (= cellular-automaton
# computation; ALU verified == CA gates). Drawing routines use CALL/RET + a row-address table.
import json
from ca1sys import CA1Sys, asm

W, H, FB = 160, 120, 0x8000
ROWLO, ROWHI, FONT = 0x400, 0x480, 0x500
# zero-page vars
AX, AY, AW, AH, ACOL = 0x10, 0x11, 0x12, 0x13, 0x14
GX, GY, GCH, GCOL = 0x15, 0x16, 0x17, 0x18
RR, CC, T0, T1, T2, T3 = 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E
MX, MY, MB, MBP = 0x20, 0x21, 0x22, 0x23
C_ACC, C_CUR, C_OP, C_FRESH, C_HASR = 0x24, 0x25, 0x26, 0x27, 0x28
NVL, NVH, QLO, QHI, REM = 0x2C, 0x2D, 0x2E, 0x2F, 0x30
D0, D1, D2, D3, I = 0x31, 0x32, 0x33, 0x34, 0x35

# palette: 0 black 1 teal 2 gray 3 dkgray 4 white 5 navy 6 ltgray 7 blue 8 red 9 green 10 yellow
PALETTE = ["#000000", "#118f8f", "#c0c0c0", "#808080", "#ffffff", "#000080",
           "#dfdfdf", "#1084d0", "#d04040", "#10b050", "#f0e030", "#202830"]
BLK, TEAL, GRAY, DKG, WHT, NAVY, LTG, BLU, RED, GRN, YEL = range(11)

FONTGLYPH = {  # 3x5, rows top->bottom, bits 4=left 2=mid 1=right ; idx 0-9 digits then symbols
    0: [7, 5, 5, 5, 7], 1: [2, 6, 2, 2, 7], 2: [7, 1, 7, 4, 7], 3: [7, 1, 7, 1, 7],
    4: [5, 5, 7, 1, 1], 5: [7, 4, 7, 1, 7], 6: [7, 4, 7, 5, 7], 7: [7, 1, 2, 2, 2],
    8: [7, 5, 7, 5, 7], 9: [7, 5, 7, 1, 7],
    10: [0, 2, 7, 2, 0], 11: [0, 0, 7, 0, 0], 12: [0, 5, 2, 5, 0],   # + - x
    13: [1, 1, 2, 4, 4], 14: [0, 7, 0, 7, 0], 15: [7, 4, 4, 4, 7],   # / = C
    16: [0, 0, 0, 0, 0]}                                             # blank
GL_PLUS, GL_MINUS, GL_MUL, GL_DIV, GL_EQ, GL_C, GL_BLANK = 10, 11, 12, 13, 14, 15, 16

# calculator buttons: (x, y, glyph, kind, val)  kind: 'd' digit, 'o' op(val=opcode), 'e' eq, 'c' clear
BTN_W, BTN_H, BX0, BY0, GAPX, GAPY = 16, 12, 46, 44, 3, 3
def btn_grid():
    layout = [[(7, 'd', 7), (8, 'd', 8), (9, 'd', 9), (GL_PLUS, 'o', 0)],
              [(4, 'd', 4), (5, 'd', 5), (6, 'd', 6), (GL_MINUS, 'o', 1)],
              [(1, 'd', 1), (2, 'd', 2), (3, 'd', 3), (GL_MUL, 'o', 2)],
              [(0, 'd', 0), (GL_C, 'c', 0), (GL_EQ, 'e', 0), (GL_BLANK, 'b', 0)]]
    btns = []
    for r, row in enumerate(layout):
        for c, (gl, kind, val) in enumerate(row):
            if kind == 'b': continue
            x = BX0 + c * (BTN_W + GAPX); y = BY0 + r * (BTN_H + GAPY)
            btns.append((x, y, gl, kind, val))
    return btns
BTNS = btn_grid()

def load_memory(m):
    for y in range(H):
        addr = FB + y * W; m.M[ROWLO + y] = addr & 0xFF; m.M[ROWHI + y] = (addr >> 8) & 0xFF
    for g, rows in FONTGLYPH.items():
        for i, b in enumerate(rows): m.M[FONT + g * 5 + i] = b

def program():
    L = []; a = L.append
    # ============ boot + main loop ============
    a(("LDI", 0)); a(("STA", C_ACC)); a(("STA", C_CUR)); a(("STA", C_OP)); a(("STA", C_HASR)); a(("STA", MBP))
    a(("LDI", 1)); a(("STA", C_FRESH))
    a(("main:",))
    # click edge: MB==1 and MBP==0
    a(("LDA", MB)); a(("JZ", "noclick")); a(("LDA", MBP)); a(("JNZ", "noclick")); a(("CALL", "onclick"))
    a(("noclick:",))
    a(("CALL", "draw"))
    a(("LDA", MB)); a(("STA", MBP))
    a(("FRAME",)); a(("JMP", "main"))

    # ============ draw whole screen ============
    a(("draw:",))
    # desktop
    a(("LDI", 0)); a(("STA", AX)); a(("STA", AY)); a(("LDI", W)); a(("STA", AW)); a(("LDI", H)); a(("STA", AH)); a(("LDI", TEAL)); a(("STA", ACOL)); a(("CALL", "fillrect"))
    # taskbar
    a(("LDI", 0)); a(("STA", AX)); a(("LDI", 110)); a(("STA", AY)); a(("LDI", W)); a(("STA", AW)); a(("LDI", 10)); a(("STA", AH)); a(("LDI", GRAY)); a(("STA", ACOL)); a(("CALL", "fillrect"))
    a(("LDI", 2)); a(("STA", AX)); a(("LDI", 112)); a(("STA", AY)); a(("LDI", 22)); a(("STA", AW)); a(("LDI", 7)); a(("STA", AH)); a(("LDI", LTG)); a(("STA", ACOL)); a(("CALL", "fillrect"))
    a(("CALL", "drawcalc"))
    a(("CALL", "cursor"))
    a(("RET",))

    # ============ fillrect(AX,AY,AW,AH,ACOL) ============
    a(("fillrect:",))
    a(("LDA", AH)); a(("STA", RR)); a(("LDA", AY)); a(("STA", T0))
    a(("fr_row:",)); a(("LDA", RR)); a(("JZ", "fr_done"))
    a(("LDX", T0)); a(("LDAX", ROWLO)); a(("PLO",)); a(("LDX", T0)); a(("LDAX", ROWHI)); a(("PHI",))
    a(("LDA", AW)); a(("STA", CC)); a(("LDA", AX)); a(("TAX",))
    a(("fr_col:",)); a(("LDA", CC)); a(("JZ", "fr_nr"))
    a(("LDA", ACOL)); a(("STPX",)); a(("INX",)); a(("LDA", CC)); a(("SUBI", 1)); a(("STA", CC)); a(("JMP", "fr_col"))
    a(("fr_nr:",)); a(("LDA", T0)); a(("ADDI", 1)); a(("STA", T0)); a(("LDA", RR)); a(("SUBI", 1)); a(("STA", RR)); a(("JMP", "fr_row"))
    a(("fr_done:",)); a(("RET",))

    # ============ blitglyph(GX,GY,GCH,GCOL) — 3x5 ============
    a(("blitglyph:",))
    a(("LDA", GCH)); a(("SHL",)); a(("SHL",)); a(("STA", T1)); a(("LDA", GCH)); a(("ADD", T1)); a(("STA", T1))   # T1 = GCH*5
    a(("LDI", 0)); a(("STA", T2))
    a(("bg_row:",)); a(("LDA", T2)); a(("CMPI", 5)); a(("JC", "bg_done"))   # T2>=5 done
    a(("LDA", T1)); a(("ADD", T2)); a(("TAX",)); a(("LDAX", FONT)); a(("STA", T3))   # T3 = font row bits
    a(("LDA", GY)); a(("ADD", T2)); a(("TAX",)); a(("LDAX", ROWLO)); a(("PLO",))
    a(("LDA", GY)); a(("ADD", T2)); a(("TAX",)); a(("LDAX", ROWHI)); a(("PHI",))
    a(("LDA", T3)); a(("ANDI", 4)); a(("JZ", "bg_c1")); a(("LDA", GX)); a(("TAX",)); a(("LDA", GCOL)); a(("STPX",)); a(("bg_c1:",))
    a(("LDA", T3)); a(("ANDI", 2)); a(("JZ", "bg_c2")); a(("LDA", GX)); a(("ADDI", 1)); a(("TAX",)); a(("LDA", GCOL)); a(("STPX",)); a(("bg_c2:",))
    a(("LDA", T3)); a(("ANDI", 1)); a(("JZ", "bg_c3")); a(("LDA", GX)); a(("ADDI", 2)); a(("TAX",)); a(("LDA", GCOL)); a(("STPX",)); a(("bg_c3:",))
    a(("LDA", T2)); a(("ADDI", 1)); a(("STA", T2)); a(("JMP", "bg_row"))
    a(("bg_done:",)); a(("RET",))

    # ============ cursor at (MX,MY): a small 3x4 arrow in white ============
    a(("cursor:",))
    for (dx, dy) in [(0,0),(0,1),(1,1),(0,2),(1,2),(2,2),(0,3)]:
        a(("LDA", MY)); a(("ADDI", dy)); a(("TAX",)); a(("LDAX", ROWLO)); a(("PLO",))
        a(("LDA", MY)); a(("ADDI", dy)); a(("TAX",)); a(("LDAX", ROWHI)); a(("PHI",))
        a(("LDA", MX)); a(("ADDI", dx)); a(("TAX",)); a(("LDI", WHT)); a(("STPX",))
    a(("RET",))

    # ============ drawcalc: window + display + buttons ============
    a(("drawcalc:",))
    a(("LDI", 38)); a(("STA", AX)); a(("LDI", 12)); a(("STA", AY)); a(("LDI", 84)); a(("STA", AW)); a(("LDI", 92)); a(("STA", AH)); a(("LDI", GRAY)); a(("STA", ACOL)); a(("CALL", "fillrect"))
    a(("LDI", 38)); a(("STA", AX)); a(("LDI", 12)); a(("STA", AY)); a(("LDI", 84)); a(("STA", AW)); a(("LDI", 9)); a(("STA", AH)); a(("LDI", NAVY)); a(("STA", ACOL)); a(("CALL", "fillrect"))
    # display (white)
    a(("LDI", 44)); a(("STA", AX)); a(("LDI", 24)); a(("STA", AY)); a(("LDI", 72)); a(("STA", AW)); a(("LDI", 13)); a(("STA", AH)); a(("LDI", WHT)); a(("STA", ACOL)); a(("CALL", "fillrect"))
    # display digits D0..D3 (blanked leading zeros), positions
    for i, dv in enumerate([D0, D1, D2, D3]):
        a(("LDA", dv)); a(("STA", GCH)); a(("LDI", 94 + i * 5)); a(("STA", GX)); a(("LDI", 28)); a(("STA", GY)); a(("LDI", BLK)); a(("STA", GCOL)); a(("CALL", "blitglyph"))
    # buttons
    for (bx, by, gl, kind, val) in BTNS:
        a(("LDI", bx)); a(("STA", AX)); a(("LDI", by)); a(("STA", AY)); a(("LDI", BTN_W)); a(("STA", AW)); a(("LDI", BTN_H)); a(("STA", AH)); a(("LDI", LTG)); a(("STA", ACOL)); a(("CALL", "fillrect"))
        a(("LDI", bx + 1)); a(("STA", AX)); a(("LDI", by + 1)); a(("STA", AY)); a(("LDI", BTN_W - 2)); a(("STA", AW)); a(("LDI", BTN_H - 2)); a(("STA", AH)); a(("LDI", GRAY)); a(("STA", ACOL)); a(("CALL", "fillrect"))
        a(("LDI", gl)); a(("STA", GCH)); a(("LDI", bx + 6)); a(("STA", GX)); a(("LDI", by + 4)); a(("STA", GY)); a(("LDI", BLK)); a(("STA", GCOL)); a(("CALL", "blitglyph"))
    a(("RET",))

    # ============ onclick: hit-test mouse vs buttons ============
    a(("onclick:",))
    for idx, (bx, by, gl, kind, val) in enumerate(BTNS):
        lbl = f"miss{idx}"
        a(("LDA", MX)); a(("CMPI", bx)); a(("JNC", lbl))                 # MX<bx
        a(("LDA", MX)); a(("CMPI", bx + BTN_W)); a(("JC", lbl))          # MX>=bx+w
        a(("LDA", MY)); a(("CMPI", by)); a(("JNC", lbl))
        a(("LDA", MY)); a(("CMPI", by + BTN_H)); a(("JC", lbl))
        if kind == 'd':
            a(("LDI", val)); a(("STA", T0)); a(("CALL", "press_digit"))
        elif kind == 'o':
            a(("LDI", val)); a(("STA", T0)); a(("CALL", "press_op"))
        elif kind == 'e':
            a(("CALL", "press_eq"))
        elif kind == 'c':
            a(("CALL", "press_clr"))
        a(("RET",))
        a((f"{lbl}:",))
    a(("RET",))

    # press_digit(T0=digit): C_CUR = (fresh?0:C_CUR*10)+digit, cap 99 ; C_HASR=0
    a(("press_digit:",))
    a(("LDI", 0)); a(("STA", C_HASR))
    a(("LDA", C_FRESH)); a(("JZ", "pd_app")); a(("LDI", 0)); a(("STA", C_CUR)); a(("LDI", 0)); a(("STA", C_FRESH))
    a(("pd_app:",))
    # C_CUR = C_CUR*10 (repeated add) if <10 else keep (cap)
    a(("LDA", C_CUR)); a(("CMPI", 10)); a(("JC", "pd_set"))    # if C_CUR>=10, ignore further (2-digit cap)
    # C_CUR = C_CUR*10 + digit : mul by 10 = C_CUR*8 + C_CUR*2
    a(("LDA", C_CUR)); a(("SHL",)); a(("STA", T1))             # 2x
    a(("LDA", T1)); a(("SHL",)); a(("SHL",)); a(("ADD", T1)); a(("ADD", T0)); a(("STA", C_CUR))  # 8x+2x+digit
    a(("pd_set:",)); a(("CALL", "show_cur")); a(("RET",))

    # press_op(T0=opcode): C_ACC=C_CUR; C_OP=T0; C_FRESH=1
    a(("press_op:",))
    a(("LDA", C_CUR)); a(("STA", C_ACC)); a(("LDA", T0)); a(("STA", C_OP)); a(("LDI", 1)); a(("STA", C_FRESH))
    a(("RET",))

    # press_clr: reset
    a(("press_clr:",))
    a(("LDI", 0)); a(("STA", C_ACC)); a(("STA", C_CUR)); a(("STA", C_OP)); a(("STA", C_HASR)); a(("LDI", 1)); a(("STA", C_FRESH))
    a(("CALL", "show_cur")); a(("RET",))

    # press_eq: result16 = C_ACC op C_CUR ; into NVL/NVH ; num2dig ; C_HASR=1
    a(("press_eq:",))
    a(("LDA", C_OP)); a(("CMPI", 0)); a(("JZ", "eq_add"))
    a(("LDA", C_OP)); a(("CMPI", 1)); a(("JZ", "eq_sub"))
    a(("JMP", "eq_mul"))
    a(("eq_add:",)); a(("LDA", C_ACC)); a(("ADD", C_CUR)); a(("STA", NVL)); a(("LDI", 0)); a(("JNC", "eq_a0")); a(("LDI", 1)); a(("eq_a0:",)); a(("STA", NVH)); a(("JMP", "eq_fin"))
    a(("eq_sub:",)); a(("LDA", C_ACC)); a(("CMP", C_CUR)); a(("JNC", "eq_sneg")); a(("LDA", C_ACC)); a(("SUB", C_CUR)); a(("STA", NVL)); a(("LDI", 0)); a(("STA", NVH)); a(("JMP", "eq_fin"))
    a(("eq_sneg:",)); a(("LDI", 0)); a(("STA", NVL)); a(("STA", NVH)); a(("JMP", "eq_fin"))
    a(("eq_mul:",)); a(("LDI", 0)); a(("STA", NVL)); a(("STA", NVH)); a(("LDA", C_CUR)); a(("STA", I))
    a(("em_l:",)); a(("LDA", I)); a(("JZ", "eq_fin"))
    a(("LDA", NVL)); a(("ADD", C_ACC)); a(("STA", NVL)); a(("JNC", "em_nc")); a(("LDA", NVH)); a(("ADDI", 1)); a(("STA", NVH)); a(("em_nc:",))
    a(("LDA", I)); a(("SUBI", 1)); a(("STA", I)); a(("JMP", "em_l"))
    a(("eq_fin:",)); a(("CALL", "num2dig")); a(("LDI", 1)); a(("STA", C_HASR)); a(("RET",))

    # show_cur: NVL=C_CUR, NVH=0, num2dig
    a(("show_cur:",)); a(("LDA", C_CUR)); a(("STA", NVL)); a(("LDI", 0)); a(("STA", NVH)); a(("CALL", "num2dig")); a(("RET",))

    # num2dig: NVL/NVH (16-bit) -> D0..D3 (glyph idx, leading blanks)
    a(("num2dig:",))
    a(("CALL", "div10")); a(("STA", D3)); a(("CALL", "div10")); a(("STA", D2))
    a(("CALL", "div10")); a(("STA", D1)); a(("CALL", "div10")); a(("STA", D0))
    # blank leading zeros: D0
    a(("LDA", D0)); a(("JNZ", "nd_done")); a(("LDI", GL_BLANK)); a(("STA", D0))
    a(("LDA", D1)); a(("JNZ", "nd_done")); a(("LDI", GL_BLANK)); a(("STA", D1))
    a(("LDA", D2)); a(("JNZ", "nd_done")); a(("LDI", GL_BLANK)); a(("STA", D2))
    a(("nd_done:",)); a(("RET",))

    # div10: NVL/NVH /=10, returns remainder in A (0-9)
    a(("div10:",)); a(("LDI", 0)); a(("STA", QLO)); a(("STA", QHI))
    a(("d10_l:",))
    a(("LDA", NVH)); a(("JNZ", "d10_sub"))           # hi!=0 -> >=10
    a(("LDA", NVL)); a(("CMPI", 10)); a(("JNC", "d10_done"))   # lo<10 -> done
    a(("d10_sub:",))
    a(("LDA", NVL)); a(("SUBI", 10)); a(("STA", NVL)); a(("JC", "d10_nb")); a(("LDA", NVH)); a(("SUBI", 1)); a(("STA", NVH)); a(("d10_nb:",))
    a(("LDA", QLO)); a(("ADDI", 1)); a(("STA", QLO)); a(("JNC", "d10_qok")); a(("LDA", QHI)); a(("ADDI", 1)); a(("STA", QHI)); a(("d10_qok:",))
    a(("JMP", "d10_l"))
    a(("d10_done:",)); a(("LDA", NVL)); a(("STA", REM)); a(("LDA", QLO)); a(("STA", NVL)); a(("LDA", QHI)); a(("STA", NVH)); a(("LDA", REM)); a(("RET",))

    return asm(L)

if __name__ == "__main__":
    m = CA1Sys(fb_addr=FB, fb_w=W, fb_h=H); load_memory(m)
    m.M[MX] = 80; m.M[MY] = 60; m.M[MB] = 0
    code = program()
    # render one frame (no click)
    prog, _ = code
    # run until first FRAME
    m.run(code, max_i=5_000_000, frame_on=lambda mm: True)
    fb = m.M[FB:FB + W * H]
    print(f"CA-OS: {m.icount} instructions for one frame ({W}x{H})")
    # ASCII preview (downsample 2x)
    ramp = {0:' ',1:'~',2:'.',3:':',4:'#',5:'N',6:'-',7:'b',8:'R',9:'g',10:'y',11:'.'}
    for y in range(0, H, 2):
        print("".join(ramp.get(fb[y*W+x],'?') for x in range(0, W, 2)))
