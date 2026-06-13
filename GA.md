# atn-ga — an evolved mixture of brains that tiles a large corpus

`atn-ga.py` grows a **population of atn brains**, each trained on a region of a
much larger corpus, and uses a genetic algorithm to search over *where each
brain sits* so that — used together as a mixture of experts — they compress
held-out text as well as possible. The result is a routable network: any query
"lights up" the brain whose territory it falls in.

This is the scaling story for atn. A single brain saturates on a big, diverse
corpus; a *population* of cheap brains can cover one of any size, because the GA
evolves the **partition** (which expert owns which region), not the weights, and
only the addressed slices are ever read. Point it at 25 MB of news today or a
Wikipedia / Library-of-Congress dump later — the machinery is identical.

## The idea in atn terms

| Concept | Realized as |
|---|---|
| an expert / node | one atn brain (`--train`, counts not gradients — trains in ~ms) |
| a gene | `(start_chunk, span, map_bits, orders)` — region, capacity, and the n-gram context orders |
| fitness | **coverage**: how much a brain lowers the population's held-out bits/byte (its *marginal* contribution, via `--score`) |
| selection | steady-state: keep useful experts, replace the redundant ~0-marginal ones with children of survivors |
| the graph | per held-out line, `owner = argmin bpb`, `fallback = 2nd best` → directed edges |
| "lighting up" | brains are files; only the winning expert is loaded from disk at query time |

**Why coverage fitness needs no separate dedup penalty:** a brain that merely
duplicates a sibling's territory rarely wins the per-line argmin, so its marginal
value is ~0 and it is selected out. Redundancy is punished for free.

**Why steady-state:** coverage is a property of the whole *set*. Full-population
churn keeps destroying good tilings. Replacing only the worst (≈0-marginal)
experts each generation means the population can only ratchet down — and it
retrains far fewer brains per generation (survivors' brains are cached on disk by
gene signature).

## Validated result (5-language corpus)

A 4.7 MB corpus was built by concatenating five Project Gutenberg books into
contiguous regions — English (Austen), Spanish (Quijote), French (Proust),
German (Grimm), Italian (Dante) — so that *position correlates with content*.
24 brains, 14 generations, ~0.3 MB per brain:

```
python3 atn-ga.py run --corpus corpus_multi.txt --out run \
    --pop 24 --gens 14 --span-mb 0.3 --replace-frac 0.3
```

- **Coverage dropped monotonically** 2.83 → **2.72 bpb** (finalized at the best).
- **Beats a single brain** trained on the whole corpus: 3.11 → 2.72 bpb (~13%).
- **Experts self-organized by language with no labels** — purely from coverage
  pressure. Brains at locus 0.0–0.14 cover English, 0.17–0.36 Spanish, 0.68
  French, 0.84–0.90 Italian; each owns held-out lines from its own region.
- **Routing works:** an English query lights up an English-region expert, a
  Spanish query a Spanish one, a French query the French one. The fallback graph
  wires same-language neighbors (French→French, Spanish→Spanish, …).

(German, a narrow 6% region, got absorbed by neighbors — expected when the per-
brain span is wider than the region. Shrinking `--span-mb` recovers it.)

## Scaling up: 100 MB of real Wikipedia (enwik8)

The same loop, pointed at enwik8 (the standard 100 MB Wikipedia benchmark) —
48 brains, 16 generations:

```
# positional (contiguous loci)
python3 atn-ga.py run --corpus enwik8 --out wiki --pop 48 --gens 16 \
    --span-mb 0.6 --eval-frac 0.01
# strongest setup: document chunks + content loci + evolving the n-gram orders
python3 atn-ga.py run --corpus enwik8 --out wikic --pop 48 --gens 12 \
    --locus content --chunk-on '<title>' --evolve-orders --span-mb 0.6 --eval-frac 0.01
python3 atn-ga.py mixture --out wikic
```

- **It scales:** 100 MB (20× the toy corpus) indexed and evolved in **3.5 min**,
  peak **300 MB RAM** — only the addressed slices are ever read.
- **The soft mixture wins big at scale:** best single expert 3.12 bpb → online
  fixed-share mixture **2.44 bpb** (−22%), which here even **beats the hindsight
  per-line oracle (2.68)** — real Wikipedia lines benefit from blending different
  experts *within* a line, which one-expert-per-line routing can't capture.
- **Positional evolution stalls on dump-ordered text.** With contiguous loci,
  coverage did *not* improve over generations — the best tiling was generation 1's
  uniform spread (2.78 bpb) and evolution drifted slightly worse. enwik8 is
  articles in **dump order** (not topically sorted), so a contiguous region is an
  unrelated grab-bag: there is no coherent territory for the GA to discover, and a
  uniform spread is already near-optimal. Same wall the news corpus hit.
- **Content loci unstall it — and the *chunk unit* is the real lever.** With
  `--locus content` the GA improves generation over generation, but how much
  depends entirely on what a chunk *is*:
  - *Fixed 4 KB fragments* (`--chunk-kb 4`, 22,808 chunks via **LSH**): the GA
    improves (2.80 → 2.76) but only edges past positional (~0.4%). A 4 KB chunk is
    a mid-article fragment, so its topical signal is weak — topical-word Jaccard of
    neighbors ≈ 2.3× random.
  - *Whole articles* (`--chunk-on '<title>'`, 12,289 document chunks): topical
    neighbors jump to **7.8× random** ("Military of Burundi" → "Military of
    Burkina Faso / Brazil / Brunei"; "Nimzowitsch" → "Karpov"), and content now
    **decisively** beats positional: **2.70 vs 2.81 bpb (~4%)**, improving 2.74 →
    2.70 over generations while positional stalls at its gen-1 spread. Its mixture
    reaches **2.41 bpb** — 15% under the best single brain (2.85).

  The lesson: content addressing needs a coherent topical *unit*. Fragments blur
  the signature; document-aware chunking (`--chunk-on`) is what lets the
  evolutionary search find real topical territory in an unsorted dump.
- **The signature itself is not the bottleneck — Jaccard beats cosine here.** A
  TF-IDF-weighted SimHash (`--sig simhash`, cosine similarity, meant to amplify
  rare topical words) was implemented and A/B'd against word-set MinHash
  (`--sig minhash`, the default). MinHash won on the actual coverage task (2.75 vs
  2.76 at 4 KB; cleaner topical neighbors on articles) — an n-gram expert benefits
  from shared *exact vocabulary* (Jaccard) more than from cosine of weighted
  vectors. SimHash stays available for corpora where cosine fits better.

The takeaway: the evolutionary search pays off when position correlates with
content (languages, topics, sorted/sharded data); when it doesn't, the *mixture*
of even a uniformly-spread population is still a large, deployable win over any
single brain.

## Resumable, time-boxed cron evolver

A run is a **checkpoint on disk**, so evolution can be advanced in slices by a
cron job instead of one long process. `--minutes N` evolves as many generations
as fit the budget, writes an atomic checkpoint (`state.json`) every generation,
and exits; rerunning **resumes exactly where it left off** — and because the RNG
state is checkpointed, splitting a run across many ticks is *bit-for-bit
identical* to one continuous run (verified). The frozen structural config
(`config.json`) means a resume needs only `--out`.

```
# first tick — create the run with its corpus + params
ga-step.sh /data/eo 10 --corpus enwik8 --chunk-on '<title>' \
           --locus content --evolve-orders --pop 48 --span-mb 0.6
# every later tick — just continue (no args)
ga-step.sh /data/eo 10
```

Cron (advance 10 minutes every hour, forever):

```cron
0 * * * *  /path/to/atn/ga-step.sh /data/eo 10 >> /data/eo/cron.log 2>&1
```

Each tick also scores the best population on an **untouched test set**
(`--test-frac`, never selected on) and prints the eval-vs-test gap — the honest
measure of how much the GA is overfitting the eval set it optimizes against. Watch
that gap: as long as it stays near zero the coverage gains are real; when it opens
up, the evolver is fitting the scorekeeper, not the data. (`atn --score`'s line
buffer is 8 KB, so held-out lines are capped to that length to keep one score per
line; training text keeps full lines.)

Determinism note: the GA trains/scores brains across worker threads. Reads from
the territory file use `os.pread` (positioned, no shared file offset) so parallel
workers can't clobber each other — without that, concurrent `seek+read` on one
handle silently trained brains on the wrong bytes and made runs non-reproducible.

## What a finished run is good for

An evolved `RUNDIR/` is a routable **mixture of cheap experts over your corpus** —
no GPU, counts not gradients. It is good at *judging* and *organizing* text, not
*generating* it (these are n-gram surprisal models). The driver is pure Python
standard library (no numpy); the signatures + neighbour table are computed in C
(`atn --neighbors`). Five ready-to-use commands:

```
# 1. CLASSIFY — route each line to its best-fitting expert (topic/lang/shard),
#    with a confidence margin. Batch: each brain loads once.
classify.sh RUNDIR file.txt
echo "the troops advanced at dawn" | classify.sh RUNDIR

# 2. NOVELTY — out-of-distribution / anomaly score (lowest bpb any expert gives).
#    Flags foreign / corrupted / off-topic text; threshold auto-set from the corpus.
novelty.sh RUNDIR file.txt          # NOVELTY_THRESHOLD=4 to override

# 3. LIGHTUP — which expert "lights up" for one query, plus its graph neighbours.
#    Also prints what that expert specialises in (distinctive words + a sample
#    line read from its own training articles) and a plain-English legend.
python3 atn-ga.py lightup --out RUNDIR "some query text"

# 4. MIXTURE — the population AS a corpus language model: deployable bits/byte
#    (typicality scorer / compressor front-end).
python3 atn-ga.py mixture --out RUNDIR

# 5. EXPORT — portable, framework-agnostic model data: experts/passages/edges as
#    CSV plus a self-contained atlas.db (tables run/expert/passage/edge).
python3 atn-ga.py export --out RUNDIR --format both
```

The exported `atlas.db` / CSVs are meant to be loaded into any downstream
project. **[web/](web/)** is one: a Django "corpus atlas" that browses each
territory's distinctive vocabulary, visualises the routing graph, and routes
**live queries** against the real brains.

Plus two artifacts you can consume directly: `tiling.tsv` is the corpus carved
into coherent topical slices (each expert's territory) — a label-free sharding you
can feed to a real LLM's data pipeline — and `graph.tsv` is the routing graph
(owner → fallback expert) for navigating it. Example outputs:

```
classify:  expert 7   2.197 bpb  margin 0.063   "the function returns a pointer..."   (code-ish slice)
           expert 23  2.870 bpb  margin 0.116   "she sang an aria at the opera..."    (arts slice)
novelty:   2.16 ok     "the empire collapsed after a long decline"   (in-corpus)
           5.86 NOVEL  "aaaa zzzz qqqq 8888 !!!!"                     (junk)
           5.14 NOVEL  "import numpy as np; arr = np.zeros((10,10))"  (off-domain code)
```

## Demos (one-command corpora to try)

Each builds a corpus and evolves a population over it; the experts self-organise
by whatever structure the corpus has. From the repo root:

| script | corpus | the experts separate by |
|---|---|---|
| `./demo-news.sh` | 1920s–40s US newspapers (AmericanStories) | era / section (subtle — one domain) |
| `./demo-languages.sh` | seven-language Wikipedia (en/nl/fr/de/es/it/zh) | language |
| `./demo-code.sh` | local filesystem: C / Python / shell / asm / hex | kind of code |
| `./demo-formal.sh` | generated FOL / linear algebra / set / calculus / λ / regex | formal system |
| `./demo-all.sh` | runs the four above back to back | — |
| `./demo-meta.sh` | the pooled corpora of the prior runs | the coarse kind (news vs language vs code vs formal) and finer structure within |
| `./demo-route.sh` | (builds a routing tree over the prior runs) | — coarse domain gate → fine expert; sublinear routing, not a new training |

`atn-ga.py route --out demo-route "text"` then routes any text in two hops:
a coarse brain per domain picks the domain, the domain's population picks the
expert — touching #domains + (experts in one domain) brains, not all of them.
A scaling structure, not a smarter model (quality is still the leaf brain's).

`demo-news.sh` and `demo-languages.sh` need internet; the rest are local/offline.
`demo-meta.sh` trains on the previous trainings, so run some of the others first.

## Usage

```
# evolve a population over any corpus (one document/article per line)
python3 atn-ga.py run --corpus CORPUS.txt --out RUNDIR [options]

# route a query against the evolved population (which expert lights up?)
python3 atn-ga.py lightup --out RUNDIR "some query text"

# soft online mixture of experts vs single brain / hindsight oracle
python3 atn-ga.py mixture --out RUNDIR

# export the run as portable CSV + SQLite (model-shaped tables)
python3 atn-ga.py export --out RUNDIR --format both   # csv | sqlite | both
```

`run` options (all have sensible defaults):

| flag | default | meaning |
|---|---|---|
| `--pop` | 32 | population size |
| `--gens` | 15 | generations |
| `--span-mb` | 0.5 | target training bytes per brain |
| `--span-chunks` | 8 | initial span (in chunks) of each gene |
| `--locus` | positional | `positional` (contiguous region) or `content` (gather MinHash-similar chunks) |
| `--chunk-kb` | (derived) | fixed chunk size in KB (alternative to `--chunk-on`) |
| `--chunk-on` | (none) | regex; start a new chunk when a line matches → document-aware chunks (e.g. `'<title>'`) |
| `--sig` | minhash | content signature: `minhash` (word-set Jaccard, best for n-gram coverage) or `simhash` (TF-IDF cosine) |
| `--orders` | 2,4,7 | initial n-gram context orders for every gene (each 1..7, up to 6) |
| `--evolve-orders` | off | let the GA mutate each gene's n-gram orders (biggest measured win) |
| `--df-max` | 0.5 | content: drop words in >this fraction of chunks (trims stopwords/markup) |
| `--eval-frac` | 0.05 | fraction of lines held out for scoring |
| `--replace-frac` | 0.3 | worst fraction replaced each generation |
| `--elite` | 4 | (legacy; steady-state keeps survivors) |
| `--jitter` | 3 | locus mutation range (chunks) |
| `--mapbits` | 22 | initial `--map-bits` per brain |
| `--minutes` | (none) | wall-clock budget for this run; evolve as many generations as fit, checkpoint, exit |
| `--restart` | off | ignore any checkpoint and start fresh |
| `--test-frac` | 0.02 | fraction held out as an untouched TEST set (reported, never selected on) |
| `--seed` | 1 | RNG seed (runs are fully reproducible — incl. across resume) |
| `--jobs` | cores−1 | parallel train/score workers |
| `--atn` | `./atn` | path to the atn binary |

## What `RUNDIR/` contains

```
territory.txt   the trainable text (eval lines removed)
index.tsv       chunk_id <tab> byte_off <tab> byte_len   (addressable slices)
neighbors.bin   content mode: per-chunk nearest-neighbour table (atn --neighbors)
eval.txt        held-out lines used to measure coverage
eval_pos.tsv    each eval line's fractional position (for the tiling map)
brains/         cached brains, named by gene signature (reused across gens)
history.tsv     gen <tab> coverage_bpb <tab> best_marginal <tab> n_owners
genes.json      final population: genes, marginals, coverage
tiling.tsv      which region each surviving expert owns (centroid, range)
graph.tsv       routing graph: owner -> fallback edges with weights
graph.dot       same graph as Graphviz (dot -Tpng graph.dot -o graph.png)
```

And, after `export`, portable model-shaped data for downstream consumers:

```
atlas.db        SQLite: tables run / expert / passage / edge (mirrors the web models)
experts.csv     run, expert_id, brain_path, mapbits, orders, marginal, n_owned,
                centroid, pos_lo, pos_hi, label, terms, sample
passages.csv    run, expert_id, text        (a few sample passages per expert)
edges.csv       run, src_expert_id, dst_expert_id, weight
run.csv         name, corpus, coverage_bpb, n_experts, config_json
```

## Honest limits & next steps

- **Evolvable n-gram orders (`--evolve-orders`, implemented).** The model's
  context orders used to be compile-time `{2,4,7}`; atn now takes `--orders 2,4,7`
  at runtime (each 1..7, up to 6 orders) and a gene carries its own order set, so
  the GA can tune each expert's context lengths to its territory — the one
  model-internal the genome can now touch. This is the single biggest win
  measured: on enwik8 article chunks, evolving orders took coverage from **2.689
  → 2.549 bpb (~5%)** and the population kept improving every generation (no
  plateau), with its mixture reaching **2.37**. The settled orders are genuinely
  heterogeneous — only ~36% of experts kept `(2,4,7)`; others found `(1,2,4,7)`,
  `(2,4)`, `(1,2,4,6)`, `(2,3,7)` — different topical territories prefer different
  context lengths (many added order-1, absent from the default).
- **Content loci (`--locus content`, implemented).** A positional gene is a
  contiguous byte region — fine when nearby text is related (a sorted/sharded
  corpus), useless when it isn't. A content gene instead names a *seed chunk* and
  gathers its `span` nearest chunks by **word-level MinHash** similarity (shared
  vocabulary), so an expert specializes topically regardless of position. Note
  the signature is over single words, not phrase shingles: shingles catch
  near-duplicates, words catch topic/language. Validated by shuffling the
  5-language corpus at block level so contiguous regions become mixed-language:
  positional coverage degraded to 2.74 bpb, while content **recovered to 2.69** —
  better even than positional on the *unshuffled* corpus (2.72), because it builds
  pure same-language training sets (top-8 neighbors are 90% same-language) instead
  of regions that straddle boundaries. Content mode auto-selects its index:
  exact brute-force for ≤2500 chunks, **banded MinHash LSH** beyond (validated at
  22,808 chunks). The signature uses **document-frequency filtering** (`--df-max`):
  dropping corpus-universal words (stopwords/markup) sharpens topic discrimination
  in mono-lingual data, while keeping enough to preserve language discrimination.
  Granularity matters most — coarse chunks are multi-topic grab-bags whose
  signatures blur (enwik8 at 78 KB: content 2.82 ≥ positional 2.78; at 4 KB only
  ~0.4% ahead), while **document-aware chunks** (`--chunk-on '<title>'`, one
  article each) lift topical-neighbor quality to 7.8× random and content beats
  positional by ~4% (2.70 vs 2.81). Content addressing is a *document-granularity*
  tool — pair `--locus content` with `--chunk-on` on real corpora. Signature
  choice (`--sig`) is secondary: MinHash (Jaccard) edges TF-IDF SimHash (cosine)
  for this n-gram task, since experts reward shared exact vocabulary.
  Signatures and the exact/LSH neighbour table are computed in C
  (`atn --neighbors`, see `content.c`) and cached to `RUNDIR/neighbors.bin`, so
  the GA driver runs on the Python standard library alone — no numpy.
- **Soft mixture (`mixture` command, implemented).** Coverage uses a hard
  per-line argmin. The deployable router can't peek at the answer, so `mixture`
  runs an **online fixed-share** predictor over the eval stream: each byte is
  predicted as a weighted blend of all experts (weights ∝ recent per-byte
  accuracy via atn's new `--score-bytes`), with a small `alpha` leaked back to
  uniform each step so the weights can *switch* experts as the stream crosses
  regions. On the 5-language run it scored **2.62 bpb with no hindsight** —
  beating the best single expert (3.39, by 23%) and coming within 0.02 of the
  hindsight oracle (2.60). Plain Bayesian mixing (alpha=0) gets stuck at 3.82;
  the fixed-share leak is what lets it track. Line-level mixing can't do this —
  line-probabilities are too peaked for a second expert to matter, so the gain
  has to come per byte.
- **Non-Latin scripts (`./demo-languages.sh`, implemented).** The pipeline was
  ASCII-centric in three places that silently dropped non-Latin text; all three
  now accept UTF-8: `atn --train` (a Chinese corpus used to ingest 0 bytes and
  train a degenerate brain), `--prep`'s quality filter and dedup fingerprint, and
  the content tokeniser (each CJK character is its own token, so Chinese chunks
  get real signatures and cluster). A Chinese-trained brain scores Chinese ~4.6
  bpb vs ~8.3 for an English brain, so on a 7-language Wikipedia mix
  (en/nl/fr/de/es/it/zh) the experts separate by language and a query routes to
  its language's expert — including Chinese.
- **Symbol-aware tokeniser (`./demo-formal.sh`, implemented).** The content
  tokeniser also treats math/logic/Greek symbols (∀ ∃ ∈ ∪ λ ∫ ∂ Σ → ¬ …) as
  their own tokens, so formal notation clusters on the operators that define it
  instead of collapsing to bare letters. On a generated corpus of six formal
  systems (first-order logic, linear algebra, set theory, calculus, lambda
  calculus, regex) all six separate; the closest call is first-order logic vs
  lambda calculus, which share a surface shape (binder + variables + parens) and
  are the last to resolve. The symbols are absent from prose/code, so existing
  corpora are unaffected.
- **Owner protection (implemented).** Steady-state replacement removed the
  lowest-*marginal* genes each generation. A minority region (e.g. one language)
  is covered by a few mutually-redundant experts that each show low marginal, so
  a batch replace could wipe the whole cluster at once and never recover it — the
  multilingual demo culled Chinese this way. Fix: never replace an expert that is
  the sole owner of an eval line; only the worst non-owners are dropped. This
  preserves at least one expert per covered region while still pruning redundancy.
- Scaling up: the corpus is never resident — a gene addresses a slice, we stream
  just that slice to train one brain plus a fixed held-out sample. The same loop
  runs on Wikipedia or larger; only `--span-mb`, `--pop`, and the chunk size grow.
