#!/usr/bin/env python3
# select_presets.py — pick faithful exemplar rules for the CA-Photoshop lab, across ALL
# fractal families (Newton/Julia/Mandelbrot/Burning Ship), by behaviour category:
#   PRESERVE (retain) · WIPE (shift, binned by direction) · DISSOLVE (grow) ·
#   GLITCH (chaos) · STYLIZE (settles to a stable/blinky pattern that isn't the original).
# Export each one's REAL rulehub LUT (packed base64) so the in-browser effect is genuine.
import base64, json
import numpy as np
import rulehub, retain

def lut_for(fam, cx, cy, span, c, it=160, side=128):
    st = span/side; ox = cx-st*side*.5; oy = cy-st*side*.5
    gx, gy = np.meshgrid(ox+np.arange(side)*st, oy+np.arange(side)*st)
    if fam == "newton":  e = rulehub._newton(gx, gy, it)
    elif fam == "julia": e = rulehub._esc(gx, gy, np.full_like(gx, c[0]), np.full_like(gy, c[1]), "mandel", it)
    elif fam == "burning": e = rulehub._esc(np.zeros_like(gx), np.zeros_like(gy), gx, gy, "burning", it)
    else:                e = rulehub._esc(np.zeros_like(gx), np.zeros_like(gy), gx, gy, "mandel", it)
    return rulehub._posterise(e, it)

def classify_lut(lut, T=10):
    b = retain.IMG.copy().astype(np.uint8); chg = 0.0
    for _ in range(T):
        nb = lut[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
        chg = float((nb != b).mean()); b = nb
        if (b > 0).sum() == 0: return "die", 0, (0,0), 0, 0, 0
    ret = retain.match(b, retain.IMG); sm, sh = retain.shift_match(b, retain.IMG); fill = float((b > 0).mean())
    return None, ret, sh, sm, fill, chg

def pack(lut):
    a = (lut.astype(np.uint8) & 3); out = bytearray()
    for i in range(0, len(a), 4):
        out.append(a[i] | (a[i+1] << 2) | (a[i+2] << 4) | (a[i+3] << 6))
    return base64.b64encode(bytes(out)).decode()

ARROWS = {(-1,0):"↑",(1,0):"↓",(0,-1):"←",(0,1):"→",(-1,-1):"↖",(-1,1):"↗",(1,-1):"↙",(1,1):"↘"}
def sgn(v): return (v>0)-(v<0)

def main():
    rng = np.random.default_rng(7)
    retain_c, grow_c, chaos_c, styl_c = [], [], [], []
    shift_dir = {}                                   # (sy,sx) -> (sm, fam, co, sh)
    fams = ["newton", "julia", "mandelbrot", "burning"]
    for n in range(4000):
        fam = fams[n % 4]
        win = rulehub.WINDOWS[fam]; bx, by, bs = win[rng.integers(0, len(win))]
        cx = bx + (rng.random()*2-1)*0.4*bs; cy = by + (rng.random()*2-1)*0.4*bs
        span = bs * (0.25 + 0.9*rng.random())
        c = rulehub.JULIA_C[rng.integers(0, len(rulehub.JULIA_C))] if fam == "julia" else None
        lut = lut_for(fam, cx, cy, span, c)
        r = classify_lut(lut)
        if r[0] == "die": continue
        _, ret, sh, sm, fill, chg = r
        co = (round(float(cx),4), round(float(cy),4), round(float(span),4))
        rec = (fam, co, c)
        if ret > 0.9:
            retain_c.append((ret, rec))
        elif sm > 0.78 and sh != (0,0) and ret < 0.8:
            d = (sgn(sh[0]), sgn(sh[1]))
            if d != (0,0) and (d not in shift_dir or sm > shift_dir[d][0]):
                shift_dir[d] = (sm, rec, sh)
        elif fill > 0.6 and chg > 0.03:
            grow_c.append((fill, rec))
        elif chg > 0.25 and 0.05 < ret < 0.55:
            chaos_c.append((chg, rec))
        elif chg < 0.04 and 0.55 < ret < 0.9:
            styl_c.append((ret, rec))

    presets = []
    def add(name, cat, rec, note):
        fam, co, c = rec
        lut = lut_for(fam, co[0], co[1], co[2], c)
        presets.append(dict(name=name, cat=cat, fam=fam, cx=co[0], cy=co[1], span=co[2],
                            c=list(c) if c else None, note=note, lut=pack(lut)))

    def topn(lst, n):                                # dedupe near-duplicate coords
        out = []
        for v, rec in sorted(lst, reverse=True):
            if all(abs(rec[1][0]-o[1][1][0])+abs(rec[1][1]-o[1][1][1]) > 0.05 or rec[0] != o[1][0] for o in out):
                out.append((v, rec))
            if len(out) >= n: break
        return out

    for i,(ret,rec) in enumerate(topn(retain_c, 3)):
        add(f"Preserve {i+1}", "RETAIN", rec, f"{rec[0]} · retention {ret:.2f} (wire/memory)")
    for d,(sm,rec,sh) in sorted(shift_dir.items(), key=lambda kv:-kv[1][0]):
        add(f"Wipe {ARROWS.get(d,'?')}", "SHIFT/WIPE", rec, f"{rec[0]} · pans {ARROWS.get(d,'?')} (shift {sh}, match {sm:.2f})")
    for i,(fill,rec) in enumerate(topn(grow_c, 3)):
        add(f"Dissolve {i+1}", "GROW", rec, f"{rec[0]} · floods to {fill:.2f} (carrier)")
    for i,(chg,rec) in enumerate(topn(chaos_c, 4)):
        add(f"Glitch {i+1}", "CHAOS", rec, f"{rec[0]} · churns {chg:.2f} (chaos)")
    for i,(ret,rec) in enumerate(topn(styl_c, 3)):
        add(f"Stylize {i+1}", "STYLIZE", rec, f"{rec[0]} · settles to a stable pattern (ret {ret:.2f})")

    json.dump(presets, open("/tmp/presets.json","w"))
    by = {}
    for p in presets: by.setdefault(p["cat"], []).append(p["name"])
    print(f"selected {len(presets)} presets across families:")
    for p in presets:
        print(f"  [{p['cat']:10s}] {p['name']:14s} {p['fam']:10s} ({p['cx']},{p['cy']},{p['span']})  {p['note']}")

if __name__ == "__main__":
    main()
