#!/usr/bin/env python3
# caca.py — a directed-graph NETWORK of class-4 HEXAGONAL cellular automata
# (the mandelhunt 7->1, K=4 hex rule) used as a reservoir for next-byte
# prediction. This is the CORRECT CA (reca.py used 1-D elementary rules by
# mistake): K=4 states, 7-cell pointy-top neighbourhood, toroidal, each node a
# distinct class-4 LUT discovered by the Mandelbrot walk (mandelhunt.c).
#
# The reservoir is untrained; only a cheap linear readout is fit (ridge for fast
# GA fitness, logistic for honest bits/byte). The honest question, unchanged from
# reca.py: does the CA NETWORK add predictive information a plain linear context
# model lacks? So we always compute the matched control and the lift of
# (context + reservoir) over (context alone) on HELD-OUT data.
#
# numpy is used only for vectorised CA stepping and the linear readout — no net.

import argparse, os, glob, sys
import numpy as np

LUT_SIZE = 16384  # 4^7
POOL_DIR = "/home/handyc/claubsh/velour-dev/isolation/artifacts/mandelhunt/mh_pool"

# --- vectorised hex CA: step ALL network nodes at once -----------------------
# boards: (N, S, S) uint8 in {0,1,2,3}.  rules: (N, LUT_SIZE) uint8.
# Reimplements mandelhunt.c hex_step (pointy-top, even/odd row column shift):
#   key = (self<<12)|(nw<<10)|(ne<<8)|(r<<6)|(se<<4)|(sw<<2)|l
def _even_mask(S):
    return (np.arange(S) % 2 == 0).reshape(1, S, 1)

def hex_step(boards, rules, em):
    b = boards.astype(np.int32)
    up = np.roll(b, 1, axis=1)      # row r-1
    dn = np.roll(b, -1, axis=1)     # row r+1
    l  = np.roll(b, 1, axis=2)      # col c-1  (n_l)
    rg = np.roll(b, -1, axis=2)     # col c+1  (n_r)
    up_l = np.roll(up, 1, axis=2); up_r = np.roll(up, -1, axis=2)
    dn_l = np.roll(dn, 1, axis=2); dn_r = np.roll(dn, -1, axis=2)
    nw = np.where(em, up_l, up)
    ne = np.where(em, up,  up_r)
    sw = np.where(em, dn_l, dn)
    se = np.where(em, dn,  dn_r)
    key = (b << 12) | (nw << 10) | (ne << 8) | (rg << 6) | (se << 4) | (sw << 2) | l
    N = boards.shape[0]
    out = np.take_along_axis(rules, key.reshape(N, -1), axis=1)
    return out.reshape(boards.shape).astype(np.uint8)


# --- hex symmetry (per-node prior): C6 rotations / D6 rotations+reflections --
# Collapse each neighbourhood's symmetry orbit to one output -> an isotropic rule.
# Shrinks the rule space ~6-10x; used as a GA-selectable per-node prior.
_SYM_SHIFTS = [6, 8, 10, 0, 2, 4]   # r,ne,nw,l,sw,se  (cyclic CCW); self=bits12-13
_CANON = {}

def _canon_map(reflect):
    key = bool(reflect)
    if key in _CANON:
        return _CANON[key]
    canon = np.arange(16384, dtype=np.int64)
    seen = np.zeros(16384, dtype=bool)
    def mk(selfv, vals):
        k = selfv << 12
        for s, v in zip(_SYM_SHIFTS, vals):
            k |= v << s
        return k
    for kk in range(16384):
        if seen[kk]:
            continue
        selfv = (kk >> 12) & 3
        base = [(kk >> s) & 3 for s in _SYM_SHIFTS]
        variants = [base, base[::-1]] if reflect else [base]
        orb = set()
        for v0 in variants:
            v = list(v0)
            for _ in range(6):
                orb.add(mk(selfv, v)); v = [v[-1]] + v[:-1]
        c = min(orb)
        for k in orb:
            canon[k] = c; seen[k] = True
    _CANON[key] = canon
    return canon

def symmetrize_rule(rule, sym):
    """sym: 0=none, 1=C6 (rotations), 2=D6 (rotations+reflections)."""
    if not sym:
        return rule
    return rule[_canon_map(sym == 2)].astype(np.uint8)


# --- load a diverse set of class-4 rules from the mandelhunt pool ------------
def load_pool(k, pool_dir=POOL_DIR, seed=0, by="c4"):
    files = glob.glob(os.path.join(pool_dir, "*.lut"))
    def score(f):
        import re
        m = re.search(r"c4([0-9.]+)", os.path.basename(f))
        return float(m.group(1).rstrip(".")) if m else 0.0
    files = [f for f in files if os.path.getsize(f) == LUT_SIZE]
    files.sort(key=score, reverse=True)
    # take a spread across the c4-ranked list (not just the top, for diversity)
    rng = np.random.default_rng(seed)
    if len(files) > k:
        idx = np.linspace(0, len(files) - 1, k).astype(int)
        files = [files[i] for i in idx]
    rules = np.zeros((len(files), LUT_SIZE), dtype=np.uint8)
    for i, f in enumerate(files):
        rules[i] = np.frombuffer(open(f, "rb").read(LUT_SIZE), dtype=np.uint8)
    return rules, [os.path.basename(f) for f in files]


# --- the CA-network reservoir ------------------------------------------------
class HexNet:
    """A directed graph of hex-CA nodes. Each node has its own class-4 LUT,
    an SxS toroidal board, and parents whose state perturbs it each step."""
    def __init__(self, gene, pool, seed=0):
        rng = np.random.default_rng(seed)
        self.S = gene["side"]
        self.ticks = gene["ticks"]
        ids = gene["lut_ids"]
        self.N = len(ids)
        self.rules = pool[np.array(ids)].copy()          # (N, LUT_SIZE)
        self.em = _even_mask(self.S)
        self.boards = np.zeros((self.N, self.S, self.S), dtype=np.uint8)
        cells = self.S * self.S
        # directed graph: parents per node (loose DAG with wraparound).
        self.parents = gene["parents"]
        self.couple = gene.get("couple", 6)             # 1/couple cells coupled
        self.cmask = (rng.integers(0, self.couple, size=(self.N, cells)) == 0)
        self.coff = rng.integers(0, cells, size=self.N)  # per-node coupling roll
        # input drive: write the byte's 4 base-4 digits to `reps` cells of node 0.
        reps = gene.get("reps", 12)
        flat = rng.permutation(cells)[: 4 * reps]
        self.drive = [flat[k * reps:(k + 1) * reps] for k in range(4)]
        # input-sensitivity lever: a fixed set of cells zeroed each step so the
        # board cannot fully lock into the rule's attractor (these rules were bred
        # for STABILITY, the opposite of what a reservoir wants). decay=0 -> off.
        decay = gene.get("decay", 0.0)
        self.dmask = (rng.random((self.N, cells)) < decay) if decay > 0 else None
        # readout: a fixed random sample of cells per node (keeps feature dim sane)
        self.rcells = min(gene.get("rcells", 64), cells)
        self.rsel = np.array([rng.permutation(cells)[: self.rcells] for _ in range(self.N)])
        self.dim = self.N * self.rcells * 4              # one-hot K=4
        self.seed = seed

    def reset(self):
        self.boards[:] = 0

    def feed(self, byte=None, ext=None):
        cells = self.S * self.S
        flat = self.boards.reshape(self.N, cells)
        # drive node 0: a byte (4 base-4 digits, redundant) OR an external vector
        # (for stacked/deep reservoirs — the prior layer's sampled cell values).
        if ext is not None:
            e = np.mod(np.asarray(ext, dtype=np.int64), 4).astype(np.uint8)
            if len(e):
                for k in range(4):
                    g = self.drive[k]
                    flat[0, g] = e[(np.arange(len(g)) + k) % len(e)]
        else:
            digs = [(byte >> (2 * k)) & 3 for k in range(4)]
            for k in range(4):
                flat[0, self.drive[k]] = digs[k]
        # directed coupling: each node += masked, rolled parent state (mod 4).
        prev = flat.copy()
        for i, ps in enumerate(self.parents):
            for p in ps:
                contrib = np.roll(prev[p], int(self.coff[i])) * self.cmask[i]
                flat[i] = (flat[i] + contrib) & 3
        # advance every CA `ticks` steps; optional fixed-mask decay for input
        # sensitivity (zero a fixed set of cells each step).
        for _ in range(self.ticks):
            self.boards = hex_step(self.boards, self.rules, self.em)
            if self.dmask is not None:
                flat2 = self.boards.reshape(self.N, cells)
                flat2[self.dmask] = 0
        # read out: one-hot of sampled cells (and stash raw values for stacking).
        flat = self.boards.reshape(self.N, cells)
        feats = np.zeros((self.N, self.rcells, 4), dtype=np.float32)
        vals_all = np.empty(self.N * self.rcells, dtype=np.uint8)
        for i in range(self.N):
            vals = flat[i, self.rsel[i]]
            feats[i, np.arange(self.rcells), vals] = 1.0
            vals_all[i * self.rcells:(i + 1) * self.rcells] = vals
        self.last_vals = vals_all
        return feats.reshape(-1)

    def run(self, data, warmup=200):
        self.reset()
        n = len(data)
        F = np.zeros((n, self.dim), dtype=np.float32)
        for t in range(n):
            F[t] = self.feed(data[t])
        return F


class DeepHexNet:
    """A STACK of HexNets (deep / hierarchical reservoir = the user's 'meta-node /
    meta-network'). Layer 0 is driven by the byte; each deeper layer is driven by
    the previous layer's sampled cell values. Features = concat of all layers, so
    the readout sees both shallow (input-near) and deep (abstracted) state."""
    def __init__(self, gene, pool, seed=0):
        self.depth = max(1, int(gene.get("depth", 1)))
        self.layers = [HexNet(gene, pool, seed=seed + 17 * d) for d in range(self.depth)]
        self.dim = sum(l.dim for l in self.layers)

    def reset(self):
        for l in self.layers:
            l.reset()

    def feed(self, byte):
        out = [self.layers[0].feed(byte)]
        prev = self.layers[0].last_vals
        for l in self.layers[1:]:
            out.append(l.feed(ext=prev))
            prev = l.last_vals
        return np.concatenate(out)

    def run(self, data, warmup=0):
        self.reset()
        n = len(data)
        F = np.zeros((n, self.dim), dtype=np.float32)
        for t in range(n):
            F[t] = self.feed(data[t])
        return F


def build_net(gene, pool, seed=0):
    """HexNet, or DeepHexNet if gene asks for depth>1."""
    if int(gene.get("depth", 1)) > 1:
        return DeepHexNet(gene, pool, seed=seed)
    return HexNet(gene, pool, seed=seed)


# --- readouts + honest metrics (shared with the GA) --------------------------
def _softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    p = np.exp(z); p /= p.sum(axis=1, keepdims=True)
    return p

def softmax_fit(X, y, C, lam=1e-3, iters=250, lr=0.5):
    n, d = X.shape
    W = np.zeros((d, C)); b = np.zeros(C)
    oh = np.eye(C)[y]; vW = np.zeros_like(W); vb = np.zeros_like(b); mom = 0.9
    for _ in range(iters):
        p = _softmax(X @ W + b)
        g = (p - oh) / n
        vW = mom * vW - lr * (X.T @ g + lam * W); W += vW
        vb = mom * vb - lr * g.sum(axis=0); b += vb
    return W, b

def ridge_logits(Xtr, ytr, Xte, C, lam=1.0):
    """Fast closed-form readout for GA fitness: ridge to one-hot -> raw scores."""
    d = Xtr.shape[1]
    W = np.linalg.solve(Xtr.T @ Xtr + lam * np.eye(d), Xtr.T @ np.eye(C)[ytr])
    return Xte @ W

def standardize(Xtr, *rest):
    mu = Xtr.mean(0); sd = Xtr.std(0) + 1e-6
    return [(Xtr - mu) / sd] + [(R - mu) / sd for R in rest]

def accuracy(logits, y):
    return float((logits.argmax(1) == y).mean())

def bpb(p, y, uni, alpha=0.05, beta=0.005):
    p = (1 - alpha - beta) * p + alpha * uni[None, :] + beta / 256.0
    return float(np.mean(-np.log2(p[np.arange(len(y)), y])))


def make_targets(data, s, e):
    targ = np.frombuffer(data, dtype=np.uint8)[s + 1:e + 1].astype(np.int64)
    seen = sorted(set(targ.tolist()))
    remap = {b: i for i, b in enumerate(seen)}
    y = np.array([remap[b] for b in targ.tolist()], np.int64)
    return y, len(seen)

def context_features(data, s, e, ctx):
    raw = np.frombuffer(data, dtype=np.uint8).astype(np.int64)
    cols = []
    for k in range(1, ctx + 1):
        c = np.zeros((e - s, 256), np.float32)
        c[np.arange(e - s), raw[s - k:e - k]] = 1.0
        cols.append(c)
    return np.hstack(cols)

def split3(M, i1, i2):
    return M[:i1], M[i1:i2], M[i2:]


def evaluate(Fres, data, s, e, ctx=4, full=False):
    """Honest comparison on a chronological train/val/test split.
    Returns dict of test accuracies (and bpb if full)."""
    y, C = make_targets(data, s, e)
    Xctx = context_features(data, s, e, ctx)
    m = len(y); i1, i2 = int(m * 0.7), int(m * 0.85)
    ytr, yva, yte = split3(y, i1, i2)
    uni = np.bincount(ytr, minlength=C).astype(np.float64); uni /= uni.sum()
    out = {"C": C, "n": m}

    def run_model(Xall, key):
        Xtr, Xva, Xte = standardize(*split3(Xall, i1, i2))
        if full:
            W, b = softmax_fit(Xtr, ytr, C)
            pte = _softmax(Xte @ W + b)
            out[key + "_acc"] = accuracy(Xte @ W + b, yte)
            out[key + "_bpb"] = bpb(pte, yte, uni)
        else:
            lg = ridge_logits(Xtr, ytr, Xte, C)
            out[key + "_acc"] = accuracy(lg, yte)

    # unigram floor
    out["uni_bpb"] = float(np.mean(-np.log2(np.maximum(uni[yte], 1e-12))))
    out["uni_acc"] = float((yte == uni.argmax()).mean())
    run_model(Xctx, "ctx")
    run_model(Fres, "res")
    run_model(np.hstack([Xctx, Fres]), "both")
    out["lift_acc"] = out["both_acc"] - out["ctx_acc"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--bytes", type=int, default=20000)
    ap.add_argument("--nodes", type=int, default=4)
    ap.add_argument("--side", type=int, default=24)
    ap.add_argument("--ticks", type=int, default=2)
    ap.add_argument("--rcells", type=int, default=64)
    ap.add_argument("--couple", type=int, default=6)
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--ctx", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--poolk", type=int, default=64)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    pool, names = load_pool(a.poolk, seed=a.seed)
    rng = np.random.default_rng(a.seed)
    ids = rng.choice(len(pool), size=a.nodes, replace=False).tolist()
    # simple loose-DAG topology: node i's parents = a couple of earlier nodes.
    parents = [[] if i == 0 else sorted(rng.choice(i, size=min(2, i), replace=False).tolist())
               for i in range(a.nodes)]
    gene = dict(side=a.side, ticks=a.ticks, lut_ids=ids, parents=parents,
                couple=a.couple, reps=a.reps, rcells=a.rcells, leak=1.0)

    data = open(a.file, "rb").read(a.bytes)
    print(f"corpus: {a.file}  {len(data)} bytes")
    print(f"network: {a.nodes} hex CAs {a.side}x{a.side}, {a.ticks} ticks/byte, "
          f"parents={parents}")
    print(f"rules: {[names[i] for i in ids]}")
    net = HexNet(gene, pool, seed=a.seed)
    Fres = net.run(data, warmup=a.warmup)
    s, e = a.warmup, len(data) - 1
    Fres = Fres[s:e]
    r = evaluate(Fres, data, s, e, ctx=a.ctx, full=True)
    print(f"feature dim: reservoir={net.dim}, samples={r['n']}, classes={r['C']}\n")
    print(f"{'model':<26}{'test acc':>10}{'test bpb':>10}")
    print("-" * 46)
    print(f"{'unigram floor':<26}{r['uni_acc']:>10.3f}{r['uni_bpb']:>10.3f}")
    print(f"{'linear ctx-'+str(a.ctx)+' (control)':<26}{r['ctx_acc']:>10.3f}{r['ctx_bpb']:>10.3f}")
    print(f"{'CA reservoir':<26}{r['res_acc']:>10.3f}{r['res_bpb']:>10.3f}")
    print(f"{'reservoir + ctx':<26}{r['both_acc']:>10.3f}{r['both_bpb']:>10.3f}")
    print()
    dba = r['ctx_bpb'] - r['both_bpb']
    daa = r['both_acc'] - r['ctx_acc']
    print(f"lift of reservoir over context-alone:  acc {daa:+.3f}   bpb {dba:+.3f}")
    if dba > 0.01:
        print("VERDICT: the hex-CA network ADDS predictive signal beyond context.")
    else:
        print("VERDICT: no lift over context alone — the reservoir isn't earning its keep.")


def selftest():
    """Check the vectorised hex_step matches a scalar reimplementation."""
    S = 16
    rng = np.random.default_rng(7)
    rule = rng.integers(0, 4, size=LUT_SIZE).astype(np.uint8)
    board = rng.integers(0, 4, size=(S, S)).astype(np.uint8)
    em = _even_mask(S)
    vec = hex_step(board[None], rule[None], em)[0]

    def scalar(state, rule):
        out = np.zeros((S, S), np.uint8)
        st = state.astype(int)   # Python ints — avoid uint8 overflow in <<
        for r in range(S):
            even = not (r & 1)
            up, dn = (r - 1) % S, (r + 1) % S
            for c in range(S):
                l = (c - 1) % S; rc = (c + 1) % S
                n_l = st[r, l]; n_r = st[r, rc]
                n_nw = st[up, l] if even else st[up, c]
                n_ne = st[up, c] if even else st[up, rc]
                n_sw = st[dn, l] if even else st[dn, c]
                n_se = st[dn, c] if even else st[dn, rc]
                key = ((st[r, c] << 12) | (n_nw << 10) | (n_ne << 8) | (n_r << 6)
                       | (n_se << 4) | (n_sw << 2) | n_l)
                out[r, c] = rule[key]
        return out
    sc = scalar(board, rule)
    ok = np.array_equal(vec, sc)
    print("hex_step vectorised == scalar:", ok)
    if not ok:
        print("MISMATCH count:", int((vec != sc).sum()))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
