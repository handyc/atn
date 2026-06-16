#!/usr/bin/env python3
# reservoir.py — the real test: does the feedback-stack actually COMPUTE WITH MEMORY?
# Standard reservoir-computing benchmark (Jaeger memory capacity / delayed recall):
# drive the closed-loop stacked-glider CA with a random input stream u_t, read out its
# state features x_t, and train LINEAR readouts to reconstruct u_{t-k} for delays k.
# Memory capacity MC = sum_k test-R^2 of recovering input k steps ago. We compare the
# evolved feedback (vf>0) to the SAME substrate with the loop OFF (vf=0): if feedback
# raises MC, the recurrence genuinely adds working memory. Honest, standard, falsifiable.
import glob, json, sys
import numpy as np
sys.path.insert(0, "alice/stackga-v3")
import stackga as S
import rulehub

def drive(g, luts, vf, u, washout=200):
    L = g["L"]; W = np.array(g["W"]); tau = np.array(g["tau"]); op = g["op"]; p = g["p"]; per = g["period"]
    side = S.SIDE; rng = np.random.default_rng(0)
    B = [np.zeros((side, side), np.uint8) for _ in range(L)]
    for k in range(L):
        r0, c0 = rng.integers(14, side-14, 2); B[k][r0-2:r0+3, c0-2:c0+3] = rng.integers(1, 4, (5, 5))
    feats = []
    for t in range(len(u)):
        if u[t] > 0.5:                                   # INPUT injection: a glider seed at the port
            B[0][3:7, 3:7] = rng.integers(1, 4, (4, 4))
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
        if vf > 0:
            src = B[L-1] > 0; inj = src & (rng.random((side, side)) < vf) & (B[0] == 0); B[0][inj] = 1
        comb = np.maximum.reduce([(b > 0) for b in B]).astype(np.float32)
        x = [float((comb*m).sum()) for m in RMASKS] + [float((b > 0).sum()) for b in B]
        feats.append(x)
    F = np.array(feats[washout:]); uu = u[washout:]
    return F, uu

RM = np.random.default_rng(7)
RMASKS = [(RM.random((S.SIDE, S.SIDE)) < 0.5) for _ in range(20)]

def memory_capacity(F, u, maxk=30, ridge=1e-2):
    n = len(u); tr = slice(0, n*2//3); te = slice(n*2//3, n)
    X = np.hstack([F, np.ones((n, 1))]); mc = []; curve = []
    for k in range(1, maxk+1):
        y = np.zeros(n); y[k:] = u[:-k]
        Xtr, ytr = X[tr], y[tr]; Xte, yte = X[te], y[te]
        A = Xtr.T @ Xtr + ridge*np.eye(Xtr.shape[1]); w = np.linalg.solve(A, Xtr.T @ ytr)
        pred = Xte @ w
        if yte.std() < 1e-9: r2 = 0.0
        else:
            c = np.corrcoef(pred, yte)[0, 1]; r2 = 0.0 if np.isnan(c) else max(0.0, c)**2
        mc.append(r2); curve.append(r2)
    return float(np.sum(mc)), curve

def main():
    R = [json.load(open(f)) for f in glob.glob("alice/stackga-v3/outputs/result_*.json")]
    if not R: print("no stackga-v3 results yet"); return
    R.sort(key=lambda r: -r["fitness"]); g = R[0]["genome"]; luts = S.luts_of(g)
    print(f"reservoir test on best v3 genome: L={g['L']} op={g['op']} vf={g['vf']:.2f} "
          f"(reported memory {R[0]['memory']:.0f}, periodicity {R[0]['periodicity']:.2f})\n")
    rng = np.random.default_rng(123); u = (rng.random(1400) < 0.5).astype(float)
    for label, vf in [("feedback ON (vf=%.2f)" % g["vf"], g["vf"]), ("feedback OFF (vf=0)", 0.0)]:
        F, uu = drive(g, luts, vf, u)
        mc, curve = memory_capacity(F, uu)
        kept = [i+1 for i, r in enumerate(curve) if r > 0.1]
        print(f"  {label}: memory capacity MC = {mc:.2f}  "
              f"(delays recovered >0.1 R^2: up to k={max(kept) if kept else 0}, {len(kept)} delays)")
        print(f"     per-delay R^2 (k=1..10): {[round(c,2) for c in curve[:10]]}")
    print("\n  read: MC = total recoverable past inputs. If feedback-ON MC clearly exceeds")
    print("  feedback-OFF, the closed loop adds genuine working memory (reservoir behaviour).")

if __name__ == "__main__":
    main()
