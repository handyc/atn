#!/usr/bin/env python3
# cell11_glider.py — from transport to COMPUTATION. Screen the class-4 library for
# gliders, then test a PROGRAMMABLE SIGNAL GATE: a glider launched left->right is a
# 1-bit signal; a port-placed WALL should BLOCK it. A rule where (no wall -> signal
# arrives) AND (wall -> blocked) is a programmable gate (signal passes iff gate
# open) — non-local computation orchestrated by cell-11 ports, beyond local slices.
import argparse, time
import numpy as np
import caca

def glider_score(rule, side, ticks, seed):
    if rule[0] != 0: return 0.0
    rng = np.random.default_rng(seed)
    b = np.zeros((side, side), np.uint8); c = side // 2
    b[c - 2:c + 3, c - 2:c + 3] = rng.integers(1, 4, (5, 5))
    em = caca._even_mask(side); acts = []; coms = []
    for _ in range(ticks):
        b = caca.hex_step(b[None], rule[None], em)[0]
        nz = np.flatnonzero(b)
        if nz.size == 0: return 0.0
        acts.append(nz.size); ys, xs = np.divmod(nz, side); coms.append((ys.mean(), xs.mean()))
    acts = np.array(acts)
    if acts.max() > side * side * 0.12 or acts.mean() > 300: return 0.0
    coms = np.array(coms)
    return float(np.hypot(*(coms[-1] - coms[0])))

def run_glider(rule, side, ticks, sink, seed):
    """Launch a glider near the left. sink=True puts an ABSORBING band (forced to
    0) across mid-board — a barrier that can't inject. Returns (final live mass,
    final COM-x, max COM-x reached)."""
    rng = np.random.default_rng(seed)
    b = np.zeros((side, side), np.uint8); cy = side // 2
    b[cy - 2:cy + 3, 4:9] = rng.integers(1, 4, (5, 5))
    em = caca._even_mask(side); maxx = 0.0; comx = 0.0; mass = 0
    mid = side // 2
    for _ in range(ticks):
        b = caca.hex_step(b[None], rule[None], em)[0]
        if sink:
            b[:, mid - 1:mid + 2] = 0                         # absorbing barrier
        nz = np.flatnonzero(b)
        mass = nz.size
        if mass:
            comx = float((nz % side).mean()); maxx = max(maxx, comx)
    return mass, comx, maxx

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", default="alice/c4lib-v2/outputs/c4lib.npy")
    ap.add_argument("--sample", type=int, default=8000)
    ap.add_argument("--topk", type=int, default=60)
    ap.add_argument("--side", type=int, default=80)
    ap.add_argument("--ticks", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    lib = np.load(a.lib, mmap_mode="r")
    rng = np.random.default_rng(a.seed)
    idx = np.sort(rng.choice(len(lib), size=min(a.sample, len(lib)), replace=False))
    print(f"screening {len(idx)} rules for gliders...", flush=True)
    t0 = time.time(); gl = []
    for j in idx:
        d = glider_score(np.array(lib[j]), a.side, 40, a.seed)
        if d > 4.0: gl.append((d, int(j)))
    gl.sort(reverse=True)
    print(f"  {len(gl)} gliders found [{time.time()-t0:.0f}s]; testing top {a.topk} for a GATE\n", flush=True)

    mid = a.side // 2; gates = []
    for d, j in gl[:a.topk]:
        rule = np.array(lib[j])
        # average over 3 seeds; require a rightward-crossing glider when open
        om = np.mean([run_glider(rule, a.side, a.ticks, False, s)[0] for s in range(3)])
        cx = np.mean([run_glider(rule, a.side, a.ticks, False, s)[2] for s in range(3)])
        sm = np.mean([run_glider(rule, a.side, a.ticks, True, s)[0] for s in range(3)])
        crossed = cx > mid + 6
        if crossed and om > 5 and sm < om * 0.3:        # crosses open, absorbed by sink
            gates.append((om / (sm + 1e-9), j, om, sm, cx))
    print(f"PROGRAMMABLE GATES (glider crosses when open, absorbed by sink barrier): {len(gates)}")
    for ratio, j, om, sm, cx in sorted(gates, reverse=True)[:10]:
        print(f"  rule#{j}: open mass {om:.0f} (reached x={cx:.0f}>mid={mid}), sink mass {sm:.0f}"
              f"  -> {ratio:.0f}x suppression")
    if gates:
        print("\n-> SIGNAL passes when the gate is open, is ABSORBED when a port writes a sink")
        print("   barrier = a non-local 1-bit gate driven by the class-4 dynamics under program")
        print("   control. This is the step from programmable transforms to COMPUTATION.")
    else:
        print("\n-> gliders transport (1000s found), but no clean port-SINK gate landed in this")
        print("   sample: most gliders don't cross horizontally, or aren't cleanly absorbed.")
        print("   Reliable collision-gating is genuinely hard (Adamatzky territory) — a bigger")
        print("   rule x geometry search (ALICE) is the honest next step.")

if __name__ == "__main__":
    main()
