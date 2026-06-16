#!/usr/bin/env python3
# shiftreg.py — a clock-orchestrated CA shift register (serial-in / serial-out delay
# line). The CA cells STORE the bits (verified stable); a simple clock controller does
# the shift each tick: read all cells, then rewrite cell0=input, cell_i=old cell_{i-1}.
# Feed a bit-stream in; the same stream should emerge at the last cell, delayed by N.
# HONEST framing: storage is the CA's job (verified); the SHIFT here is clocked control
# logic, not yet autonomous substrate transport (gliders carrying bits = the harder
# next step). This measures whether the storage survives the repeated write/hold/shift
# cycle cleanly over a long stream.
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

def shift_register(stream, N=6, C=44, G=10, H=44, hold=12, seed=0):
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
    cur = [0]*N; writebits(cur); out_stream = []
    for inp in stream:                                   # each clock: shift right, in at cell0, out at cellN-1
        cur = readbits()
        out_stream.append(cur[N-1])                      # bit shifted out
        newbits = [inp] + cur[:N-1]
        writebits(newbits)
    return out_stream

def main():
    N = 6; rng = np.random.default_rng(3); stream = list((rng.random(24) < 0.5).astype(int))
    out = shift_register(stream, N=N)
    # output at clock t is the bit that was at cell N-1; a length-N delay line:
    # input fed at clock t appears at output at clock t+N
    correct = tot = 0
    for t in range(len(stream)):
        if t + N < len(out):
            tot += 1; correct += (out[t + N] == stream[t])
    print(f"clocked CA shift register, N={N} cells, stream len {len(stream)}")
    print(f"  input : {''.join(map(str,stream))}")
    print(f"  output: {''.join(map(str,out))}")
    print(f"  serial-in/serial-out fidelity (delay {N}): {correct}/{tot} = {100*correct/max(1,tot):.0f}%")
    print("\n  note: CA = storage (verified stable); the clock controller performs the shift.")
    print("  A fully autonomous in-substrate shift (gliders carrying bits) is the next step.")

if __name__ == "__main__":
    main()
