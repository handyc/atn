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
import argparse, array, json, os, random, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

# ----------------------------------------------------------------------------
# content addressing: a content gene gathers topically-SIMILAR chunks via a
# per-chunk nearest-neighbour table. Signatures (MinHash / TF-IDF SimHash) and
# the exact/LSH ranking now live in C (content.c, `atn --neighbors`) so this
# script needs no numpy — the table is read back as plain int32 rows.
# ----------------------------------------------------------------------------
class NeighborTable:
    """Reads the binary table written by `atn --neighbors`. neighbors(i) returns
    the chunk ids most similar to i (i itself ranks first), -1 padding stripped.
    Layout (native int32): [n, rowcap] then n rows of `rowcap` ids each."""
    def __init__(self, path):
        a = array.array("i")
        with open(path, "rb") as f:
            a.frombytes(f.read())
        self.n, self.rowcap = a[0], a[1]
        self._a = a

    def neighbors(self, i):
        base = 2 + i * self.rowcap
        return [x for x in self._a[base:base + self.rowcap] if x >= 0]

def build_neighbor_table(atn, territory, index_tsv, out_bin, sig, df_max):
    """Invoke the C kernel to (re)build the neighbour table, then load it."""
    subprocess.run([atn, "--neighbors", territory, "--nn-index", index_tsv,
                    "--nn-sig", sig, "--nn-dfmax", str(df_max), "-o", out_bin],
                   stderr=subprocess.DEVNULL, check=True)
    return NeighborTable(out_bin)

# ----------------------------------------------------------------------------
# corpus indexing: split into territory (trainable) + a held-out eval sample
# ----------------------------------------------------------------------------
def build_index(corpus, out, eval_frac, test_frac, chunk_bytes, seed, chunk_on=None):
    """Split corpus lines into territory chunks (contiguous, line-aligned), a
    held-out EVAL set (the GA selects on it), and an untouched TEST set (scored
    only for honesty — the eval-vs-test gap is the overfitting). Writes:
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
    testp = os.path.join(out, "test.txt")
    estride = max(2, round(1.0 / eval_frac))     # every estride-th line -> eval
    tstride = max(2, round(1.0 / test_frac)) if test_frac > 0 else 0

    with open(corpus, "r", errors="ignore") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    n = len(lines)
    terr = open(terr_path, "w"); ev = open(evalp, "w"); pf = open(pos_path, "w"); te = open(testp, "w")
    chunks = []            # (byte_off, byte_len) into territory.txt
    cur_off = 0; cur_len = 0
    # held-out lines are scored one-per-line by `atn --score`, whose line buffer is
    # 8192 bytes; cap them so a long line can't split into several score rows (which
    # would misalign the per-line arrays). Territory (training) keeps full lines.
    CAP = 8000
    for i, ln in enumerate(lines):
        if i % estride == 0:                      # -> eval (the GA selects on this)
            ev.write(ln[:CAP] + "\n"); pf.write(f"{i / n:.6f}\n"); continue
        if tstride and i % tstride == tstride // 2:   # -> test (NEVER touched by the GA)
            te.write(ln[:CAP] + "\n"); continue
        if chunk_on is not None and cur_len and chunk_on.search(ln):
            chunks.append((cur_off, cur_len)); cur_off += cur_len; cur_len = 0  # document boundary
        b = (ln + "\n").encode("utf-8", "ignore")
        terr.write(ln + "\n")
        cur_len += len(b)
        if cur_len >= chunk_bytes:                # byte cap (also splits huge documents)
            chunks.append((cur_off, cur_len)); cur_off += cur_len; cur_len = 0
    if cur_len:
        chunks.append((cur_off, cur_len))
    terr.close(); ev.close(); pf.close(); te.close()
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
        self._fd = os.open(territory, os.O_RDONLY)       # read via os.pread (thread-safe)
        self.nn = None                                   # neighbor provider (content mode)
        if mode == "content":
            cachef = os.path.join(out, "neighbors.bin")  # cache the table across cron ticks
            if not os.path.exists(cachef):
                build_neighbor_table(atn, territory, os.path.join(out, "index.tsv"),
                                     cachef, sig, df_max)
            self.nn = NeighborTable(cachef)
            exact = len(chunks) <= 2500                  # exact for small, LSH at scale
            print(f"[index] content index: {sig} signature, "
                  f"{'exact O(n^2)' if exact else 'LSH (16 bands)'} over {len(chunks)} chunks")

    def _read(self, off, length):
        # os.pread does NOT use/modify the fd's file position, so concurrent reads
        # from worker threads can't clobber each other (a plain seek+read would).
        return os.pread(self._fd, length, off)

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
        # dedupe by gene signature: a generation can hold duplicate genes (elitism /
        # crossover clones), and training the SAME brain file from two threads at once
        # races and corrupts it — the source of run-to-run nondeterminism. One per sig.
        uniq = {g.sig(): g for g in pop}
        with ThreadPoolExecutor(max_workers=self.jobs) as ex:
            list(ex.map(self.train, uniq.values()))

    def score_all(self, pop, eval_path):
        uniq = {}
        for g in pop:
            uniq.setdefault(g.sig(), g)
        with ThreadPoolExecutor(max_workers=self.jobs) as ex:
            res = dict(zip(uniq.keys(), ex.map(lambda g: self.score(g, eval_path), uniq.values())))
        return [res[g.sig()] for g in pop]

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
# checkpoint / config persistence (for the resumable, time-boxed cron evolver)
# ----------------------------------------------------------------------------
CONFIG_KEYS = ["corpus", "pop", "locus", "sig", "df_max", "chunk_kb", "chunk_on",
               "span_mb", "span_chunks", "eval_frac", "test_frac", "mapbits",
               "orders", "evolve_orders", "jitter", "replace_frac", "seed"]

def save_config(out, a):
    cfg = {k: getattr(a, k) for k in CONFIG_KEYS}
    json.dump(cfg, open(os.path.join(out, "config.json"), "w"), indent=2)

def load_config(out, a):
    """Apply the run's frozen structural config onto args so a resume only needs
    --out (and --minutes). Returns the config dict."""
    cfg = json.load(open(os.path.join(out, "config.json")))
    for k, v in cfg.items():
        setattr(a, k, v)
    return cfg

def save_state(out, gen, rng, pop, best_cov, best_pop):
    state = {
        "gen": gen,
        "rng": list(rng.getstate()),                 # (version, [ints], gauss)
        "pop": [g.to_dict() for g in pop],
        "best_cov": best_cov,
        "best_pop": [g.to_dict() for g in best_pop] if best_pop else None,
    }
    tmp = os.path.join(out, "state.json.tmp")
    json.dump(state, open(tmp, "w"))
    os.replace(tmp, os.path.join(out, "state.json"))  # atomic: a kill never corrupts it

def _gene_from_dict(d):
    return Gene(d["start"], d["span"], d["mapbits"], tuple(d.get("orders", (2, 4, 7))))

def load_state(out):
    p = os.path.join(out, "state.json")
    if not os.path.exists(p):
        return None
    s = json.load(open(p))
    v, ints, gauss = s["rng"]
    s["rng_state"] = (v, tuple(ints), gauss)
    s["pop"] = [_gene_from_dict(d) for d in s["pop"]]
    s["best_pop"] = [_gene_from_dict(d) for d in s["best_pop"]] if s.get("best_pop") else None
    return s

# ----------------------------------------------------------------------------
# run  (single-shot OR resumable, time-boxed cron step-evolver)
# ----------------------------------------------------------------------------
def cmd_run(a):
    rng = random.Random(a.seed)
    import time
    resuming = os.path.exists(os.path.join(a.out, "state.json")) and not a.restart
    if not resuming and not a.corpus:
        raise SystemExit("a fresh run needs --corpus (resume needs only --out)")

    if resuming:
        load_config(a.out, a)                        # freeze structural params from creation
        chunks = load_index(a.out)
        st = load_state(a.out)
        gen0 = st["gen"]; pop = st["pop"]; best_cov = st["best_cov"]; best_pop = st["best_pop"]
        rng = random.Random(); rng.setstate(st["rng_state"])
        print(f"[resume] {a.out}: at gen {gen0}, pop {len(pop)}, best {best_cov:.4f} bpb")
    else:
        if a.restart:
            for f in ("state.json", "neighbors.bin"):
                try: os.remove(os.path.join(a.out, f))
                except FileNotFoundError: pass
        # chunk size: explicit --chunk-kb, else generous cap when splitting on document
        # boundaries (--chunk-on), else derived from the per-brain budget / initial span.
        chunk_on = re.compile(a.chunk_on) if a.chunk_on else None
        if a.chunk_kb:        chunk_bytes = int(a.chunk_kb * 1024)
        elif chunk_on:        chunk_bytes = 65536
        else:                 chunk_bytes = int(a.span_mb * 1024 * 1024 / max(1, a.span_chunks))
        print(f"[index] {a.corpus} -> {a.out}  (eval {a.eval_frac}, test {a.test_frac}, chunk≈{chunk_bytes}B"
              f"{', doc-split on /' + a.chunk_on + '/' if chunk_on else ''})")
        chunks = build_index(a.corpus, a.out, a.eval_frac, a.test_frac, chunk_bytes, a.seed, chunk_on)
        avg = max(1, sum(l for _, l in chunks) // len(chunks))
        init_span = max(1, round(a.span_mb * 1024 * 1024 / avg))
        init_orders = tuple(int(x) for x in a.orders.replace(",", " ").split())
        print(f"[index] chunks={len(chunks)} (avg {avg}B), locus={a.locus}, init span={init_span}, "
              f"orders={init_orders}{' (evolving)' if a.evolve_orders else ''}")
        rng = random.Random(a.seed)
        pop = []
        for i in range(a.pop):
            start = round(i * len(chunks) / a.pop)
            g = Gene(start + rng.randint(-1, 1), init_span, a.mapbits, init_orders)
            pop.append(clamp(g, a.locus, len(chunks), 1, max(1, len(chunks) // 2)))
        gen0 = 0; best_cov = 1e18; best_pop = None
        save_config(a.out, a)

    nchunks = len(chunks)
    span_min, span_max = 1, max(1, nchunks // 2)
    eval_path = os.path.join(a.out, "eval.txt")
    eng = Engine(a.atn, a.out, os.path.join(a.out, "territory.txt"), chunks, a.jobs,
                 mode=a.locus, df_max=a.df_max, sig=a.sig)

    hist = open(os.path.join(a.out, "history.tsv"), "a")
    if gen0 == 0:
        hist.write("gen\tcoverage_bpb\tbest_marginal\tn_owners\n")
    gens_cap = (a.gens if a.gens and a.gens > 0 else None) if (a.gens is not None) \
               else (None if a.minutes else 15)
    deadline = time.time() + a.minutes * 60 if a.minutes else None

    gen = gen0
    while True:
        if gens_cap and gen >= gens_cap:
            print(f"[stop] reached generation cap {gens_cap}"); break
        t0 = time.time()
        gen += 1
        eng.train_all(pop)
        cols = eng.score_all(pop, eval_path)
        coverage, marginal, owner, second = evaluate(cols)
        n_owners = len(set(owner))
        flag = ""
        if coverage < best_cov:                       # keep the best tiling ever seen
            best_cov = coverage; best_pop = [clone(g) for g in pop]; flag = "  <- best"
        hist.write(f"{gen}\t{coverage:.4f}\t{max(marginal):.4f}\t{n_owners}\n"); hist.flush()
        print(f"[gen {gen:3d}] coverage={coverage:.4f} bpb   active={n_owners}/{a.pop}   "
              f"best={best_cov:.4f}{flag}")

        # build the next generation (steady-state: replace the worst, keep survivors)
        order = sorted(range(len(pop)), key=lambda p: marginal[p])
        n_rep = max(1, round(len(pop) * a.replace_frac))
        survivors = [pop[i] for i in order[n_rep:]]
        nxt = [clone(g) for g in survivors]
        while len(nxt) < a.pop:
            if rng.random() < 0.5:
                child = crossover(rng.choice(survivors), rng.choice(survivors), rng)
            else:
                child = clone(rng.choice(survivors))
            nxt.append(mutate(child, rng, a.locus, nchunks, span_min, span_max, a.jitter,
                              eng, a.evolve_orders))
        pop = nxt
        save_state(a.out, gen, rng, pop, best_cov, best_pop)   # atomic checkpoint each gen

        gen_time = time.time() - t0
        if deadline and time.time() + gen_time > deadline:
            print(f"[budget] {a.minutes} min used at gen {gen} (next gen ~{gen_time:.0f}s won't fit)")
            break

    hist.close()
    # finalize on the BEST population (re-score it for ownership/graph; brains are cached)
    print(f"[best] coverage={best_cov:.4f} bpb after {gen} total generations")
    eng.train_all(best_pop)
    bcols = eng.score_all(best_pop, eval_path)
    bcov, bmarg, bown, bsec = evaluate(bcols)
    finalize(a, eng, best_pop, bmarg, bown, bsec, bcov)

    # honesty: score the best population on the UNTOUCHED test set; the gap is overfitting
    test_path = os.path.join(a.out, "test.txt")
    if os.path.exists(test_path) and os.path.getsize(test_path) > 0:
        tcols = eng.score_all(best_pop, test_path)
        tcov, *_ = evaluate(tcols)
        print(f"[honesty] eval {bcov:.4f}  vs  test {tcov:.4f} bpb  "
              f"(gap {tcov - bcov:+.4f} = overfitting to the eval set)")
    print(f"[done] checkpoint at {a.out}/state.json — rerun to continue evolving")

def finalize(a, eng, pop, marginal, owner, second, coverage):
    """Write the surviving population, tiling map, and routing graph."""
    pos = [float(x) for x in open(os.path.join(a.out, "eval_pos.tsv"), errors="ignore")]
    # surviving experts = those that own >=1 eval line
    from collections import defaultdict, Counter
    owned = defaultdict(list)
    for m, p in enumerate(owner):
        owned[p].append(pos[m] if m < len(pos) else 0.0)   # guard against any misalignment
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
    """Return (Bits[P][N] per-byte surprisal as lists, line_lengths) for the eval stream."""
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
    N = min(len(x) for x in rows) if rows else 0
    Bits = [x[:N] for x in rows]
    return Bits, line_lens

def cmd_mixture(a):
    import math
    meta = json.load(open(os.path.join(a.out, "genes.json")))
    survivors = [g for g in meta["genes"] if g["n_owned"] > 0]
    eval_path = os.path.join(a.out, "eval.txt")
    print(f"[mixture] {len(survivors)} experts, scoring per byte over the eval stream ...")
    Bits, line_lens = _perbyte_matrix(a, survivors, eval_path)
    P = len(Bits); N = len(Bits[0]) if P else 0
    if not P or not N:
        print("  no experts or empty eval stream"); return
    # p_k[t] = prob expert k gave the realized byte, clipped away from 0
    P_prob = [[min(max(2.0 ** -Bits[k][t], 1e-12), 1.0) for t in range(N)] for k in range(P)]

    # baselines
    best_single = min(sum(Bits[k]) / N for k in range(P))
    # oracle hard per-line routing (pick the lowest-sum expert for each line, with hindsight)
    oracle = 0.0; t = 0
    for L in line_lens:
        if L == 0: continue
        oracle += min(sum(Bits[k][t:t + L]) for k in range(P)); t += L
    oracle /= max(1, N)

    # online fixed-share mixture: weights track the best expert through the stream,
    # with a small `alpha` leaked back to uniform each step so it can SWITCH experts.
    def run_mixture(alpha):
        w = [1.0 / P] * P; bits = 0.0
        for t in range(N):
            mix = sum(w[k] * P_prob[k][t] for k in range(P))
            bits += -math.log2(max(mix, 1e-12))
            w = [w[k] * P_prob[k][t] for k in range(P)]
            s = sum(w)
            w = [wk / s for wk in w] if s > 0 else [1.0 / P] * P
            w = [(1 - alpha) * wk + alpha / P for wk in w]   # fixed-share: tracks switches
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
    print("\n  What this means: this uses the whole POPULATION as one language model.")
    print("  For each character it blends every expert's prediction, leaning on")
    print("  whichever has been predicting best lately. Beating the best single expert")
    print("  (and the 'oracle' is the unbeatable best-case that peeks at the answer)")
    print("  shows the experts learned genuinely different, complementary slices.")

# ----------------------------------------------------------------------------
# classify / novelty: apply an evolved population to new text (batch)
# ----------------------------------------------------------------------------
def _read_lines(paths, cap=8000):
    """Read lines from files (or stdin if none), trimmed and capped to atn's score
    line buffer so each input line yields exactly one score."""
    out = []
    if paths:
        for p in paths:
            with open(p, "r", errors="ignore") as f:
                out += [ln.rstrip("\n")[:cap] for ln in f if ln.strip()]
    else:
        for ln in sys.stdin:
            if ln.strip():
                out.append(ln.rstrip("\n")[:cap])
    return out

def _pop_scores(a, survivors, lines):
    """bpb[expert][line]: each surviving brain scores ALL lines in one --score call
    (brain loaded once), run in parallel across experts."""
    blob = ("\n".join(lines) + "\n").encode("utf-8", "ignore")
    def score_one(g):
        bp = os.path.join(a.out, g["brain"])
        r = subprocess.run([a.atn, "--score", "--brain", bp, "--map-bits", str(g["mapbits"]),
                            "--orders", _orders_csv(g)],
                           input=blob, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        vals = []
        for ln in r.stdout.decode("utf-8", "ignore").splitlines():
            try: vals.append(float(ln.split("\t")[0].strip().split()[0]))
            except (ValueError, IndexError): vals.append(99.0)
        return (vals + [99.0] * len(lines))[:len(lines)]
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        return list(ex.map(score_one, survivors))

# ----------------------------------------------------------------------------
# human-readable helpers: turn an opaque "expert 3" into what it specializes in,
# read straight from the text that expert was trained on.
# ----------------------------------------------------------------------------
_STOP = set(("the a an of to in and for on at by is was were be been being as it its "
             "with from that this these those his her their our your my he she they we "
             "you i not no but or are had has have will would can could shall should "
             "said say says one two three new now out up off over under into onto per "
             "who whom which what when where why how all any some such than then there "
             "here also more most very much many other another about after before "
             "mr mrs miss dr st am pm").split())

def _load_run_config(out):
    try:
        return json.load(open(os.path.join(out, "config.json")))
    except FileNotFoundError:
        return {}

# Latin words ≥4 chars (skips OCR cruft) OR a single CJK character (Chinese has
# no word spaces, so each character is its own token — mirrors content.c).
_TOK = re.compile(r"[a-zà-ÿ]{4,}|[㐀-鿿]")

def _expert_profile(out, gene, cfg, n_words=10, cap_chunks=40, baseline=1200):
    """Describe an expert by reading the text it actually trained on. Returns
    (distinctive_words, sample_line). Words are ranked by TF-IDF against a sampled
    corpus baseline so generic news vocabulary ('day', 'city') is down-weighted in
    favour of what makes this expert's territory distinctive. Content loci gather
    MinHash-similar chunks; positional loci take a contiguous run."""
    import math
    from collections import Counter
    try:
        chunks = load_index(out)
    except FileNotFoundError:
        return [], ""
    terr = os.path.join(out, "territory.txt")
    try:
        fd = os.open(terr, os.O_RDONLY)
    except FileNotFoundError:
        return [], ""

    def read_chunk(cid):
        o, l = chunks[cid]
        return os.pread(fd, l, o).decode("utf-8", "ignore")

    try:
        start, span = gene["start"], gene["span"]
        nb = os.path.join(out, "neighbors.bin")
        if cfg.get("locus") == "content" and os.path.exists(nb):
            ids = NeighborTable(nb).neighbors(start)[:span]
        else:
            ids = list(range(start, min(start + span, len(chunks))))
        ids = ids[:cap_chunks]

        # corpus baseline: document frequency over an evenly-spaced sample of chunks
        n = len(chunks)
        step = max(1, n // baseline)
        sample_ids = range(0, n, step)
        df = Counter(); nsamp = 0
        for cid in sample_ids:
            nsamp += 1
            df.update({w for w in _TOK.findall(read_chunk(cid).lower()) if w not in _STOP})

        # this expert's term frequencies + candidate lines to sample from
        tf = Counter(); cands = []
        for cid in ids:
            text = read_chunk(cid)
            tf.update(w for w in _TOK.findall(text.lower()) if w not in _STOP)
            for ln in text.splitlines():
                # a usable sample line has ≥8 real tokens (Latin words or CJK
                # chars) — works whether or not the language uses spaces.
                if len(cands) < 120 and len(_TOK.findall(ln.lower())) >= 8:
                    cands.append(ln.strip())
    finally:
        os.close(fd)

    # TF-IDF: frequent HERE but rare across the corpus = distinctive
    scored = ((cnt * math.log((nsamp + 1) / (df.get(w, 0) + 1)), w)
              for w, cnt in tf.items() if cnt >= 2)
    top = [w for _, w in sorted(scored, reverse=True)[:n_words]]
    # pick the sample line that best reflects the distinctive words, so the
    # example is in the same language/topic the expert specialises in.
    topset = set(top)
    best_line = max(cands, key=lambda ln: sum(
        w in topset for w in _TOK.findall(ln.lower())), default="")
    return top, best_line[:72]

def cmd_classify(a):
    meta = json.load(open(os.path.join(a.out, "genes.json")))
    survivors = [g for g in meta["genes"] if g["n_owned"] > 0]
    lines = _read_lines(a.files)
    if not survivors or not lines:
        print("no survivors or no input"); return
    cols = _pop_scores(a, survivors, lines)
    nchunks = len(open(os.path.join(a.out, "index.tsv")).read().splitlines()) or 1
    print(f"{'expert':<8}{'bpb':<8}{'margin':<8}{'territory':<11}text")
    for i, line in enumerate(lines):
        ranked = sorted(range(len(survivors)), key=lambda e: cols[e][i])
        e0 = ranked[0]; best = cols[e0][i]
        second = cols[ranked[1]][i] if len(ranked) > 1 else best
        g = survivors[e0]
        print(f"{g['expert']:<8}{best:<8.3f}{second-best:<8.3f}"
              f"{g['start']/nchunks:<11.3f}{line[:50]}")
    print("\n  How to read this: each line is routed to the expert that finds it least")
    print("  surprising (lowest bpb = bits/byte). 'margin' is how much better that")
    print("  expert fit than the runner-up — a wide margin = a confident, distinctive")
    print("  topical match; near 0 = two experts cover similar ground. 'territory' is")
    print("  where that expert sits in the corpus (0=start .. 1=end).")

def cmd_novelty(a):
    meta = json.load(open(os.path.join(a.out, "genes.json")))
    survivors = [g for g in meta["genes"] if g["n_owned"] > 0]
    lines = _read_lines(a.files)
    if not survivors or not lines:
        print("no survivors or no input"); return
    cov = meta.get("coverage_bpb", 3.0)
    thr = a.threshold if a.threshold is not None else round(cov * 1.6, 2)
    cols = _pop_scores(a, survivors, lines)
    print(f"# in-corpus bpb≈{cov:.2f}; flagging NOVEL when best-expert bpb ≥ {thr}")
    print(f"{'bpb':<8}{'flag':<7}text")
    nflag = 0
    for i, line in enumerate(lines):
        m = min(cols[e][i] for e in range(len(survivors)))
        novel = m >= thr
        nflag += novel
        print(f"{m:<8.3f}{'NOVEL' if novel else 'ok':<7}{line[:56]}")
    print(f"# {nflag}/{len(lines)} flagged novel (≥{thr} bpb)")
    print("\n  How to read this: 'bpb' is how surprised the BEST-fitting expert still")
    print("  is — if even the closest expert is very surprised, nothing in the corpus")
    print("  looks like this text, so it's flagged NOVEL (out-of-distribution). Useful")
    print("  for spotting off-topic, anachronistic, or garbled input.")

# ----------------------------------------------------------------------------
# lightup: route a query against the surviving population
# ----------------------------------------------------------------------------
def cmd_lightup(a):
    meta = json.load(open(os.path.join(a.out, "genes.json")))
    cfg = _load_run_config(a.out)
    cov = meta.get("coverage_bpb")
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

    win_bpb, win_g = scored[0]
    print(f"\nlit up: expert {win_g['expert']}  ({win_bpb:.3f} bpb — lowest surprisal)")
    top, sample = _expert_profile(a.out, win_g, cfg)
    if top:
        print("  specializes in:", ", ".join(top))
    if sample:
        print(f'  e.g. from its territory: "{sample}"')
    nbrs = sorted(edges.get(win_g["expert"], []), key=lambda x: -x[1])[:5]
    if nbrs:
        print("  related experts (routing fallbacks):",
              ", ".join(f"{v}(w={w})" for v, w in nbrs))

    # ---- plain-English legend so the table above is self-explanatory ----
    print("\n  What this means:")
    print("  • bpb = bits/byte of 'surprise' — how UNfamiliar your text is to that")
    print("    expert. Lower = better fit; the lowest-bpb expert 'lights up'.")
    print("  • The RANKING is the signal, not the absolute number: short, misspelled,")
    print("    or out-of-period queries score high for everyone. Try a full sentence.")
    if cov:
        print(f"  • For scale, the corpus itself sits at ≈{cov:.2f} bpb; your best was "
              f"{win_bpb:.2f}.")
    print("  • 'specializes in' / 'e.g.' are read from the actual articles that expert")
    print("    trained on — that's what 'expert {}' really is.".format(win_g["expert"]))

# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="evolve atn brains that tile a corpus")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="index a corpus and evolve a population (resumable)")
    r.add_argument("--corpus", default=None, help="corpus file (only for a fresh run; "
                   "on resume it is read from the checkpoint's config)")
    r.add_argument("--out", required=True)
    r.add_argument("--atn", default="./atn")
    r.add_argument("--pop", type=int, default=32)
    r.add_argument("--gens", type=int, default=None,
                   help="total generation cap (default 15 single-shot; 0 or with --minutes = unlimited)")
    r.add_argument("--minutes", type=float, default=None,
                   help="wall-clock budget for THIS run; evolve as many generations as fit, then "
                        "checkpoint and exit. Rerun (e.g. from cron) to keep going.")
    r.add_argument("--restart", action="store_true", help="ignore any checkpoint and start fresh")
    r.add_argument("--test-frac", type=float, default=0.02,
                   help="fraction held out as an UNTOUCHED test set (reported, never selected on)")
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

    jdef = max(1, (os.cpu_count() or 2) - 1)
    c = sub.add_parser("classify", help="route each input line to its best-fitting expert")
    c.add_argument("--out", required=True)
    c.add_argument("--atn", default="./atn")
    c.add_argument("--jobs", type=int, default=jdef)
    c.add_argument("files", nargs="*", help="files to classify (stdin if none)")
    c.set_defaults(func=cmd_classify)

    nv = sub.add_parser("novelty", help="score each input line's novelty (best-expert bpb)")
    nv.add_argument("--out", required=True)
    nv.add_argument("--atn", default="./atn")
    nv.add_argument("--jobs", type=int, default=jdef)
    nv.add_argument("--threshold", type=float, default=None,
                    help="flag lines at/above this bpb (default: ~1.6x the corpus bpb)")
    nv.add_argument("files", nargs="*", help="files to score (stdin if none)")
    nv.set_defaults(func=cmd_novelty)

    a = ap.parse_args()
    a.func(a)

if __name__ == "__main__":
    main()
