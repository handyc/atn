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
import argparse, json, os, random, re, subprocess, tempfile, zlib
from concurrent.futures import ThreadPoolExecutor
try:
    import numpy as np
except ImportError:
    np = None

# ----------------------------------------------------------------------------
# content addressing: per-chunk MinHash signatures, with an LSH index so a gene
# can gather topically-SIMILAR chunks (not contiguous ones) even when there are
# tens of thousands of document-granularity chunks (brute-force O(n^2) would die).
# ----------------------------------------------------------------------------
SIG_BITS = 128                                     # SimHash signature width (bits)
_WORD = re.compile(r"[a-zà-ÿ0-9']+")

def _word_bits(words):
    """Deterministic SimHash hyperplane signs for each word: a {-1,+1}^SIG_BITS row
    from the word's hash (two crc32s give 64 bits; tiled to SIG_BITS)."""
    h = np.empty((len(words), (SIG_BITS + 63) // 64), dtype=np.uint64)
    for j in range(h.shape[1]):
        salt = bytes([j])
        h[:, j] = np.fromiter((zlib.crc32(salt + w) | (zlib.crc32(salt + b"\x01" + w) << 32)
                               for w in words), dtype=np.uint64, count=len(words))
    bitpos = np.arange(SIG_BITS, dtype=np.uint64)
    word64 = h[:, bitpos // 64]                    # pick the 64-bit word holding each bit
    bit = (word64 >> (bitpos % np.uint64(64))) & np.uint64(1)
    return bit.astype(np.int8) * 2 - 1             # [nwords, SIG_BITS] in {-1,+1}

def _df_stats(chunk_texts):
    from collections import Counter
    toks, df = [], Counter()
    for t in chunk_texts:
        c = Counter(_WORD.findall(t.lower())); toks.append(c); df.update(c.keys())
    return toks, df

def _sig_minhash(chunk_texts, df_max, min_df):
    """MinHash over the df-filtered word SET (estimates Jaccard of vocabularies)."""
    NH = 32
    mult = np.array([(0x9E3779B97F4A7C15 * (2 * i + 1)) & ((1 << 64) - 1) for i in range(NH)],
                    dtype=np.uint64)
    toks, df = _df_stats(chunk_texts)
    n = len(chunk_texts); hi = df_max * n if df_max < 1 else n + 1
    sigs = np.full((n, NH), (1 << 64) - 1, dtype=np.uint64)
    for i, c in enumerate(toks):
        kept = [w for w in c if min_df <= df[w] <= hi]
        if len(kept) < 4:
            continue
        hs = np.fromiter((zlib.crc32(w.encode("utf-8")) for w in kept), dtype=np.uint64, count=len(kept))
        m = hs[:, None] * mult[None, :]
        m ^= m >> np.uint64(29)
        sigs[i] = m.min(axis=0)
    return sigs

def _sig_simhash(chunk_texts, df_max, min_df):
    """TF-IDF-weighted SimHash (SIG_BITS bits): rare topical words dominate the
    signature; bit-agreement ≈ cosine of the TF-IDF vectors. Topic is carried by
    the rare-word tail, so weighting by IDF should beat unweighted Jaccard."""
    import math
    toks, df = _df_stats(chunk_texts)
    n = len(chunk_texts); hi = df_max * n if df_max < 1 else n + 1
    vocab = [w for w in df if min_df <= df[w] <= hi]
    vidx = {w: i for i, w in enumerate(vocab)}
    sigs = np.zeros((n, SIG_BITS), dtype=np.uint8)
    if not vocab:
        return sigs
    idf = np.array([math.log(n / df[w]) for w in vocab])
    signs = _word_bits([w.encode("utf-8") for w in vocab])   # [V, SIG_BITS] in {-1,+1}
    for i, c in enumerate(toks):
        idxs, wts = [], []
        for w, cnt in c.items():
            j = vidx.get(w)
            if j is not None:
                idxs.append(j); wts.append((1.0 + math.log(cnt)) * idf[j])
        if idxs:
            v = (signs[idxs] * np.array(wts)[:, None]).sum(axis=0)
            sigs[i] = (v > 0).astype(np.uint8)
    return sigs

def build_signatures(chunk_texts, df_max=0.5, min_df=2, sig="minhash"):
    """Per-chunk content signature. `sig`: 'simhash' (TF-IDF weighted, cosine) or
    'minhash' (word-set Jaccard). Both band for LSH the same way (per-slot equality)."""
    return (_sig_simhash if sig == "simhash" else _sig_minhash)(chunk_texts, df_max, min_df)

class LSHIndex:
    """Banded MinHash LSH. neighbors(i) returns chunks sharing a band-bucket with
    chunk i, ranked by full-signature similarity — O(bucket) per query, not O(n)."""
    def __init__(self, sigs, bands=16, cap=400):
        self.sigs = sigs; self.n = len(sigs); self.cap = cap
        self.B = bands; self.R = max(1, sigs.shape[1] // bands)
        self.buckets = [dict() for _ in range(self.B)]
        for i in range(self.n):
            for b in range(self.B):
                key = self._key(i, b)
                self.buckets[b].setdefault(key, []).append(i)
        self._cache = {}

    def _key(self, i, b):
        return zlib.crc32(self.sigs[i, b * self.R:(b + 1) * self.R].tobytes())

    def neighbors(self, i):
        r = self._cache.get(i)
        if r is not None:
            return r
        cand = set()
        for b in range(self.B):
            cand.update(self.buckets[b].get(self._key(i, b), ()))
        cand.discard(i); cand = list(cand)
        if cand:
            sim = (self.sigs[cand] == self.sigs[i]).mean(axis=1)
            order = np.argsort(-sim, kind="stable")[:self.cap]
            res = [i] + [cand[j] for j in order]
        else:
            res = [i]
        self._cache[i] = res
        return res

class ExactNeighbors:
    """Brute-force exact neighbor ranking — for small chunk counts where O(n^2) is
    fine and we want exact (not approximate) results."""
    def __init__(self, sigs):
        self.sigs = sigs; self.n = len(sigs); self._cache = {}
    def neighbors(self, i):
        r = self._cache.get(i)
        if r is None:
            sim = (self.sigs == self.sigs[i]).mean(axis=1)
            r = np.argsort(-sim, kind="stable").astype(int).tolist()
            self._cache[i] = r
        return r

# ----------------------------------------------------------------------------
# corpus indexing: split into territory (trainable) + a held-out eval sample
# ----------------------------------------------------------------------------
def build_index(corpus, out, eval_frac, chunk_bytes, seed, chunk_on=None):
    """Split corpus lines into territory chunks (contiguous, line-aligned) and a
    held-out eval set sampled uniformly across the corpus. Writes:
        out/territory.txt   the trainable text
        out/index.tsv       chunk_id <tab> byte_off <tab> byte_len  (into territory.txt)
        out/eval.txt        held-out lines (never trained on)
        out/eval_pos.tsv    parallel: each eval line's fractional position 0..1
    If chunk_on (a compiled regex) is given, a new chunk also starts whenever a
    line matches it — document-aware chunking, so each chunk is one coherent unit
    (e.g. one Wikipedia article) instead of a fixed byte window.
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
    cur_off = 0; cur_len = 0
    for i, ln in enumerate(lines):
        if i % stride == 0:                       # -> held out for eval
            ev.write(ln + "\n"); pf.write(f"{i / n:.6f}\n"); continue
        if chunk_on is not None and cur_len and chunk_on.search(ln):
            chunks.append((cur_off, cur_len)); cur_off += cur_len; cur_len = 0  # document boundary
        b = (ln + "\n").encode("utf-8", "ignore")
        terr.write(ln + "\n")
        cur_len += len(b)
        if cur_len >= chunk_bytes:                # byte cap (also splits huge documents)
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
    """A gene's loci fields are mode-dependent:
       positional: start = first chunk, span = number of contiguous chunks
       content:    start = SEED chunk,  span = how many nearest chunks to gather
    `orders` is the model's n-gram context orders (the atn --orders gene) — the
    one model-internal the GA can now evolve, tuple of 1..6 ints each in 1..7."""
    __slots__ = ("start", "span", "mapbits", "orders")
    def __init__(self, start, span, mapbits, orders=(2, 4, 7)):
        self.start, self.span, self.mapbits, self.orders = start, span, mapbits, tuple(orders)
    def orders_csv(self):
        return ",".join(map(str, self.orders))
    def sig(self):
        return f"{self.start}_{self.span}_{self.mapbits}_{'-'.join(map(str, self.orders))}"
    def to_dict(self):
        return {"start": self.start, "span": self.span, "mapbits": self.mapbits,
                "orders": list(self.orders)}

def _orders_csv(gd):
    """orders CSV from a gene dict (backward-compatible with pre-orders runs)."""
    return ",".join(map(str, gd.get("orders", [2, 4, 7])))

def clamp(g, mode, nchunks, span_min, span_max):
    g.span = max(span_min, min(span_max, g.span))
    if mode == "content":
        g.start = max(0, min(nchunks - 1, g.start))     # seed is any chunk
    else:
        g.start = max(0, min(nchunks - g.span, g.start)) # contiguous region must fit
    g.mapbits = max(16, min(26, g.mapbits))
    o = sorted({v for v in g.orders if 1 <= v <= 7})[:6] # valid, sorted, deduped, ≤6
    g.orders = tuple(o) if o else (2, 4, 7)
    return g

# ----------------------------------------------------------------------------
# train / score via the atn binary (cached by gene signature)
# ----------------------------------------------------------------------------
class Engine:
    def __init__(self, atn, out, territory, chunks, jobs, mode="positional", df_max=0.5, sig="minhash"):
        self.atn = atn
        self.out = out
        self.terr = territory
        self.chunks = chunks
        self.jobs = jobs
        self.mode = mode
        self.df_max = df_max
        self.sig = sig
        self.cache_dir = os.path.join(out, "brains")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._fp = open(territory, "rb")
        self.nn = None                                   # neighbor provider (content mode)
        if mode == "content":
            if np is None:
                raise SystemExit("--locus content needs numpy")
            texts = [self._read(o, l).decode("utf-8", "ignore") for (o, l) in chunks]
            sigs = build_signatures(texts, df_max=df_max, sig=sig)
            exact = len(chunks) <= 2500                  # exact for small, LSH at scale
            self.nn = ExactNeighbors(sigs) if exact else LSHIndex(sigs, bands=16)
            print(f"[index] content index: {sig} signature, "
                  f"{'exact O(n^2)' if exact else 'LSH (16 bands)'} over {len(chunks)} chunks")

    def _read(self, off, length):
        self._fp.seek(off); return self._fp.read(length)

    def neighbors(self, seed):
        return self.nn.neighbors(seed)

    def chunk_ids(self, g):
        if self.mode == "content":                       # seed + its nearest neighbors
            return self.nn.neighbors(g.start)[:g.span]
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
            subprocess.run([self.atn, "--train", slice_path, "--brain", bp, "-q",
                            "--map-bits", str(g.mapbits), "--orders", g.orders_csv()],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        finally:
            os.unlink(slice_path)
        return bp

    def score(self, g, eval_path):
        """Return list of bits/byte for each eval line under gene g's brain."""
        bp = self.brain_path(g)
        with open(eval_path, "rb") as ef:
            r = subprocess.run([self.atn, "--score", "--brain", bp,
                                "--map-bits", str(g.mapbits), "--orders", g.orders_csv()],
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
    orders = a.orders if rng.random() < 0.5 else b.orders
    return Gene(start, span, mapbits, orders)

def clone(g):
    return Gene(g.start, g.span, g.mapbits, g.orders)

def mutate_orders(orders, rng):
    """Add, drop, or shift one context order (each 1..7, up to 6, kept sorted)."""
    o = set(orders)
    r = rng.random()
    if r < 0.4 and len(o) < 6:                            # add an order
        o.add(rng.randint(1, 7))
    elif r < 0.7 and len(o) > 1:                          # drop an order
        o.discard(rng.choice(sorted(o)))
    else:                                                 # shift one order by ±1
        v = rng.choice(sorted(o)); o.discard(v)
        o.add(min(7, max(1, v + rng.choice([-1, 1]))))
    return tuple(sorted(o)) or (2, 4, 7)

def mutate(g, rng, mode, nchunks, span_min, span_max, jitter, eng=None, evolve_orders=False):
    if mode == "content":
        if rng.random() < 0.6 and eng:                   # hop to a near neighbor of the seed
            nb = eng.neighbors(g.start)
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
    if evolve_orders and rng.random() < 0.4:             # evolve the n-gram orders gene
        g.orders = mutate_orders(g.orders, rng)
    return clamp(g, mode, nchunks, span_min, span_max)

# ----------------------------------------------------------------------------
# run
# ----------------------------------------------------------------------------
def cmd_run(a):
    rng = random.Random(a.seed)
    # chunk size: explicit --chunk-kb, else a generous cap when splitting on document
    # boundaries (--chunk-on), else derived from the per-brain budget / initial span.
    chunk_on = re.compile(a.chunk_on) if a.chunk_on else None
    if a.chunk_kb:
        chunk_bytes = int(a.chunk_kb * 1024)
    elif chunk_on is not None:
        chunk_bytes = 65536                          # cap; the regex is the real splitter
    else:
        chunk_bytes = int(a.span_mb * 1024 * 1024 / max(1, a.span_chunks))
    print(f"[index] {a.corpus} -> {a.out}  (eval_frac={a.eval_frac}, chunk≈{chunk_bytes}B"
          f"{', doc-split on /' + a.chunk_on + '/' if chunk_on is not None else ''})")
    chunks = build_index(a.corpus, a.out, a.eval_frac, chunk_bytes, a.seed, chunk_on)
    nchunks = len(chunks)
    eval_path = os.path.join(a.out, "eval.txt")
    M = sum(1 for _ in open(eval_path, errors="ignore"))
    # initial span = chunks needed to hit the per-brain byte budget (works for any
    # chunk size, fixed or variable document-sized)
    avg = max(1, sum(l for _, l in chunks) // nchunks)
    init_span = max(1, round(a.span_mb * 1024 * 1024 / avg))
    print(f"[index] territory chunks={nchunks} (avg {avg}B), eval lines={M}")
    span_min, span_max = 1, max(1, nchunks // 2)

    init_orders = tuple(int(x) for x in a.orders.replace(",", " ").split())
    print(f"[index] locus mode = {a.locus}, init span = {init_span} chunks, "
          f"orders = {init_orders}{' (evolving)' if a.evolve_orders else ''}")
    eng = Engine(a.atn, a.out, os.path.join(a.out, "territory.txt"), chunks, a.jobs,
                 mode=a.locus, df_max=a.df_max, sig=a.sig)

    # init: spread P loci (positional start, or content seed) across territory
    pop = []
    for i in range(a.pop):
        start = round(i * nchunks / a.pop)
        g = Gene(start + rng.randint(-1, 1), init_span, a.mapbits, init_orders)
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
            nxt.append(mutate(child, rng, a.locus, nchunks, span_min, span_max, a.jitter,
                              eng, a.evolve_orders))
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
# mixture: soft combination of experts via an online fixed-share predictor
# ----------------------------------------------------------------------------
def _perbyte_matrix(a, survivors, eval_path):
    """Return (Bits[P][N] per-byte surprisal, line_lengths) for the eval stream."""
    rows = []
    line_lens = None
    for g in survivors:
        bp = os.path.join(a.out, g["brain"])
        with open(eval_path, "rb") as ef:
            r = subprocess.run([a.atn, "--score-bytes", "--brain", bp, "--map-bits", str(g["mapbits"]),
                                "--orders", _orders_csv(g)],
                               stdin=ef, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
        flat = []; lens = []
        for line in r.stdout.decode("utf-8", "ignore").splitlines():
            vals = [float(x) for x in line.split()] if line.strip() else []
            flat.extend(vals); lens.append(len(vals))
        rows.append(flat)
        if line_lens is None:
            line_lens = lens
    N = min(len(x) for x in rows)
    Bits = np.array([x[:N] for x in rows], dtype=np.float64)
    return Bits, line_lens

def cmd_mixture(a):
    if np is None:
        raise SystemExit("mixture needs numpy")
    meta = json.load(open(os.path.join(a.out, "genes.json")))
    survivors = [g for g in meta["genes"] if g["n_owned"] > 0]
    eval_path = os.path.join(a.out, "eval.txt")
    print(f"[mixture] {len(survivors)} experts, scoring per byte over the eval stream ...")
    Bits, line_lens = _perbyte_matrix(a, survivors, eval_path)
    P, N = Bits.shape
    P_prob = np.exp2(-Bits)                      # p_k[t] = prob expert k gave the realized byte
    P_prob = np.clip(P_prob, 1e-12, 1.0)

    # baselines
    best_single = float(Bits.mean(axis=1).min())
    # oracle hard per-line routing (pick the lowest-sum expert for each line, with hindsight)
    oracle = 0.0; t = 0
    for L in line_lens:
        if L == 0: continue
        seg = Bits[:, t:t + L].sum(axis=1)
        oracle += seg.min(); t += L
    oracle /= max(1, N)

    # online fixed-share mixture: weights track the best expert through the stream,
    # with a small `alpha` leaked back to uniform each step so it can SWITCH experts.
    def run_mixture(alpha):
        w = np.full(P, 1.0 / P); bits = 0.0
        for t in range(N):
            p = P_prob[:, t]
            mix = float(w @ p)
            bits += -np.log2(max(mix, 1e-12))
            w = w * p
            s = w.sum()
            w = (w / s) if s > 0 else np.full(P, 1.0 / P)
            w = (1 - alpha) * w + alpha / P     # fixed-share: enables tracking switches
        return bits / N

    alphas = [a.alpha] if a.alpha is not None else [0.0, 0.01, 0.05, 0.2]
    results = {al: run_mixture(al) for al in alphas}
    print(f"\n  best single expert (no mixing) : {best_single:.4f} bpb")
    print(f"  oracle hard routing (hindsight): {oracle:.4f} bpb   <- per-line argmin")
    for al, v in results.items():
        tag = "Bayes mix" if al == 0.0 else f"fixed-share α={al}"
        print(f"  online {tag:<20}: {v:.4f} bpb")
    best_al = min(results, key=results.get)
    gain = 100 * (best_single - results[best_al]) / best_single
    print(f"\n  best online mixture beats the best single expert by {gain:.1f}% "
          f"(no hindsight, deployable)")

# ----------------------------------------------------------------------------
# lightup: route a query against the surviving population
# ----------------------------------------------------------------------------
def cmd_lightup(a):
    meta = json.load(open(os.path.join(a.out, "genes.json")))
    survivors = [g for g in meta["genes"] if g["n_owned"] > 0]
    scored = []
    for g in survivors:
        bp = os.path.join(a.out, g["brain"])
        r = subprocess.run([a.atn, "--score", "--brain", bp, "--map-bits", str(g["mapbits"]),
                            "--orders", _orders_csv(g)],
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
    r.add_argument("--chunk-kb", type=float, default=None,
                   help="chunk size in KB (set small for document-granularity content loci)")
    r.add_argument("--locus", choices=["positional", "content"], default="positional",
                   help="positional: contiguous region; content: gather MinHash-similar chunks")
    r.add_argument("--df-max", type=float, default=0.5,
                   help="content: drop words in >this fraction of chunks (topical signature)")
    r.add_argument("--sig", choices=["minhash", "simhash"], default="minhash",
                   help="content signature: minhash (word-set Jaccard) or simhash (TF-IDF/cosine)")
    r.add_argument("--orders", default="2,4,7",
                   help="initial n-gram context orders for every gene (each 1..7, up to 6)")
    r.add_argument("--evolve-orders", action="store_true",
                   help="let the GA mutate each gene's n-gram orders (the model-internal gene)")
    r.add_argument("--chunk-on", default=None,
                   help="regex: start a new chunk when a line matches (document-aware chunking, "
                        "e.g. '<title>' for a Wikipedia dump) so each chunk is one coherent document")
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

    m = sub.add_parser("mixture", help="soft online mixture of experts vs single/oracle")
    m.add_argument("--out", required=True)
    m.add_argument("--atn", default="./atn")
    m.add_argument("--alpha", type=float, default=None, help="fixed-share rate (default: sweep)")
    m.set_defaults(func=cmd_mixture)

    a = ap.parse_args()
    a.func(a)

if __name__ == "__main__":
    main()
