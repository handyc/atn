#!/usr/bin/env python3
# caos2.py — CA-OS v2: a faster, more Windows-like desktop running ENTIRELY on CA-1.
# Upgrades over v1: 256x192 framebuffer with PAGE-ALIGNED addressing (FB=0x4000, so pixel
# (x,y) = 0x4000 + (y<<8) + x  -> no row tables, address math is trivial); a readable 5x7
# font for window titles/labels; beveled 3D Win9x window + button chrome; a smooth software
# mouse cursor with save-under/restore; a draggable window; and DIRTY-RECTANGLE rendering —
# the full UI is repainted only when something changes, so an idle frame only repaints the
# 8x12 area under the cursor (~hundreds of instructions) instead of all 49,152 pixels.
# Browser stays a dumb terminal (blit framebuffer + forward mouse). rulehub-free; pure CA-1.
import json
from ca1sys import CA1Sys, asm

W, H, FB = 256, 192, 0x4000          # FB occupies 0x4000..0xFFFF exactly (256*192=49152)
FBPAGE = FB >> 8                      # 0x40
STACK = 0x3F00                        # call/data stack BELOW the framebuffer (vars/font are <0x800)
# palette (Win9x): 0 black 1 teal 2 silver 3 gray 4 white 5 navy 6 ltsilver 7 blue 8 red 9 green
PAL = ["#000000","#008080","#c0c0c0","#808080","#ffffff","#000080","#dfdfdf","#1084d0","#b00000","#107010"]
BLK,TEAL,SIL,GRY,WHT,NAV,LSV,BLU,RED,GRN = range(10)

# ---- zero-page vars ----
AX,AY,AW,AH,ACOL = 0x10,0x11,0x12,0x13,0x14
GX,GY,GCH,GCOL   = 0x15,0x16,0x17,0x18
RR,CC,T0,T1,T2,T3= 0x19,0x1A,0x1B,0x1C,0x1D,0x1E
MX,MY,MB,MBP     = 0x20,0x21,0x22,0x23
CX,CY,OCX,OCY,HAVES,DIRTY = 0x24,0x25,0x26,0x27,0x28,0x29
WINX,WINY,DRAG,DOFX,DOFY  = 0x2A,0x2B,0x2C,0x2D,0x2E
C_ACC,C_CUR,C_OP,C_FRESH,C_HASR = 0x30,0x31,0x32,0x33,0x34
NVL,NVH,QLO,QHI,REM,I = 0x35,0x36,0x37,0x38,0x39,0x3A
D0,D1,D2,D3,D4 = 0x3B,0x3C,0x3D,0x3E,0x3F
SX,SY,SPTR,SCOL = 0x40,0x41,0x42,0x43          # puts args

CURBUF = 0x0300        # 8*16 save-under buffer (128 bytes)
FONT   = 0x0500        # 5x7 font, 7 bytes/glyph
STRTAB = 0x0700        # string table (glyph-index sequences, 0xFF terminated)

# ---- 5x7 font (ascii art) ----
GART = {
 '0':[".###.","#...#","#..##","#.#.#","##..#","#...#",".###."],
 '1':["..#..",".##..","..#..","..#..","..#..","..#..",".###."],
 '2':[".###.","#...#","....#","..##.",".#...","#....","#####"],
 '3':["#####","....#","...#.","..##.","....#","#...#",".###."],
 '4':["...#.","..##.",".#.#.","#..#.","#####","...#.","...#."],
 '5':["#####","#....","####.","....#","....#","#...#",".###."],
 '6':["..##.",".#...","#....","####.","#...#","#...#",".###."],
 '7':["#####","....#","...#.","..#..",".#...",".#...",".#..."],
 '8':[".###.","#...#","#...#",".###.","#...#","#...#",".###."],
 '9':[".###.","#...#","#...#",".####","....#","...#.",".##.."],
 '+':[".....","..#..","..#..","#####","..#..","..#..","....."],
 '-':[".....",".....",".....","#####",".....",".....","....."],
 'x':[".....",".....","#...#",".#.#.","..#..",".#.#.","#...#"],
 '/':["..#..",".....",".....","#####",".....",".....","..#.."],
 '=':[".....",".....","#####",".....","#####",".....","....."],
 ' ':[".....",".....",".....",".....",".....",".....","....."],
 '.':[".....",".....",".....",".....",".....",".##..",".##.."],
 'A':[".###.","#...#","#...#","#####","#...#","#...#","#...#"],
 'B':["####.","#...#","#...#","####.","#...#","#...#","####."],
 'C':[".###.","#...#","#....","#....","#....","#...#",".###."],
 'L':["#....","#....","#....","#....","#....","#....","#####"],
 'O':[".###.","#...#","#...#","#...#","#...#","#...#",".###."],
 'R':["####.","#...#","#...#","####.","#.#..","#..#.","#...#"],
 'S':[".####","#....","#....",".###.","....#","....#","####."],
 'T':["#####","..#..","..#..","..#..","..#..","..#..","..#.."],
 'U':["#...#","#...#","#...#","#...#","#...#","#...#",".###."],
}
GLYPHS = list(GART.keys())
GIDX = {ch:i for i,ch in enumerate(GLYPHS)}
STRINGS = {"CALCULATOR":0x700, "START":0x720, "CA-OS 2":0x740}
def enc_rows(rows):
    out=[]
    for r in rows:
        b=0
        for c in range(5):
            if r[c]=='#': b|=(1<<(4-c))
        out.append(b)
    return out

# calculator geometry (window-relative)
DISP=(8,20,104,16)          # x,y,w,h within window
BTN_W,BTN_H,BX0,BY0,GX_,GY_=24,18,8,42,2,2
def buttons():
    layout=[[('7','d',7),('8','d',8),('9','d',9),('/','o',3)],
            [('4','d',4),('5','d',5),('6','d',6),('x','o',2)],
            [('1','d',1),('2','d',2),('3','d',3),('-','o',1)],
            [('0','d',0),('C','c',0),('=','e',0),('+','o',0)]]
    out=[]
    for r,row in enumerate(layout):
        for c,(lab,kind,val) in enumerate(row):
            x=BX0+c*(BTN_W+GX_); y=BY0+r*(BTN_H+GY_)
            out.append((x,y,lab,kind,val))
    return out
BTNS=buttons()
WW,WH=112,142   # window size

# cursor sprite (8 wide x 12 tall): K outline, W fill, . transparent
CUR=["K.......","KK......","KWK.....","KWWK....","KWWWK...","KWWWWK..",
     "KWWWWWK.","KWWWWWWK","KWWWKKK.","KWK.KWK.","KK...KWK","......K."]
CURPIX=[]
for dy,row in enumerate(CUR):
    for dx,ch in enumerate(row):
        if ch=='W': CURPIX.append((dx,dy,WHT))
        elif ch=='K': CURPIX.append((dx,dy,BLK))
CURW,CURH=8,12

def load_memory(m):
    for ch,i in GIDX.items():
        for r,b in enumerate(enc_rows(GART[ch])): m.M[FONT+i*7+r]=b
    for s,addr in STRINGS.items():
        for j,ch in enumerate(s): m.M[addr+j]=GIDX.get(ch, GIDX[' '])
        m.M[addr+len(s)]=0xFF

def program():
    L=[]; a=L.append
    # ---------- helpers emitted as subroutines ----------
    a(("JMP","boot"))

    # setpix-row: set P = FB + (T0<<8) (row T0, col 0). uses A.
    # fillrect(AX,AY,AW,AH,ACOL): AW<=255
    a(("fillrect:",))
    a(("LDA",AH)); a(("STA",RR)); a(("LDA",AY)); a(("STA",T0))
    a(("fr_row:",)); a(("LDA",RR)); a(("JZ","fr_done"))
    a(("LDI",0)); a(("PLO",)); a(("LDA",T0)); a(("ADDI",FBPAGE)); a(("PHI",))
    a(("LDA",AW)); a(("STA",CC)); a(("LDA",AX)); a(("TAX",))
    a(("fr_col:",)); a(("LDA",CC)); a(("JZ","fr_nr"))
    a(("LDA",ACOL)); a(("STPX",)); a(("INX",)); a(("LDA",CC)); a(("SUBI",1)); a(("STA",CC)); a(("JMP","fr_col"))
    a(("fr_nr:",)); a(("LDA",T0)); a(("ADDI",1)); a(("STA",T0)); a(("LDA",RR)); a(("SUBI",1)); a(("STA",RR)); a(("JMP","fr_row"))
    a(("fr_done:",)); a(("RET",))

    # bevel(AX,AY,AW,AH): raised 3D border. top+left = WHT, bottom+right = GRY (over face)
    a(("bevel:",))
    # top line
    a(("LDA",AH)); a(("STA",T3))                      # save AH
    a(("LDI",1)); a(("STA",AH)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
    # left line
    a(("LDA",T3)); a(("STA",AH)); a(("LDA",AW)); a(("STA",T2)); a(("LDI",1)); a(("STA",AW)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
    # bottom line: y=AY+AH-1
    a(("LDA",T2)); a(("STA",AW)); a(("LDA",AY)); a(("STA",T1)); a(("LDA",AY)); a(("ADD",AH)); a(("SUBI",1)); a(("STA",AY))
    a(("LDI",1)); a(("STA",AH)); a(("LDI",GRY)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDA",T1)); a(("STA",AY))
    # right line: x=AX+AW-1
    a(("LDA",AX)); a(("STA",T1)); a(("LDA",AX)); a(("ADD",AW)); a(("SUBI",1)); a(("STA",AX))
    a(("LDA",T3)); a(("STA",AH)); a(("LDI",1)); a(("STA",AW)); a(("LDI",GRY)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDA",T1)); a(("STA",AX)); a(("LDA",T2)); a(("STA",AW)); a(("LDA",T3)); a(("STA",AH))
    a(("RET",))

    # blitglyph(GX,GY,GCH,GCOL) 5x7
    a(("blitglyph:",))
    a(("LDA",GCH)); a(("STA",T1)); a(("SHL",)); a(("SHL",)); a(("STA",T2))   # *4
    a(("LDA",T2)); a(("SHL",)); a(("SUB",T1)); a(("STA",T1))                 # *8 - *1 = *7
    a(("LDI",0)); a(("STA",T2))
    a(("bg_row:",)); a(("LDA",T2)); a(("CMPI",7)); a(("JC","bg_done"))
    a(("LDA",T1)); a(("ADD",T2)); a(("TAX",)); a(("LDAX",FONT)); a(("STA",T3))   # row bits
    a(("LDI",0)); a(("PLO",)); a(("LDA",GY)); a(("ADD",T2)); a(("ADDI",FBPAGE)); a(("PHI",))
    for col in range(5):
        bit=1<<(4-col); lbl=f"bgc{col}"
        a(("LDA",T3)); a(("ANDI",bit)); a(("JZ",lbl)); a(("LDA",GX)); a(("ADDI",col)); a(("TAX",)); a(("LDA",GCOL)); a(("STPX",)); a((f"{lbl}:",))
    a(("LDA",T2)); a(("ADDI",1)); a(("STA",T2)); a(("JMP","bg_row"))
    a(("bg_done:",)); a(("RET",))

    # puts2: SPTR holds low byte offset into a fixed page 0x07; read M[0x0700+idx]
    a(("puts2:",)); a(("LDA",SX)); a(("STA",GX)); a(("LDI",0)); a(("STA",T0))   # T0 = char index
    a(("pl2:",)); a(("LDA",SPTR)); a(("ADD",T0)); a(("TAX",)); a(("LDAX",0x0700)); a(("STA",T1))
    a(("CMPI",0xFF)); a(("JZ","pl2_done"))
    a(("LDA",T1)); a(("STA",GCH)); a(("LDA",SY)); a(("STA",GY)); a(("LDA",SCOL)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    a(("LDA",GX)); a(("ADDI",6)); a(("STA",GX))
    a(("LDA",T0)); a(("ADDI",1)); a(("STA",T0)); a(("JMP","pl2"))
    a(("pl2_done:",)); a(("RET",))

    # ---------- cursor save/restore/draw ----------
    # save_under: copy CURW x CURH block at (CX,CY) -> CURBUF
    a(("saveun:",)); a(("LDI",0)); a(("STA",T2))      # row
    a(("su_r:",)); a(("LDA",T2)); a(("CMPI",CURH)); a(("JC","su_done"))
    a(("LDI",0)); a(("PLO",)); a(("LDA",CY)); a(("ADD",T2)); a(("ADDI",FBPAGE)); a(("PHI",))
    a(("LDI",0)); a(("STA",T3))                       # col
    a(("su_c:",)); a(("LDA",T3)); a(("CMPI",CURW)); a(("JC","su_nr"))
    a(("LDA",CX)); a(("ADD",T3)); a(("TAX",)); a(("LDPX",))     # A = pixel
    a(("STA",T1))
    # CURBUF index = T2*CURW + T3 (CURW=8 -> T2<<3 + T3)
    a(("LDA",T2)); a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("ADD",T3)); a(("TAX",)); a(("LDA",T1)); a(("STAX",CURBUF))
    a(("LDA",T3)); a(("ADDI",1)); a(("STA",T3)); a(("JMP","su_c"))
    a(("su_nr:",)); a(("LDA",T2)); a(("ADDI",1)); a(("STA",T2)); a(("JMP","su_r"))
    a(("su_done:",)); a(("RET",))

    # restore_under at (OCX,OCY)
    a(("restun:",)); a(("LDI",0)); a(("STA",T2))
    a(("ru_r:",)); a(("LDA",T2)); a(("CMPI",CURH)); a(("JC","ru_done"))
    a(("LDI",0)); a(("PLO",)); a(("LDA",OCY)); a(("ADD",T2)); a(("ADDI",FBPAGE)); a(("PHI",))
    a(("LDI",0)); a(("STA",T3))
    a(("ru_c:",)); a(("LDA",T3)); a(("CMPI",CURW)); a(("JC","ru_nr"))
    a(("LDA",T2)); a(("SHL",)); a(("SHL",)); a(("SHL",)); a(("ADD",T3)); a(("TAX",)); a(("LDAX",CURBUF)); a(("STA",T1))
    a(("LDA",OCX)); a(("ADD",T3)); a(("TAX",)); a(("LDA",T1)); a(("STPX",))
    a(("LDA",T3)); a(("ADDI",1)); a(("STA",T3)); a(("JMP","ru_c"))
    a(("ru_nr:",)); a(("LDA",T2)); a(("ADDI",1)); a(("STA",T2)); a(("JMP","ru_r"))
    a(("ru_done:",)); a(("RET",))

    # draw_cursor at (CX,CY)
    a(("drawcur:",))
    for (dx,dy,col) in CURPIX:
        a(("LDI",0)); a(("PLO",)); a(("LDA",CY)); a(("ADDI",dy)); a(("ADDI",FBPAGE)); a(("PHI",))
        a(("LDA",CX)); a(("ADDI",dx)); a(("TAX",)); a(("LDI",col)); a(("STPX",))
    a(("RET",))

    # ---------- full UI redraw ----------
    a(("drawui:",))
    a(("CALL","clearbg"))
    # taskbar
    a(("LDI",0)); a(("STA",AX)); a(("LDI",182)); a(("STA",AY)); a(("LDI",255)); a(("STA",AW)); a(("LDI",10)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDI",0)); a(("STA",AX)); a(("LDI",181)); a(("STA",AY)); a(("LDI",255)); a(("STA",AW)); a(("LDI",1)); a(("STA",AH)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
    # start button
    a(("LDI",2)); a(("STA",AX)); a(("LDI",183)); a(("STA",AY)); a(("LDI",40)); a(("STA",AW)); a(("LDI",8)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("CALL","bevel"))
    a(("LDI",6)); a(("STA",SX)); a(("LDI",184)); a(("STA",SY)); a(("LDI",0x20)); a(("STA",SPTR)); a(("LDI",BLK)); a(("STA",SCOL)); a(("CALL","puts2"))
    a(("CALL","drawwin"))
    a(("RET",))

    # clearbg: fill whole FB with TEAL (page 0x40..0xFF)
    a(("clearbg:",)); a(("LDI",FBPAGE)); a(("STA",T0))
    a(("cb_p:",)); a(("LDA",T0)); a(("CMPI",0)); a(("JZ","cb_done"))   # wrapped past 0xFF
    a(("LDI",0)); a(("PLO",)); a(("LDA",T0)); a(("PHI",)); a(("LXI",0))
    a(("cb_x:",)); a(("LDI",TEAL)); a(("STPX",)); a(("INX",)); a(("JNZ","cb_x"))
    a(("LDA",T0)); a(("ADDI",1)); a(("STA",T0)); a(("JMP","cb_p"))
    a(("cb_done:",)); a(("RET",))

    # drawwin: calculator window at (WINX,WINY)
    a(("drawwin:",))
    a(("LDA",WINX)); a(("STA",AX)); a(("LDA",WINY)); a(("STA",AY)); a(("LDI",WW)); a(("STA",AW)); a(("LDI",WH)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDA",WINX)); a(("STA",AX)); a(("LDA",WINY)); a(("STA",AY)); a(("LDI",WW)); a(("STA",AW)); a(("LDI",WH)); a(("STA",AH)); a(("CALL","bevel"))
    # title bar
    a(("LDA",WINX)); a(("ADDI",2)); a(("STA",AX)); a(("LDA",WINY)); a(("ADDI",2)); a(("STA",AY)); a(("LDI",WW-4)); a(("STA",AW)); a(("LDI",12)); a(("STA",AH)); a(("LDI",NAV)); a(("STA",ACOL)); a(("CALL","fillrect"))
    a(("LDA",WINX)); a(("ADDI",5)); a(("STA",SX)); a(("LDA",WINY)); a(("ADDI",4)); a(("STA",SY)); a(("LDI",0x00)); a(("STA",SPTR)); a(("LDI",WHT)); a(("STA",SCOL)); a(("CALL","puts2"))
    # close box
    a(("LDA",WINX)); a(("ADDI",WW-13)); a(("STA",AX)); a(("LDA",WINY)); a(("ADDI",3)); a(("STA",AY)); a(("LDI",10)); a(("STA",AW)); a(("LDI",10)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
    # display (sunken white)
    a(("LDA",WINX)); a(("ADDI",DISP[0])); a(("STA",AX)); a(("LDA",WINY)); a(("ADDI",DISP[1])); a(("STA",AY)); a(("LDI",DISP[2])); a(("STA",AW)); a(("LDI",DISP[3])); a(("STA",AH)); a(("LDI",WHT)); a(("STA",ACOL)); a(("CALL","fillrect"))
    # display digits D0..D4 right-aligned
    for i,dv in enumerate([D0,D1,D2,D3,D4]):
        a(("LDA",dv)); a(("STA",GCH)); a(("LDA",WINX)); a(("ADDI",DISP[0]+8+i*7)); a(("STA",GX)); a(("LDA",WINY)); a(("ADDI",DISP[1]+5)); a(("STA",GY)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    # buttons
    for (bx,by,lab,kind,val) in BTNS:
        a(("LDA",WINX)); a(("ADDI",bx)); a(("STA",AX)); a(("LDA",WINY)); a(("ADDI",by)); a(("STA",AY)); a(("LDI",BTN_W)); a(("STA",AW)); a(("LDI",BTN_H)); a(("STA",AH)); a(("LDI",SIL)); a(("STA",ACOL)); a(("CALL","fillrect")); a(("CALL","bevel"))
        a(("LDI",GIDX[lab])); a(("STA",GCH)); a(("LDA",WINX)); a(("ADDI",bx+9)); a(("STA",GX)); a(("LDA",WINY)); a(("ADDI",by+5)); a(("STA",GY)); a(("LDI",BLK)); a(("STA",GCOL)); a(("CALL","blitglyph"))
    a(("RET",))

    # ---------- boot + main loop ----------
    a(("boot:",))
    a(("LDI",0)); a(("STA",C_ACC)); a(("STA",C_CUR)); a(("STA",C_OP)); a(("STA",C_HASR)); a(("STA",MBP)); a(("STA",DRAG)); a(("STA",HAVES))
    a(("LDI",1)); a(("STA",C_FRESH)); a(("STA",DIRTY))
    a(("LDI",70)); a(("STA",WINX)); a(("LDI",30)); a(("STA",WINY))
    a(("LDI",80)); a(("STA",CX)); a(("STA",OCX)); a(("LDI",70)); a(("STA",CY)); a(("STA",OCY))
    a(("CALL","show_cur"))

    a(("main:",))
    # clamp mouse -> CX,CY (CX<=W-CURW, CY<=H-CURH)
    a(("LDA",MX)); a(("CMPI",W-CURW)); a(("JNC","cx_ok")); a(("LDI",W-CURW)); a(("STA",CX)); a(("JMP","cx_d")); a(("cx_ok:",)); a(("LDA",MX)); a(("STA",CX)); a(("cx_d:",))
    a(("LDA",MY)); a(("CMPI",H-CURH)); a(("JNC","cy_ok")); a(("LDI",H-CURH)); a(("STA",CY)); a(("JMP","cy_d")); a(("cy_ok:",)); a(("LDA",MY)); a(("STA",CY)); a(("cy_d:",))
    # click edge?
    a(("LDA",MB)); a(("JZ","no_edge")); a(("LDA",MBP)); a(("JNZ","no_edge")); a(("CALL","onclick"))
    a(("no_edge:",))
    # dragging?
    a(("LDA",DRAG)); a(("JZ","no_drag")); a(("LDA",MB)); a(("JZ","drag_end"))
    a(("LDA",MX)); a(("SUB",DOFX)); a(("STA",WINX)); a(("LDA",MY)); a(("SUB",DOFY)); a(("STA",WINY)); a(("LDI",1)); a(("STA",DIRTY)); a(("JMP","no_drag"))
    a(("drag_end:",)); a(("LDI",0)); a(("STA",DRAG))
    a(("no_drag:",))
    # ---- render ----
    a(("LDA",HAVES)); a(("JZ","r_dirty")); a(("LDA",DIRTY)); a(("JNZ","r_dirty")); a(("CALL","restun"))   # restore only if not dirty
    a(("r_dirty:",))
    a(("LDA",DIRTY)); a(("JZ","r_nodirty")); a(("CALL","drawui")); a(("LDI",0)); a(("STA",DIRTY)); a(("r_nodirty:",))
    a(("CALL","saveun")); a(("LDI",1)); a(("STA",HAVES)); a(("LDA",CX)); a(("STA",OCX)); a(("LDA",CY)); a(("STA",OCY))
    a(("CALL","drawcur"))
    a(("LDA",MB)); a(("STA",MBP))
    a(("FRAME",)); a(("JMP","main"))

    # ---------- onclick: title-bar drag start / close / buttons ----------
    a(("onclick:",))
    # title bar region: WINX+2..WINX+WW-14 (excl close), WINY+2..WINY+14 -> start drag
    a(("LDA",MY)); a(("LDA",WINY)); a(("ADDI",2)); a(("STA",T0)); a(("LDA",MY)); a(("CMP",T0)); a(("JNC","oc_btn"))
    a(("LDA",WINY)); a(("ADDI",14)); a(("STA",T0)); a(("LDA",MY)); a(("CMP",T0)); a(("JC","oc_btn"))
    a(("LDA",WINX)); a(("ADDI",2)); a(("STA",T0)); a(("LDA",MX)); a(("CMP",T0)); a(("JNC","oc_btn"))
    a(("LDA",WINX)); a(("ADDI",WW-14)); a(("STA",T0)); a(("LDA",MX)); a(("CMP",T0)); a(("JC","oc_btn"))
    # start drag
    a(("LDI",1)); a(("STA",DRAG)); a(("LDA",MX)); a(("SUB",WINX)); a(("STA",DOFX)); a(("LDA",MY)); a(("SUB",WINY)); a(("STA",DOFY)); a(("RET",))
    a(("oc_btn:",))
    for idx,(bx,by,lab,kind,val) in enumerate(BTNS):
        lbl=f"bmiss{idx}"
        a(("LDA",WINX)); a(("ADDI",bx)); a(("STA",T0)); a(("LDA",MX)); a(("CMP",T0)); a(("JNC",lbl))
        a(("LDA",WINX)); a(("ADDI",bx+BTN_W)); a(("STA",T0)); a(("LDA",MX)); a(("CMP",T0)); a(("JC",lbl))
        a(("LDA",WINY)); a(("ADDI",by)); a(("STA",T0)); a(("LDA",MY)); a(("CMP",T0)); a(("JNC",lbl))
        a(("LDA",WINY)); a(("ADDI",by+BTN_H)); a(("STA",T0)); a(("LDA",MY)); a(("CMP",T0)); a(("JC",lbl))
        if kind=='d': a(("LDI",val)); a(("STA",T0)); a(("CALL","press_digit"))
        elif kind=='o': a(("LDI",val)); a(("STA",T0)); a(("CALL","press_op"))
        elif kind=='e': a(("CALL","press_eq"))
        elif kind=='c': a(("CALL","press_clr"))
        a(("LDI",1)); a(("STA",DIRTY)); a(("RET",))
        a((f"{lbl}:",))
    a(("RET",))

    # ---- calculator logic (operands 0-99, 16-bit result) ----
    a(("press_digit:",)); a(("LDI",0)); a(("STA",C_HASR))
    a(("LDA",C_FRESH)); a(("JZ","pd_app")); a(("LDI",0)); a(("STA",C_CUR)); a(("LDI",0)); a(("STA",C_FRESH))
    a(("pd_app:",)); a(("LDA",C_CUR)); a(("CMPI",10)); a(("JC","pd_set"))
    a(("LDA",C_CUR)); a(("SHL",)); a(("STA",T1)); a(("LDA",T1)); a(("SHL",)); a(("SHL",)); a(("ADD",T1)); a(("ADD",T0)); a(("STA",C_CUR))
    a(("pd_set:",)); a(("CALL","show_cur")); a(("RET",))
    a(("press_op:",)); a(("LDA",C_CUR)); a(("STA",C_ACC)); a(("LDA",T0)); a(("STA",C_OP)); a(("LDI",1)); a(("STA",C_FRESH)); a(("RET",))
    a(("press_clr:",)); a(("LDI",0)); a(("STA",C_ACC)); a(("STA",C_CUR)); a(("STA",C_OP)); a(("STA",C_HASR)); a(("LDI",1)); a(("STA",C_FRESH)); a(("CALL","show_cur")); a(("RET",))
    a(("press_eq:",))
    a(("LDA",C_OP)); a(("CMPI",0)); a(("JZ","eq_add")); a(("LDA",C_OP)); a(("CMPI",1)); a(("JZ","eq_sub")); a(("LDA",C_OP)); a(("CMPI",2)); a(("JZ","eq_mul")); a(("JMP","eq_div"))
    a(("eq_add:",)); a(("LDA",C_ACC)); a(("ADD",C_CUR)); a(("STA",NVL)); a(("LDI",0)); a(("JNC","eqa0")); a(("LDI",1)); a(("eqa0:",)); a(("STA",NVH)); a(("JMP","eq_fin"))
    a(("eq_sub:",)); a(("LDA",C_ACC)); a(("CMP",C_CUR)); a(("JNC","eqsn")); a(("LDA",C_ACC)); a(("SUB",C_CUR)); a(("STA",NVL)); a(("LDI",0)); a(("STA",NVH)); a(("JMP","eq_fin")); a(("eqsn:",)); a(("LDI",0)); a(("STA",NVL)); a(("STA",NVH)); a(("JMP","eq_fin"))
    a(("eq_mul:",)); a(("LDI",0)); a(("STA",NVL)); a(("STA",NVH)); a(("LDA",C_CUR)); a(("STA",I))
    a(("eml:",)); a(("LDA",I)); a(("JZ","eq_fin")); a(("LDA",NVL)); a(("ADD",C_ACC)); a(("STA",NVL)); a(("JNC","emnc")); a(("LDA",NVH)); a(("ADDI",1)); a(("STA",NVH)); a(("emnc:",)); a(("LDA",I)); a(("SUBI",1)); a(("STA",I)); a(("JMP","eml"))
    a(("eq_div:",)); a(("LDI",0)); a(("STA",NVH)); a(("LDA",C_CUR)); a(("JZ","eqsn2")); a(("LDI",0)); a(("STA",QLO))
    a(("dvl:",)); a(("LDA",C_ACC)); a(("CMP",C_CUR)); a(("JNC","dvd")); a(("LDA",C_ACC)); a(("SUB",C_CUR)); a(("STA",C_ACC)); a(("LDA",QLO)); a(("ADDI",1)); a(("STA",QLO)); a(("JMP","dvl"))
    a(("dvd:",)); a(("LDA",QLO)); a(("STA",NVL)); a(("JMP","eq_fin")); a(("eqsn2:",)); a(("LDI",0)); a(("STA",NVL)); a(("STA",NVH))
    a(("eq_fin:",)); a(("CALL","num2dig")); a(("LDI",1)); a(("STA",C_HASR)); a(("RET",))
    a(("show_cur:",)); a(("LDA",C_CUR)); a(("STA",NVL)); a(("LDI",0)); a(("STA",NVH)); a(("CALL","num2dig")); a(("RET",))

    a(("num2dig:",))
    a(("CALL","div10")); a(("STA",D4)); a(("CALL","div10")); a(("STA",D3)); a(("CALL","div10")); a(("STA",D2)); a(("CALL","div10")); a(("STA",D1)); a(("CALL","div10")); a(("STA",D0))
    a(("LDA",D0)); a(("JNZ","ndd")); a(("LDI",GIDX[' '])); a(("STA",D0))
    a(("LDA",D1)); a(("JNZ","ndd")); a(("LDI",GIDX[' '])); a(("STA",D1))
    a(("LDA",D2)); a(("JNZ","ndd")); a(("LDI",GIDX[' '])); a(("STA",D2))
    a(("LDA",D3)); a(("JNZ","ndd")); a(("LDI",GIDX[' '])); a(("STA",D3))
    a(("ndd:",)); a(("RET",))

    a(("div10:",)); a(("LDI",0)); a(("STA",QLO)); a(("STA",QHI))
    a(("d10l:",)); a(("LDA",NVH)); a(("JNZ","d10s")); a(("LDA",NVL)); a(("CMPI",10)); a(("JNC","d10d"))
    a(("d10s:",)); a(("LDA",NVL)); a(("SUBI",10)); a(("STA",NVL)); a(("JC","d10nb")); a(("LDA",NVH)); a(("SUBI",1)); a(("STA",NVH)); a(("d10nb:",))
    a(("LDA",QLO)); a(("ADDI",1)); a(("STA",QLO)); a(("JNC","d10q")); a(("LDA",QHI)); a(("ADDI",1)); a(("STA",QHI)); a(("d10q:",)); a(("JMP","d10l"))
    a(("d10d:",)); a(("LDA",NVL)); a(("STA",REM)); a(("LDA",QLO)); a(("STA",NVL)); a(("LDA",QHI)); a(("STA",NVH)); a(("LDA",REM)); a(("RET",))
    return asm(L)

if __name__=="__main__":
    m=CA1Sys(fb_addr=FB,fb_w=W,fb_h=H); load_memory(m); m.SP=STACK
    m.M[MX]=80;m.M[MY]=70;m.M[MB]=0
    code=program()
    m.run(code,max_i=8_000_000,frame_on=lambda mm:True)
    fb=m.M[FB:FB+W*H]
    print(f"CA-OS v2: {m.icount} instructions for the FIRST frame ({W}x{H})")
    # ASCII preview (downsample 4x)
    ramp={BLK:' ',TEAL:'~',SIL:'.',GRY:':',WHT:'#',NAV:'N',LSV:'-',BLU:'b',RED:'R',GRN:'g'}
    for y in range(0,H,3):
        print("".join(ramp.get(fb[y*W+x],'?') for x in range(0,W,3)))
