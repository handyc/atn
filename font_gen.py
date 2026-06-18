#!/usr/bin/env python3
# font_gen.py — rasterize a BOOK-QUALITY 16-px font for the CA to blit.
#
# Three things make screen type look printed rather than like a broken toy, and this does all three:
#   1. A REAL alpha ramp — 16 grey levels (4-bit), not 3 inks.  Curved stems stop looking like
#      stair-steps once the edge has 16 shades to fall through.
#   2. A screen-hinted Latin face — DejaVu Sans, grid-fitted by FreeType at the exact target size,
#      so verticals land on whole pixels and stay crisp.  WenQuanYi only does the CJK/kana/Hangul it
#      was actually designed for; GNU Unifont is the last-resort fallback for the rest of the BMP.
#   3. True baseline metrics — every glyph is set on ONE baseline via FreeType's "ls" anchor, instead
#      of the old fixed-dy fudge that let each face float wherever its own box happened to sit.
#
# Each pixel is 4 bits (level 0 = paper .. 15 = full ink), packed LSB-first 2 px/byte -> 8 bytes/row
# -> 128 bytes/glyph.  Coverage is gamma-corrected before quantising so thin stems keep their weight.
# Output unifont16.json = { v, bpp, n, cps_b64 (uint16 LE), w_b64 (advance/glyph), b64 (zlib blob) }.
import json, zlib, base64, struct
import numpy as np
from PIL import Image, ImageFont, ImageDraw
from fontTools.ttLib import TTFont

CELL     = 16          # glyph box, px
BASELINE = 12.5        # baseline row inside the box (x-height above, descenders below)
GAMMA    = 1.35        # coverage gamma: >1 fattens thin AA edges so stems read at 16 px
LEVELS   = 16          # 4-bit grey ramp

# (path, fontNumber, em-size, x-shift) — first face that has the codepoint wins.
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
WQY    = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
UNIFONT= "/usr/share/fonts/opentype/unifont/unifont.otf"
FACES = [
    {"path": DEJAVU,  "num": 0, "size": 15, "dx": 0.0},   # Latin / Greek / Cyrillic / punctuation / symbols
    {"path": WQY,     "num": 0, "size": 15, "dx": 0.0},   # CJK / kana / Hangul
    {"path": UNIFONT, "num": 0, "size": 16, "dx": 0.0},   # everything else in the BMP
]

def build():
    for f in FACES:
        f["font"] = ImageFont.truetype(f["path"], f["size"])
        tt = TTFont(f["path"], fontNumber=f["num"]) if f["path"].endswith(".ttc") else TTFont(f["path"])
        f["cmap"] = set(tt["cmap"].getBestCmap())
    cps = sorted({cp for f in FACES for cp in f["cmap"] if 0x20 <= cp <= 0xFFFF})
    ramp = (np.linspace(0, 1, 256) ** GAMMA)                      # gamma curve, coverage 0..255 -> 0..1

    blob = bytearray(); widths = bytearray()
    for cp in cps:
        face = next(f for f in FACES if cp in f["cmap"])
        # render onto a tall scratch so ascenders/descenders never clip, then take the 16-px cell
        pad = 8
        img = Image.new("L", (CELL + 2*pad, CELL + 2*pad), 0)
        ImageDraw.Draw(img).text((pad + face["dx"], pad + BASELINE), chr(cp),
                                 font=face["font"], fill=255, anchor="ls")
        a = np.asarray(img, dtype=np.float64)[pad:pad+CELL, pad:pad+CELL] / 255.0
        lvl = np.clip(np.round(ramp[(a*255).astype(int)] * (LEVELS-1)), 0, LEVELS-1).astype(np.uint8)
        for r in range(CELL):
            row = lvl[r]
            for b in range(CELL//2):                              # 2 px/byte, LSB-first (px0 -> low nibble)
                blob.append(int(row[b*2]) | (int(row[b*2+1]) << 4))
        if cp == 0x20:
            adv = 5
        else:
            adv = max(1, min(CELL, round(face["font"].getlength(chr(cp)))))
        widths.append(adv)

    raw = bytes(blob); comp = zlib.compress(raw, 9)
    out = {"v": 2, "bpp": 4, "cell": CELL, "n": len(cps),
           "cps_b64": base64.b64encode(b"".join(struct.pack("<H", c) for c in cps)).decode(),
           "w_b64":   base64.b64encode(bytes(widths)).decode(),
           "b64":     base64.b64encode(comp).decode()}
    json.dump(out, open("unifont16.json", "w"), separators=(",", ":"))
    print(f"glyphs={len(cps)}  {CELL}x{CELL} 4-bit  raw={len(raw)} ({len(raw)/1048576:.2f} MB)  "
          f"zlib={len(comp)} ({len(comp)/1048576:.2f} MB)  json={len(json.dumps(out))/1048576:.2f} MB")

if __name__ == "__main__":
    build()
