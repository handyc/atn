#!/usr/bin/env python3
# synth_clean.py — a clean, parity-aware from-scratch synthesis, fixing the vertical
# flip of the crude excitable template (vflip.py).
#
# (A) ADVECTION gliders on the 6 hex BOND axes. Rule: copy the OPPOSITE neighbor,
#     LUT[key] = value of neighbor (-d). This rigidly shifts the whole board one cell
#     per step toward +d -> an exact glider in bond direction angle(d), for all 6
#     directions. The law predicts it exactly: only a_{-d}=1, so F=dir(-d) and
#     heading=angle(-d)+180=angle(d). A pure generative confirmation.
#
# (B) PARITY-AWARE vertical. Pure vertical (90/270) is NOT a bond axis, so a single
#     shift can't reach it; it needs both north (or both south) neighbors. The crude
#     template used "exactly one of {nw,ne}" (an XOR that the offset parity breaks).
#     Parity-symmetric fix: copy max(nw,ne) (move down) / max(sw,se) (move up) — both
#     north neighbors drive the cell, cancelling the parity asymmetry. Test if this
#     gives a clean vertical glider with no flip.
import numpy as np
import rulehub
from mechanism import DIRV, SHIFT, flow_angle, cmean, cR, cdiff
from synthesize import evolve

OPP = {"nw": "se", "ne": "sw", "r": "l", "se": "nw", "sw": "ne", "l": "r"}
KEYS = np.arange(16384)
DIR_ANG = {k: float(np.arctan2(v[0], v[1])) for k, v in DIRV.items()}

def advection_lut(d):
    return (((KEYS >> SHIFT[OPP[d]]) & 3).astype(np.uint8))

def vertical_lut(which):  # which='down' copies max(nw,ne); 'up' copies max(sw,se)
    a, b = (("nw", "ne") if which == "down" else ("sw", "se"))
    va = (KEYS >> SHIFT[a]) & 3; vb = (KEYS >> SHIFT[b]) & 3
    return np.maximum(va, vb).astype(np.uint8)

def heading_of(lut, seeds=6):
    hs = [evolve(lut, s) for s in range(seeds)]
    hs = [h for k, h in hs if k == "translating" and h is not None]
    return (cmean(hs), cR(hs), len(hs)) if len(hs) >= 3 and cR(hs) > 0.6 else (None, None, len(hs))

def main():
    print("=== (A) De-novo ADVECTION gliders on the 6 hex bond axes ===")
    print("  dir   bond-angle   law angle(F)+180   measured   err   R")
    errs = []
    for d in ("r", "se", "sw", "l", "nw", "ne"):
        lut = advection_lut(d)
        bond = np.degrees(DIR_ANG[d])
        fa, fs = flow_angle(lut, "single")
        law = np.degrees(fa + np.pi)
        mh, R, n = heading_of(lut)
        if mh is None:
            print(f"  {d:<4}  {bond:+6.0f}        {law:+6.0f}          (no clean glider, n={n})"); continue
        md = np.degrees(mh); err = np.degrees(cdiff(mh, DIR_ANG[d])); errs.append(err)
        print(f"  {d:<4}  {bond:+6.0f}        {law:+6.0f}          {md:+6.0f}   {err:3.0f}   {R:.2f}")
    if errs:
        print(f"  -> mean error to bond axis: {np.mean(errs):.0f} deg over {len(errs)}/6 directions")
        print("     exact rigid gliders built from nothing; the law predicts each.\n")

    print("=== (B) Parity-aware VERTICAL (the headings the XOR template flipped) ===")
    print("  build              target   law angle(F)+180   measured   err   R")
    for which, target in (("down", 90.0), ("up", -90.0)):
        lut = vertical_lut(which)
        fa, fs = flow_angle(lut, "single"); law = np.degrees(fa + np.pi)
        mh, R, n = heading_of(lut)
        if mh is None:
            print(f"  copy-max {which:<8}  {target:+5.0f}      {law:+6.0f}          (no clean glider n={n})"); continue
        md = np.degrees(mh); err = np.degrees(cdiff(mh, np.radians(target)))
        verdict = "FIXED (no flip)" if err < 30 else ("still flipped" if err > 120 else "partial")
        print(f"  copy-max {which:<8}  {target:+5.0f}      {law:+6.0f}          {md:+6.0f}   {err:3.0f}   {R:.2f}  [{verdict}]")
    print("\n  -> if copy-max gives clean vertical gliders with small error, the vertical")
    print("     flip was the XOR/parity tie-break, and a parity-symmetric build fixes it:")
    print("     de-novo synthesis then covers all 6 bond axes AND the vertical.")

if __name__ == "__main__":
    main()
