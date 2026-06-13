#!/usr/bin/env python3
"""
atn-ga.py — evolve a population of atn brains that TILE a large corpus.

Each brain (an atn n-gram model) is one expert trained on a contiguous region
of the corpus. A "gene" specifies that region (start chunk, span) plus the
brain's --map-bits. A genetic algorithm searches over WHERE to place each expert
so the population, used together as a mixture-of-experts, compresses held-out
text as well as possible.

Fitness = COVERAGE: a brain's worth is how much it lowers the population's
bits/byte on a held-out global sample (its *marginal* contribution). A brain that
merely duplicates a sibling's territory rarely wins the per-line argmin, so its
marginal value is ~0 and it is selected out — redundancy is punished for free.

The surviving population is a routable network: each held-out line is "owned" by
its best brain (argmin bits/byte); the second-best gives a directed fallback edge
owner->second. At query time only the winning brain(s) need to be loaded from
disk — they "light up".

Everything shells out to the atn binary; the GA bookkeeping is here. Fixed-seed
RNG => fully reproducible runs.

  atn-ga.py run --corpus FILE --out DIR [--pop 32 --gens 15 --span-mb 0.5 ...]
  atn-ga.py lightup --out DIR "a query string"

This is corpus-agnostic: point --corpus at 25MB of news now, or a Wikipedia /
Library-of-Congress dump later. Only the addressed slices are ever read.
"""
import argparse, json, os, random, re, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor
try:
    import numpy as np
except ImportError:
    np = None

# ----------------------------------------------------------------------------
# content addressing: per-chunk MinHash signatures + nearest-neighbor table
# (used by --locus content, so a gene gathers SIMILAR chunks, not contiguous ones)
# ----------------------------------------------------------------------------
NH = 32                                            # MinHash slots per chunk
MASK = (1 << 64) - 1
MULT = [(0x9E3779B97F4A7C15 * (2 * i + 1)) & MASK for i in range(NH)]  # fixed, deterministic
_WORD = re.compile(r"[a-zÀ-ɏ']+")

def _fnv(s):
    h = 1469598103934665603
    for b in s.encode("utf-8", "ignore"):
        h = ((h ^ b) * 1099511628211) & MASK
    return h

def chunk_signature(text):
    # MinHash over the WORD SET (vocabulary overlap), not phrase shingles. This
    # captures topical/language similarity — same-language chunks share function
    # words heavily — whereas 4-word shingles would only catch near-duplicates.
    mins = [MASK] * NH
    seen = set()
    for w in _WORD.findall(text.lower()):
        if w in seen:
            continue
        seen.add(w)
        hw = _fnv(w)
        for h in range(NH):
            v = (hw * MULT[h]) & MASK
            v ^= v >> 29
            if v < mins[h]:
                mins[h] = v
    return mins

def build_neighbors(chunk_texts):
    """Return neigh[i] = chunk ids sorted by MinHash similarity to i (i first)."""
    sigs = np.array([chunk_signature(t) for t in chunk_texts], dtype=np.uint64)
    n = len(sigs)
    neigh = []
    for i in range(n):
        sim = (sigs == sigs[i]).mean(axis=1)        # fraction of matching MinHash slots
        neigh.append(np.argsort(-sim, kind="stable").astype(int).tolist())
    return neigh

# ----------------------------------------------------------------------------
# corpus indexing: split into territory (trainable) + a held-out eval sample
# ----------------------------------------------------------------------------
def build_index(corpus, out, eval_frac, chunk_bytes, seed):
    """Split corpus lines into territory chunks (contiguous, line-aligned) and a
    held-out eval set sampled uniformly across the corpus. Writes:
        out/territory.txt   the trainable text
        out/index.tsv       chunk_id <tab> byte_off <tab> byte_len  (into territory.txt)
        out/eval.txt        held-out lines (never trained on)
        out/eval_pos.tsv    parallel: each eval line's fractional position 0..1
    """
    os.makedirs(out, exist_ok=True)
    terr_path = os.path.join(out, "territory.txt")
    evalp = os.path.join(out, "eval.txt")
    pos_path = os.path.join(out, "eval_pos.tsv")
    stride = max(2, round(1.0 / eval_frac))      # hold out every `stride`-th line

    with open(corpus, "r", errors="ignore") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    n = len(lines)
    terr = open(terr_path, "w"); ev = open(evalp, "w"); pf = open(pos_path, "w")
    chunks = []            # (byte_off, byte_len) into territory.txt
    off = 0; cur_off = 0; cur_len = 0
    for i, ln in enumerate(lines):
        if i % stride == 0:                       # -> held out for eval
            ev.write(ln + "\n"); pf.write(f"{i / n:.6f}\n"); continue
        b = (ln + "\n").encode("utf-8", "ignore")
        terr.write(ln + "\n")
        cur_len += len(b)
        if cur_len >= chunk_bytes:                # close a chunk on a line boundary
            chunks.append((cur_off, cur_len)); cur_off += cur_len; cur_len = 0
    if cur_len:
        chunks.append((cur_off, cur_len))
    terr.close(); ev.close(); pf.close()
    with open(os.path.join(out, "index.tsv"), "w") as ix:
        for cid, (o, l) in enumerate(chunks):
            ix.write(f"{cid}\t{o}\t{l}\n")
    return chunks

def load_index(out):
    chunks = []
    with open(os.path.join(out, "index.tsv")) as f:
        for line in f:
            cid, o, l = line.split("\t")
            chunks.append((int(o), int(l)))
    return chunks

# ----------------------------------------------------------------------------
# genes
# ----------------------------------------------------------------------------
class Gene:
    """A gene's two loci fields are mode-dependent:
       positional: start = first chunk, span = number of contiguous chunks
       content:    start = SEED chunk,  span = how many nearest chunks to gather"""
    __slots__ = ("start", "span", "mapbits")
    def __init__(self, start, span, mapbits):
        self.start, self.span, self.mapbits = start, span, mapbits
    def sig(self):
        return f"{self.start}_{self.span}_{self.mapbits}"
    def to_dict(self):
        return {"start": self.start, "span": self.span, "mapbits": self.mapbits}

def clamp(g, mode, nchunks, span_min, span_max):
    g.span = max(span_min, min(span_max, g.span))
    if mode == "content":
        g.start = max(0, min(nchunks - 1, g.start))     # seed is any chunk
    else:
        g.start = max(0, min(nchunks - g.span, g.start)) # contiguous region must fit
    g.mapbits = max(16, min(26, g.mapbits))
    return g

# ----------------------------------------------------------------------------
# train / score via the atn binary (cached by gene signature)
# ----------------------------------------------------------------------------
class Engine:
    def __init__(self, atn, out, territory, chunks, jobs, mode="positional"):
        self.atn = atn
        self.out = out
        self.terr = territory
        self.chunks = chunks
        self.jobs = jobs
        self.mode = mode
        self.cache_dir = os.path.join(out, "brains")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._fp = open(territory, "rb")
        self.neigh = None
        if mode == "content":
            if np is None:
                raise SystemExit("--locus content needs numpy")
            texts = [self._read(o, l) for (o, l) in chunks]
            self.neigh = build_neighbors([t.decode("utf-8", "ignore") for t in texts])

    def _read(self, off, length):
        self._fp.seek(off); return self._fp.read(length)

    def chunk_ids(self, g):
        if self.mode == "content":                       # seed + its nearest neighbors
            return self.neigh[g.start][:g.span]
        return list(range(g.start, min(g.start + g.span, len(self.chunks))))  # contiguous

    def slice_bytes(self, g):
        parts = []
        for cid in self.chunk_ids(g):
            o, l = self.chunks[cid]; parts.append(self._read(o, l))
        return b"".join(parts)

    def brain_path(self, g):
        pre = "c" if self.mode == "content" else "p"
        return os.path.join(self.cache_dir, pre + g.sig() + ".brain")

    def train(self, g):
        """Train a brain for gene g if not already cached. Returns brain path."""
        bp = self.brain_path(g)
        if os.path.exists(bp):
            return bp
        data = self.slice_bytes(g)
        with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as tf:
            tf.write(data); slice_path = tf.name
        try:
            subprocess.run([self.atn, "--train", slice_path, "--brain", bp,
                            "-q", "--map-bits", str(g.mapbits)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        finally:
            os.unlink(slice_path)
        return bp

    def score(self, g, eval_path):
        """Return list of bits/byte for each eval line under gene g's brain."""
        bp = self.brain_path(g)
        with open(eval_path, "rb") as ef:
            r = subprocess.run([self.atn, "--score", "--brain", bp,
                                "--map-bits", str(g.mapbits)],
                               stdin=ef, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, check=True)
        out = []
        for line in r.stdout.decode("utf-8", "ignore").splitlines():
            try: out.append(float(line.split("\t")[0].strip().split()[0]))
            except (ValueError, IndexError): out.append(99.0)
        return out

    def train_all(self, pop):
        with ThreadPoolExecutor(max_workers=self.jobs) as ex:
            list(ex.map(self.train, pop))

    def score_all(self, pop, eval_path):
        with ThreadPoolExecutor(max_workers=self.jobs) as ex:
            return list(ex.map(lambda g: self.score(g, eval_path), pop))

# ----------------------------------------------------------------------------
# fitness: coverage + marginal contribution
# ----------------------------------------------------------------------------
def evaluate(cols):
    """cols[p][m] = bits/byte of brain p on eval line m.
    Returns (coverage_bpb, marginal[p], owner[m], second[m])."""
    P = len(cols); M = len(cols[0]) if P else 0
    coverage = 0.0
    marginal = [0.0] * P
    owner = [0] * M; second = [0] * M
    for m in range(M):
        best = secondv = 1e18; bi = si = -1
        for p in range(P):
            v = cols[p][m]
            if v < best:
                secondv, si = best, bi
                best, bi = v, p
            elif v < secondv:
                secondv, si = v, p
        coverage += best
        owner[m] = bi; second[m] = si if si >= 0 else bi
        # marginal value of the winner on this line = how much worse we'd do without it
        marginal[bi] += (secondv - best)
    coverage /= max(1, M)
    marginal = [x / max(1, M) for x in marginal]
    return coverage, marginal, owner, second

# ----------------------------------------------------------------------------
# GA operators
# ----------------------------------------------------------------------------
def tournament(pop, fit, rng, k=3):
    best = rng.randrange(len(pop)); bf = fit[best]
    for _ in range(k - 1):
        c = rng.randrange(len(pop))
        if fit[c] > bf: best, bf = c, fit[c]
    return pop[best]

def crossover(a, b, rng):
    # block inheritance: take a whole parent's position, not the average (averaging
    # two good loci can land a child between them — a different region entirely).
    start = a.start if rng.random() < 0.5 else b.start
    span = a.span if rng.random() < 0.5 else b.span
    mapbits = a.mapbits if rng.random() < 0.5 else b.mapbits
    return Gene(start, span, mapbits)

def clone(g):
    return Gene(g.start, g.span, g.mapbits)

def mutate(g, rng, mode, nchunks, span_min, span_max, jitter, neigh=None):
    if mode == "content":
        if rng.random() < 0.6 and neigh:                 # hop to a near neighbor of the seed
            nb = neigh[g.start]
            g.start = nb[rng.randint(1, min(6, len(nb) - 1))] if len(nb) > 1 else g.start
        elif rng.random() < 0.2:
            g.start = rng.randrange(nchunks)             # occasional long jump
    else:
        if rng.random() < 0.7:
            g.start += rng.randint(-jitter, jitter)
    if rng.random() < 0.5:
        g.span = round(g.span * rng.uniform(0.7, 1.4))
    if rng.random() < 0.15:
        g.mapbits += rng.choice([-1, 1])
    return clamp(g, mode, nchunks, span_min, span_max)

# ----------------------------------------------------------------------------
# run
# ----------------------------------------------------------------------------
def cmd_run(a):
    rng = random.Random(a.seed)
    chunk_bytes = int(a.span_mb * 1024 * 1024 / max(1, a.span_chunks))
    print(f"[index] {a.corpus} -> {a.out}  (eval_frac={a.eval_frac}, chunk≈{chunk_bytes}B)")
    chunks = build_index(a.corpus, a.out, a.eval_frac, chunk_bytes, a.seed)
    nchunks = len(chunks)
    eval_path = os.path.join(a.out, "eval.txt")
    M = sum(1 for _ in open(eval_path, errors="ignore"))
    print(f"[index] territory chunks={nchunks}, eval lines={M}")
    span_min, span_max = 1, max(1, nchunks // 3)

    print(f"[index] locus mode = {a.locus}")
    eng = Engine(a.atn, a.out, os.path.join(a.out, "territory.txt"), chunks, a.jobs, mode=a.locus)

    # init: spread P loci (positional start, or content seed) across territory
    pop = []
    for i in range(a.pop):
        start = round(i * nchunks / a.pop)
        g = Gene(start + rng.randint(-1, 1), a.span_chunks, a.mapbits)
        pop.append(clamp(g, a.locus, nchunks, span_min, span_max))

    hist = open(os.path.join(a.out, "history.tsv"), "w")
    hist.write("gen\tcoverage_bpb\tbest_marginal\tn_owners\n")
    best_state = None; best_cov = 1e18
    for gen in range(1, a.gens + 1):
        eng.train_all(pop)
        cols = eng.score_all(pop, eval_path)
        coverage, marginal, owner, second = evaluate(cols)
        n_owners = len(set(owner))
        hist.write(f"{gen}\t{coverage:.4f}\t{max(marginal):.4f}\t{n_owners}\n"); hist.flush()
        flag = ""
        if coverage < best_cov:                       # keep the best tiling ever seen
            best_cov = coverage
            best_state = ([clone(g) for g in pop], list(marginal), list(owner), list(second), coverage)
            flag = "  <- best"
        print(f"[gen {gen:2d}] coverage={coverage:.4f} bpb   "
              f"active_experts={n_owners}/{a.pop}   best_marginal={max(marginal):.4f}{flag}")

        if gen == a.gens:
            break
        # STEADY-STATE: keep the useful experts, replace only the worst `replace_frac`
        # (the redundant ~0-marginal ones) with children of the survivors. Replaced
        # experts owned almost nothing, so coverage can't spike up — it ratchets down.
        order = sorted(range(len(pop)), key=lambda p: marginal[p])   # worst first
        n_rep = max(1, round(len(pop) * a.replace_frac))
        survivors = [pop[i] for i in order[n_rep:]]
        nxt = [clone(g) for g in survivors]
        while len(nxt) < a.pop:
            if rng.random() < 0.5:
                child = crossover(rng.choice(survivors), rng.choice(survivors), rng)
            else:
                child = clone(rng.choice(survivors))               # local search on a survivor
            nxt.append(mutate(child, rng, a.locus, nchunks, span_min, span_max, a.jitter, eng.neigh))
        pop = nxt

    print(f"[best] coverage={best_cov:.4f} bpb (finalizing this population)")
    finalize(a, eng, *best_state)
    hist.close()
    print(f"[done] population + graph written under {a.out}/")

def finalize(a, eng, pop, marginal, owner, second, coverage):
    """Write the surviving population, tiling map, and routing graph."""
    pos = [float(x) for x in open(os.path.join(a.out, "eval_pos.tsv"), errors="ignore")]
    # surviving experts = those that own >=1 eval line
    from collections import defaultdict, Counter
    owned = defaultdict(list)
    for m, p in enumerate(owner):
        owned[p].append(pos[m])
    genes = []
    tiling = open(os.path.join(a.out, "tiling.tsv"), "w")
    tiling.write("expert\tgene_start\tgene_span\tmapbits\tn_owned\tpos_centroid\tpos_lo\tpos_hi\tbrain\n")
    for p, g in enumerate(pop):
        positions = owned.get(p, [])
        rec = g.to_dict(); rec["expert"] = p; rec["n_owned"] = len(positions)
        rec["brain"] = os.path.relpath(eng.brain_path(g), a.out)
        rec["marginal"] = round(marginal[p], 5)
        genes.append(rec)
        if positions:
            c = sum(positions) / len(positions)
            tiling.write(f"{p}\t{g.start}\t{g.span}\t{g.mapbits}\t{len(positions)}\t"
                         f"{c:.4f}\t{min(positions):.4f}\t{max(positions):.4f}\t{rec['brain']}\n")
    tiling.close()
    json.dump({"coverage_bpb": coverage, "genes": genes},
              open(os.path.join(a.out, "genes.json"), "w"), indent=2)
    # routing graph: aggregate owner->second fallback edges over eval lines
    edges = Counter()
    for m in range(len(owner)):
        if owner[m] != second[m]:
            edges[(owner[m], second[m])] += 1
    with open(os.path.join(a.out, "graph.tsv"), "w") as gt:
        gt.write("from_expert\tto_expert\tweight\n")
        for (u, v), w in edges.most_common():
            gt.write(f"{u}\t{v}\t{w}\n")
    with open(os.path.join(a.out, "graph.dot"), "w") as dot:
        dot.write("digraph atn_ga {\n  rankdir=LR; node [shape=circle];\n")
        for (u, v), w in edges.most_common(60):
            dot.write(f'  {u} -> {v} [label="{w}"];\n')
        dot.write("}\n")

# ----------------------------------------------------------------------------
# lightup: route a query against the surviving population
# ----------------------------------------------------------------------------
def cmd_lightup(a):
    meta = json.load(open(os.path.join(a.out, "genes.json")))
    survivors = [g for g in meta["genes"] if g["n_owned"] > 0]
    scored = []
    for g in survivors:
        bp = os.path.join(a.out, g["brain"])
        r = subprocess.run([a.atn, "--score", "--brain", bp, "--map-bits", str(g["mapbits"])],
                           input=(a.query + "\n").encode(), stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL)
        try: bpb = float(r.stdout.decode().split("\t")[0].strip().split()[0])
        except Exception: bpb = 99.0
        scored.append((bpb, g))
    scored.sort(key=lambda x: x[0])
    if not scored:
        print("no surviving experts in", a.out); return
    edges = {}
    gp = os.path.join(a.out, "graph.tsv")
    if os.path.exists(gp):
        for line in open(gp).readlines()[1:]:
            u, v, w = line.split("\t"); edges.setdefault(int(u), []).append((int(v), int(w)))
    nchunks = len(open(os.path.join(a.out, "index.tsv")).read().splitlines()) or 1
    print(f'query: "{a.query}"\n')
    print(f"{'rank':<5}{'expert':<8}{'bpb':<8}{'locus':<8}territory")
    for i, (bpb, g) in enumerate(scored[:8]):
        pos = g["start"] / nchunks
        print(f"{i+1:<5}{g['expert']:<8}{bpb:<8.3f}{pos:<8.3f}chunks[{g['start']}:+{g['span']}]")
    win = scored[0][1]["expert"]
    print(f"\nlit up: expert {win}  (lowest surprisal)")
    nbrs = sorted(edges.get(win, []), key=lambda x: -x[1])[:5]
    if nbrs:
        print("fallback neighbors (graph):", ", ".join(f"{v}(w={w})" for v, w in nbrs))

# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="evolve atn brains that tile a corpus")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="index a corpus and evolve a population")
    r.add_argument("--corpus", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--atn", default="./atn")
    r.add_argument("--pop", type=int, default=32)
    r.add_argument("--gens", type=int, default=15)
    r.add_argument("--span-mb", type=float, default=0.5, help="target training bytes per brain (MB)")
    r.add_argument("--span-chunks", type=int, default=8, help="initial span in chunks")
    r.add_argument("--locus", choices=["positional", "content"], default="positional",
                   help="positional: contiguous region; content: gather MinHash-similar chunks")
    r.add_argument("--eval-frac", type=float, default=0.05)
    r.add_argument("--elite", type=int, default=4)
    r.add_argument("--jitter", type=int, default=3)
    r.add_argument("--replace-frac", type=float, default=0.3)
    r.add_argument("--mapbits", type=int, default=22)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    r.set_defaults(func=cmd_run)

    l = sub.add_parser("lightup", help="route a query against the evolved population")
    l.add_argument("--out", required=True)
    l.add_argument("--atn", default="./atn")
    l.add_argument("query")
    l.set_defaults(func=cmd_lightup)

    a = ap.parse_args()
    a.func(a)

if __name__ == "__main__":
    main()
