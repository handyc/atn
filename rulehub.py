#!/usr/bin/env python3
# rulehub.py — "BitTorrent for class-4 CA rulesets": a FEDERATED rule-DISCOVERY
# swarm. Each node owns a SHARD of fractal-space (family x region x seed),
# discovers class-4 rules there, and publishes each as a CONTENT-ADDRESSED piece
# (sha256 of the LUT = the piece id, so peers dedup automatically) plus rich
# metadata. The union of all shards = a distributed, queryable rule library; the
# index is the "tracker"; `query` is pull-by-criteria.
#
# Modes:
#   node  --spec inputs/task_NNNN.json --out OUT   # one swarm node (a shard)
#   index OUT                                       # merge+dedup all shards
#   query OUT [--dim 3] [--family julia] [--min-c4 0.7] [--glider] ...
#
# Self-contained: numpy + hashlib only (runs on ALICE with just SciPy-bundle).
import argparse, json, os, sys, glob, hashlib, collections
import numpy as np

LUT7 = 1 << 14

# ---------- fractal generators -> 4^7 LUT ----------
def _esc(zx, zy, cx, cy, kind, it):
    e = np.full(zx.shape, it, np.int32); al = np.ones(zx.shape, bool)
    with np.errstate(over="ignore", invalid="ignore"):
        for i in range(it):
            if kind == "burning": zx = np.abs(zx); zy = np.abs(zy)
            zx2 = zx * zx - zy * zy + cx; zy = 2 * zx * zy + cy; zx = zx2
            m = (zx * zx + zy * zy) >= 4.0; nw = m & al
            e[nw] = i; al &= ~m; zx[~al] = 0; zy[~al] = 0
    return e

def _newton(zx, zy, it):
    e = np.full(zx.shape, it, np.int32); done = np.zeros(zx.shape, bool)
    with np.errstate(all="ignore"):
        for i in range(it):
            d2x = zx * zx - zy * zy; d2y = 2 * zx * zy
            z3x = zx * d2x - zy * d2y; z3y = zx * d2y + zy * d2x
            nx = z3x - 1.0; ny = z3y; dx = 3 * d2x; dy = 3 * d2y
            dd = dx * dx + dy * dy + 1e-12
            qx = (nx * dx + ny * dy) / dd; qy = (ny * dx - nx * dy) / dd
            nzx = zx - qx; nzy = zy - qy
            conv = ((nzx - zx) ** 2 + (nzy - zy) ** 2) < 1e-6
            e[conv & ~done] = i; done |= conv; zx, zy = nzx, nzy; zx[done] = 0; zy[done] = 0
    return e

def _posterise(e, it):
    f = e.ravel(); fin = f[f < it]; lut = np.ones(f.size, np.uint8)
    if fin.size < 3: b1, b2 = it // 3, 2 * it // 3
    else:
        b1 = np.quantile(fin, 1 / 3); b2 = np.quantile(fin, 2 / 3)
        if b2 <= b1: b2 = b1 + 1
    lut[f < b1] = 0; lut[(f >= b1) & (f < b2)] = 2; lut[f >= it] = 3
    return lut

JULIA_C = [(-0.4, 0.6), (0.285, 0.01), (-0.70176, -0.3842), (-0.8, 0.156),
           (-0.835, -0.2321), (0.45, 0.1428), (-0.7269, 0.1889)]
WINDOWS = {"mandelbrot": [(-0.5, 0, 3.0), (-0.745, 0.113, 0.05), (0.272, 0.005, 0.01)],
           "burning": [(-0.5, -0.5, 3.0), (-1.75, -0.03, 0.2)],
           "julia": [(0, 0, 3.2)], "newton": [(0, 0, 3.0), (0, 0, 0.6)]}

def gen_lut(fam, rng, it=200, side=128):
    win = WINDOWS[fam]; cx, cy, span = win[rng.integers(0, len(win))]
    cx += (rng.random() * 2 - 1) * 0.3 * span; cy += (rng.random() * 2 - 1) * 0.3 * span
    sp = span * (0.4 + 0.8 * rng.random())
    st = sp / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    if fam == "julia":
        c = JULIA_C[rng.integers(0, len(JULIA_C))]
        e = _esc(gx, gy, np.full_like(gx, c[0]), np.full_like(gy, c[1]), "mandel", it)
    elif fam == "newton": e = _newton(gx, gy, it)
    else: e = _esc(np.zeros_like(gx), np.zeros_like(gy), gx, gy,
                   "burning" if fam == "burning" else "mandel", it)
    return _posterise(e, it), (cx, cy, sp)

# ---------- 2D hex step + classify ----------
# The 6 hex neighbours of every cell are a FIXED toroidal permutation, so precompute the gather indices
# once per board size and cache them: each step is then 6 flat gathers instead of 8 np.roll + 4 np.where on
# int64.  Bit-exact with the old roll/where version for the int64 boards every caller feeds in (verified in
# bench_hexkey.py); ~2.6-3.3x faster, and it gates EVERY sim (gates, CPU, clock, the ALICE wide-word runs).
_NIDX = {}
def _nidx(H, W):
    k = (H, W)
    hit = _NIDX.get(k)
    if hit is not None: return hit
    R, C = np.meshgrid(np.arange(H), np.arange(W), indexing="ij")
    even = (R % 2 == 0)
    def flat(rr, cc): return ((rr % H) * W + (cc % W)).ravel().astype(np.intp)
    idx = (flat(R-1, np.where(even, C-1, C)),          # nw
           flat(R-1, np.where(even, C,   C+1)),        # ne
           flat(R,   C+1),                             # rg (east)
           flat(R+1, np.where(even, C,   C+1)),        # se
           flat(R+1, np.where(even, C-1, C)),          # sw
           flat(R,   C-1))                             # l  (west)
    _NIDX[k] = idx; return idx

def hex_key(b):
    H, W = b.shape
    nw, ne, rg, se, sw, l = _nidx(H, W)
    bf = b.reshape(-1).astype(np.uint16)               # 2-bit states packed into a 14-bit key (overflow-safe)
    key = ((bf << 12) | (bf[nw] << 10) | (bf[ne] << 8) | (bf[rg] << 6)
           | (bf[se] << 4) | (bf[sw] << 2) | bf[l])
    return key.reshape(H, W)
def cls_of(act):
    return 1 if act < 0.02 else 2 if act < 0.08 else 3 if act > 0.55 else 4
def classify_hex(rule, side=80, ticks=14, seed=0):
    rng = np.random.default_rng(seed); b = rng.integers(0, 4, (side, side)).astype(np.int64)
    half = ticks // 2; tail = 0; cells = side * side
    for t in range(ticks):
        nb = rule[hex_key(b)].astype(np.int64)
        if t >= half: tail += int((nb != b).sum())
        b = nb
    return cls_of(tail / ((ticks - half) * cells))

# ---------- 3D von Neumann classify (same 4^7 LUT) ----------
def step3d(b, rule):
    key = (b << 12); slot = 5
    for ax in range(3):
        for d in (1, -1): key = key | (np.roll(b, d, axis=ax) << (2 * slot)); slot -= 1
    return rule[key]
def classify_3d(rule, side=16, ticks=12, seed=0):
    rng = np.random.default_rng(seed); b = rng.integers(0, 4, (side,) * 3).astype(np.int64)
    half = ticks // 2; tail = 0; cells = side ** 3
    for t in range(ticks):
        nb = step3d(b, rule).astype(np.int64)
        if t >= half: tail += int((nb != b).sum())
        b = nb
    return cls_of(tail / ((ticks - half) * cells))

# ---------- glider detector ----------
def glider_disp(rule, side=64, ticks=30, seed=0):
    if rule[0] != 0: return 0.0
    rng = np.random.default_rng(seed); b = np.zeros((side, side), np.uint8); c = side // 2
    b[c - 2:c + 3, c - 2:c + 3] = rng.integers(1, 4, (5, 5)); coms = []; acts = []
    for _ in range(ticks):
        b = rule[hex_key(b.astype(np.int64))].astype(np.uint8)
        nz = np.flatnonzero(b)
        if nz.size == 0: return 0.0
        acts.append(nz.size); ys, xs = np.divmod(nz, side); coms.append((ys.mean(), xs.mean()))
    acts = np.array(acts)
    if acts.max() > side * side * 0.12 or acts.mean() > 300: return 0.0
    coms = np.array(coms); return float(np.hypot(*(coms[-1] - coms[0])))

# ---------- hex symmetry (C6/D6) ----------
_SH = [6, 8, 10, 0, 2, 4]
_CANON = {}
def canon(reflect):
    if reflect in _CANON: return _CANON[reflect]
    c = np.arange(LUT7, dtype=np.int64); seen = np.zeros(LUT7, bool)
    def mk(s, v):
        k = s << 12
        for sh, vv in zip(_SH, v): k |= vv << sh
        return k
    for kk in range(LUT7):
        if seen[kk]: continue
        s = (kk >> 12) & 3; base = [(kk >> sh) & 3 for sh in _SH]; orb = set()
        for v0 in ([base, base[::-1]] if reflect else [base]):
            v = list(v0)
            for _ in range(6): orb.add(mk(s, v)); v = [v[-1]] + v[:-1]
        cc = min(orb)
        for k in orb: c[k] = cc; seen[k] = True
    _CANON[reflect] = c; return c

# ---------- swarm node ----------
def cmd_node(a):
    spec = json.load(open(a.spec))
    rng = np.random.default_rng(spec["seed"])
    fams = spec["families"]; n = spec["n_candidates"]
    blobs = os.path.join(a.out, "blobs"); os.makedirs(blobs, exist_ok=True)
    c6 = canon(False); d6 = canon(True)
    rows = []; seen_hash = set(); kept = 0
    for i in range(n):
        fam = fams[i % len(fams)]
        lut, (cx, cy, sp) = gen_lut(fam, rng)
        if classify_hex(lut, ticks=12, seed=spec["seed"] + i) != 4:
            continue
        h = hashlib.sha256(lut.tobytes()).hexdigest()[:16]   # content address (piece id)
        if h in seen_hash: continue                          # local dedup
        seen_hash.add(h)
        act_seed = spec["seed"] + i
        # rich metadata (only on class-4 hits)
        c3 = classify_3d(lut, seed=act_seed)
        gd = glider_disp(lut, seed=act_seed)
        sc6 = classify_hex(lut[c6].astype(np.uint8), ticks=12, seed=act_seed)
        sd6 = classify_hex(lut[d6].astype(np.uint8), ticks=12, seed=act_seed)
        # c4 quality from a fresh activity probe
        rng2 = np.random.default_rng(act_seed + 7); bb = rng2.integers(0, 4, (60, 60)).astype(np.int64)
        tail = 0
        for t in range(12):
            nb = lut[hex_key(bb)].astype(np.int64)
            if t >= 6: tail += int((nb != bb).sum())
            bb = nb
        act = tail / (6 * 3600); c4 = max(0.0, 1.0 - 4.0 * abs(act - 0.32))
        lut.tofile(os.path.join(blobs, h + ".lut"))           # content-addressed blob
        rows.append({"hash": h, "family": fam, "c4": round(c4, 3), "act": round(act, 3),
                     "class3d": c3, "glider": int(gd > 3.0), "disp": round(gd, 1),
                     "symC6": sc6, "symD6": sd6, "cx": round(cx, 6), "cy": round(cy, 6),
                     "span": round(sp, 6), "shard": spec.get("shard", a.spec)})
        kept += 1
    open(os.path.join(a.out, f"manifest_{spec.get('shard','x'):0>4}.jsonl"), "w").write(
        "\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))
    print(f"node {spec.get('shard')}: scanned {n}, published {kept} unique class-4 pieces")

# ---------- index (tracker): merge + dedup across the swarm ----------
def load_manifest(outdir):
    recs = {}
    for f in glob.glob(os.path.join(outdir, "manifest_*.jsonl")):
        for ln in open(f):
            ln = ln.strip()
            if ln:
                r = json.loads(ln); recs[r["hash"]] = r       # dedup by content hash
    return recs

def cmd_index(a):
    recs = load_manifest(a.out)
    json.dump(list(recs.values()), open(os.path.join(a.out, "library.json"), "w"))
    fam = collections.Counter(r["family"] for r in recs.values())
    print(f"=== distributed rule library: {len(recs)} UNIQUE class-4 pieces ===")
    print("by family:", dict(fam))
    g = sum(r["glider"] for r in recs.values())
    s3 = sum(r["class3d"] == 4 for r in recs.values())
    c6 = sum(r["symC6"] == 4 for r in recs.values()); d6 = sum(r["symD6"] == 4 for r in recs.values())
    nn = max(1, len(recs))
    print(f"gliders: {g} ({100*g/nn:.0f}%) | survive 3D class-4: {s3} ({100*s3/nn:.0f}%) | "
          f"C6-stable: {100*c6/nn:.0f}% | D6-stable: {100*d6/nn:.0f}%")
    print(f"saved index -> {a.out}/library.json ; blobs in {a.out}/blobs/<hash>.lut")

# ---------- query (pull-by-criteria) ----------
def cmd_query(a):
    lib = os.path.join(a.out, "library.json")
    recs = json.load(open(lib)) if os.path.exists(lib) else list(load_manifest(a.out).values())
    out = recs
    if a.family: out = [r for r in out if r["family"] == a.family]
    if a.dim == 3: out = [r for r in out if r["class3d"] == 4]
    if a.min_c4 is not None: out = [r for r in out if r["c4"] >= a.min_c4]
    if a.glider: out = [r for r in out if r["glider"]]
    if a.sym: out = [r for r in out if r["sym" + a.sym] == 4]
    out.sort(key=lambda r: r["c4"], reverse=True)
    print(f"query matched {len(out)} of {len(recs)} pieces"
          + (f" (family={a.family})" if a.family else "")
          + (" dim=3-class4" if a.dim == 3 else "")
          + (f" c4>={a.min_c4}" if a.min_c4 is not None else "")
          + (" glider" if a.glider else "") + (f" sym{a.sym}" if a.sym else ""))
    for r in out[:a.n]:
        print(f"  {r['hash']}  {r['family']:<10} c4={r['c4']:.2f} 3d={r['class3d']} "
              f"glider={r['glider']}(d{r['disp']}) C6={r['symC6']} D6={r['symD6']}")
    print(f"(pull a piece: {a.out}/blobs/<hash>.lut)")

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd")
    n = sub.add_parser("node"); n.add_argument("--spec", required=True); n.add_argument("--out", default="hub")
    ix = sub.add_parser("index"); ix.add_argument("out")
    q = sub.add_parser("query"); q.add_argument("out")
    q.add_argument("--dim", type=int, default=0); q.add_argument("--family")
    q.add_argument("--min-c4", type=float, default=None); q.add_argument("--glider", action="store_true")
    q.add_argument("--sym", choices=["C6", "D6"]); q.add_argument("-n", type=int, default=15)
    a = ap.parse_args()
    {"node": cmd_node, "index": cmd_index, "query": cmd_query}.get(a.cmd, lambda _a: ap.print_help())(a)

if __name__ == "__main__":
    main()
