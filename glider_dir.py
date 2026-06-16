#!/usr/bin/env python3
# glider_dir.py — does fractal LOCATION predict a glider's VELOCITY (direction +
# speed), not just its existence? For each glider rule in the local library, run
# the glider and measure its velocity vector, then ask whether angle/speed are
# organised by fractal coordinate (cx,cy,span). If so, fractal-space is a dial for
# glider dynamics — a novel "fractal -> behaviour" map.
import argparse, json, os
import numpy as np
import rulehub  # hex_key

def glider_velocity(rule, side=96, ticks=20, seed=0):
    if rule[0] != 0: return None
    rng = np.random.default_rng(seed); b = np.zeros((side, side), np.uint8); c = side // 2
    b[c - 2:c + 3, c - 2:c + 3] = rng.integers(1, 4, (5, 5))
    coms = []
    for t in range(ticks):
        b = rule[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
        nz = np.flatnonzero(b)
        if nz.size == 0 or nz.size > 0.1 * side * side: return None
        ys, xs = np.divmod(nz, side); coms.append((ys.mean(), xs.mean()))
    coms = np.array(coms)
    # velocity from an early window (avoids transient + toroidal wrap of fast gliders)
    v = (coms[14] - coms[3]) / 11.0
    sp = float(np.hypot(*v))
    if sp < 0.15: return None                      # not actually translating
    return float(np.arctan2(v[0], v[1])), sp       # angle (rad), speed (cells/tick)

def circ_stats(angles):
    a = np.array(angles)
    R = np.hypot(np.cos(a).mean(), np.sin(a).mean())   # mean resultant length: 0=uniform,1=aligned
    return R

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", default="alice/swarm-v1/outputs")
    ap.add_argument("--family", default="newton")
    ap.add_argument("--max", type=int, default=1200)
    a = ap.parse_args()
    recs = [r for r in json.load(open(os.path.join(a.lib, "library.json")))
            if r["glider"] and r["family"] == a.family][:a.max]
    blobs = os.path.join(a.lib, "blobs")
    ang = []; spd = []; cx = []; cy = []; span = []
    for r in recs:
        lut = np.fromfile(os.path.join(blobs, r["hash"] + ".lut"), dtype=np.uint8, count=16384)
        v = glider_velocity(lut)
        if v is None: continue
        ang.append(v[0]); spd.append(v[1]); cx.append(r["cx"]); cy.append(r["cy"]); span.append(r["span"])
    ang = np.array(ang); spd = np.array(spd); cx = np.array(cx); cy = np.array(cy); span = np.array(span)
    n = len(ang)
    print(f"family={a.family}: {n} clean translating gliders measured\n")
    # 1) global direction distribution: clustered or many directions?
    R = circ_stats(ang)
    print(f"global glider-angle alignment R = {R:.2f}  (0=all directions equally, 1=one direction)")
    hist, edges = np.histogram(np.degrees(ang) % 360, bins=12, range=(0, 360))
    print("angle histogram (deg, 30-deg bins):", hist.tolist())
    print(f"speed: mean {spd.mean():.2f} +- {spd.std():.2f} cells/tick (range {spd.min():.2f}-{spd.max():.2f})\n")
    # 2) does fractal location organise DIRECTION?  bin (cx,cy), per-bin angle alignment
    nb = 8
    bx = np.clip(((cx - cx.min()) / (np.ptp(cx) + 1e-9) * nb).astype(int), 0, nb - 1)
    by = np.clip(((cy - cy.min()) / (np.ptp(cy) + 1e-9) * nb).astype(int), 0, nb - 1)
    bid = bx * nb + by
    within = []
    for b in np.unique(bid):
        aa = ang[bid == b]
        if len(aa) >= 8: within.append(circ_stats(aa))
    within_R = np.mean(within) if within else 0.0
    print(f"per-region angle alignment (mean R within fractal bins) = {within_R:.2f}")
    print(f"  -> if within-bin R ({within_R:.2f}) >> global R ({R:.2f}), each fractal REGION")
    print(f"     has its own glider direction = location controls direction.")
    # 3) speed vs zoom (span)
    if spd.std() > 0:
        rsp = np.corrcoef(np.log(span + 1e-9), spd)[0, 1]
        print(f"\nspeed vs log(span/zoom) correlation: {rsp:+.2f}  "
              f"({'zoom controls glider speed' if abs(rsp) > 0.15 else 'no zoom-speed link'})")

if __name__ == "__main__":
    main()
