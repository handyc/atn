#!/usr/bin/env python3
# font_gen.py — rasterize GNU Unifont (the OTF) into a 16x16 1-bit bitmap table for the CA to blit.
# Output: unifont16.json  = { "cps":[...assigned BMP codepoints...], "b64": <zlib+base64 of the glyph blob> }
# Each glyph is 32 bytes: 16 rows x 2 bytes (big-endian within the row, bit (15-x) = pixel x).
# The CA stores these at FONTBASE + cp*32 (a direct codepoint->glyph table) and blits 16x16.
import json, zlib, base64
import numpy as np
from PIL import Image, ImageFont, ImageDraw
from fontTools.ttLib import TTFont

UF = "/usr/share/fonts/opentype/unifont/unifont.otf"

def build():
    ft = ImageFont.truetype(UF, 16)
    cmap = TTFont(UF)["cmap"].getBestCmap()
    cps = sorted(cp for cp in cmap if 0x20 <= cp <= 0xFFFF)
    blob = bytearray()
    for cp in cps:
        img = Image.new("L", (16, 16), 0)
        ImageDraw.Draw(img).text((0, -2), chr(cp), font=ft, fill=255)
        a = (np.frombuffer(img.tobytes(), dtype=np.uint8).reshape(16, 16) > 110)
        # pack each row's 16 bits MSB-first into 2 bytes
        packed = np.packbits(a, axis=1)            # (16,2)
        blob += packed.tobytes()
    raw = bytes(blob)
    comp = zlib.compress(raw, 9)
    cpbytes = b"".join(int(cp).to_bytes(2, "little") for cp in cps)   # codepoints as uint16 LE
    out = {"cps_b64": base64.b64encode(cpbytes).decode(), "b64": base64.b64encode(comp).decode(), "n": len(cps)}
    json.dump(out, open("unifont16.json", "w"), separators=(",", ":"))
    print(f"glyphs={len(cps)}  raw={len(raw)} ({len(raw)/1048576:.2f} MB)  "
          f"zlib={len(comp)} ({len(comp)/1048576:.2f} MB)  json={len(json.dumps(out))/1048576:.2f} MB")

if __name__ == "__main__":
    build()
