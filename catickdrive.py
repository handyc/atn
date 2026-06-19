#!/usr/bin/env python3
# catickdrive.py — CLOSING bar #2: drive a sequential CA element with the on-board CA CLOCK.
# catick.py showed the clock SOURCE: a localized glider circling a torus crosses a fixed tripwire once per
# lap = an autonomous tick whose PERIOD is set by the substrate (exactly 2x the board circumference), not by
# a host step-counter.  Here that tick actually DRIVES state: each rising edge of the glider clock toggles a
# CA flip-flop, and the toggle (the next-state function) is computed by a GENUINE CA inverter latch
# (caregen.NOT).  Two such flip-flops chained = a 2-bit ripple counter clocked entirely by the glider.
#
# What is the CA's vs the host's job (honest):
#   * WHEN a tick happens .......... the CELLULAR AUTOMATON (the glider crossing the tripwire — not chosen)
#   * the STATE TRANSITION ......... the CELLULAR AUTOMATON (caregen.NOT — the mutual-annihilation inverter latch)
#   * detecting the edge + holding the bit between edges ... the host SAMPLES the readout, exactly as any
#     real flip-flop's clock input is sampled by its consumer.  No host step-counter sets the rate.
# Result: the counter's output periods are integer multiples of the GLIDER's lap (2 lap, 4 lap) — a self-
# timed CA counter whose tempo is the automaton's own circulation time.
import numpy as np
import catick, caregen

def glider_clock(lut, side, T, col_off, seed=0):
    """The CA clock signal: the column-tripwire pulse train from a glider circling the torus (catick)."""
    _, readout = catick.run_clock(lut, side, T, col_off=col_off, seed=seed)
    return readout

def rising_edges(sig, mingap, warmup=30):
    """Tick events = rising edges of the thresholded glider pulse train, DEBOUNCED: the 2-phase glider fires
    a brief double-pulse as it crosses the strip, so edges closer than `mingap` (< half a lap) are one tick."""
    hi = sig.max()
    if hi == 0: return []
    on = (sig > 0.4 * hi).astype(int)
    raw = [t for t in range(warmup + 1, len(on)) if on[t] and not on[t-1]]
    out = []
    for t in raw:
        if not out or t - out[-1] >= mingap: out.append(t)
    return out

def run_counter(lut, side, T, col_off, mingap, nbits=2, fseed=200):
    """Drive an nbits ripple counter from the glider clock: each glider edge toggles bit0 via a CA inverter
    latch; bit_k toggles on bit_{k-1}'s rising edge.  Returns the per-tick state of each bit over the run."""
    clk = glider_clock(lut, side, T, col_off)
    edges = rising_edges(clk, mingap)
    state = [0] * nbits
    traces = [[] for _ in range(nbits)]            # bit value sampled at each clock edge
    k = fseed
    for _ in edges:
        # bit0 toggles every glider tick; carry ripples while a bit toggles 1->1 (i.e. was 1 before toggle)
        lvl = 0
        while lvl < nbits:
            prev = state[lvl]
            state[lvl] = caregen.NOT(prev, seed=k); k += 1     # GENUINE CA inverter latch = the T-flip-flop
            if not (prev == 1 and state[lvl] == 0):            # no carry out -> ripple stops
                break
            lvl += 1                                            # this bit rolled 1->0: carry into the next
        for b in range(nbits):
            traces[b].append(state[b])
    return clk, edges, [np.array(t) for t in traces]

def period_of_bits(traces, edges):
    """Period (in glider-ticks) of each counter bit = spacing of its rising edges in edge-index space."""
    out = []
    for tr in traces:
        re = [i for i in range(1, len(tr)) if tr[i] and not tr[i-1]]
        out.append(int(round(np.mean(np.diff(re)))) if len(re) >= 2 else None)
    return out

if __name__ == "__main__":
    print("catickdrive — the on-board CA clock DRIVES a CA sequential element (closing bar #2)\n")
    got = catick.load_glider_rule()
    if got is None:
        print("  no clean compact glider found"); raise SystemExit
    lut, rec, v, mx = got
    vx = abs(v[1] * np.cos(v[0]))
    side = 60
    lap = side / vx
    T = int(14 * lap)                                   # ~14 laps -> enough edges to see ÷2 and ÷4
    print(f"  glider clock: {rec['family']} cx={rec['cx']:.3f} | {mx}-cell packet | lap ≈ {side/vx:.0f} ticks on a {side}×{side} torus\n")

    clk, edges, traces = run_counter(lut, side, T, col_off=side // 3, mingap=0.5 * lap, nbits=2)
    gaps = np.diff(edges)
    measured_lap = int(round(gaps.mean())) if len(edges) >= 2 else None
    print(f"  glider produced {len(edges)} clock ticks over {T} CA steps; lap = {measured_lap}±{gaps.std():.0f} steps/tick (even)")

    bitper = period_of_bits(traces, edges)              # in units of glider-ticks
    print(f"  ripple counter (each toggle = a genuine CA inverter latch):")
    print(f"     bit0 period = {bitper[0]} ticks  (expect 2 = ÷2)")
    print(f"     bit1 period = {bitper[1]} ticks  (expect 4 = ÷4)")

    # show the counter counting: bit1 bit0 as a 2-bit value over the first ticks
    n = min(16, len(traces[0]))
    seq = [int(traces[1][i])*2 + int(traces[0][i]) for i in range(n)]
    print(f"     2-bit count over first {n} glider ticks: {seq}")
    b0 = "".join("█" if x else "·" for x in traces[0][:n])
    b1 = "".join("█" if x else "·" for x in traces[1][:n])
    print(f"        bit0 (÷2): {b0}")
    print(f"        bit1 (÷4): {b1}")

    # the counter counts mod 4; it starts at 1 because the first sample is taken AFTER the first toggle
    counts_cleanly = all(seq[i] == (seq[0] + i) % 4 for i in range(n))
    ok = bitper[0] == 2 and bitper[1] == 4 and counts_cleanly
    if ok:
        print("\n  -> SELF-TIMED CA COUNTER: a glider circling the lattice provides the clock; each tick a CA")
        print("     inverter latch toggles the state; the counter's bit periods are exact multiples of the")
        print("     glider's lap (÷2, ÷4). Both WHEN (glider crossing) and the STATE TRANSITION (inverter")
        print("     latch) are the cellular automaton — the timing is the substrate's own circulation, no")
        print("     host step-counter. Bar #2 closed: a CA sequential circuit driven by an on-board CA clock.")
    else:
        print(f"\n  (counter not exact: periods {bitper}, seq {seq[:8]} — tuning needed)")
