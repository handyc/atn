#!/usr/bin/env python3
# select_presets.py — pick faithful exemplar rules for the image-filter lab, by category
# (the retain.py taxonomy), and export their REAL rulehub LUTs (packed base64) + metadata.
# RETAIN = preserve/denoise, SHIFT/WIPE = directional wipe/pan, GROW = dissolve/flood,
# CHAOS = glitch. We bin SHIFT rules by direction so each becomes a distinct "wipe" filter.
import base64, json
import numpy as np
import rulehub
import retain   # reuse newton_lut, classify, shift_match, IMG

def pack(lut):
    a = (lut.astype(np.uint8) & 3); b = bytearray()
    for i in range(0, len(a), 4):
        b.append(a[i] | (a[i+1] << 2) | (a[i+2] << 4) | (a[i+3] << 6))
    return base64.b64encode(bytes(b)).decode()

ARROWS = {(-1,0):"↑",(1,0):"↓",(0,-1):"←",(0,1):"→",(-1,-1):"↖",(-1,1):"↗",(1,-1):"↙",(1,1):"↘"}
def sgn(v): return (v>0)-(v<0)

def main():
    rng = np.random.default_rng(1)
    retain_c, grow_c, chaos_c = [], [], []
    shift_by_dir = {}                      # (sy,sx) -> best (sm, coords, sh)
    for _ in range(900):
        cx = rng.normal(-0.12, 0.22); cy = rng.normal(-0.05, 0.22); sp = rng.uniform(0.15, 1.3)
        r = retain.classify(cx, cy, sp)
        if r[0] == "die": continue
        _, ret, sh, sm, fill, chg, lut = r
        co = (round(float(cx),4), round(float(cy),4), round(float(sp),4))
        if ret > 0.85:
            retain_c.append((ret, co))
        elif sm > 0.8 and sh != (0,0) and ret < 0.8:
            d = (sgn(sh[0]), sgn(sh[1]))
            if d != (0,0) and (d not in shift_by_dir or sm > shift_by_dir[d][0]):
                shift_by_dir[d] = (sm, co, sh)
        elif fill > 0.55 and chg > 0.02:
            grow_c.append((fill, co))
        elif 0.05 < ret < 0.6 and chg > 0.2:
            chaos_c.append((chg, co))

    presets = []
    def add(name, cat, co, note):
        lut = retain.newton_lut(*co)
        presets.append(dict(name=name, cat=cat, cx=co[0], cy=co[1], span=co[2], note=note, lut=pack(lut)))

    retain_c.sort(reverse=True)
    for i,(ret,co) in enumerate(retain_c[:2]):
        add(f"Preserve {i+1}", "RETAIN", co, f"retention {ret:.2f} — identity-like (wire/memory)")
    # distinct wipe directions, best-match first
    for d,(sm,co,sh) in sorted(shift_by_dir.items(), key=lambda kv:-kv[1][0])[:4]:
        add(f"Wipe {ARROWS.get(d,'?')}", "SHIFT/WIPE", co, f"image pans {ARROWS.get(d,'?')} (shift {sh}, match {sm:.2f})")
    grow_c.sort(reverse=True)
    for i,(fill,co) in enumerate(grow_c[:2]):
        add(f"Dissolve/Grow {i+1}", "GROW", co, f"floods to fill {fill:.2f} (flooding carrier)")
    chaos_c.sort(reverse=True)
    for i,(chg,co) in enumerate(chaos_c[:2]):
        add(f"Glitch {i+1}", "CHAOS", co, f"churns (change {chg:.2f}) — chaotic transform")

    json.dump(presets, open("/tmp/presets.json","w"))
    print(f"selected {len(presets)} presets:")
    for p in presets:
        print(f"  [{p['cat']:10s}] {p['name']:16s} newton({p['cx']},{p['cy']},{p['span']})  {p['note']}")

if __name__ == "__main__":
    main()
