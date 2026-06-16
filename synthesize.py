#!/usr/bin/env python3
# synthesize.py — FROM-SCRATCH glider synthesis. The surgery test edited a working
# (fractal) glider rule. The stronger claim: build a glider rule DE NOVO — no fractal,
# no base rule — purely from the direction law, and have it glide in the predicted
# direction. Template: a directed excitable medium.
#   - background quiescent: LUT[0]=0.
#   - DIRECTED BIRTH: a dead cell turns on if it has an active neighbor on the
#     TRAILING side (directions aligned with phi = target_heading - 180). This is
#     exactly the single-neighbor activation the law uses, so by construction
#     F points at phi and the law predicts heading = phi+180 = target.
#   - SUPPORTED SURVIVAL: a live cell persists only while a trailing neighbor is
#     active; otherwise it dies. (Death of unsupported cells -> localization.)
# We scan threshold + birth multiplicity, run each rule from seeds, classify the
# emergent structure, and check its heading against the target.
import numpy as np
import rulehub
from mechanism import DIRV, SHIFT, cmean, cR, cdiff

DIR_SHIFT = {k: SHIFT[k] for k in DIRV}
DIR_ANG = {k: float(np.arctan2(v[0], v[1])) for k, v in DIRV.items()}
KEYS = np.arange(16384)
SELF = (KEYS >> 12) & 3
NB = {k: (KEYS >> s) & 3 for k, s in DIR_SHIFT.items()}

def build(phi, thr, birth="any", copy=True):
    aligned = [k for k in DIRV if np.cos(DIR_ANG[k] - phi) > thr]
    if not aligned: return None
    cnt = sum((NB[k] > 0).astype(int) for k in aligned)   # # active trailing neighbors
    out = np.zeros(16384, np.uint8)
    trig = (cnt == 1) if birth == "one" else (cnt >= 1)
    birth_m = (SELF == 0) & trig
    surv_m = (SELF > 0) & (cnt >= 1)
    out[birth_m] = 1
    out[surv_m] = SELF[surv_m] if copy else 1
    return out

def evolve(lut, seed, side=84, ticks=44):
    rng = np.random.default_rng(seed)
    b = np.zeros((side, side), np.uint8); c = side // 2
    b[c-2:c+3, c-2:c+3] = rng.integers(1, 4, (5, 5))
    coms, masses = [], []
    for _ in range(ticks):
        b = lut[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
        nz = np.flatnonzero(b); m = nz.size
        masses.append(m)
        if m == 0: return ("dead", None)
        if m > 0.14 * side * side: return ("explode", None)
        ys, xs = np.divmod(nz, side); coms.append((ys.mean(), xs.mean()))
    coms = np.array(coms)
    v = (coms[-1] - coms[len(coms)//3]) / (len(coms) - len(coms)//3)
    sp = float(np.hypot(*v))
    if sp < 0.12: return ("static", None)
    return ("translating", float(np.arctan2(v[0], v[1])))

def main():
    print("FROM-SCRATCH glider synthesis: build a rule from the direction law alone.\n")
    targets = np.arange(0, 360, 45)
    variants = [(thr, birth) for thr in (0.3, 0.55, 0.8) for birth in ("any", "one")]
    best = None
    for thr, birth in variants:
        rows, errs, transl = [], [], 0
        for tg in targets:
            phi = np.radians(tg) - np.pi
            lut = build(phi, thr, birth)
            if lut is None or lut[0] != 0:
                continue
            outs = [evolve(lut, s) for s in range(5)]
            kinds = [o[0] for o in outs]
            heads = [o[1] for o in outs if o[0] == "translating" and o[1] is not None]
            kind = max(set(kinds), key=kinds.count)
            if len(heads) >= 3 and cR(heads) > 0.6:
                transl += 1
                mh = cmean(heads); err = np.degrees(cdiff(mh, np.radians(tg)))
                errs.append(err)
                rows.append((tg, kind, np.degrees(mh), err, cR(heads)))
            else:
                rows.append((tg, kind, None, None, None))
        ok = len(errs)
        merr = np.mean(errs) if errs else None
        tag = f"thr={thr} birth={birth}"
        print(f"[{tag}] translating gliders: {transl}/{len(targets)}"
              + (f", mean heading err {merr:.0f} deg" if merr is not None else ""))
        for tg, kind, mh, err, R in rows:
            s = f"    target {tg:3d}: {kind}"
            if mh is not None: s += f" -> heading {mh:+.0f} (err {err:.0f}, R={R:.2f})"
            print(s)
        if errs and (best is None or (transl, -merr) > (best[0], -best[1])):
            best = (transl, merr, tag)
    print()
    if best and best[0] >= 3 and best[1] < 35:
        print(f"-> DE-NOVO SYNTHESIS WORKS (best: {best[2]}, {best[0]}/{len(targets)} headings, "
              f"mean err {best[1]:.0f} deg). A glider built from nothing but the direction")
        print("   law glides where designed: the law is constructive, not just predictive.")
    elif best and best[0] >= 2:
        print(f"-> PARTIAL: de-novo rules glide in the designed direction for some targets "
              f"(best {best[2]}: {best[0]}/{len(targets)}, err {best[1]:.0f} deg), but the")
        print("   excitable-medium template doesn't localize for all headings. Direction is")
        print("   controllable from scratch; robust localization needs a better bulk template.")
    else:
        print("-> de-novo construction did not yield clean localized gliders with this simple")
        print("   template; building the class-4 BULK from scratch remains the hard part")
        print("   (consistent with why glider rules are usually SEARCHED for). Direction")
        print("   control via surgery on existing gliders stands.")

if __name__ == "__main__":
    main()
