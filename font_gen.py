#!/usr/bin/env python3
# font_gen.py — rasterize an ANTIALIASED 16x16 font for the CA to blit (far nicer than 1-bit).
# Primary: WenQuanYi Zen Hei (smooth, proportional Latin/Greek/Cyrillic + CJK/kana/Hangul);
# fallback: GNU Unifont for any BMP codepoint WenQuanYi lacks (full coverage).
# Each pixel is 2 bits (4 grey levels: 0 transparent, 1 light, 2 dark, 3 full ink), packed LSB-first
# 4 px/byte -> 4 bytes/row -> 64 bytes/glyph.  Also emits a per-glyph advance width (proportional).
# Output unifont16.json = { n, cps_b64 (uint16 LE), w_b64 (advance per glyph), b64 (zlib glyph blob) }.
import json, zlib, base64, struct
import numpy as np
from PIL import Image, ImageFont, ImageDraw
from fontTools.ttLib import TTFont

WQ = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
UF = "/usr/share/fonts/opentype/unifont/unifont.otf"

def build():
    wq = ImageFont.truetype(WQ, 15); uf = ImageFont.truetype(UF, 16)
    wq_cmap = set(TTFont(WQ, fontNumber=0)["cmap"].getBestCmap())
    uf_cmap = set(TTFont(UF)["cmap"].getBestCmap())
    cps = sorted(cp for cp in (wq_cmap | uf_cmap) if 0x20 <= cp <= 0xFFFF)
    blob = bytearray(); widths = bytearray()
    for cp in cps:
        ft, dy = (wq, 2) if cp in wq_cmap else (uf, -2)
        img = Image.new("L", (16, 16), 0)
        ImageDraw.Draw(img).text((0, dy), chr(cp), font=ft, fill=255)
        a = np.frombuffer(img.tobytes(), dtype=np.uint8).reshape(16, 16).astype(np.uint16)
        lvl = ((a * 3 + 127) // 255).astype(np.uint8)            # coverage 0..255 -> level 0..3
        for r in range(16):
            row = lvl[r]
            for b in range(4):                                   # 4 px/byte, LSB-first (px0 in bits 0..1)
                blob.append(int(row[b*4]) | (int(row[b*4+1]) << 2) | (int(row[b*4+2]) << 4) | (int(row[b*4+3]) << 6))
        adv = 5 if cp == 0x20 else max(1, min(16, round(ft.getlength(chr(cp)))))
        widths.append(adv)
    raw = bytes(blob); comp = zlib.compress(raw, 9)
    out = {"n": len(cps),
           "cps_b64": base64.b64encode(b"".join(struct.pack("<H", c) for c in cps)).decode(),
           "w_b64":   base64.b64encode(bytes(widths)).decode(),
           "b64":     base64.b64encode(comp).decode()}
    json.dump(out, open("unifont16.json", "w"), separators=(",", ":"))
    print(f"glyphs={len(cps)}  raw={len(raw)} ({len(raw)/1048576:.2f} MB)  "
          f"zlib={len(comp)} ({len(comp)/1048576:.2f} MB)  json={len(json.dumps(out))/1048576:.2f} MB")

if __name__ == "__main__":
    build()
