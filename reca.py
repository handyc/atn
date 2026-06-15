#!/usr/bin/env python3
# reca.py — a directed graph of class-4 cellular automata as a reservoir for
# next-byte prediction (Reservoir Computing with CAs, "ReCA").
#
# The reservoir is a network of 1-D elementary CAs, each node carrying a DIFFERENT
# class-4 (complex / "edge of chaos") rule. Bytes drive the input node; directed
# edges carry each node's state into its children; the board state PERSISTS across
# the byte stream, so the reservoir has memory a fixed-order n-gram does not. Only
# a cheap linear readout is trained (closed-form ridge — no gradients, no GPU):
# the interesting part, the dynamics, stays pure deterministic CA rules.
#
# The honest question this answers: does the CA network add anything a plain
# linear model over the same context could not? So we always train a MATCHED
# CONTROL — the identical readout fed "last-k bytes" instead of reservoir state.
# If the reservoir cannot beat its own control, the dynamics buy nothing.
#
# Usage:  python3 reca.py [--file zz.txt] [--bytes 40000] [--nodes 6] [--width 64]
#                         [--ticks 4] [--ctx 4] [--rules 110,54,124,137,193,147]
#
# numpy is used ONLY for the linear-algebra readout and to vectorise the CA step;
# nothing here is a neural net. Deterministic given --seed.

import argparse, sys
import numpy as np

# --- class-4 / complex elementary CA rules -----------------------------------
# Wolfram's genuinely complex elementary rules: 110 (Turing-complete) and its
# mirror/complement twins 124/137/193, plus 54 (the other famous class-4 rule)
# and a few long-transient "edge of chaos" rules. Each node gets a distinct one.
DEFAULT_RULES = [110, 54, 124, 137, 193, 147, 86, 30]  # 30 is class-3 (a chaotic foil)

def rule_table(rules):
    """(N,8) uint8 lookup: new center value for neighbourhood (l<<2|c<<1|r)."""
    t = np.zeros((len(rules), 8), dtype=np.uint8)
    for i, r in enumerate(rules):
        for nb in range(8):
            t[i, nb] = (r >> nb) & 1
    return t

def build_graph(n, fanin, rng):
    """A directed graph over the nodes: node i draws `fanin` parents from earlier
    nodes where possible (a loose DAG), wrapping to others so every node but the
    input has incoming structure. Returns list of (parent, roll-offset)."""
    edges = []
    for i in range(n):
        ps = []
        cand = [j for j in range(n) if j != i]
        rng.shuffle(cand)
        for j in cand[:fanin]:
            ps.append((j, int(rng.integers(0, 9999)) % 17))
        edges.append(ps)
    return edges


class Reservoir:
    def __init__(self, rules, width, ticks, fanin, couple, seed, spacetime=True, reps=6):
        rng = np.random.default_rng(seed)
        self.n = len(rules)
        self.w = width
        self.ticks = ticks
        self.spacetime = spacetime
        self.rt = rule_table(rules)
        self.edges = build_graph(self.n, fanin, rng)
        # sparse coupling mask per node: only ~1/couple cells receive cross-node
        # signal, so each CA's intrinsic dynamics dominate over the coupling.
        self.cmask = (rng.integers(0, couple, size=(self.n, self.w)) == 0)
        self.board = np.zeros((self.n, self.w), dtype=np.uint8)
        # distributed input drive: each of the 8 input bits is written to `reps`
        # fixed cells spread across ALL nodes, so a byte is a strong, redundant
        # perturbation the readout can later see — not 8 cells lost in 384.
        flat = rng.permutation(self.n * self.w)[: 8 * reps]
        self.drive = [flat[k * reps:(k + 1) * reps] for k in range(8)]
        self.dim = (self.ticks if spacetime else 1) * self.n * self.w

    def reset(self):
        self.board[:] = 0

    def _step_once(self):
        b = self.board
        l = np.roll(b, 1, axis=1)
        r = np.roll(b, -1, axis=1)
        idx = (l.astype(np.int64) << 2) | (b.astype(np.int64) << 1) | r.astype(np.int64)
        self.board = self.rt[np.arange(self.n)[:, None], idx]

    def feed(self, byte):
        """Inject one byte (distributed), apply directed-graph coupling, advance
        every CA, and read the SPACETIME (board after each tick) as features."""
        flat = self.board.reshape(-1)
        for k in range(8):
            flat[self.drive[k]] = (byte >> k) & 1
        # directed coupling: each node XORs in a rolled, masked copy of its parents.
        prev = self.board.copy()
        for i, ps in enumerate(self.edges):
            for (j, off) in ps:
                self.board[i] ^= np.roll(prev[j], off) & self.cmask[i]
        snaps = []
        for _ in range(self.ticks):
            self._step_once()
            if self.spacetime:
                snaps.append(self.board.reshape(-1).astype(np.float64))
        if self.spacetime:
            return np.concatenate(snaps)
        return self.board.reshape(-1).astype(np.float64)


# --- softmax (multinomial logistic) readout + honest bits-per-byte -----------
# The standard ReCA readout: the reservoir is the untrained nonlinear part; this
# one linear layer is fit by cross-entropy (convex; gradient descent on a single
# linear map — logistic regression, not a deep net). Calibrated probabilities, so
# bits/byte is meaningful.
def _softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    p = np.exp(z); p /= p.sum(axis=1, keepdims=True)
    return p

def softmax_fit(X, y, C, lam, iters=300, lr=0.5):
    n, d = X.shape
    W = np.zeros((d, C)); b = np.zeros(C)
    onehot = np.eye(C)[y]
    vW = np.zeros_like(W); vb = np.zeros_like(b); mom = 0.9
    for _ in range(iters):
        p = _softmax(X @ W + b)
        g = (p - onehot) / n
        gW = X.T @ g + lam * W
        gb = g.sum(axis=0)
        vW = mom * vW - lr * gW; W += vW
        vb = mom * vb - lr * gb; b += vb
    return W, b

def bpb(p, ytrue, uni, alpha, beta):
    """Honest bits/byte, with a small unigram (alpha) + uniform-over-256 (beta)
    floor so no probability is ever zero — even for a context unseen in training."""
    p = (1 - alpha - beta) * p + alpha * uni[None, :] + beta * (1.0 / 256.0)
    return float(np.mean(-np.log2(p[np.arange(len(ytrue)), ytrue])))

def standardize(Xtr, *rest):
    mu = Xtr.mean(axis=0); sd = Xtr.std(axis=0) + 1e-6
    out = [(Xtr - mu) / sd] + [(R - mu) / sd for R in rest]
    return out

def tune_and_score(Xtr, ytr, Xva, yva, Xte, yte, C, uni, lam):
    Xtr, Xva, Xte = standardize(Xtr, Xva, Xte)
    W, b = softmax_fit(Xtr, ytr, C, lam)
    pva, pte = _softmax(Xva @ W + b), _softmax(Xte @ W + b)
    best = (1e9, 0.02, 0.005)
    for alpha in (0.0, 0.01, 0.02, 0.05, 0.1):
        v = bpb(pva, yva, uni, alpha, 0.005)
        if v < best[0]:
            best = (v, alpha, 0.005)
    _, alpha, beta = best
    return bpb(pte, yte, uni, alpha, beta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="zz.txt")
    ap.add_argument("--bytes", type=int, default=40000)
    ap.add_argument("--nodes", type=int, default=6)
    ap.add_argument("--width", type=int, default=64)
    ap.add_argument("--ticks", type=int, default=4)
    ap.add_argument("--fanin", type=int, default=2)
    ap.add_argument("--couple", type=int, default=4)
    ap.add_argument("--ctx", type=int, default=4, help="control: last-k bytes")
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--lam", type=float, default=1e-3)
    ap.add_argument("--rules", default="")
    ap.add_argument("--reps", type=int, default=6, help="cells per input bit")
    ap.add_argument("--final-only", action="store_true", help="read final board, not spacetime")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    rules = [int(x) for x in a.rules.split(",")] if a.rules else DEFAULT_RULES[:a.nodes]
    if len(rules) < a.nodes:
        rules = (rules * a.nodes)[:a.nodes]
    rules = rules[:a.nodes]

    data = open(a.file, "rb").read(a.bytes)
    n = len(data)
    print(f"corpus: {a.file}  {n} bytes")
    print(f"reservoir: {a.nodes} nodes x {a.width} cells, {a.ticks} ticks/byte, "
          f"fanin {a.fanin}, {'spacetime' if not a.final_only else 'final-state'} readout, "
          f"rules {rules}")

    # build reservoir features for the whole stream (recurrent: state persists).
    res = Reservoir(rules, a.width, a.ticks, a.fanin, a.couple, a.seed,
                    spacetime=not a.final_only, reps=a.reps)
    res.reset()
    D = res.dim
    feats = np.zeros((n, D), dtype=np.float64)
    for t in range(n):
        feats[t] = res.feed(data[t])

    # samples: feature after byte t  ->  predict byte t+1.  classes = bytes seen.
    s, e = a.warmup, n - 1
    Xres = feats[s:e]
    targ = np.frombuffer(data, dtype=np.uint8)[s + 1:e + 1].astype(np.int64)

    # control features: one-hot of the last `ctx` bytes (a linear n-gram-ish model).
    raw = np.frombuffer(data, dtype=np.uint8).astype(np.int64)
    ctxcols = []
    for k in range(1, a.ctx + 1):
        col = np.zeros((e - s, 256))
        idxs = raw[s - k:e - k]
        col[np.arange(e - s), idxs] = 1.0
        ctxcols.append(col)
    Xctx = np.hstack(ctxcols) if ctxcols else np.zeros((e - s, 1))

    # class map (compact, over bytes that occur in the sample window).
    seen = sorted(set(targ.tolist()))
    remap = {b: i for i, b in enumerate(seen)}
    C = len(seen)
    y = np.array([remap[b] for b in targ.tolist()], dtype=np.int64)

    # train / val / test split (chronological — no leakage).
    m = len(y)
    i1, i2 = int(m * 0.7), int(m * 0.85)
    def sp(M): return M[:i1], M[i1:i2], M[i2:]
    ytr, yva, yte = sp(y)
    uni = np.bincount(ytr, minlength=C).astype(np.float64); uni /= uni.sum()

    print(f"samples: {m}  (train {i1} / val {i2-i1} / test {m-i2})   classes: {C}")
    print()

    # 1) order-0 floor.
    floor = float(np.mean(-np.log2(np.maximum(uni[yte], 1e-12))))

    # 2) matched control: linear model over last-ctx bytes.
    Xc = [a1[:, None] if a1.ndim == 1 else a1 for a1 in sp(Xctx)]
    ctx_bpb = tune_and_score(Xc[0], ytr, Xc[1], yva, Xc[2], yte, C, uni, a.lam)

    # 3) the CA reservoir.
    Xr = sp(Xres)
    res_bpb = tune_and_score(Xr[0], ytr, Xr[1], yva, Xr[2], yte, C, uni, a.lam)

    # 4) reservoir + context together (do the dynamics ADD to the context?).
    Xboth = np.hstack([Xres, Xctx])
    Xb = sp(Xboth)
    both_bpb = tune_and_score(Xb[0], ytr, Xb[1], yva, Xb[2], yte, C, uni, a.lam)

    print(f"{'model':<34}{'test bpb':>10}")
    print(f"{'-'*44}")
    print(f"{'order-0 (unigram floor)':<34}{floor:>10.3f}")
    print(f"{'linear ctx-'+str(a.ctx)+' bytes (control)':<34}{ctx_bpb:>10.3f}")
    print(f"{'CA reservoir':<34}{res_bpb:>10.3f}")
    print(f"{'reservoir + ctx-'+str(a.ctx):<34}{both_bpb:>10.3f}")
    print()

    # honest verdict.
    d = ctx_bpb - res_bpb
    if res_bpb < ctx_bpb - 0.01:
        print(f"verdict: reservoir BEATS its matched control by {d:+.3f} bpb — the CA "
              f"dynamics add information the raw context does not.")
    elif res_bpb < floor - 0.01:
        print(f"verdict: reservoir beats the unigram floor but NOT the matched linear "
              f"control ({d:+.3f}) — it learned, but a plain context model is as good or "
              f"better. The dynamics aren't earning their keep here.")
    else:
        print(f"verdict: reservoir barely beats the unigram floor — at this scale the "
              f"readout can't decode the CA state into prediction.")
    dd = ctx_bpb - both_bpb
    print(f"         ctx+reservoir vs ctx alone: {dd:+.3f} bpb "
          f"({'reservoir adds signal on top of context' if dd > 0.01 else 'no lift over context alone'}).")


if __name__ == "__main__":
    main()
