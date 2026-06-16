#!/usr/bin/env python3
# regtest.py — THOROUGH test of the CA memory register. Given an evolved flip-flop
# genome, build an N-bit register (N latch cells on one shared board, isolated by
# quiescent gaps), write many random N-bit words, HOLD a long time with no input, and
# read back at checkpoints. Reports bit-fidelity and whole-word-perfect rate vs hold
# time — to map CAPACITY (does it hold at large N without cross-talk?) and RETENTION
# (does it stay 100% out to long holds?). Self-contained: rulehub + numpy.
import argparse, json, os
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

def run_word(lutA, lutB, ps, pt, N, hold, checkpoints, C=44, G=10, H=44, seed=0):
    W = N*(C+G); rng = np.random.default_rng(seed)
    A = np.zeros((H, W), np.uint8); B = np.zeros((H, W), np.uint8)
    centers = [i*(C+G) + G + C//2 for i in range(N)]; cy = H // 2; psl = min(ps, C-4)
    pattern = (rng.random(N) < 0.5).astype(int)
    def step():
        nonlocal A, B
        A = lutA[rulehub.hex_key(A.astype(np.int64))].astype(np.uint8)
        B = lutB[rulehub.hex_key(B.astype(np.int64))].astype(np.uint8)
        both = (A > 0) & (B > 0); A[both] = 0; B[both] = 0
    def readbits():
        out = []
        for i in range(N):
            x0 = i*(C+G); reg = slice(x0, x0+C+G)
            out.append(1 if int((A[:, reg] > 0).sum()) > int((B[:, reg] > 0).sum()) else 0)
        return np.array(out)
    for t in range(16):
        for i in range(N):
            cx = centers[i]; tgt = A if pattern[i] == 1 else B
            if t < pt: tgt[cy-psl//2:cy-psl//2+psl, cx-psl//2:cx-psl//2+psl] = rng.integers(1, 4, (psl, psl))
        step()
    res = {}
    for h in range(hold):
        step()
        if h in checkpoints:
            bits = readbits(); res[h] = (int(np.sum(bits == pattern)), int(np.all(bits == pattern)))
    return N, res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); s = json.load(open(a.spec)); os.makedirs(a.out, exist_ok=True)
    tag = os.path.splitext(os.path.basename(a.spec))[0].split("_")[-1]
    g = s["genome"]; N = s["N"]; hold = s["hold"]; trials = s.get("trials", 10); seed0 = s.get("seed0", 0)
    lutA = newton_lut(*g["A"]); lutB = newton_lut(*g["B"]); ps = g["psize"]; pt = g["pticks"]
    cps = sorted(set([50, hold//2, hold-1]))
    bitacc = {h: [] for h in cps}; wordok = {h: [] for h in cps}
    for tr in range(trials):
        _, res = run_word(lutA, lutB, ps, pt, N, hold, cps, seed=seed0 + tr)
        for h in cps:
            if h in res: bitacc[h].append(res[h][0] / N); wordok[h].append(res[h][1])
    out = dict(N=N, hold=hold, trials=trials, genome_tag=s.get("gtag", "?"),
               checkpoints={str(h): dict(bit=float(np.mean(bitacc[h])), word=float(np.mean(wordok[h]))) for h in cps})
    json.dump(out, open(os.path.join(a.out, f"result_{tag}.json"), "w"))
    last = cps[-1]
    print(f"task {tag}: N={N} hold={hold} gtag={s.get('gtag')} -> bit-acc@{last}={np.mean(bitacc[last]):.2f} "
          f"word-perfect@{last}={np.mean(wordok[last]):.2f}")

if __name__ == "__main__":
    main()
