#!/usr/bin/env python3
# memcap.py — "if you have storage, you have memory." The analog reservoir FAILED the
# memory-capacity test (recall u_{t-k}; MC = 0.08, no delays recovered). But a shift
# register built from the CA storage IS working memory: after driving it with a random
# bit-stream, cell i holds the input from i+1 clocks ago, so reading the N cells recovers
# the last N inputs. We run the SAME benchmark on it: per-delay recall accuracy and total
# memory capacity MC. Expectation: MC ~ N (perfect recall to depth N), vs reservoir 0.08.
import glob, json
import numpy as np
import rulehub

def newton_lut(cx, cy, span, it=160, side=128):
    st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l

def best_genome():
    R = [json.load(open(f)) for f in glob.glob("alice/flipflopga-v1/outputs/result_*.json")]
    R.sort(key=lambda r: -r["fitness"]); return R[0]["genome"]

def run_memcap(N=8, C=44, G=10, H=44, hold=12, L=60, seed=0):
    g = best_genome(); lutA = newton_lut(*g["A"]); lutB = newton_lut(*g["B"])
    ps = min(g["psize"], C-4); W = N*(C+G); rng = np.random.default_rng(seed)
    A = np.zeros((H, W), np.uint8); B = np.zeros((H, W), np.uint8)
    centers = [i*(C+G) + G + C//2 for i in range(N)]; cy = H // 2
    def settle():
        nonlocal A, B
        for _ in range(hold):
            A = lutA[rulehub.hex_key(A.astype(np.int64))].astype(np.uint8)
            B = lutB[rulehub.hex_key(B.astype(np.int64))].astype(np.uint8)
            both = (A > 0) & (B > 0); A[both] = 0; B[both] = 0
    def readbits():
        out = []
        for i in range(N):
            x0 = i*(C+G); reg = slice(x0, x0+C+G)
            out.append(1 if int((A[:, reg] > 0).sum()) > int((B[:, reg] > 0).sum()) else 0)
        return out
    def writebits(bits):
        nonlocal A, B
        for i in range(N):
            x0 = i*(C+G); reg = slice(x0, x0+C+G); A[:, reg] = 0; B[:, reg] = 0
            cx = centers[i]; tgt = A if bits[i] == 1 else B
            tgt[cy-ps//2:cy-ps//2+ps, cx-ps//2:cx-ps//2+ps] = rng.integers(1, 4, (ps, ps))
        settle()
    stream = list((rng.random(L) < 0.5).astype(int))
    cur = [0]*N; writebits(cur)
    # per-delay recall: at clock t, cell i should hold stream[t-1-i]
    hit = np.zeros(N); cnt = np.zeros(N)
    for t, inp in enumerate(stream):
        cur = readbits()                       # cells BEFORE this clock hold past inputs
        for i in range(N):
            k = i  # cell i = input from (i+1) clocks ago -> delay k+1
            if t-1-i >= 0:
                cnt[i] += 1; hit[i] += (cur[i] == stream[t-1-i])
        writebits([inp] + cur[:N-1])
    acc = np.where(cnt > 0, hit/np.maximum(cnt, 1), 0.0)
    return acc  # acc[i] = recall accuracy at delay (i+1)

def main():
    N = 8
    accs = np.mean([run_memcap(N=N, seed=s) for s in range(5)], axis=0)
    # memory capacity = sum over delays of (2*acc-1)^2 squared-correlation proxy; use acc directly
    mc_bits = float(np.sum(2*np.maximum(accs-0.5, 0)))   # bits recoverable above chance
    print(f"shift-register memory (N={N} cells), 5 seeds x 60-bit streams:\n")
    print("  delay k :  " + "  ".join(f"k{ i+1}" for i in range(N)))
    print("  recall  :  " + "  ".join(f"{a:.2f}" for a in accs))
    print(f"\n  memory capacity MC = {mc_bits:.1f} bits  (perfect recall to depth where acc=1.0)")
    print(f"  vs the ANALOG RESERVOIR: MC = 0.08 bits, 0 delays recovered.")
    if accs[:N].min() > 0.95:
        print("\n  -> the storage gives PERFECT working memory of the last "
              f"{N} inputs (MC~{N}). 'If you have storage, you have memory' — confirmed.")
    else:
        print("\n  -> recall holds to the depth where accuracy stays ~1.0; beyond that it degrades.")

if __name__ == "__main__":
    main()
