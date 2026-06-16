#!/usr/bin/env python3
# register.py — chain CA flip-flops into a multi-bit REGISTER. Each bit = one
# mutual-annihilation latch (the verified flippable flip-flop from flipflopga), placed
# in its own column-cell on a shared board, isolated by quiescent gaps. We WRITE a
# random N-bit word (pulse layer A where bit=1, layer B where bit=0), HOLD with no
# input, then READ each cell (A dominant -> 1, B dominant -> 0). Fidelity = how
# faithfully the word is stored & recalled, vs hold time (memory persistence). A
# reliable readback = a working CA memory register.
import glob, json, sys
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

def load_genome():
    R = [json.load(open(f)) for f in glob.glob("alice/flipflopga-v1/outputs/result_*.json")]
    if R:
        def clean(st):
            if not st: return False
            (a1,b1),(a2,b2),(a3,b3)=st
            return a1>3*max(1,b1) and b2>3*max(1,a2) and a3>3*max(1,b3)
        R.sort(key=lambda r: (clean(r.get("heldout_states")), r["fitness"]), reverse=True)
        return R[0]["genome"], "best evolved (fit %.2f)" % R[0]["fitness"]
    return dict(A=[-0.1,-0.05,0.4], B=[-0.12,-0.02,0.42], psize=16, pticks=12), "fallback default"

def register_run(g, N, C=44, G=10, H=44, hold=60, seed=0):
    lutA = newton_lut(*g["A"]); lutB = newton_lut(*g["B"]); ps = min(g["psize"], C-4); pt = g["pticks"]
    W = N*(C+G); rng = np.random.default_rng(seed)
    A = np.zeros((H, W), np.uint8); B = np.zeros((H, W), np.uint8)
    centers = [i*(C+G) + G + C//2 for i in range(N)]
    pattern = (rng.random(N) < 0.5).astype(int)
    def step(A, B):
        A = lutA[rulehub.hex_key(A.astype(np.int64))].astype(np.uint8)
        B = lutB[rulehub.hex_key(B.astype(np.int64))].astype(np.uint8)
        both = (A > 0) & (B > 0); A[both] = 0; B[both] = 0
        return A, B
    cy = H // 2
    for t in range(16):                              # WRITE pulse
        for i in range(N):
            cx = centers[i]; tgt = A if pattern[i] == 1 else B
            if t < pt: tgt[cy-ps//2:cy-ps//2+ps, cx-ps//2:cx-ps//2+ps] = rng.integers(1, 4, (ps, ps))
        A, B = step(A, B)
    reads = {}
    for h in range(hold):                            # HOLD, sampling readback over time
        A, B = step(A, B)
        if h in (10, 30, hold-1):
            bits = []
            for i in range(N):
                x0 = i*(C+G); reg = slice(x0, x0+C+G)
                ma = int((A[:, reg] > 0).sum()); mb = int((B[:, reg] > 0).sum())
                bits.append(1 if ma > mb else 0)
            reads[h] = int(np.sum(np.array(bits) == pattern))
    return pattern, reads, N

def main():
    g, src = load_genome()
    print(f"CA register from flip-flop genome ({src})\n")
    for N in (4, 8, 16):
        accs = {10: [], 30: [], 59: []}
        for seed in range(8):
            pat, reads, _ = register_run(g, N, hold=60, seed=seed)
            for h in accs:
                if h in reads: accs[h].append(reads[h] / N)
        print(f"  N={N:2d}-bit register | readback accuracy:  "
              f"hold10 {100*np.mean(accs[10]):3.0f}%   hold30 {100*np.mean(accs[30]):3.0f}%   "
              f"hold59 {100*np.mean(accs[59]):3.0f}%   (chance 50%)")
    print("\n  read: accuracy>>50% = the register stores & recalls the word; drop with hold time")
    print("  = memory decay. High stable accuracy at N bits = a working N-bit CA memory register.")

if __name__ == "__main__":
    main()
