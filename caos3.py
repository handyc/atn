#!/usr/bin/env python3
# caos3.py — CA-OFFICE: CA-OS grown into a small office suite, all running on the CA-1 machine.
# Adds a Start menu + a one-window app switcher + KEYBOARD input, and three apps:
#   WRITER  — a tiny word processor: type text (5x7 font), backspace, blinking caret.
#   SHEET   — a 3x4 spreadsheet; click a cell, +/- to change it; TOTAL is summed by the CA ALU.
#   CALC    — the calculator (ported).
# Same engine as caos2: page-aligned 256x192 framebuffer, beveled Win9x chrome, software cursor,
# dirty-rectangle redraw, CALL/RET. Browser stays a dumb terminal (framebuffer + mouse + keys).
import json
from ca1sys import CA1Sys, asm

W, H, FB = 256, 192, 0x4000
FBPAGE = FB >> 8
STACK = 0x3F00
PAL = ["#000000","#008080","#c0c0c0","#808080","#ffffff","#000080","#dfdfdf","#1084d0","#b00000","#107010"]
BLK,TEAL,SIL,GRY,WHT,NAV,LSV,BLU,RED,GRN = range(10)

# zero-page
AX,AY,AW,AH,ACOL = 0x10,0x11,0x12,0x13,0x14
GX,GY,GCH,GCOL   = 0x15,0x16,0x17,0x18
RR,CC,T0,T1,T2,T3= 0x19,0x1A,0x1B,0x1C,0x1D,0x1E
MX,MY,MB,MBP,KEY = 0x20,0x21,0x22,0x23,0x24
CX,CY,OCX,OCY,HAVES,DIRTY = 0x25,0x26,0x27,0x28,0x29,0x2A
APP,START,BLINK = 0x2B,0x2C,0x2D     # active app 0=none 1=writer 2=sheet 3=calc; start-menu open; caret blink
NVL,NVH,QLO,QHI,REM,I = 0x30,0x31,0x32,0x33,0x34,0x35
D0,D1,D2,D3,D4 = 0x36,0x37,0x38,0x39,0x3A
SX,SY,SPTR,SCOL = 0x3B,0x3C,0x3D,0x3E
C_ACC,C_CUR,C_OP,C_FRESH = 0x40,0x41,0x42,0x43
TLEN,SELC = 0x44,0x45
SUMSRC = 0x46
BFL,BFH = 0x47,0x48      # blitglyph 16-bit font-base pointer (font table > 256 bytes)
WX,WY,DRAG,DOFX,DOFY = 0x49,0x4A,0x4B,0x4C,0x4D   # runtime window position + drag state
BOLD = 0x4E      # 1 = blitglyph draws 2px-wide strokes (bold heading font)
SFRESH = 0x4F    # 1 = selected sheet cell is fresh; next digit replaces (not appends)
PCOL = 0x50      # Paint: selected colour (palette index)
PSL,PSH,DDH,DDL,PTMP,PROW = 0x52,0x53,0x54,0x55,0x56,0x57   # Paint blit pointers/scratch
PW,PH = 96,96    # paint canvas size (px); buffer = PW*PH bytes
PSWATCH = [0,3,4,8,9,7,5,2]   # palette swatches: BLK,GRY,WHT,RED,GRN,BLU,NAV,SIL
# Minesweeper (APP=5): cell byte = bit0 mine, bit1 revealed, bit2 flagged, bit3 queued, bits4-7 count
MFLAG,MOVER,MSEED,MSP,MNREV,MR,MC,MTMP,MI,MK,MIDX = 0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F,0x60,0x61,0x62
MGRID = 0x0080   # 64 cells (0x80-0xBF)
MSTK  = 0x0100   # flood-fill stack (deduped via queued bit -> <=64 deep)
GW,MINES = 8,10  # grid 8x8, 10 mines
FONT  = 0x0500      # 5x7 font, 7 bytes/glyph (now ~80 glyphs incl lowercase -> ~560 bytes)
STRP  = 0x0780      # strings table base (moved past the bigger font)
TBUF  = 0x0900      # writer text buffer (glyph indices)
CELLS = 0x0A00      # 12 spreadsheet cells (bytes)
PBUF  = 0x0B00      # Paint canvas backing buffer (PW*PH = 9216 bytes -> 0x0B00..0x2F00, below stack 0x3F00)
CURBUF= 0x0300

# ── 5x7 font: full A-Z, 0-9, space, symbols ──
GART = {
 '0':[".###.","#...#","#..##","#.#.#","##..#","#...#",".###."],'1':["..#..",".##..","..#..","..#..","..#..","..#..",".###."],
 '2':[".###.","#...#","....#","..##.",".#...","#....","#####"],'3':["#####","....#","...#.","..##.","....#","#...#",".###."],
 '4':["...#.","..##.",".#.#.","#..#.","#####","...#.","...#."],'5':["#####","#....","####.","....#","....#","#...#",".###."],
 '6':["..##.",".#...","#....","####.","#...#","#...#",".###."],'7':["#####","....#","...#.","..#..",".#...",".#...",".#..."],
 '8':[".###.","#...#","#...#",".###.","#...#","#...#",".###."],'9':[".###.","#...#","#...#",".####","....#","...#.",".##.."],
 ' ':[".....",".....",".....",".....",".....",".....","....."],'.':[".....",".....",".....",".....",".....",".##..",".##.."],
 ',':[".....",".....",".....",".....",".##..",".##..",".#..."],':':[".....",".##..",".##..",".....",".##..",".##..","....."],
 '!':["..#..","..#..","..#..","..#..","..#..",".....","..#.."],'?':[".###.","#...#","...#.","..#..","..#..",".....","..#.."],
 '+':[".....","..#..","..#..","#####","..#..","..#..","....."],'-':[".....",".....",".....","#####",".....",".....","....."],
 '=':[".....",".....","#####",".....","#####",".....","....."],'/':["....#","...#.","..#..",".#...","#....",".....","....."],
 'A':[".###.","#...#","#...#","#####","#...#","#...#","#...#"],'B':["####.","#...#","#...#","####.","#...#","#...#","####."],
 'C':[".###.","#...#","#....","#....","#....","#...#",".###."],'D':["###..","#..#.","#...#","#...#","#...#","#..#.","###.."],
 'E':["#####","#....","#....","####.","#....","#....","#####"],'F':["#####","#....","#....","####.","#....","#....","#...."],
 'G':[".###.","#...#","#....","#.###","#...#","#...#",".###."],'H':["#...#","#...#","#...#","#####","#...#","#...#","#...#"],
 'I':[".###.","..#..","..#..","..#..","..#..","..#..",".###."],'J':["..###","...#.","...#.","...#.","#..#.","#..#.",".##.."],
 'K':["#...#","#..#.","#.#..","##...","#.#..","#..#.","#...#"],'L':["#....","#....","#....","#....","#....","#....","#####"],
 'M':["#...#","##.##","#.#.#","#.#.#","#...#","#...#","#...#"],'N':["#...#","##..#","#.#.#","#..##","#...#","#...#","#...#"],
 'O':[".###.","#...#","#...#","#...#","#...#","#...#",".###."],'P':["####.","#...#","#...#","####.","#....","#....","#...."],
 'Q':[".###.","#...#","#...#","#...#","#.#.#","#..#.",".##.#"],'R':["####.","#...#","#...#","####.","#.#..","#..#.","#...#"],
 'S':[".####","#....","#....",".###.","....#","....#","####."],'T':["#####","..#..","..#..","..#..","..#..","..#..","..#.."],
 'U':["#...#","#...#","#...#","#...#","#...#","#...#",".###."],'V':["#...#","#...#","#...#","#...#","#...#",".#.#.","..#.."],
 'W':["#...#","#...#","#...#","#.#.#","#.#.#","##.##","#...#"],'X':["#...#","#...#",".#.#.","..#..",".#.#.","#...#","#...#"],
 'Y':["#...#","#...#",".#.#.","..#..","..#..","..#..","..#.."],'Z':["#####","....#","...#.","..#..",".#...","#....","#####"],
 'x':[".....",".....","#...#",".#.#.","..#..",".#.#.","#...#"],
 'a':[".....",".....",".###.","....#",".####","#...#",".####"],'b':["#....","#....","####.","#...#","#...#","#...#","####."],
 'c':[".....",".....",".###.","#...#","#....","#...#",".###."],'d':["....#","....#",".####","#...#","#...#","#...#",".####"],
 'e':[".....",".....",".###.","#...#","#####","#....",".###."],'f':["..##.",".#..#",".#...","###..",".#...",".#...",".#..."],
 'g':[".....",".####","#...#","#...#",".####","....#",".###."],'h':["#....","#....","####.","#...#","#...#","#...#","#...#"],
 'i':["..#..",".....","..#..","..#..","..#..","..#..","..#.."],'j':["...#.",".....","...#.","...#.","...#.","#..#.",".##.."],
 'k':["#....","#....","#..#.","#.#..","##...","#.#..","#..#."],'l':["..#..","..#..","..#..","..#..","..#..","..#..","..#.."],
 'm':[".....",".....","##.#.","#.#.#","#.#.#","#...#","#...#"],'n':[".....",".....","####.","#...#","#...#","#...#","#...#"],
 'o':[".....",".....",".###.","#...#","#...#","#...#",".###."],'p':[".....","####.","#...#","#...#","####.","#....","#...."],
 'q':[".....",".####","#...#","#...#",".####","....#","....#"],'r':[".....",".....","#.##.","##..#","#....","#....","#...."],
 's':[".....",".....",".####","#....",".###.","....#","####."],'t':[".#...",".#...","###..",".#...",".#...",".#..#","..##."],
 'u':[".....",".....","#...#","#...#","#...#","#..##",".##.#"],'v':[".....",".....","#...#","#...#","#...#",".#.#.","..#.."],
 'w':[".....",".....","#...#","#...#","#.#.#","#.#.#",".#.#."],'y':[".....","#...#","#...#",".####","....#","#...#",".###."],
 'z':[".....",".....","#####","...#.","..#..",".#...","#####"],
 '(':["..#..",".#...",".#...",".#...",".#...",".#...","..#.."],')':["..#..","...#.","...#.","...#.","...#.","...#.","..#.."],
 "'":["..#..","..#..","..#..",".....",".....",".....","....."],';':[".....","..#..",".....",".....","..#..","..#..",".#..."],
}
GLYPHS=list(GART.keys()); GIDX={ch:i for i,ch in enumerate(GLYPHS)}
def gi(ch): return GIDX.get(ch, GIDX[' '])
def enc_rows(rows):
    out=[]
    for r in rows:
        b=0
        for c in range(5):
            if r[c]=='#': b|=1<<(4-c)
        out.append(b)
    return out
STRINGS={"caoffice":("CA-Office",0x00),"start":("Start",0x10),"writer":("Writer",0x18),
         "sheet":("Sheet",0x20),"calc":("Calc",0x28),"total":("Total",0x30),"paint":("Paint",0x38),
         "mine":("Mines",0x40)}
def soff(k): return STRINGS[k][1]

# calculator buttons (window-relative), used by CALC app
BTN_W,BTN_H=22,16
def calc_btns():
    lay=[[('7','d',7),('8','d',8),('9','d',9),('/','o',3)],[('4','d',4),('5','d',5),('6','d',6),('x','o',2)],
         [('1','d',1),('2','d',2),('3','d',3),('-','o',1)],[('0','d',0),('C','c',0),('=','e',0),('+','o',0)]]
    out=[]
    for r,row in enumerate(lay):
        for c,(lab,kind,val) in enumerate(row):
            out.append((8+c*25, 40+r*20, lab, kind, val))
    return out
CBTNS=calc_btns()
# spreadsheet cells 3 cols x 4 rows, window-relative
def sheet_cells():
    out=[]
    for r in range(4):
        for c in range(3):
            out.append((8+c*34, 22+r*16))
    return out
SCELLS=sheet_cells()
WINX,WINY,WW,WH=40,16,150,150

def load_memory(m):
    for ch,i in GIDX.items():
        for r,b in enumerate(enc_rows(GART[ch])): m.M[FONT+i*7+r]=b
    for k,(text,off) in STRINGS.items():
        for j,ch in enumerate(text): m.M[STRP+off+j]=gi(ch)
        m.M[STRP+off+len(text)]=0xFF

def program():
    L=[]; a=L.append
    # window-relative position helpers (runtime, so the window can be dragged)
    def wx(dest, off): a(("LDA",WX)); a(("ADDI",off)); a(("STA",dest))           # dest = WINX + off
    def wy(dest, off): a(("LDA",WY)); a(("ADDI",off)); a(("STA",dest))           # dest = WINY + off
    def hx(off, lbl, ge): a(("LDA",WX)); a(("ADDI",off)); a(("STA",T0)); a(("LDA",MX)); a(("CMP",T0)); a(("JC" if ge else "JNC",lbl))
    def hy(off, lbl, ge): a(("LDA",WY)); a(("ADDI",off)); a(("STA",T0)); a(("LDA",MY)); a(("CMP",T0)); a(("JC" if ge else "JNC",lbl))
    # for each in-bounds neighbour of (MR,MC): compute its cell index into X, then emit action(k)
    NB=[(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
    def gen_neighbors(action, tag):
        for k,(dr,dc) in enumerate(NB):
            skip=f"{tag}_s{k}"
            if dr==-1: a(("LDA",MR)); a(("JZ",skip))
            if dr== 1: a(("LDA",MR)); a(("CMPI",GW-1)); a(("JC",skip))
            if dc==-1: a(("LDA",MC)); a(("JZ",skip))
            if dc== 1: a(("LDA",MC)); a(("CMPI",GW-1)); a(("JC",skip))
            a(("LDA",MR))
            if dr==-1: a(("SUBI",1))
            if dr== 1: a(("ADDI",1))
            a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("STA",MTMP))     # nr*8
            a(("LDA",MC))
            if dc==-1: a(("SUBI",1))
            if dc== 1: a(("ADDI",1))
            a(("ADD",MTMP)); a(("TAX",))                              # X = nr*8 + nc
            action(k)
            a((f"{skip}:",))
    a(("JMP","boot"))
    # ---- fillrect ----
    a(("fillrect:",)); a(("LDA",AH)); a(("STA",RR)); a(("LDA",AY)); a(("STA",T0))
    a(("fr_row:",)); a(("LDA",RR)); a(("JZ","fr_done"))
    a(("LDI",0)); a(("PLO",)); a(("LDA",T0)); a(("ADDI",FBPAGE)); a(("PHI",))
    a(("LDA",AW)); a(("STA",CC)); a(("LDA",AX)); a(("TAX",))
    a(("fr_col:",)); a(("LDA",CC)); a(("JZ","fr_nr")); a(("LDA",ACOL)); a(("STPX",)); a(("INX",)); a(("LDA",CC)); a(("SUBI",1)); a(("STA",CC)); a(("JMP","fr_col"))
    a(("fr_nr:",)); a(("LDA",T0)); a(("ADDI",1)); a(("STA",T0)); a(("LDA",RR)); a(("SUBI",1)); a(("STA",RR)); a(("JMP","fr_row"))
    a(("fr_done:",)); a(("RET",))
    # ---- bevel(AX,AY,AW,AH) raised ----
    a(("bevel:",)); a(("LDA",AH)); a(("STA",T3))
    a(("LDI",1)); a(("STA",AH)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDA",T3)); a(("STA",AH)); a(("LDA",AW)); a(("STA",T2)); a(("LDI",1)); a(("STA",AW)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDA",T2)); a(("STA",AW)); a(("LDA",AY)); a(("STA",T1)); a(("LDA",AY)); a(("ADD",AH)); a(("SUBI",1)); a(("STA",AY)); a(("LDI",1)); a(("STA",AH)); a(("LDI",GRY)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("LDA",T1)); a(("STA",AY))
    a(("LDA",AX)); a(("STA",T1)); a(("LDA",AX)); a(("ADD",AW)); a(("SUBI",1)); a(("STA",AX)); a(("LDA",T3)); a(("STA",AH)); a(("LDI",1)); a(("STA",AW)); a(("LDI",GRY)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDA",T1)); a(("STA",AX)); a(("LDA",T2)); a(("STA",AW)); a(("LDA",T3)); a(("STA",AH)); a(("RET",))
    # ---- blitglyph(GX,GY,GCH,GCOL) — 16-bit font addressing (font table > 256 bytes) ----
    a(("blitglyph:",))
    a(("LDI",0)); a(("STA",T1)); a(("STA",T2)); a(("LDI",7)); a(("STA",T3))      # acc(T1lo,T2hi)=0, counter T3=7
    a(("bg_mul:",)); a(("LDA",T3)); a(("JZ","bg_muld"))                          # acc = GCH*7
    a(("LDA",T1)); a(("ADD",GCH)); a(("STA",T1)); a(("JNC","bg_mnc")); a(("LDA",T2)); a(("ADDI",1)); a(("STA",T2)); a(("bg_mnc:",))
    a(("LDA",T3)); a(("SUBI",1)); a(("STA",T3)); a(("JMP","bg_mul"))
    a(("bg_muld:",)); a(("LDA",T1)); a(("STA",BFL)); a(("LDA",T2)); a(("ADDI",FONT>>8)); a(("STA",BFH))   # font_base = FONT + GCH*7
    a(("LDI",0)); a(("STA",T2))
    a(("bg_row:",)); a(("LDA",T2)); a(("CMPI",7)); a(("JC","bg_done"))
    a(("LDA",BFL)); a(("PLO",)); a(("LDA",BFH)); a(("PHI",)); a(("LDX",T2)); a(("LDPX",)); a(("STA",T3))   # font byte for this row
    a(("LDI",0)); a(("PLO",)); a(("LDA",GY)); a(("ADD",T2)); a(("ADDI",FBPAGE)); a(("PHI",))               # pixel row base
    for col in range(5):
        bit=1<<(4-col); lbl=f"bgc{col}"
        a(("LDA",T3)); a(("ANDI",bit)); a(("JZ",lbl)); a(("LDA",GX)); a(("ADDI",col)); a(("TAX",)); a(("LDA",GCOL)); a(("STPX",))
        a(("LDA",BOLD)); a(("JZ",lbl)); a(("INX",)); a(("LDA",GCOL)); a(("STPX",)); a((f"{lbl}:",))   # bold: also draw col+1
    a(("LDA",T2)); a(("ADDI",1)); a(("STA",T2)); a(("JMP","bg_row")); a(("bg_done:",)); a(("RET",))
    # ---- puts2(SX,SY,SPTR,SCOL): string from page 7 ----
    a(("puts2:",)); a(("LDA",SX)); a(("STA",GX)); a(("LDI",0)); a(("STA",T0))
    a(("pl2:",)); a(("LDA",SPTR)); a(("ADD",T0)); a(("TAX",)); a(("LDAX",STRP)); a(("STA",T1)); a(("CMPI",0xFF)); a(("JZ","pl2d"))
    a(("LDA",T1)); a(("STA",GCH)); a(("LDA",SY)); a(("STA",GY)); a(("LDA",SCOL)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    a(("LDA",GX)); a(("ADDI",6)); a(("ADD",BOLD)); a(("STA",GX)); a(("LDA",T0)); a(("ADDI",1)); a(("STA",T0)); a(("JMP","pl2")); a(("pl2d:",)); a(("RET",))
    # ---- cursor save/restore/draw (8x12) ----
    a(("saveun:",)); a(("LDI",0)); a(("STA",T2))
    a(("su_r:",)); a(("LDA",T2)); a(("CMPI",8)); a(("JC","su_d"))
    a(("LDI",0)); a(("PLO",)); a(("LDA",CY)); a(("ADD",T2)); a(("ADDI",FBPAGE)); a(("PHI",)); a(("LDI",0)); a(("STA",T3))
    a(("su_c:",)); a(("LDA",T3)); a(("CMPI",8)); a(("JC","su_n"))
    a(("LDA",CX)); a(("ADD",T3)); a(("TAX",)); a(("LDPX",)); a(("STA",T1))
    a(("LDA",T2)); a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("ADD",T3)); a(("TAX",)); a(("LDA",T1)); a(("STAX",CURBUF))
    a(("LDA",T3)); a(("ADDI",1)); a(("STA",T3)); a(("JMP","su_c")); a(("su_n:",)); a(("LDA",T2)); a(("ADDI",1)); a(("STA",T2)); a(("JMP","su_r")); a(("su_d:",)); a(("RET",))
    a(("restun:",)); a(("LDI",0)); a(("STA",T2))
    a(("ru_r:",)); a(("LDA",T2)); a(("CMPI",8)); a(("JC","ru_d"))
    a(("LDI",0)); a(("PLO",)); a(("LDA",OCY)); a(("ADD",T2)); a(("ADDI",FBPAGE)); a(("PHI",)); a(("LDI",0)); a(("STA",T3))
    a(("ru_c:",)); a(("LDA",T3)); a(("CMPI",8)); a(("JC","ru_n"))
    a(("LDA",T2)); a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("ADD",T3)); a(("TAX",)); a(("LDAX",CURBUF)); a(("STA",T1))
    a(("LDA",OCX)); a(("ADD",T3)); a(("TAX",)); a(("LDA",T1)); a(("STPX",))
    a(("LDA",T3)); a(("ADDI",1)); a(("STA",T3)); a(("JMP","ru_c")); a(("ru_n:",)); a(("LDA",T2)); a(("ADDI",1)); a(("STA",T2)); a(("JMP","ru_r")); a(("ru_d:",)); a(("RET",))
    a(("drawcur:",))
    for (dx,dy) in [(0,0),(0,1),(1,1),(0,2),(1,2),(2,2),(0,3),(1,3),(2,3),(3,3),(0,4),(1,4),(2,4),(3,4),(4,4),(0,5),(1,5),(2,5),(3,5),(4,5),(5,5),(0,6),(1,6),(0,7)]:
        a(("LDI",0)); a(("PLO",)); a(("LDA",CY)); a(("ADDI",dy)); a(("ADDI",FBPAGE)); a(("PHI",)); a(("LDA",CX)); a(("ADDI",dx)); a(("TAX",)); a(("LDI",(BLK if dx==0 or dx==dy else WHT))); a(("STPX",))
    a(("RET",))

    # ============ num2dig / div10 (shared) ============
    a(("num2dig:",))
    a(("CALL","div10")); a(("STA",D4)); a(("CALL","div10")); a(("STA",D3)); a(("CALL","div10")); a(("STA",D2)); a(("CALL","div10")); a(("STA",D1)); a(("CALL","div10")); a(("STA",D0))
    a(("LDA",D0)); a(("JNZ","ndd")); a(("LDI",gi(' '))); a(("STA",D0)); a(("LDA",D1)); a(("JNZ","ndd")); a(("LDI",gi(' '))); a(("STA",D1)); a(("LDA",D2)); a(("JNZ","ndd")); a(("LDI",gi(' '))); a(("STA",D2)); a(("LDA",D3)); a(("JNZ","ndd")); a(("LDI",gi(' '))); a(("STA",D3)); a(("ndd:",)); a(("RET",))
    a(("div10:",)); a(("LDI",0)); a(("STA",QLO)); a(("STA",QHI))
    a(("d10l:",)); a(("LDA",NVH)); a(("JNZ","d10s")); a(("LDA",NVL)); a(("CMPI",10)); a(("JNC","d10d"))
    a(("d10s:",)); a(("LDA",NVL)); a(("SUBI",10)); a(("STA",NVL)); a(("JC","d10nb")); a(("LDA",NVH)); a(("SUBI",1)); a(("STA",NVH)); a(("d10nb:",))
    a(("LDA",QLO)); a(("ADDI",1)); a(("STA",QLO)); a(("JNC","d10q")); a(("LDA",QHI)); a(("ADDI",1)); a(("STA",QHI)); a(("d10q:",)); a(("JMP","d10l"))
    a(("d10d:",)); a(("LDA",NVL)); a(("STA",REM)); a(("LDA",QLO)); a(("STA",NVL)); a(("LDA",QHI)); a(("STA",NVH)); a(("LDA",REM)); a(("RET",))
    # drawnum(GX,GY) draws NVL/NVH as up-to-5 digits (uses num2dig -> D0..D4)
    a(("drawnum:",)); a(("CALL","num2dig"))
    for i,dv in enumerate([D0,D1,D2,D3,D4]):
        a(("LDA",dv)); a(("STA",GCH)); a(("LDA",GX)); a(("ADDI",i*6)); a(("PUSH",)); a(("LDA",GY)); a(("STA",T0))
        a(("POP",)); a(("STA",GX)); a(("LDA",T0)); a(("STA",GY)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
        a(("LDA",GX)); a(("SUBI",i*6)); a(("STA",GX))   # restore GX base for next index
    a(("RET",))

    # ============ DRAW everything ============
    a(("draw:",)); a(("CALL","clearbg"))
    # taskbar
    a(("LDI",0)); a(("STA",AX)); a(("LDI",182)); a(("STA",AY)); a(("LDI",255)); a(("STA",AW)); a(("LDI",10)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDI",0)); a(("STA",AX)); a(("LDI",181)); a(("STA",AY)); a(("LDI",255)); a(("STA",AW)); a(("LDI",1)); a(("STA",AH)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDI",2)); a(("STA",AX)); a(("LDI",183)); a(("STA",AY)); a(("LDI",40)); a(("STA",AW)); a(("LDI",8)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    a(("LDI",6)); a(("STA",SX)); a(("LDI",184)); a(("STA",SY)); a(("LDI",soff("start"))); a(("STA",SPTR)); a(("LDI",BLK)); a(("STA",SCOL)); a(("CALL","puts2"))
    # active app window
    a(("LDA",APP)); a(("JZ","dw_done")); a(("CALL","drawwin")); a(("dw_done:",))
    # start menu (on top)
    a(("LDA",START)); a(("JZ","dm_done")); a(("CALL","drawmenu")); a(("dm_done:",))
    a(("CALL","cursor")); a(("RET",))
    a(("clearbg:",)); a(("LDI",FBPAGE)); a(("STA",T0))
    a(("cb_p:",)); a(("LDA",T0)); a(("CMPI",0)); a(("JZ","cb_d")); a(("LDI",0)); a(("PLO",)); a(("LDA",T0)); a(("PHI",)); a(("LXI",0))
    a(("cb_x:",)); a(("LDI",TEAL)); a(("STPX",)); a(("INX",)); a(("JNZ","cb_x")); a(("LDA",T0)); a(("ADDI",1)); a(("STA",T0)); a(("JMP","cb_p")); a(("cb_d:",)); a(("RET",))
    a(("cursor:",)); a(("CALL","drawcur")); a(("RET",))    # alias

    # window frame + dispatch to app body
    a(("drawwin:",))
    wx(AX,0); wy(AY,0); a(("LDI",WW)); a(("STA",AW)); a(("LDI",WH)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    wx(AX,2); wy(AY,2); a(("LDI",WW-4)); a(("STA",AW)); a(("LDI",12)); a(("STA",AH)); a(("LDI",NAV)); a(("STA",ACOL)); a(("CALL","fillrect"))
    # title text by app
    wx(SX,5); wy(SY,4); a(("LDI",WHT)); a(("STA",SCOL)); a(("LDI",1)); a(("STA",BOLD))   # bold title
    a(("LDA",APP)); a(("CMPI",1)); a(("JZ","tw")); a(("CMPI",2)); a(("JZ","ts")); a(("CMPI",3)); a(("JZ","tc")); a(("CMPI",4)); a(("JZ","tpa")); a(("LDI",soff("mine"))); a(("STA",SPTR)); a(("JMP","tp"))
    a(("tw:",)); a(("LDI",soff("writer"))); a(("STA",SPTR)); a(("JMP","tp")); a(("ts:",)); a(("LDI",soff("sheet"))); a(("STA",SPTR)); a(("JMP","tp"))
    a(("tc:",)); a(("LDI",soff("calc"))); a(("STA",SPTR)); a(("JMP","tp")); a(("tpa:",)); a(("LDI",soff("paint"))); a(("STA",SPTR))
    a(("tp:",)); a(("CALL","puts2")); a(("LDI",0)); a(("STA",BOLD))
    # close box
    wx(AX,WW-13); wy(AY,3); a(("LDI",10)); a(("STA",AW)); a(("LDI",10)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    wx(GX,WW-11); wy(GY,4); a(("LDI",gi('x'))); a(("STA",GCH)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    # body
    a(("LDA",APP)); a(("CMPI",1)); a(("JZ","body_w")); a(("CMPI",2)); a(("JZ","body_s")); a(("CMPI",3)); a(("JZ","body_c")); a(("CMPI",4)); a(("JZ","body_p")); a(("CALL","draw_mine")); a(("RET",))
    a(("body_p:",)); a(("CALL","draw_paint")); a(("RET",))
    a(("body_w:",)); a(("CALL","draw_writer")); a(("RET",))
    a(("body_s:",)); a(("CALL","draw_sheet")); a(("RET",))
    a(("body_c:",)); a(("CALL","draw_calc")); a(("RET",))

    # ---- WRITER body: text area + buffer glyphs + caret ----
    a(("draw_writer:",))
    wx(AX,6); wy(AY,18); a(("LDI",WW-12)); a(("STA",AW)); a(("LDI",WH-26)); a(("STA",AH)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
    # draw TBUF glyphs, wrapping; 6px/char, 8px/line
    a(("LDI",0)); a(("STA",T0))
    wx(GX,9); wy(GY,22)
    a(("dw_l:",)); a(("LDA",T0)); a(("CMP",TLEN)); a(("JC","dw_caret"))   # exit when T0>=TLEN
    a(("LDX",T0)); a(("LDAX",TBUF)); a(("CMPI",0xFD)); a(("JZ","dw_nl"))  # 0xFD = newline marker
    a(("STA",GCH)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    a(("LDA",GX)); a(("ADDI",6)); a(("STA",GX))
    a(("LDA",WX)); a(("ADDI",WW-12)); a(("STA",T1)); a(("LDA",GX)); a(("CMP",T1)); a(("JNC","dw_nx"))   # GX < margin -> keep line
    a(("dw_nl:",)); wx(GX,9); a(("LDA",GY)); a(("ADDI",8)); a(("STA",GY))   # newline / wrap
    a(("dw_nx:",)); a(("LDA",T0)); a(("ADDI",1)); a(("STA",T0)); a(("JMP","dw_l"))
    a(("dw_caret:",))                          # caret if BLINK&8
    a(("LDA",BLINK)); a(("ANDI",8)); a(("JZ","dw_done2"))
    a(("LDA",GX)); a(("STA",AX)); a(("LDA",GY)); a(("STA",AY)); a(("LDI",1)); a(("STA",AW)); a(("LDI",7)); a(("STA",AH)); a(("LDI",BLK)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("dw_done2:",)); a(("RET",))

    # ---- SHEET body: 3x4 grid + TOTAL (CA sum) ----
    a(("draw_sheet:",))
    for idx,(bx,by) in enumerate(SCELLS):
        # cell box (selected -> blue tint via LSV else white)
        wx(AX,bx); wy(AY,by); a(("LDI",32)); a(("STA",AW)); a(("LDI",14)); a(("STA",AH))
        a(("LDA",SELC)); a(("CMPI",idx)); a(("JZ",f"sel{idx}")); a(("LDI",WHT)); a(("JMP",f"selc{idx}")); a((f"sel{idx}:",)); a(("LDI",LSV)); a((f"selc{idx}:",)); a(("STA",ACOL)); a(("CALL","fillrect"))
        wx(AX,bx); wy(AY,by); a(("LDI",32)); a(("STA",AW)); a(("LDI",14)); a(("STA",AH)); a(("CALL","bevel"))
        # value: 3 digits (cells hold 0-255), sized to fit the 32px cell
        a(("LXI",idx)); a(("LDAX",CELLS)); a(("STA",NVL)); a(("LDI",0)); a(("STA",NVH)); a(("CALL","num2dig"))  # LXI = load X immediate (LDX would load M[idx]!)
        for di,dv in enumerate([D2,D3,D4]):
            a(("LDA",dv)); a(("STA",GCH)); wx(GX,bx+8+di*7); wy(GY,by+4); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    # +/- buttons + TOTAL
    wx(AX,8); wy(AY,94); a(("LDI",16)); a(("STA",AW)); a(("LDI",14)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    wx(GX,14); wy(GY,98); a(("LDI",gi('+'))); a(("STA",GCH)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    wx(AX,28); wy(AY,94); a(("LDI",16)); a(("STA",AW)); a(("LDI",14)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    wx(GX,34); wy(GY,98); a(("LDI",gi('-'))); a(("STA",GCH)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    wx(SX,52); wy(SY,98); a(("LDI",soff("total"))); a(("STA",SPTR)); a(("LDI",BLK)); a(("STA",SCOL)); a(("CALL","puts2"))
    a(("CALL","sheet_sum"))                     # -> NVL/NVH
    wx(GX,100); wy(GY,98); a(("CALL","drawnum"))
    a(("RET",))
    # sheet_sum: NVL/NVH = sum of 12 cells (CA repeated add)
    a(("sheet_sum:",)); a(("LDI",0)); a(("STA",NVL)); a(("STA",NVH)); a(("LDI",0)); a(("STA",T0))
    a(("ss_l:",)); a(("LDA",T0)); a(("CMPI",12)); a(("JC","ss_d"))
    a(("LDX",T0)); a(("LDAX",CELLS)); a(("ADD",NVL)); a(("STA",NVL)); a(("JNC","ss_nc")); a(("LDA",NVH)); a(("ADDI",1)); a(("STA",NVH)); a(("ss_nc:",))
    a(("LDA",T0)); a(("ADDI",1)); a(("STA",T0)); a(("JMP","ss_l")); a(("ss_d:",)); a(("RET",))

    # ---- CALC body ----
    a(("draw_calc:",))
    wx(AX,8); wy(AY,18); a(("LDI",WW-16)); a(("STA",AW)); a(("LDI",14)); a(("STA",AH)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDA",C_CUR)); a(("STA",NVL)); a(("LDI",0)); a(("STA",NVH))
    wx(GX,WW-44); wy(GY,22); a(("CALL","drawnum"))
    for (bx,by,lab,kind,val) in CBTNS:
        wx(AX,bx); wy(AY,by); a(("LDI",BTN_W)); a(("STA",AW)); a(("LDI",BTN_H)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
        wx(GX,bx+8); wy(GY,by+4); a(("LDI",gi(lab))); a(("STA",GCH)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    a(("RET",))

    # ---- PAINT: blit the canvas buffer, draw the palette + clear button ----
    a(("draw_paint:",))
    wx(AX,5); wy(AY,17); a(("LDI",PW+2)); a(("STA",AW)); a(("LDI",PH+2)); a(("STA",AH)); a(("LDI",BLK)); a(("STA",ACOL)); a(("CALL","fillrect"))  # 1px frame
    a(("LDI",PBUF & 0xFF)); a(("STA",PSL)); a(("LDI",PBUF>>8)); a(("STA",PSH))                 # src = PBUF
    a(("LDA",WY)); a(("ADDI",18)); a(("ADDI",FBPAGE)); a(("STA",DDH)); a(("LDA",WX)); a(("ADDI",6)); a(("STA",DDL))   # dst row base
    a(("LDI",0)); a(("STA",PROW))
    a(("dp_row:",)); a(("LXI",0))
    a(("dp_col:",))
    a(("LDA",PSL)); a(("PLO",)); a(("LDA",PSH)); a(("PHI",)); a(("LDPX",)); a(("STA",PTMP))     # A = src[col]
    a(("LDA",DDL)); a(("PLO",)); a(("LDA",DDH)); a(("PHI",)); a(("LDA",PTMP)); a(("STPX",))     # dst[col] = A
    a(("INX",)); a(("TXA",)); a(("CMPI",PW)); a(("JNC","dp_col"))
    a(("LDA",PSL)); a(("ADDI",PW)); a(("STA",PSL)); a(("JNC","dp_nc")); a(("LDA",PSH)); a(("ADDI",1)); a(("STA",PSH)); a(("dp_nc:",))
    a(("LDA",DDH)); a(("ADDI",1)); a(("STA",DDH))
    a(("LDA",PROW)); a(("ADDI",1)); a(("STA",PROW)); a(("CMPI",PH)); a(("JNC","dp_row"))
    # palette swatches (selected one gets a white ring)
    for i,col in enumerate(PSWATCH):
        y=18+i*14
        a(("LDA",PCOL)); a(("CMPI",col)); a(("JNZ",f"pn{i}"))
        wx(AX,104); wy(AY,y-2); a(("LDI",34)); a(("STA",AW)); a(("LDI",16)); a(("STA",AH)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
        a((f"pn{i}:",))
        wx(AX,105); wy(AY,y-1); a(("LDI",32)); a(("STA",AW)); a(("LDI",14)); a(("STA",AH)); a(("LDI",BLK)); a(("STA",ACOL)); a(("CALL","fillrect"))
        wx(AX,106); wy(AY,y); a(("LDI",30)); a(("STA",AW)); a(("LDI",12)); a(("STA",AH)); a(("LDI",col)); a(("STA",ACOL)); a(("CALL","fillrect"))
    wx(AX,106); wy(AY,132); a(("LDI",30)); a(("STA",AW)); a(("LDI",13)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    wx(GX,118); wy(GY,135); a(("LDI",gi('C'))); a(("STA",GCH)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    a(("RET",))
    # clear the paint buffer to white (PW*PH = 36 pages)
    a(("clearpaint:",)); a(("LDI",PBUF>>8)); a(("STA",T0))
    a(("cp_p:",)); a(("LDA",T0)); a(("CMPI",(PBUF>>8)+36)); a(("JZ","cp_d")); a(("LDI",0)); a(("PLO",)); a(("LDA",T0)); a(("PHI",)); a(("LXI",0))
    a(("cp_x:",)); a(("LDI",WHT)); a(("STPX",)); a(("INX",)); a(("JNZ","cp_x")); a(("LDA",T0)); a(("ADDI",1)); a(("STA",T0)); a(("JMP","cp_p")); a(("cp_d:",)); a(("RET",))
    # paint a 2x2 dab at the cursor into PBUF (called while MB held over the canvas)
    a(("pokepaint:",))
    a(("LDA",MX)); a(("CMP",WX)); a(("JNC","pp_no"))
    a(("LDA",MX)); a(("SUB",WX)); a(("STA",T1)); a(("CMPI",6)); a(("JNC","pp_no")); a(("LDA",T1)); a(("SUBI",6)); a(("STA",T1)); a(("CMPI",PW-1)); a(("JC","pp_no"))
    a(("LDA",MY)); a(("CMP",WY)); a(("JNC","pp_no"))
    a(("LDA",MY)); a(("SUB",WY)); a(("STA",T2)); a(("CMPI",18)); a(("JNC","pp_no")); a(("LDA",T2)); a(("SUBI",18)); a(("STA",T2)); a(("CMPI",PH-1)); a(("JC","pp_no"))
    a(("LDI",0)); a(("STA",PSL)); a(("STA",PSH)); a(("LDA",T2)); a(("STA",PROW))                 # acc = py*PW
    a(("pp_mul:",)); a(("LDA",PROW)); a(("JZ","pp_md")); a(("LDA",PSL)); a(("ADDI",PW)); a(("STA",PSL)); a(("JNC","pp_mnc")); a(("LDA",PSH)); a(("ADDI",1)); a(("STA",PSH)); a(("pp_mnc:",)); a(("LDA",PROW)); a(("SUBI",1)); a(("STA",PROW)); a(("JMP","pp_mul"))
    a(("pp_md:",)); a(("LDA",PSL)); a(("PLO",)); a(("LDA",PSH)); a(("ADDI",PBUF>>8)); a(("PHI",))   # P = PBUF + py*PW
    a(("LDA",T1)); a(("TAX",)); a(("LDA",PCOL)); a(("STPX",)); a(("INX",)); a(("LDA",PCOL)); a(("STPX",))           # (py, px)(py, px+1)
    a(("LDA",T1)); a(("ADDI",PW)); a(("TAX",)); a(("LDA",PCOL)); a(("STPX",)); a(("INX",)); a(("LDA",PCOL)); a(("STPX",))  # (py+1, px)(py+1, px+1)
    a(("LDI",1)); a(("STA",DIRTY))
    a(("pp_no:",)); a(("RET",))

    # ============ MINESWEEPER (APP=5) ============
    # new game: clear grid, place MINES via an LCG (deterministic -> Alice/Bob identical), count neighbours
    a(("mnew:",)); a(("LDI",0)); a(("STA",MI))
    a(("mn_clr:",)); a(("LDX",MI)); a(("LDI",0)); a(("STAX",MGRID)); a(("LDA",MI)); a(("ADDI",1)); a(("STA",MI)); a(("CMPI",64)); a(("JNC","mn_clr"))
    a(("LDI",0)); a(("STA",MOVER)); a(("STA",MNREV)); a(("STA",MK))
    a(("mn_place:",)); a(("LDA",MK)); a(("CMPI",MINES)); a(("JC","mn_counts"))
    a(("LDA",MSEED)); a(("SHL",)); a(("SHL",)); a(("STA",MTMP)); a(("LDA",MSEED)); a(("ADD",MTMP)); a(("ADDI",1)); a(("STA",MSEED))   # seed=seed*5+1
    a(("ANDI",0x3F)); a(("STA",MIDX))
    a(("LDX",MIDX)); a(("LDAX",MGRID)); a(("ANDI",0x01)); a(("JNZ","mn_place"))   # already a mine -> redraw seed
    a(("LDX",MIDX)); a(("LDI",1)); a(("STAX",MGRID)); a(("LDA",MK)); a(("ADDI",1)); a(("STA",MK)); a(("JMP","mn_place"))
    a(("mn_counts:",)); a(("LDI",0)); a(("STA",MI))
    a(("mn_cl:",)); a(("LDX",MI)); a(("LDAX",MGRID)); a(("ANDI",0x01)); a(("JZ","mn_cn"))
    a(("LDA",MI)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("STA",MR)); a(("LDA",MI)); a(("ANDI",0x07)); a(("STA",MC))
    gen_neighbors(lambda k:(a(("LDAX",MGRID)),a(("ADDI",0x10)),a(("STAX",MGRID))), "mc")
    a(("mn_cn:",)); a(("LDA",MI)); a(("ADDI",1)); a(("STA",MI)); a(("CMPI",64)); a(("JNC","mn_cl"))
    a(("RET",))
    # flood-reveal from MIDX (iterative; queued bit 0x08 dedups so the stack stays <=64 deep)
    a(("mreveal:",)); a(("LDI",0)); a(("STA",MSP)); a(("LDX",MSP)); a(("LDA",MIDX)); a(("STAX",MSTK)); a(("LDI",1)); a(("STA",MSP))
    a(("fl_loop:",)); a(("LDA",MSP)); a(("JZ","fl_done"))
    a(("SUBI",1)); a(("STA",MSP)); a(("LDX",MSP)); a(("LDAX",MSTK)); a(("STA",MI))
    a(("LDX",MI)); a(("LDAX",MGRID)); a(("ANDI",0x02)); a(("JNZ","fl_loop"))     # already revealed
    a(("LDX",MI)); a(("LDAX",MGRID)); a(("ANDI",0x04)); a(("JNZ","fl_loop"))     # flagged -> leave
    a(("LDX",MI)); a(("LDAX",MGRID)); a(("ADDI",2)); a(("STAX",MGRID))           # set revealed
    a(("LDA",MNREV)); a(("ADDI",1)); a(("STA",MNREV))
    a(("LDX",MI)); a(("LDAX",MGRID)); a(("ANDI",0xF0)); a(("JNZ","fl_loop"))     # count>0 -> stop flood here
    a(("LDA",MI)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("STA",MR)); a(("LDA",MI)); a(("ANDI",0x07)); a(("STA",MC))
    def push_action(k):
        a(("LDAX",MGRID)); a(("ANDI",0x0A)); a(("JNZ",f"fl_ps{k}"))              # revealed or queued -> skip
        a(("LDAX",MGRID)); a(("ADDI",0x08)); a(("STAX",MGRID))                   # mark queued
        a(("TXA",)); a(("STA",MTMP)); a(("LDX",MSP)); a(("LDA",MTMP)); a(("STAX",MSTK)); a(("LDA",MSP)); a(("ADDI",1)); a(("STA",MSP))
        a((f"fl_ps{k}:",))
    gen_neighbors(push_action, "fl")
    a(("JMP","fl_loop")); a(("fl_done:",)); a(("RET",))
    # draw the minesweeper window body (top bar + 8x8 grid, unrolled)
    a(("draw_mine:",))
    wx(AX,8); wy(AY,16); a(("LDI",30)); a(("STA",AW)); a(("LDI",11)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    wx(GX,13); wy(GY,18); a(("LDI",gi('N'))); a(("STA",GCH)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    wx(AX,42); wy(AY,16); a(("LDI",30)); a(("STA",AW)); a(("LDI",11)); a(("STA",AH))
    a(("LDA",MFLAG)); a(("JZ","dm_fn")); a(("LDI",RED)); a(("JMP","dm_fc")); a(("dm_fn:",)); a(("LDI",SIL)); a(("dm_fc:",)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    wx(GX,47); wy(GY,18); a(("LDI",gi('F'))); a(("STA",GCH)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    a(("LDA",MOVER)); a(("CMPI",1)); a(("JZ","dm_lose")); a(("CMPI",2)); a(("JZ","dm_win")); a(("JMP","dm_grid"))
    a(("dm_lose:",)); wx(GX,80); wy(GY,18); a(("LDI",gi('x'))); a(("STA",GCH)); a(("LDI",RED)); a(("STA",GCOL)); a(("CALL","blitglyph")); a(("JMP","dm_grid"))
    a(("dm_win:",)); wx(GX,80); wy(GY,18); a(("LDI",gi('W'))); a(("STA",GCH)); a(("LDI",GRN)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    a(("dm_grid:",))
    for r in range(GW):
        for c in range(GW):
            idx=r*GW+c; cx=10+c*14; cy=30+r*14; t=f"cm{idx}"
            a(("LXI",idx)); a(("LDAX",MGRID)); a(("STA",MTMP))
            a(("ANDI",0x02)); a(("JZ",f"{t}_h"))
            a(("LDA",MTMP)); a(("ANDI",0x01)); a(("JZ",f"{t}_sf"))
            wx(AX,cx); wy(AY,cy); a(("LDI",13)); a(("STA",AW)); a(("STA",AH)); a(("LDI",RED)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("JMP",f"{t}_d"))
            a((f"{t}_sf:",)); wx(AX,cx); wy(AY,cy); a(("LDI",13)); a(("STA",AW)); a(("STA",AH)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
            a(("LDA",MTMP)); a(("ANDI",0xF0)); a(("JZ",f"{t}_d"))
            a(("LDA",MTMP)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("SHR",)); a(("STA",GCH))
            wx(GX,cx+4); wy(GY,cy+3); a(("LDI",NAV)); a(("STA",GCOL)); a(("CALL","blitglyph")); a(("JMP",f"{t}_d"))
            a((f"{t}_h:",)); a(("LDA",MOVER)); a(("CMPI",1)); a(("JNZ",f"{t}_b")); a(("LDA",MTMP)); a(("ANDI",0x01)); a(("JZ",f"{t}_b"))
            wx(AX,cx); wy(AY,cy); a(("LDI",13)); a(("STA",AW)); a(("STA",AH)); a(("LDI",RED)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("JMP",f"{t}_d"))
            a((f"{t}_b:",)); wx(AX,cx); wy(AY,cy); a(("LDI",13)); a(("STA",AW)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
            a(("LDA",MTMP)); a(("ANDI",0x04)); a(("JZ",f"{t}_d"))
            wx(GX,cx+4); wy(GY,cy+3); a(("LDI",gi('F'))); a(("STA",GCH)); a(("LDI",RED)); a(("STA",GCOL)); a(("CALL","blitglyph"))
            a((f"{t}_d:",))
    a(("RET",))

    # ---- start menu ----
    a(("drawmenu:",))
    a(("LDI",2)); a(("STA",AX)); a(("LDI",123)); a(("STA",AY)); a(("LDI",70)); a(("STA",AW)); a(("LDI",59)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    a(("LDI",8)); a(("STA",SX)); a(("LDI",126)); a(("STA",SY)); a(("LDI",soff("writer"))); a(("STA",SPTR)); a(("LDI",BLK)); a(("STA",SCOL)); a(("CALL","puts2"))
    a(("LDI",8)); a(("STA",SX)); a(("LDI",137)); a(("STA",SY)); a(("LDI",soff("sheet"))); a(("STA",SPTR)); a(("LDI",BLK)); a(("STA",SCOL)); a(("CALL","puts2"))
    a(("LDI",8)); a(("STA",SX)); a(("LDI",148)); a(("STA",SY)); a(("LDI",soff("calc"))); a(("STA",SPTR)); a(("LDI",BLK)); a(("STA",SCOL)); a(("CALL","puts2"))
    a(("LDI",8)); a(("STA",SX)); a(("LDI",159)); a(("STA",SY)); a(("LDI",soff("paint"))); a(("STA",SPTR)); a(("LDI",BLK)); a(("STA",SCOL)); a(("CALL","puts2"))
    a(("LDI",8)); a(("STA",SX)); a(("LDI",170)); a(("STA",SY)); a(("LDI",soff("mine"))); a(("STA",SPTR)); a(("LDI",BLK)); a(("STA",SCOL)); a(("CALL","puts2"))
    a(("RET",))

    # ============ boot + main ============
    a(("boot:",)); a(("LDI",0))
    for v in (APP,START,MBP,HAVES,C_ACC,C_CUR,C_OP,TLEN,SELC,BLINK,KEY,DRAG,BOLD,PCOL,MFLAG): a(("STA",v))
    a(("LDI",1)); a(("STA",C_FRESH)); a(("STA",DIRTY))
    a(("CALL","clearpaint"))    # paint canvas starts white
    a(("LDI",0x4D)); a(("STA",MSEED)); a(("CALL","mnew"))   # minesweeper: seed LCG + first board
    a(("LDI",80)); a(("STA",CX)); a(("STA",OCX)); a(("LDI",70)); a(("STA",CY)); a(("STA",OCY))
    a(("LDI",WINX)); a(("STA",WX)); a(("LDI",WINY)); a(("STA",WY))
    a(("main:",))
    a(("LDA",MX)); a(("CMPI",W-8)); a(("JNC","cxok")); a(("LDI",W-8)); a(("STA",CX)); a(("JMP","cxd")); a(("cxok:",)); a(("LDA",MX)); a(("STA",CX)); a(("cxd:",))
    a(("LDA",MY)); a(("CMPI",H-8)); a(("JNC","cyok")); a(("LDI",H-8)); a(("STA",CY)); a(("JMP","cyd")); a(("cyok:",)); a(("LDA",MY)); a(("STA",CY)); a(("cyd:",))
    a(("LDA",MB)); a(("JZ","noedge")); a(("LDA",MBP)); a(("JNZ","noedge")); a(("CALL","onclick")); a(("noedge:",))
    # window dragging (title-bar grab set DRAG in onclick; follow the mouse while held)
    a(("LDA",DRAG)); a(("JZ","nodrag")); a(("LDA",MB)); a(("JZ","dragend"))
    a(("LDA",MX)); a(("SUB",DOFX)); a(("STA",WX)); a(("LDA",MY)); a(("SUB",DOFY)); a(("STA",WY)); a(("LDI",1)); a(("STA",DIRTY)); a(("JMP","nodrag"))
    a(("dragend:",)); a(("LDI",0)); a(("STA",DRAG))
    a(("nodrag:",))
    # Paint: drag to draw (button held over the canvas)
    a(("LDA",APP)); a(("CMPI",4)); a(("JNZ","npaint")); a(("LDA",MB)); a(("JZ","npaint")); a(("CALL","pokepaint")); a(("npaint:",))
    a(("CALL","keyin"))                       # keyboard (writer/sheet)
    # blink counter
    a(("LDA",BLINK)); a(("ADDI",1)); a(("STA",BLINK)); a(("ANDI",7)); a(("JNZ","nbd")); a(("LDA",APP)); a(("CMPI",1)); a(("JNZ","nbd")); a(("LDI",1)); a(("STA",DIRTY)); a(("nbd:",))
    a(("LDA",HAVES)); a(("JZ","rdty")); a(("LDA",DIRTY)); a(("JNZ","rdty")); a(("CALL","restun")); a(("rdty:",))
    a(("LDA",DIRTY)); a(("JZ","rnod")); a(("CALL","draw")); a(("LDI",0)); a(("STA",DIRTY)); a(("rnod:",))
    a(("CALL","saveun")); a(("LDI",1)); a(("STA",HAVES)); a(("LDA",CX)); a(("STA",OCX)); a(("LDA",CY)); a(("STA",OCY)); a(("CALL","drawcur"))
    a(("LDA",MB)); a(("STA",MBP)); a(("FRAME",)); a(("JMP","main"))

    # ---- keyboard: writer text input ----
    a(("keyin:",)); a(("LDA",KEY)); a(("JZ","ki_d"))
    a(("LDA",APP)); a(("CMPI",1)); a(("JZ","ki_writer"))
    a(("LDA",APP)); a(("CMPI",2)); a(("JZ","ki_sheet"))
    a(("JMP","ki_eat"))                                   # other apps -> consume key, ignore
    # WRITER: append any char (incl. 0xFD newline) ; 0xFE = backspace
    a(("ki_writer:",)); a(("LDA",KEY)); a(("CMPI",0xFE)); a(("JZ","ki_bs"))
    a(("LDX",TLEN)); a(("LDA",KEY)); a(("STAX",TBUF)); a(("LDA",TLEN)); a(("CMPI",90)); a(("JC","ki_dty")); a(("ADDI",1)); a(("STA",TLEN)); a(("JMP","ki_dty"))
    a(("ki_bs:",)); a(("LDA",TLEN)); a(("JZ","ki_dty")); a(("SUBI",1)); a(("STA",TLEN)); a(("JMP","ki_dty"))
    # SHEET: digit keys (glyph idx 0..9) type into the selected cell ; 0xFE = clear cell
    a(("ki_sheet:",)); a(("LDA",KEY)); a(("CMPI",0xFE)); a(("JZ","ks_clr"))
    a(("LDA",KEY)); a(("CMPI",10)); a(("JNC","ks_dig"))   # KEY<10 -> a digit
    a(("JMP","ki_eat"))                                   # non-digit -> ignore
    # fresh cell? clear it first so the first digit replaces the old value (real-spreadsheet feel)
    a(("ks_dig:",)); a(("LDA",SFRESH)); a(("JZ","ks_app")); a(("LDI",0)); a(("STA",SFRESH)); a(("LDI",0)); a(("LDX",SELC)); a(("STAX",CELLS))
    a(("ks_app:",)); a(("LDX",SELC)); a(("LDAX",CELLS)); a(("CMPI",10)); a(("JC","ki_dty"))   # 2-digit cap
    a(("SHL",)); a(("STA",T1)); a(("LDA",T1)); a(("SHL",)); a(("SHL",)); a(("ADD",T1)); a(("ADD",KEY)); a(("LDX",SELC)); a(("STAX",CELLS)); a(("JMP","ki_dty"))
    a(("ks_clr:",)); a(("LDI",0)); a(("LDX",SELC)); a(("STAX",CELLS))
    a(("ki_dty:",)); a(("LDI",1)); a(("STA",DIRTY))
    a(("ki_eat:",)); a(("LDI",0)); a(("STA",KEY)); a(("ki_d:",)); a(("RET",))

    # ---- click handling ----
    a(("onclick:",))
    # start button (taskbar): x2..42, y183..191
    a(("LDA",MX)); a(("CMPI",2)); a(("JNC","oc_notstart")); a(("CMPI",43)); a(("JC","oc_notstart")); a(("LDA",MY)); a(("CMPI",182)); a(("JNC","oc_notstart"))
    a(("LDA",START)); a(("JNZ","oc_sclose")); a(("LDI",1)); a(("STA",START)); a(("JMP","oc_dirty")); a(("oc_sclose:",)); a(("LDI",0)); a(("STA",START)); a(("JMP","oc_dirty"))
    a(("oc_notstart:",))
    # start menu items (if open): box x2..72 y123..182, items at y126/137/148/159/170
    a(("LDA",START)); a(("JZ","oc_nomenu"))
    a(("LDA",MX)); a(("CMPI",2)); a(("JNC","oc_menudone")); a(("CMPI",72)); a(("JC","oc_menudone"))
    a(("LDA",MY)); a(("CMPI",134)); a(("JNC","oc_pickw")); a(("CMPI",145)); a(("JNC","oc_picks")); a(("CMPI",156)); a(("JNC","oc_pickc")); a(("CMPI",167)); a(("JNC","oc_pickp")); a(("CMPI",178)); a(("JNC","oc_pickm")); a(("JMP","oc_menudone"))
    a(("oc_pickw:",)); a(("LDI",1)); a(("STA",APP)); a(("JMP","oc_mclose")); a(("oc_picks:",)); a(("LDI",2)); a(("STA",APP)); a(("JMP","oc_mclose"))
    a(("oc_pickc:",)); a(("LDI",3)); a(("STA",APP)); a(("JMP","oc_mclose")); a(("oc_pickp:",)); a(("LDI",4)); a(("STA",APP)); a(("JMP","oc_mclose")); a(("oc_pickm:",)); a(("LDI",5)); a(("STA",APP))
    a(("oc_mclose:",)); a(("LDI",0)); a(("STA",START)); a(("JMP","oc_dirty"))
    a(("oc_menudone:",)); a(("LDI",0)); a(("STA",START)); a(("JMP","oc_dirty"))
    a(("oc_nomenu:",))
    a(("LDA",APP)); a(("JZ","oc_ret"))
    # close box: WX+WW-13..WW-3, WY+3..13
    hx(WW-13,"oc_nocb",False); hx(WW-3,"oc_nocb",True); hy(3,"oc_nocb",False); hy(13,"oc_nocb",True)
    a(("LDI",0)); a(("STA",APP)); a(("JMP","oc_dirty"))    # close box hit
    a(("oc_nocb:",))
    # title bar -> start drag: WX+2..WW-14, WY+2..14
    hx(2,"oc_notitle",False); hx(WW-14,"oc_notitle",True); hy(2,"oc_notitle",False); hy(14,"oc_notitle",True)
    a(("LDI",1)); a(("STA",DRAG)); a(("LDA",MX)); a(("SUB",WX)); a(("STA",DOFX)); a(("LDA",MY)); a(("SUB",WY)); a(("STA",DOFY)); a(("RET",))
    a(("oc_notitle:",))
    a(("LDA",APP)); a(("CMPI",2)); a(("JZ","oc_sheet")); a(("CMPI",3)); a(("JZ","oc_calc")); a(("CMPI",4)); a(("JZ","oc_paint")); a(("CMPI",5)); a(("JZ","oc_mine")); a(("JMP","oc_dirty"))  # writer body: nothing on click
    # sheet clicks: cells + +/- buttons
    a(("oc_sheet:",))
    for idx,(bx,by) in enumerate(SCELLS):
        lbl=f"scm{idx}"
        hx(bx,lbl,False); hx(bx+32,lbl,True); hy(by,lbl,False); hy(by+14,lbl,True)
        a(("LDI",idx)); a(("STA",SELC)); a(("LDI",1)); a(("STA",SFRESH)); a(("JMP","oc_dirty")); a((f"{lbl}:",))
    hx(8,"oc_minus",False); hx(24,"oc_minus",True); hy(94,"oc_minus",False); hy(108,"oc_minus",True)
    a(("LDX",SELC)); a(("LDAX",CELLS)); a(("ADDI",1)); a(("STAX",CELLS)); a(("JMP","oc_dirty"))
    a(("oc_minus:",))
    hx(28,"oc_dirty",False); hx(44,"oc_dirty",True); hy(94,"oc_dirty",False); hy(108,"oc_dirty",True)
    a(("LDX",SELC)); a(("LDAX",CELLS)); a(("JZ","oc_dirty")); a(("SUBI",1)); a(("STAX",CELLS)); a(("JMP","oc_dirty"))
    # calc clicks
    a(("oc_calc:",))
    for idx,(bx,by,lab,kind,val) in enumerate(CBTNS):
        lbl=f"ccm{idx}"
        hx(bx,lbl,False); hx(bx+BTN_W,lbl,True); hy(by,lbl,False); hy(by+BTN_H,lbl,True)
        if kind=='d': a(("LDI",val)); a(("STA",T0)); a(("CALL","cdig"))
        elif kind=='o': a(("LDI",val)); a(("STA",T0)); a(("CALL","cop"))
        elif kind=='e': a(("CALL","ceq"))
        elif kind=='c': a(("CALL","cclr"))
        a(("JMP","oc_dirty")); a((f"{lbl}:",))
    a(("oc_dirty:",)); a(("LDI",1)); a(("STA",DIRTY)); a(("oc_ret:",)); a(("RET",))

    # paint clicks: palette swatches (right strip) + clear button
    a(("oc_paint:",))
    for i,col in enumerate(PSWATCH):
        y=18+i*14; lbl=f"pswn{i}"
        hx(106,lbl,False); hx(136,lbl,True); hy(y,lbl,False); hy(y+12,lbl,True)
        a(("LDI",col)); a(("STA",PCOL)); a(("JMP","oc_dirty")); a((f"{lbl}:",))
    hx(106,"oc_dirty",False); hx(136,"oc_dirty",True); hy(132,"oc_dirty",False); hy(145,"oc_dirty",True)
    a(("CALL","clearpaint")); a(("JMP","oc_dirty"))

    # minesweeper clicks: New / Flag-toggle / grid cell
    a(("oc_mine:",))
    hx(8,"m_nf",False); hx(38,"m_nf",True); hy(16,"m_nf",False); hy(27,"m_nf",True)
    a(("CALL","mnew")); a(("JMP","oc_dirty")); a(("m_nf:",))
    hx(42,"m_ff",False); hx(72,"m_ff",True); hy(16,"m_ff",False); hy(27,"m_ff",True)
    a(("LDA",MFLAG)); a(("JZ","m_fon")); a(("LDI",0)); a(("STA",MFLAG)); a(("JMP","oc_dirty")); a(("m_fon:",)); a(("LDI",1)); a(("STA",MFLAG)); a(("JMP","oc_dirty")); a(("m_ff:",))
    a(("LDA",MOVER)); a(("JNZ","oc_dirty"))                       # game over -> only New/Flag act
    hx(10,"oc_dirty",False); hx(122,"oc_dirty",True); hy(30,"oc_dirty",False); hy(142,"oc_dirty",True)
    a(("LDA",MX)); a(("SUB",WX)); a(("SUBI",10)); a(("STA",MTMP)); a(("LDI",0)); a(("STA",MC))
    a(("m_cd:",)); a(("LDA",MTMP)); a(("CMPI",14)); a(("JNC","m_cdd")); a(("SUBI",14)); a(("STA",MTMP)); a(("LDA",MC)); a(("ADDI",1)); a(("STA",MC)); a(("JMP","m_cd")); a(("m_cdd:",))
    a(("LDA",MY)); a(("SUB",WY)); a(("SUBI",30)); a(("STA",MTMP)); a(("LDI",0)); a(("STA",MR))
    a(("m_rd:",)); a(("LDA",MTMP)); a(("CMPI",14)); a(("JNC","m_rdd")); a(("SUBI",14)); a(("STA",MTMP)); a(("LDA",MR)); a(("ADDI",1)); a(("STA",MR)); a(("JMP","m_rd")); a(("m_rdd:",))
    a(("LDA",MC)); a(("CMPI",GW)); a(("JC","oc_dirty")); a(("LDA",MR)); a(("CMPI",GW)); a(("JC","oc_dirty"))
    a(("LDA",MR)); a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("ADD",MC)); a(("STA",MIDX))
    a(("LDA",MFLAG)); a(("JZ","m_rev"))
    a(("LDX",MIDX)); a(("LDAX",MGRID)); a(("ANDI",0x02)); a(("JNZ","oc_dirty"))   # revealed -> can't flag
    a(("LDX",MIDX)); a(("LDAX",MGRID)); a(("ANDI",0x04)); a(("JNZ","m_unflag"))
    a(("LDX",MIDX)); a(("LDAX",MGRID)); a(("ADDI",0x04)); a(("STAX",MGRID)); a(("JMP","oc_dirty"))
    a(("m_unflag:",)); a(("LDX",MIDX)); a(("LDAX",MGRID)); a(("SUBI",0x04)); a(("STAX",MGRID)); a(("JMP","oc_dirty"))
    a(("m_rev:",))
    a(("LDX",MIDX)); a(("LDAX",MGRID)); a(("ANDI",0x04)); a(("JNZ","oc_dirty"))   # flagged -> don't reveal
    a(("LDX",MIDX)); a(("LDAX",MGRID)); a(("ANDI",0x02)); a(("JNZ","oc_dirty"))   # already revealed
    a(("LDX",MIDX)); a(("LDAX",MGRID)); a(("ANDI",0x01)); a(("JZ","m_safe"))
    a(("LDI",1)); a(("STA",MOVER)); a(("JMP","oc_dirty"))                         # mine -> lose
    a(("m_safe:",)); a(("CALL","mreveal"))
    a(("LDA",MNREV)); a(("CMPI",64-MINES)); a(("JNC","oc_dirty")); a(("LDI",2)); a(("STA",MOVER)); a(("JMP","oc_dirty"))   # all safe revealed -> win

    # calc ops (8-bit display via C_CUR; result shown in C_CUR)
    a(("cdig:",)); a(("LDA",C_FRESH)); a(("JZ","cd_a")); a(("LDI",0)); a(("STA",C_CUR)); a(("LDI",0)); a(("STA",C_FRESH))
    a(("cd_a:",)); a(("LDA",C_CUR)); a(("CMPI",10)); a(("JC","cd_s")); a(("LDA",C_CUR)); a(("SHL",)); a(("STA",T1)); a(("LDA",T1)); a(("SHL",)); a(("SHL",)); a(("ADD",T1)); a(("ADD",T0)); a(("STA",C_CUR)); a(("cd_s:",)); a(("RET",))
    a(("cop:",)); a(("LDA",C_CUR)); a(("STA",C_ACC)); a(("LDA",T0)); a(("STA",C_OP)); a(("LDI",1)); a(("STA",C_FRESH)); a(("RET",))
    a(("cclr:",)); a(("LDI",0)); a(("STA",C_ACC)); a(("STA",C_CUR)); a(("STA",C_OP)); a(("LDI",1)); a(("STA",C_FRESH)); a(("RET",))
    a(("ceq:",)); a(("LDA",C_OP)); a(("CMPI",0)); a(("JZ","ce_add")); a(("CMPI",1)); a(("JZ","ce_sub")); a(("CMPI",2)); a(("JZ","ce_mul")); a(("JMP","ce_div"))
    a(("ce_add:",)); a(("LDA",C_ACC)); a(("ADD",C_CUR)); a(("STA",C_CUR)); a(("JMP","ce_f"))
    a(("ce_sub:",)); a(("LDA",C_ACC)); a(("CMP",C_CUR)); a(("JNC","ce_z")); a(("LDA",C_ACC)); a(("SUB",C_CUR)); a(("STA",C_CUR)); a(("JMP","ce_f"))
    a(("ce_mul:",)); a(("LDI",0)); a(("STA",T1)); a(("LDA",C_CUR)); a(("STA",I)); a(("cem:",)); a(("LDA",I)); a(("JZ","cem_d")); a(("LDA",T1)); a(("ADD",C_ACC)); a(("STA",T1)); a(("LDA",I)); a(("SUBI",1)); a(("STA",I)); a(("JMP","cem")); a(("cem_d:",)); a(("LDA",T1)); a(("STA",C_CUR)); a(("JMP","ce_f"))
    a(("ce_div:",)); a(("LDA",C_CUR)); a(("JZ","ce_z")); a(("LDI",0)); a(("STA",QLO)); a(("cev:",)); a(("LDA",C_ACC)); a(("CMP",C_CUR)); a(("JNC","cev_d")); a(("LDA",C_ACC)); a(("SUB",C_CUR)); a(("STA",C_ACC)); a(("LDA",QLO)); a(("ADDI",1)); a(("STA",QLO)); a(("JMP","cev")); a(("cev_d:",)); a(("LDA",QLO)); a(("STA",C_CUR)); a(("JMP","ce_f"))
    a(("ce_z:",)); a(("LDI",0)); a(("STA",C_CUR))
    a(("ce_f:",)); a(("LDI",1)); a(("STA",C_FRESH)); a(("RET",))
    return asm(L)

if __name__=="__main__":
    m=CA1Sys(fb_addr=FB,fb_w=W,fb_h=H); load_memory(m); m.SP=STACK
    m.M[MX]=80;m.M[MY]=70;m.M[MB]=0
    code=program(); prog,_=code
    print("CA-OFFICE program:", len(prog), "instructions")
    m.run(code,max_i=6_000_000,frame_on=lambda mm:True)
    print("boots, first frame instr:", m.icount)
