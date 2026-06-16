#!/usr/bin/env python3
# feedback.py — close the stack into a LOOP: feed the bottom layer's output back as
# input to the top layer (bottom->top), turning a feed-forward stack into a recurrent
# one. Run it on the VERIFIED emergent-glider genomes from stackga-v2 and ask what the
# closed loop does to the emergent intersection-structure: sustain it longer? make it
# loop/oscillate (periodicity)? freeze or explode? Compares feedback strength vf.
import glob, json, sys, os
import numpy as np
sys.path.insert(0, "alice/stackga-v2")
import stackga as S
import rulehub

def simulate_fb(g, luts, vf, side=64, T=220, seed=0):
    L = g["L"]; W = np.array(g["W"]); tau = np.array(g["tau"]); op = g["op"]
    p = g["p"]; per = g["period"]; rng = np.random.default_rng(seed)
    B = [np.zeros((side, side), np.uint8) for _ in range(L)]
    for k in range(L):
        r0, c0 = rng.integers(16, side-16, 2); B[k][r0-2:r0+3, c0-2:c0+3] = rng.integers(1, 4, (5, 5))
    imass = []; motion = []; prev = None; tot_series = []
    for t in range(T):
        for k in range(L):
            B[k] = luts[k][rulehub.hex_key(B[k].astype(np.int64))].astype(np.uint8)
        if t % per == 0:
            A = [(b > 0).astype(np.float32) for b in B]; cm = rng.random((side, side)) < p
            for k in range(L):
                sig = sum(W[k, j]*A[j] for j in range(L) if j != k); trig = (sig > tau[k]) & cm
                if op == "kill": B[k][trig] = 0
                elif op == "birth": B[k][trig & (B[k] == 0)] = 1
                elif op == "flip": B[k][trig] = (3 - B[k][trig].astype(np.int16)).astype(np.uint8)
                elif op == "setmax": mx = np.maximum.reduce(B); B[k][trig] = mx[trig]
                elif op == "decay": B[k][trig & (B[k] > 0)] -= 1
        if vf > 0:                                   # FEEDBACK: bottom layer output -> top layer input
            src = B[L-1] > 0; fm = rng.random((side, side)) < vf
            inj = src & fm & (B[0] == 0); B[0][inj] = 1
        tot = sum(int((b > 0).sum()) for b in B)
        if tot > 0.5*L*side*side: return "explode", None
        if tot == 0: return "dead", None
        tot_series.append(tot)
        inter = sum((b > 0).astype(np.int16) for b in B) >= 2
        imass.append(int(inter.sum()))
        if prev is not None: motion.append(S.shift_overlap(inter, prev)[0])
        prev = inter
    ts = np.array(tot_series[T//3:], float)
    # periodicity: strongest autocorrelation peak at lag>=3 (a loop/oscillation)
    ts = ts - ts.mean(); period_str = 0.0
    if ts.std() > 1e-6 and len(ts) > 20:
        ac = np.correlate(ts, ts, "full")[len(ts)-1:]; ac /= ac[0]
        period_str = float(np.max(ac[3:len(ts)//2])) if len(ts) > 8 else 0.0
    return "alive", dict(imass=float(np.mean(imass[T//3:])), motion=float(np.mean(motion[T//3:])),
                         period=period_str)

def main():
    R = [json.load(open(f)) for f in glob.glob("alice/stackga-v2/outputs/result_*.json")]
    R.sort(key=lambda r: -r["fitness"])
    print("feedback (bottom->top) on the verified emergent-glider stacks\n")
    for gi, gr in enumerate(R[:3]):
        g = gr["genome"]; luts = S.luts_of(g)
        print(f"genome #{gi+1}: L={g['L']} op={g['op']} (open-loop motion {gr['inter_motion']:.2f})")
        print("   vf     outcome   inter_mass  motion  periodicity")
        for vf in (0.0, 0.1, 0.3, 0.6):
            outs = [simulate_fb(g, luts, vf, seed=s) for s in (0, 1, 2)]
            alive = [o[1] for o in outs if o[0] == "alive"]
            from collections import Counter
            st = Counter(o[0] for o in outs)
            if alive:
                im = np.mean([a["imass"] for a in alive]); mo = np.mean([a["motion"] for a in alive])
                pe = np.mean([a["period"] for a in alive])
                print(f"   {vf:.1f}    {dict(st)}   {im:6.0f}    {mo:.2f}    {pe:.2f}")
            else:
                print(f"   {vf:.1f}    {dict(st)}")
        print()
    print("read: high periodicity at vf>0 = the loop sustains a recurring/oscillating")
    print("structure (memory-like); explode/dead = the feedback destabilises it.")

if __name__ == "__main__":
    main()
